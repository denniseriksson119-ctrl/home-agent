"""Persistent, deterministic Inbox preflight worker. No AI or Home Graph writes."""
import hashlib
import sqlite3
import threading
import time
from pathlib import Path

class InboxQueue:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None

    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=20)
        db.execute("PRAGMA busy_timeout=20000")
        return db

    def setup(self):
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS inbox_queue_control (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                mode TEXT NOT NULL CHECK(mode IN ('idle','running','paused')),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("INSERT OR IGNORE INTO inbox_queue_control(singleton,mode) VALUES(1,'idle')")
            db.execute("""CREATE TABLE IF NOT EXISTS inbox_preflight (
                inbox_item_id TEXT PRIMARY KEY,
                result TEXT NOT NULL CHECK(result IN ('verified','failed')),
                detail TEXT,
                checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(inbox_item_id) REFERENCES inbox_item(inbox_item_id))""")
            # An interrupted preflight is safe to retry from the source bytes.
            db.execute("""UPDATE inbox_item SET status='pending',stage='captured',
                updated_at=CURRENT_TIMESTAMP WHERE status='processing' AND stage='verifying'""")
            # After process restart, running means the worker should resume.
            db.commit()

    def mode(self):
        with self.connect() as db:
            return db.execute("SELECT mode FROM inbox_queue_control WHERE singleton=1").fetchone()[0]

    def set_mode(self, mode):
        if mode not in ('running','paused'):
            raise ValueError("Invalid queue mode")
        with self.connect() as db:
            db.execute("UPDATE inbox_queue_control SET mode=?,updated_at=CURRENT_TIMESTAMP WHERE singleton=1", (mode,))
            db.commit()

    def status(self):
        with self.connect() as db:
            mode = db.execute("SELECT mode FROM inbox_queue_control WHERE singleton=1").fetchone()[0]
            counts = dict(db.execute("SELECT status,COUNT(*) FROM inbox_item GROUP BY status").fetchall())
            ready = db.execute("SELECT COUNT(*) FROM inbox_item WHERE stage='preflight_verified' AND status='awaiting_analysis'").fetchone()[0]
            failed = db.execute("SELECT COUNT(*) FROM inbox_item WHERE status='failed'").fetchone()[0]
            pending = db.execute("SELECT COUNT(*) FROM inbox_item WHERE status='pending' AND stage='captured'").fetchone()[0]
            return dict(mode=mode, total=sum(counts.values()), pending=pending, verified=ready,
                        failed=failed, processing=counts.get('processing', 0))

    def process_one(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT mode FROM inbox_queue_control WHERE singleton=1").fetchone()[0] != 'running':
                db.rollback()
                return False
            row = db.execute("""SELECT i.inbox_item_id,s.storage_ref,s.sha256,s.source_id
                FROM inbox_item i JOIN source s ON s.source_id=i.source_id
                WHERE i.status='pending' AND i.stage='captured'
                ORDER BY i.created_at,i.inbox_item_id LIMIT 1""").fetchone()
            if not row:
                db.execute("UPDATE inbox_queue_control SET mode='idle',updated_at=CURRENT_TIMESTAMP WHERE singleton=1")
                db.commit()
                return False
            inbox_id, storage_ref, expected, source_id = row
            db.execute("""UPDATE inbox_item SET status='processing',stage='verifying',
                updated_at=CURRENT_TIMESTAMP WHERE inbox_item_id=?""", (inbox_id,))
            db.commit()
        try:
            if not storage_ref or not expected:
                raise ValueError("Missing source storage reference or SHA256")
            path = Path(storage_ref)
            # Only files in the managed source directory are valid preflight inputs.
            if path.parent != self.db_path.parent / "sources":
                raise ValueError("Source outside managed storage")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError("Original file SHA256 mismatch")
            result, detail, stage, status = 'verified', 'Original verified by SHA256', 'preflight_verified', 'awaiting_analysis'
        except (OSError, ValueError) as exc:
            result, detail, stage, status = 'failed', str(exc)[:300], 'verifying', 'failed'
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""INSERT INTO inbox_preflight(inbox_item_id,result,detail)
                VALUES(?,?,?) ON CONFLICT(inbox_item_id) DO UPDATE SET
                result=excluded.result,detail=excluded.detail,checked_at=CURRENT_TIMESTAMP""",
                (inbox_id,result,detail))
            db.execute("""UPDATE inbox_item SET stage=?,status=?,last_error=?,
                failed_stage=?,updated_at=CURRENT_TIMESTAMP WHERE inbox_item_id=?""",
                (stage,status,detail if result == 'failed' else None,
                 stage if result == 'failed' else None,inbox_id))
            db.commit()
        return True

    def run(self):
        while not self.stop.is_set():
            try:
                if self.mode() == 'running' and self.process_one():
                    continue
            except (OSError, sqlite3.Error) as exc:
                print("Inbox queue error:", exc, flush=True)
            self.stop.wait(0.7)

    def start(self):
        self.setup()
        self.thread = threading.Thread(target=self.run, daemon=True, name="inbox-preflight")
        self.thread.start()
