"""Exact calendar change proposals. Only private, single-use capabilities can apply them."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from hub.calendar import _etag, _time


class ApprovalStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        os.chmod(path, 0o600)
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("""CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY, operation TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL,
            kind TEXT NOT NULL, payload TEXT NOT NULL, preview TEXT NOT NULL,
            created REAL NOT NULL, status TEXT NOT NULL, capability_hash TEXT,
            expires REAL, attempts INTEGER NOT NULL DEFAULT 0, result TEXT NOT NULL DEFAULT ''
        )""")
        self.db.commit()

    def close(self):
        self.db.close()

    @staticmethod
    def _record(row):
        if not row:
            return None
        return {"id": row["id"], "kind": row["kind"], "payload": json.loads(row["payload"]),
                "preview": json.loads(row["preview"]), "status": row["status"], "result": row["result"],
                "notified": bool(row["capability_hash"]), "attempts": row["attempts"]}

    def get(self, proposal_id):
        with self.lock:
            return self._record(self.db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone())

    def propose(self, operation, kind, payload, preview):
        if not isinstance(operation, str) or not 1 <= len(operation) <= 128 or kind not in ("edit", "delete"):
            raise ValueError("invalid proposal operation")
        fields = {"event_id", "etag"} | ({"title", "start", "end"} if kind == "edit" else set())
        if not isinstance(payload, dict) or set(payload) != fields:
            raise ValueError("proposal fields do not match operation")
        if any(not isinstance(v, str) or not v or len(v) > 1024 for v in payload.values()):
            raise ValueError("invalid proposal text")
        _etag(payload["etag"])
        if kind == "edit":
            _time(payload["start"])
            _time(payload["end"])
        encoded = json.dumps(payload, sort_keys=True)
        fingerprint = hashlib.sha256((kind + encoded).encode()).hexdigest()
        preview_text = json.dumps(preview, default=str)
        if len(preview_text) > 16000:
            raise ValueError("preview exceeds limit")
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute("SELECT * FROM proposals WHERE operation=?", (operation,)).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise ValueError("operation already belongs to a different proposal")
                return self._record(existing)
            if self.db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0] >= 512:
                raise ValueError("approval history requires maintenance")
            proposal_id = uuid.uuid4().hex
            self.db.execute("""INSERT INTO proposals
                (id,operation,fingerprint,kind,payload,preview,created,status)
                VALUES (?,?,?,?,?,?,?,'pending')""",
                (proposal_id, operation, fingerprint, kind, encoded, preview_text, time.time()))
            return self.get(proposal_id)

    def pending(self):
        with self.lock:
            return [self._record(r) for r in self.db.execute("SELECT * FROM proposals WHERE status='pending' ORDER BY created")]

    def mint(self, proposal_id, *, now=None):
        now = time.time() if now is None else now
        capability = secrets.token_urlsafe(48)
        with self.lock, self.db:
            cursor = self.db.execute("""UPDATE proposals SET capability_hash=?,expires=?,attempts=attempts+1,status='notifying'
                WHERE id=? AND status IN ('pending','notifying') AND attempts<3
                AND (capability_hash IS NULL OR expires<=?)""",
                (hashlib.sha256(capability.encode()).hexdigest(), now + 600, proposal_id, now))
            if cursor.rowcount != 1:
                raise ValueError("proposal is unavailable for notification")
        return capability

    def mark_notified(self, proposal_id):
        with self.lock, self.db:
            self.db.execute("UPDATE proposals SET status='pending' WHERE id=? AND status='notifying'", (proposal_id,))

    def notification_failed(self, proposal_id):
        with self.lock, self.db:
            self.db.execute("""UPDATE proposals SET capability_hash=NULL,expires=NULL,
                status=CASE WHEN attempts>=3 THEN 'failed' ELSE 'pending' END WHERE id=? AND status IN ('pending','notifying')""", (proposal_id,))

    def view(self, capability, *, now=None):
        if not isinstance(capability, str) or not 32 <= len(capability) <= 128:
            return None
        now = time.time() if now is None else now
        digest = hashlib.sha256(capability.encode()).hexdigest()
        with self.lock:
            return self._record(self.db.execute("""SELECT * FROM proposals
                WHERE capability_hash=? AND status IN ('pending','notifying') AND expires>?""", (digest, now)).fetchone())

    def consume(self, capability, decision, *, now=None):
        if decision not in ("allow", "deny"):
            raise ValueError("invalid approval decision")
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            record = self.view(capability, now=now)
            if record is None:
                return None
            status = "executing" if decision == "allow" else "denied"
            self.db.execute("UPDATE proposals SET status=?,capability_hash=NULL WHERE id=?", (status, record["id"]))
            record["status"] = status
            return record

    def finish(self, proposal_id, *, succeeded):
        with self.lock, self.db:
            self.db.execute("""UPDATE proposals SET status=?,result=? WHERE id=? AND status='executing'""",
                            ("completed" if succeeded else "uncertain",
                             "Change confirmed." if succeeded else "Outcome requires verification; change was not retried.", proposal_id))

    def recover(self):
        with self.lock, self.db:
            self.db.execute("""UPDATE proposals SET status=CASE WHEN attempts>=3 THEN 'failed' ELSE 'pending' END,
                capability_hash=NULL,expires=NULL WHERE status='notifying'""")
            self.db.execute("""UPDATE proposals SET status='uncertain',capability_hash=NULL,
                result='Interrupted change requires verification; it was not replayed.' WHERE status='executing'""")

    def expire(self):
        with self.lock, self.db:
            self.db.execute("UPDATE proposals SET status='expired',capability_hash=NULL WHERE status='pending' AND expires<?", (time.time(),))
