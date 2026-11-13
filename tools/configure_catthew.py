#!/usr/bin/env python3
"""Install scoped Catthew integration without replacing its SOUL or other channels.

Run inside the existing Hermes container with its actual persistent home. No
credentials are printed. Backups contain secrets and remain in private state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path

import yaml

from hub.settings import setting as _setting


SERVERS = ("catthew-household",)


def _atomic(path, data, *, private=False):
    original = path.stat() if path.exists() else None
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".catthew-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600 if private or original is None else stat.S_IMODE(original.st_mode))
        if original and os.geteuid() == 0:
            os.chown(temporary, original.st_uid, original.st_gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _service_secret(raw, name):
    existing = _setting(raw, name)
    if existing is not None:
        if len(existing) < 32 or any(c in existing for c in "\r\n$ "):
            raise ValueError("existing service credential needs manual review")
        return raw, existing
    value = secrets.token_urlsafe(48)
    return raw.rstrip("\n") + "\n" + name + "=" + value + "\n", value


def _replace_grok(config):
    # Remove the explicitly superseded provider from Catthew's nested model settings.
    for key, value in list(config.items()):
        if isinstance(value, dict):
            _replace_grok(value)
        elif key == "provider" and value == "xai-oauth":
            config[key] = "openai-codex"
        elif key in ("model", "default") and isinstance(value, str) and value.startswith("grok-"):
            config[key] = "gpt-6.1-terra"


def _catalog(root, python):
    code = ("from hermes_cli.tools_config import _get_plugin_toolset_keys,CONFIGURABLE_TOOLSETS; "
            "import json; print(json.dumps({'plugins':sorted(_get_plugin_toolset_keys()),"
            "'builtins':[x[0] for x in CONFIGURABLE_TOOLSETS]}))")
    result = subprocess.run([str(python), "-c", code], cwd=root / "hermes-agent",
                            capture_output=True, text=True, check=True, timeout=30)
    value = json.loads(result.stdout)
    if not all(isinstance(value.get(key), list) and all(isinstance(x, str) for x in value[key])
               for key in ("plugins", "builtins")) or "stt" not in value["builtins"]:
        raise ValueError("unable to verify installed toolset catalog")
    return value


def configure(root, project, python, state):
    root, project, state = map(lambda p: Path(p).resolve(), (root, project, state))
    # Resolving a virtualenv interpreter symlink discards its site-packages context.
    python = Path(python).absolute()
    profile = root / "profiles/catthew"
    soul = profile / "SOUL.md"
    if not soul.is_file() or not project.is_dir() or not python.is_file():
        raise ValueError("existing Catthew identity, project and interpreter are required")
    soul_hash = hashlib.sha256(soul.read_bytes()).hexdigest()
    root_path, profile_path = root / "config.yaml", profile / "config.yaml"
    originals = {root_path: root_path.read_bytes(), profile_path: profile_path.read_bytes()}
    root_cfg, cfg = (yaml.safe_load(originals[path]) for path in (root_path, profile_path))
    if not isinstance(root_cfg, dict) or not isinstance(cfg, dict):
        raise ValueError("existing Hermes configurations must be mappings")
    api = root_cfg.get("platforms", {}).get("api_server", {})
    if api.get("enabled") and (api.get("extra", {}).get("port", 8642) != 8642 or api.get("extra", {}).get("host", "127.0.0.1") != "127.0.0.1"):
        raise ValueError("an existing API listener requires review before changing it")
    if cfg.get("platform_toolsets", {}).get("api_server") not in (None, list(SERVERS), ["stt", *SERVERS]):
        raise ValueError("an existing Catthew API tool policy requires review")
    for name in SERVERS:
        existing = cfg.get("mcp_servers", {}).get(name)
        if existing and "hub.household_mcp" not in existing.get("args", []):
            raise ValueError("MCP server name belongs to another integration")

    catalog = _catalog(root, python)
    root_cfg.setdefault("platforms", {})["api_server"] = {"enabled": True, "extra": {"host": "127.0.0.1", "port": 8642}}
    # stt currently has no model tools and selects Hermes's explicit-list resolver;
    # a bare MCP-only list otherwise injects x_search. Runtime checks fail closed
    # if a future STT/plugin release introduces any native tools on this channel.
    root_cfg.setdefault("platform_toolsets", {})["api_server"] = ["stt", "no_mcp"]
    for target in (root_cfg, cfg):
        target.setdefault("known_plugin_toolsets", {})["api_server"] = catalog["plugins"]
        target.setdefault("known_builtin_toolsets", {})["api_server"] = catalog["builtins"]
    cfg.setdefault("model", {}).update({"provider": "openai-codex", "default": "gpt-6.1-terra"})
    _replace_grok(cfg["model"])
    if isinstance(cfg.get("auxiliary"), dict):
        _replace_grok(cfg["auxiliary"])
    cfg.setdefault("platform_toolsets", {})["api_server"] = ["stt", *SERVERS]
    servers = cfg.setdefault("mcp_servers", {})
    for name in SERVERS:
        args = ["-m", "hub.household_mcp", "--vault", "/vault", "--profile", str(profile), "--state", str(state)]
        servers[name] = {"command": str(python), "args": args, "cwd": str(project), "trust": "full"}

    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state, 0o700)
    root_env, profile_env = root / ".env", profile / ".env"
    terminal_env = state / "terminal.env"
    for path in (root_env, profile_env, terminal_env):
        originals[path] = path.read_bytes() if path.exists() else b""
    existed = {path: path.exists() for path in originals}
    modes = {path: stat.S_IMODE(path.stat().st_mode) for path in originals if existed[path]}
    root_text, root_secret = _service_secret(originals[root_env].decode(), "API_SERVER_KEY")
    if api.get("extra", {}).get("key") not in (None, root_secret):
        raise ValueError("an existing listener credential needs review")
    profile_text, profile_secret = _service_secret(originals[profile_env].decode(), "API_SERVER_KEY")
    previous = originals[terminal_env].decode()
    terminal_text, device_secret = _service_secret(previous, "HEARTH_DEVICE_TOKEN")
    # Existing device credentials remain unchanged on reconfiguration.
    retained = [line for line in terminal_text.splitlines() if not line.startswith(("HEARTH_HERMES_URL=", "HEARTH_HERMES_KEY="))]
    terminal_text = "\n".join(retained) + "\nHEARTH_HERMES_URL=http://127.0.0.1:8642\nHEARTH_HERMES_KEY=" + profile_secret + "\n"
    writes = {root_path: yaml.safe_dump(root_cfg, sort_keys=False, allow_unicode=True).encode(),
              profile_path: yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True).encode(),
              root_env: root_text.encode(), profile_env: profile_text.encode(), terminal_env: terminal_text.encode()}
    backup = state / "backups" / uuid.uuid4().hex
    backup.mkdir(parents=True, mode=0o700)
    manifest = []
    for i, (path, raw) in enumerate(originals.items()):
        filename = f"{i}-{path.name}"
        _atomic(backup / filename, raw, private=True)
        manifest.append({"path": str(path), "existed": existed[path], "mode": modes.get(path), "file": filename})
    _atomic(backup / "manifest.json", json.dumps(manifest).encode(), private=True)
    try:
        for path, raw in writes.items():
            _atomic(path, raw, private=True)
        if hashlib.sha256(soul.read_bytes()).hexdigest() != soul_hash:
            raise RuntimeError("Catthew identity changed during configuration")
    except Exception:
        for path, raw in originals.items():
            if existed[path]:
                _atomic(path, raw, private=True)
                os.chmod(path, modes[path])
            elif path.exists():
                path.unlink()
        raise
    return {"model": "gpt-6.1-terra", "provider": "openai-codex", "soul_sha256": soul_hash,
            "listener": "127.0.0.1:8642", "tool_servers": list(SERVERS), "backup": str(backup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "project", "python", "state"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Apply backed-up scoped changes")
    args = parser.parse_args()
    if not args.apply:
        parser.error("review the approved deployment path and pass --apply to write configuration")
    print(json.dumps(configure(args.root, args.project, args.python, args.state)))


if __name__ == "__main__":
    main()
