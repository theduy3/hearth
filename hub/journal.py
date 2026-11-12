"""Crash-safe device requests. Agent turns with uncertain outcomes are never replayed."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path


class RequestConflict(ValueError):
    """A client reused an upload ID for different audio."""


class QueueFull(RuntimeError):
    pass


class Journal:
    def __init__(self, path: Path, capacity: int = 8, history_capacity: int = 10000, device_capacity: int = 32):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Create with private permissions before SQLite writes any household data.
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(path, 0o600)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._db.row_factory = sqlite3.Row
        # DELETE mode + secure_delete avoids retaining recordings/transcripts in
        # historical WAL frames after logical deletion. Commit removes rollback journals.
        self._db.execute("PRAGMA journal_mode=DELETE")
        self._db.execute("PRAGMA secure_delete=ON")
        self.capacity = capacity
        self.history_capacity = history_capacity
        self.device_capacity = device_capacity
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY, session TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, device TEXT NOT NULL, client_id TEXT NOT NULL,
                digest TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                status TEXT NOT NULL, wav BLOB, transcript TEXT NOT NULL DEFAULT '',
                reply TEXT NOT NULL DEFAULT '', run_id TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '', speech_status TEXT NOT NULL DEFAULT 'pending',
                audio BLOB, UNIQUE(device, client_id)
            );
            CREATE INDEX IF NOT EXISTS requests_queue ON requests(status, created);
        """)

    def close(self):
        with self._lock:
            self._db.close()

    @staticmethod
    def _public(row):
        return {k: row[k] for k in row.keys() if k not in ("wav", "audio", "digest", "transcript")}

    def session(self, device: str) -> str:
        if not device or len(device) > 128:
            raise ValueError("invalid device identifier")
        with self._lock, self._db:
            self._db.execute("BEGIN IMMEDIATE")
            existing = self._db.execute("SELECT session FROM devices WHERE id=?", (device,)).fetchone()
            if existing:
                return existing[0]
            if self._db.execute("SELECT COUNT(*) FROM devices").fetchone()[0] >= self.device_capacity:
                raise QueueFull("device registration capacity reached")
            self._db.execute("INSERT INTO devices VALUES (?, ?)",
                             (device, "hearth_" + uuid.uuid4().hex))
            return self._db.execute("SELECT session FROM devices WHERE id=?", (device,)).fetchone()[0]

    def accept(self, device: str, client_id: str, wav: bytes, *, now=None):
        if not device or len(device) > 128 or not client_id or len(client_id) > 64:
            raise ValueError("device and upload ID are required")
        if not wav or len(wav) > 4 * 1024 * 1024:
            raise ValueError("audio must be between 1 byte and 4 MiB")
        now = time.time() if now is None else now
        digest = hashlib.sha256(wav).hexdigest()
        with self._lock, self._db:
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute("SELECT * FROM requests WHERE device=? AND client_id=?",
                                   (device, client_id)).fetchone()
            if row:
                if row["digest"] != digest:
                    raise RequestConflict("upload ID already belongs to different audio")
                return self._public(row)
            if self.depth() >= self.capacity:
                raise QueueFull("terminal queue is full")
            if self._db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] >= self.history_capacity:
                # Fail closed instead of deleting dedupe IDs and replaying old uploads.
                raise QueueFull("request history capacity reached; retention review required")
            request_id = uuid.uuid4().hex
            self._db.execute("""INSERT INTO requests
                (id,device,client_id,digest,created,updated,status,wav)
                VALUES (?,?,?,?,?,?,'queued',?)""",
                (request_id, device, client_id, digest, now, now, wav))
            return self._public(self._db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone())

    def depth(self):
        with self._lock:
            return self._db.execute("""SELECT COUNT(*) FROM requests WHERE status IN
                ('queued','transcribing','processing','needs_confirmation')""").fetchone()[0]

    def get(self, device: str, request_id: str):
        with self._lock:
            row = self._db.execute("SELECT * FROM requests WHERE device=? AND id=?",
                                   (device, request_id)).fetchone()
            return self._public(row) if row else None

    def claim(self):
        with self._lock, self._db:
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute("SELECT * FROM requests WHERE status='queued' ORDER BY created,rowid LIMIT 1").fetchone()
            if not row:
                return None
            self._db.execute("UPDATE requests SET status='transcribing',updated=? WHERE id=?",
                             (time.time(), row["id"]))
            return dict(row)

    def begin_agent(self, request_id: str, transcript: str):
        # Commit this boundary BEFORE making any network request to Hermes.
        with self._lock, self._db:
            cursor = self._db.execute("""UPDATE requests SET status='processing',transcript=?,
                wav=NULL,updated=? WHERE id=? AND status='transcribing'""",
                (transcript, time.time(), request_id))
            if cursor.rowcount != 1:
                raise ValueError("request is not transcribing")

    def set_run(self, request_id: str, run_id: str):
        with self._lock, self._db:
            self._db.execute("UPDATE requests SET run_id=?,updated=? WHERE id=?",
                             (run_id, time.time(), request_id))

    def complete(self, request_id: str, reply: str):
        with self._lock, self._db:
            cursor = self._db.execute("""UPDATE requests SET status='completed',reply=?,
                transcript='',wav=NULL,updated=? WHERE id=? AND status IN ('processing','needs_confirmation')""",
                (reply, time.time(), request_id))
            if cursor.rowcount != 1:
                raise ValueError("request is not processing")

    def fail(self, request_id: str, error: str, *, uncertain=False):
        with self._lock, self._db:
            self._db.execute("""UPDATE requests SET status=?,error=?,wav=NULL,transcript='',
                speech_status='unavailable',updated=? WHERE id=? AND status!='completed'""",
                ("uncertain" if uncertain else "failed", error, time.time(), request_id))

    def speech_failed(self, request_id: str):
        with self._lock, self._db:
            self._db.execute("UPDATE requests SET speech_status='failed',updated=? WHERE id=? AND status='completed'",
                             (time.time(), request_id))

    def set_audio(self, request_id: str, audio: bytes):
        if not audio or len(audio) > 4 * 1024 * 1024:
            raise ValueError("invalid reply audio size")
        with self._lock, self._db:
            self._db.execute("UPDATE requests SET audio=?,speech_status='ready',updated=? WHERE id=? AND status='completed'",
                             (audio, time.time(), request_id))

    def audio(self, device: str, request_id: str):
        with self._lock:
            row = self._db.execute("SELECT audio FROM requests WHERE device=? AND id=? AND status='completed'",
                                   (device, request_id)).fetchone()
            return row[0] if row else None

    def recover(self):
        with self._lock, self._db:
            self._db.execute("UPDATE requests SET status='queued' WHERE status='transcribing'")
            self._db.execute("""UPDATE requests SET status='uncertain',wav=NULL,transcript='',
                error='Agent outcome requires verification; request was not replayed.',speech_status='unavailable'
                WHERE status IN ('processing','needs_confirmation')""")
            self._db.execute("UPDATE requests SET speech_status='failed' WHERE status='completed' AND speech_status='pending'")

    def expire(self, *, now=None):
        now = time.time() if now is None else now
        with self._lock, self._db:
            self._db.execute("""UPDATE requests SET status='failed',wav=NULL,transcript='',
                error='Audio expired before processing.',speech_status='unavailable'
                WHERE status='queued' AND created<?""", (now - 86400,))
            self._db.execute("UPDATE requests SET audio=NULL,speech_status='expired' WHERE audio IS NOT NULL AND updated<?",
                             (now - 86400,))
            self._db.execute("""UPDATE requests SET reply='',error='',transcript=''
                WHERE status IN ('completed','failed','uncertain') AND updated<?""",
                (now - 7 * 86400,))
