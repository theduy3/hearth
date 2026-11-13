"""Narrow household operations over existing vault notes and the family calendar.

The device never supplies a filesystem path or a calendar ID. Reference content
is data, and cannot expand this tool boundary.
"""
from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from markdown_it import MarkdownIt

PACIFIC = ZoneInfo("America/Vancouver")


class VaultLoader(yaml.SafeLoader):
    """Keep a mistyped human date as text instead of hiding the whole note."""


def _vault_timestamp(loader, node):
    try:
        return yaml.SafeLoader.construct_yaml_timestamp(loader, node)
    except (ValueError, AttributeError):
        return loader.construct_scalar(node)


VaultLoader.add_constructor("tag:yaml.org,2002:timestamp", _vault_timestamp)


class ScopeError(ValueError):
    pass


def _exchange(first, second):
    """Atomically exchange two files, preserving the displaced inode for review.

    POSIX replace has no compare-and-swap primitive. Linux renameat2 and macOS
    renamex_np provide an atomic exchange, so a racing writer's version survives.
    """
    native = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        call = native.renamex_np
        call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = call(os.fsencode(first), os.fsencode(second), 2)  # RENAME_SWAP
    elif sys.platform.startswith("linux"):
        call = native.renameat2
        call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = call(-100, os.fsencode(first), -100, os.fsencode(second), 2)  # RENAME_EXCHANGE
    else:
        raise OSError("atomic household edits require Linux or macOS")
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _text(value, limit=500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("text is empty or exceeds its limit")
    return value.strip()


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _has_tag(meta, body, tag):
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = re.split(r"[\s,]+", tags)
    if isinstance(tags, list) and any(isinstance(x, str) and x.lstrip("#").casefold() == tag for x in tags):
        return True
    return re.search(r"(?<![\w/#])#" + re.escape(tag) + r"(?![\w/-])", body, re.IGNORECASE) is not None


def _parse(raw):
    text = raw.decode("utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    meta = yaml.load(match.group(1), Loader=VaultLoader) if match else {}
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter must be a mapping")
    return meta, text[match.end():] if match else text


def _encode(meta, body):
    return ("---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n" + body).encode("utf-8")


def event_elapsed(item, now):
    """Only an explicit, non-recurring event with a known exclusive end expires."""
    if item.get("kind") != "event" or item.get("recurring"):
        return False
    try:
        end = item.get("event_end")
        if end and re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
            if item.get("all_day") is not True:
                return False
            until = datetime.combine(date.fromisoformat(end), datetime.min.time(), PACIFIC)
        elif end:
            until = datetime.fromisoformat(end)
            if until.tzinfo is None:
                return False
        elif item.get("all_day") is True:
            until = datetime.combine(date.fromisoformat(item["due"]) + timedelta(days=1), datetime.min.time(), PACIFIC)
        else:
            return False
        return until <= now
    except (KeyError, TypeError, ValueError):
        return False


def _grocery_text(value):
    value = _text(value, 120)
    if any(ord(char) < 32 for char in value) or "<!--" in value or "-->" in value:
        raise ValueError("grocery item must be one plain text line")
    return value


def _grocery_item_lines(body):
    return {token.map[0] for token in MarkdownIt("commonmark").parse(body)
            if token.type == "list_item_open" and token.map is not None}


def _grocery_writable(body):
    # Ask the actual Markdown parser whether a new final checkbox would be
    # visible. Open HTML comments/fences must never hide a successful write.
    probe = body.rstrip("\n") + "\n\n- [ ] Catthew boundary probe\n"
    if len(probe.splitlines()) - 1 not in _grocery_item_lines(probe):
        raise ScopeError("grocery list has an unresolved Markdown boundary")


def _grocery_rows(body):
    rows, seen = [], set()
    visible = _grocery_item_lines(body)
    for match in re.finditer(r"(?m)^([-*]) \[([ xX])\] (.+)$", body):
        if body.count("\n", 0, match.start()) not in visible:
            continue
        text = match[3].strip()
        marker = re.search(r"\s*<!-- catthew-grocery:([a-f0-9]{32}) -->$", text)
        identity = marker[1] if marker else _digest(f"{match.start()}:{text}".encode())[:32]
        if marker:
            text = text[:marker.start()].strip()
        if not text or len(text) > 300 or identity in seen or len(rows) >= 100:
            raise ScopeError("grocery list needs review: invalid, duplicate or excessive items")
        seen.add(identity)
        rows.append((match, {"id": identity, "item": text, "state": "needed" if match[2] == " " else "purchased"}))
    return rows


class Household:
    def __init__(self, vault: Path, calendar, state: Path):
        self.vault = Path(vault).resolve()
        self.calendar = calendar
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not (self.vault / "Tasks/tasks").is_dir():
            raise ValueError("existing vault task directory is required")

    @contextmanager
    def _locked(self):
        descriptor = os.open(self.state / "household.lock", os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def _records(self, directory):
        if not directory.is_dir():
            raise ScopeError("scoped vault directory is unavailable")
        if directory.resolve() != directory or not directory.is_relative_to(self.vault):
            raise ScopeError("scoped vault directory must not be a symbolic link")
        for path in sorted(directory.rglob("*.md")):
            if path.is_symlink() or not path.resolve().is_relative_to(self.vault):
                continue
            if any(part.startswith(".") for part in path.relative_to(self.vault).parts):
                continue
            try:
                if path.stat().st_size > 256 * 1024:
                    continue
                raw = path.read_bytes()
                meta, body = _parse(raw)
            except (OSError, UnicodeError, ValueError, yaml.YAMLError):
                continue
            yield path, meta, body, raw

    def _task(self, path, meta, body, raw):
        task_id = meta.get("id") or _digest(str(path.relative_to(self.vault)).encode())[:24]
        title = str(meta.get("title") or next((l.lstrip("# ") for l in body.splitlines() if l.startswith("# ")), path.stem))
        return {"id": str(task_id), "title": title[:300], "status": str(meta.get("status") or "open"),
                "due": str(meta.get("due_date") or ""), "revision": _digest(raw),
                "calendar_event_id": str(meta.get("google_event_id") or ""),
                "kind": str(meta.get("kind") or meta.get("type") or "task"),
                "all_day": meta.get("allDay") is True, "event_end": str(meta.get("event_end") or ""),
                "recurring": bool(meta.get("recurrence") or meta.get("rrule") or meta.get("recurring"))}

    def _task_records(self):
        if not (self.vault / "Tasks/tasks").is_dir():
            raise ScopeError("the Catthew task directory is unavailable")
        for name in ("tasks", "bugs", "ideas"):
            directory = self.vault / "Tasks" / name
            if directory.is_dir():
                yield from self._records(directory)

    def tasks(self):
        return [self._task(p, m, b, raw) for p, m, b, raw in self._task_records()
                if _has_tag(m, b, "catthew") and m.get("type") != "grocery-list"]

    def reference_notes(self):
        notes = []
        for path, meta, body, raw in self._records(self.vault):
            if _has_tag(meta, body, "kittyggup"):
                notes.append({"id": _digest(str(path.relative_to(self.vault)).encode())[:24],
                              "title": str(meta.get("title") or path.stem)[:300], "text": body[:2000]})
        return notes

    def search_notes(self, query):
        query = _text(query, 120).casefold()
        found = []
        for path, meta, body, raw in self._records(self.vault):
            if not _has_tag(meta, body, "kittyggup"):
                continue
            title = str(meta.get("title") or path.stem)
            pos = body.casefold().find(query)
            if pos < 0 and query not in title.casefold():
                continue
            start = max(0, pos - 150)
            found.append({"id": _digest(str(path.relative_to(self.vault)).encode())[:24],
                          "title": title[:300], "text": body[start:start + 2000]})
            if len(found) >= 8:
                break
        return found

    def _write(self, path, meta, body, *, expected=None):
        if path.is_symlink() or not any(path.resolve().is_relative_to(self.vault / "Tasks" / name) for name in ("tasks", "bugs", "ideas")) or not _has_tag(meta, body, "catthew"):
            raise ScopeError("task is outside the authorized Catthew workflow")
        if expected is not None and (not path.exists() or _digest(path.read_bytes()) != expected):
            raise ScopeError("task changed; read it again before editing")
        raw = _encode(meta, body)
        if len(raw) > 256 * 1024:
            raise ScopeError("note exceeds the readable household size limit")
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".hearth-", suffix=".tmp")
        preserve_temporary = False
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            if expected is None:
                # Atomic create refuses to overwrite even if an external writer races us.
                os.link(temporary, path)
            else:
                history = path.parent / ".catthew-history"
                history.mkdir(mode=0o700, exist_ok=True)
                if history.is_symlink() or not history.resolve().is_relative_to(path.parent.resolve()):
                    raise ScopeError("invalid task version archive")
                if sum(1 for _ in history.iterdir()) >= 256:
                    raise ScopeError("task version archive is full; review retained versions before editing")
                _exchange(temporary, path)
                preserve_temporary = True
                displaced = Path(temporary).read_bytes()
                if _digest(displaced) != expected:
                    # Restore the concurrent version atomically. A still-newer racing
                    # version is displaced into temporary and archived, never discarded.
                    _exchange(temporary, path)
                    os.rename(temporary, history / (uuid.uuid4().hex + ".md"))
                    raise ScopeError("task changed during edit; concurrent versions preserved for review")
                os.rename(temporary, history / (uuid.uuid4().hex + ".md"))
            return raw
        finally:
            if not preserve_temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def create_task(self, operation_id, title, *, due=""):
        operation_id = _text(operation_id, 128)
        title = _text(title, 300)
        when = None
        all_day = False
        if due:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
                when = date.fromisoformat(due)
                all_day = True
            else:
                when = datetime.fromisoformat(due)
                if when.tzinfo is None:
                    raise ValueError("due time requires an explicit timezone")
                when = when.astimezone(PACIFIC)
        identity = _digest(operation_id.encode())[:32]
        fingerprint = _digest(json.dumps([title, due], ensure_ascii=False).encode())
        path = self.vault / "Tasks/tasks" / f"catthew-hearth-{identity}.md"
        with self._locked():
            if path.exists():
                if path.is_symlink():
                    raise ScopeError("task path is not a regular file")
                raw = path.read_bytes()
                meta, body = _parse(raw)
                if meta.get("terminal_fingerprint") != fingerprint or not _has_tag(meta, body, "catthew"):
                    raise ScopeError("operation ID already belongs to a different task")
                current_due = str(meta.get("due_date") or "")
                expected_due = when.isoformat() if all_day else (when.date().isoformat() if when else "")
                if (str(meta.get("title")) != title or current_due != expected_due
                        or meta.get("status") != "open"
                        or (when and not all_day and str(meta.get("due_time")) != when.strftime("%H:%M"))):
                    raise ScopeError("task changed since creation; reconcile from the current note")
            else:
                meta = {"id": identity, "title": title, "type": "task", "status": "open", "tags": ["catthew", "household"],
                        "date": datetime.now(PACIFIC).date(), "terminal_fingerprint": fingerprint}
                if when:
                    meta["due_date"] = when if all_day else when.date()
                    meta["allDay"] = all_day
                    if not all_day:
                        meta["due_time"] = when.strftime("%H:%M")
                    meta["timezone"] = "America/Vancouver"
                body = f"# {title}\n\n- [ ] {title}\n"
                raw = self._write(path, meta, body)
            saved = self._task(path, meta, body, raw)
            if when and not meta.get("google_event_id"):
                try:
                    end = when + (timedelta(days=1) if all_day else timedelta(minutes=30))
                    event = self.calendar.create_event(identity, title, when.isoformat(), end.isoformat())
                    meta["google_event_id"] = event["id"]
                    meta["google_calendar_id"] = self.calendar.calendar_id
                    raw = self._write(path, meta, body, expected=_digest(raw))
                    saved = self._task(path, meta, body, raw)
                except Exception:
                    return {**saved, "ok": False, "task_saved": True, "calendar_synced": False,
                            "error": "Task saved; calendar event not confirmed. Retry this operation ID to reconcile."}
            return {**saved, "ok": True, "task_saved": True, "calendar_synced": bool(meta.get("google_event_id"))}

    def complete_task(self, task_id, revision):
        _text(task_id, 128)
        _text(revision, 64)
        with self._locked():
            for path, meta, body, raw in self._task_records():
                if meta.get("type") == "grocery-list" or not _has_tag(meta, body, "catthew"):
                    continue
                task = self._task(path, meta, body, raw)
                if task["id"] != task_id:
                    continue
                if task["revision"] != revision:
                    raise ScopeError("task changed; read it again before completion")
                return self._complete_record(path, meta, body, raw, datetime.now(PACIFIC))
        raise ScopeError("no matching task in Catthew's household scope")

    def _complete_record(self, path, meta, body, raw, now):
        task = self._task(path, meta, body, raw)
        meta["status"] = "completed"
        meta["updated"] = meta["completed_date"] = now.date()
        body = re.sub(r"(?m)^([-*]) \[ \] " + re.escape(task["title"]) + r"$",
                      lambda match: f"{match[1]} [x] {task['title']}", body, count=1)
        updated = self._write(path, meta, body, expected=_digest(raw))
        return {**self._task(path, meta, body, updated), "ok": True}

    def complete_past_events(self, *, now=None):
        now = now or datetime.now(PACIFIC)
        completed = []
        with self._locked():
            for path, meta, body, raw in self._task_records():
                if not _has_tag(meta, body, "catthew") or meta.get("status") in ("completed", "done", "cancelled"):
                    continue
                if event_elapsed(self._task(path, meta, body, raw), now):
                    completed.append(self._complete_record(path, meta, body, raw, now))
        return completed

    def _grocery_record(self):
        path = self.vault / "Tasks/tasks/grocery-shopping.md"
        if path.is_symlink() or path.parent.resolve() != path.parent:
            raise ScopeError("grocery list must be a scoped regular file")
        if not path.exists():
            return path, {"id": "catthew-grocery-shopping", "title": "Grocery Shopping", "type": "grocery-list",
                          "status": "open", "tags": ["catthew", "grocery", "household"]}, "# Grocery Shopping\n\n", None
        if path.stat().st_size > 256 * 1024:
            raise ScopeError("grocery list exceeds its size limit")
        raw = path.read_bytes()
        meta, body = _parse(raw)
        if meta.get("type") != "grocery-list" or not all(_has_tag(meta, "", tag) for tag in ("catthew", "grocery")):
            raise ScopeError("grocery filename belongs to another workflow")
        if meta.get("status") not in ("open", "pending", "in_progress"):
            raise ScopeError("grocery list is closed; do not restore old items implicitly")
        return path, meta, body, raw

    def groceries(self):
        _, _, body, raw = self._grocery_record()
        return {"revision": _digest(raw) if raw is not None else "", "items": [item for _, item in _grocery_rows(body)]}

    def add_grocery(self, operation_id, item):
        identity = _digest(("grocery:" + _text(operation_id, 128)).encode())[:32]
        item = _grocery_text(item)
        with self._locked():
            path, meta, body, raw = self._grocery_record()
            _grocery_writable(body)
            rows = _grocery_rows(body)
            for _, existing in rows:
                if existing["id"] == identity:
                    if existing["item"] != item:
                        raise ScopeError("grocery operation belongs to a changed item")
                    return {"ok": True, "item": existing, "revision": _digest(raw)}
            if len(rows) >= 100:
                raise ScopeError("grocery list is full; review purchased items first")
            body = body.rstrip("\n") + f"\n\n- [ ] {item} <!-- catthew-grocery:{identity} -->\n"
            saved = self._write(path, meta, body, expected=_digest(raw) if raw is not None else None)
            return {"ok": True, "item": {"id": identity, "item": item, "state": "needed"}, "revision": _digest(saved)}

    def update_grocery(self, item_id, revision, *, item=None, state=None):
        if not re.fullmatch(r"[a-f0-9]{32}", _text(item_id, 32)):
            raise ValueError("invalid grocery item ID")
        _text(revision, 64)
        if item is None and state is None:
            raise ValueError("grocery update is empty")
        if item is not None:
            item = _grocery_text(item)
        if state is not None and state not in ("needed", "purchased"):
            raise ValueError("invalid grocery item state")
        with self._locked():
            path, meta, body, raw = self._grocery_record()
            if raw is None or _digest(raw) != revision:
                raise ScopeError("grocery list changed; read its current revision")
            _grocery_writable(body)
            for match, existing in _grocery_rows(body):
                if existing["id"] != item_id:
                    continue
                updated = {**existing, "item": item if item is not None else existing["item"],
                           "state": state if state is not None else existing["state"]}
                checked = "x" if updated["state"] == "purchased" else " "
                line = f"{match[1]} [{checked}] {updated['item']} <!-- catthew-grocery:{item_id} -->"
                changed = body[:match.start()] + line + body[match.end():]
                saved = self._write(path, meta, changed, expected=revision)
                return {"ok": True, "item": updated, "revision": _digest(saved)}
        raise ScopeError("no matching grocery item; read the list again")
