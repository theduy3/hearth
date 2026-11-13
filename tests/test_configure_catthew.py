"""Configuration changes must preserve Catthew identity and unrelated channels."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import yaml

from tools.configure_catthew import configure


class ConfigureTests(unittest.TestCase):
    def setUp(self):
        self.catalog_patch = patch("tools.configure_catthew._catalog", return_value={"builtins": ["stt", "terminal", "x_search"], "plugins": ["homeassistant"]})
        self.catalog_patch.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "hermes"
        self.profile = self.root / "profiles/catthew"
        self.profile.mkdir(parents=True)
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        self.python = Path(self.tmp.name) / "python"
        self.python.touch()
        self.state = self.root / "terminal-state"
        self.root_config = {"platforms": {"telegram": {"enabled": True}}, "model": {"default": "other-profile-model"}}
        self.profile_config = {"model": {"default": "grok-4.7", "provider": "xai-oauth"},
                               "platform_toolsets": {"telegram": ["existing-tools"]},
                               "mcp_servers": {"existing-server": {"command": "keep-me"}},
                               "skills": {"disabled": ["keep-disabled"]}}
        (self.root / "config.yaml").write_text(yaml.safe_dump(self.root_config))
        (self.profile / "config.yaml").write_text(yaml.safe_dump(self.profile_config))
        (self.profile / "SOUL.md").write_text("Catthew's existing identity\n")
        (self.profile / ".env").write_text("EXISTING_SETTING=preserved\n")

    def tearDown(self):
        self.catalog_patch.stop()
        self.tmp.cleanup()

    def test_config_is_scoped_and_soul_is_unchanged(self):
        soul = (self.profile / "SOUL.md").read_bytes()
        result = configure(self.root, self.project, self.python, self.state)
        root = yaml.safe_load((self.root / "config.yaml").read_text())
        cfg = yaml.safe_load((self.profile / "config.yaml").read_text())
        self.assertEqual(root["model"], self.root_config["model"])
        self.assertEqual(cfg["platform_toolsets"]["telegram"], ["existing-tools"])
        self.assertEqual(cfg["skills"], self.profile_config["skills"])
        self.assertEqual(cfg["mcp_servers"]["existing-server"], {"command": "keep-me"})
        self.assertEqual(cfg["model"]["provider"], "openai-codex")
        self.assertEqual(cfg["model"]["default"], "gpt-6.1-terra")
        self.assertEqual((self.profile / "SOUL.md").read_bytes(), soul)
        self.assertEqual(cfg["platform_toolsets"]["api_server"], ["stt", "catthew-household"])
        self.assertEqual(cfg["known_plugin_toolsets"]["api_server"], ["homeassistant"])
        self.assertEqual(cfg["mcp_servers"]["catthew-household"]["trust"], "full")
        self.assertNotIn("key", str(result).lower())
        self.assertIn("EXISTING_SETTING=preserved", (self.profile / ".env").read_text())
        self.assertEqual((self.state / "terminal.env").stat().st_mode & 0o777, 0o600)

    def test_virtualenv_interpreter_symlink_is_not_resolved_away(self):
        target = Path(self.tmp.name) / "real-python"
        target.touch()
        self.python.unlink()
        self.python.symlink_to(target)
        configure(self.root, self.project, self.python, self.state)
        cfg = yaml.safe_load((self.profile / "config.yaml").read_text())
        self.assertEqual(cfg["mcp_servers"]["catthew-household"]["command"], str(self.python.absolute()))

    def test_reconfiguration_preserves_service_credentials(self):
        configure(self.root, self.project, self.python, self.state)
        before = (self.state / "terminal.env").read_bytes()
        configure(self.root, self.project, self.python, self.state)
        self.assertEqual((self.state / "terminal.env").read_bytes(), before)

    def test_rollback_restores_terminal_environment_and_original_file_absence(self):
        from unittest.mock import patch
        from tools.configure_catthew import _atomic
        self.state.mkdir()
        original = "HEARTH_DEVICE_TOKEN=" + "x" * 48 + "\nCUSTOM_SETTING=preserve\n"
        (self.state / "terminal.env").write_text(original)
        root_before = (self.root / "config.yaml").read_bytes()
        profile_before = (self.profile / "config.yaml").read_bytes()

        def change_identity(path, data, **kwargs):
            _atomic(path, data, **kwargs)
            if path == (self.state / "terminal.env").resolve():
                (self.profile / "SOUL.md").write_text("Concurrent identity edit")

        with patch("tools.configure_catthew._atomic", side_effect=change_identity):
            with self.assertRaises(RuntimeError):
                configure(self.root, self.project, self.python, self.state)
        self.assertEqual((self.root / "config.yaml").read_bytes(), root_before)
        self.assertEqual((self.profile / "config.yaml").read_bytes(), profile_before)
        self.assertEqual((self.state / "terminal.env").read_text(), original)
        self.assertFalse((self.root / ".env").exists())

    def test_existing_different_api_listener_is_not_silently_replaced(self):
        self.root_config["platforms"]["api_server"] = {"enabled": True, "extra": {"port": 9000}}
        (self.root / "config.yaml").write_text(yaml.safe_dump(self.root_config))
        with self.assertRaises(ValueError):
            configure(self.root, self.project, self.python, self.state)
        self.assertEqual(yaml.safe_load((self.profile / "config.yaml").read_text()), self.profile_config)


if __name__ == "__main__":
    unittest.main()
