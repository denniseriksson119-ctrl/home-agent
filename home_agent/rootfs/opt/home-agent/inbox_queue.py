"""Persistent, deterministic Inbox preprocessing. No semantic AI or domain writes."""
import hashlib
import sqlite3
import threading
from pathlib import Path

_wakeup = threading.Event()
_worker_lock = threading.Lock()

def migrate(db):
    db.execute("""CREATE TABLE IF NOT EXISTS inbox_queue_control (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        state TEXT NOT NULL DEFAULT 'idle',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("INSERT OR IGNORE INTO inbox_queue_control(singleton,state) VALUES(1,'idle')")
    db.execute("""CREATE TABLE IF NOT EXISTS inbox_queue_attempt (
        inbox_item_id TEXT PRIMARY KEY REFERENCES inbox_item(inbox_item_id),
        attempts INTEGER NOT NULL DEFAULT 0,
        started_at TEXT,
        finished_at TEXT
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_inbox_queue_work ON inbox_item(status,stage)")

def connect(db_file):
    db = sqlite3.connect(db_file, timeout=15)
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def state(db_file):
    with connect(db_file) as db:
        control = db.execute("SELECT state FROM inbox_queue_control WHERE singleton=1").fetchone()[0]
        counts = dict(db.execute("SELECT status, COUNT(*) FROM inbox_item GROUP BY status").fetchall())
        return control, counts

def command(db_file, action):
    if action not in ('start','pause','resume'):
        raise ValueError("Unknown queue action")
    with connect(db_file) as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT state FROM inbox_queue_control WHERE singleton=1").fetchone()[0]
        if action == 'pause':
            new = 'paused'
        else:
            new = 'running'
            if old == 'paused':
                db.execute("UPDATE inbox_item SET status='pending', updated_at=CURRENT_TIMESTAMP WHERE status='paused' AND stage='captured'")
        db.execute("UPDATE inbox_queue_control SET state=?, updated_at=CURRENT_TIMESTAMP WHERE singleton=1",(new,))
        db.commit()
    _wakeup.set()
    return new

def recover(db_file):
    with connect(db_file) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""UPDATE inbox_item SET status='pending',updated_at=CURRENT_TIMESTAMP
                      WHERE status='processing' AND stage='captured'""")
        db.commit()

def process_one(db_file, source_dir):
    with connect(db_file) as db:
        db.execute("BEGIN IMMEDIATE")
        control = db.execute("SELECT state FROM inbox_queue_control WHERE singleton=1").fetchone()[0]
        if control != 'running':
            db.commit()
            return False
        item = db.execute("""SELECT i.inbox_item_id,s.storage_ref,s.sha256
                             FROM inbox_item i JOIN source s ON s.source_id=i.source_id
                             WHERE i.stage='captured' AND i.status='pending'
                             ORDER BY i.created_at,i.inbox_item_id LIMIT 1""").fetchone()
        if not item:
            db.execute("UPDATE inbox_queue_control SET state='idle',updated_at=CURRENT_TIMESTAMP WHERE singleton=1")
            db.commit()
            return False
        ident, storage, expected = item
        db.execute("UPDATE inbox_item SET status='processing',updated_at=CURRENT_TIMESTAMP WHERE inbox_item_id=?",(ident,))
        db.execute("""INSERT INTO inbox_queue_attempt(inbox_item_id,attempts,started_at)
                      VALUES(?,1,CURRENT_TIMESTAMP) ON CONFLICT(inbox_item_id)
                      DO UPDATE SET attempts=attempts+1,started_at=CURRENT_TIMESTAMP""",(ident,))
        db.commit()
    try:
        path = Path(storage).resolve(strict=True)
        root = Path(source_dir).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Source is not a regular file within source storage")
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(65536), b''):
                digest.update(chunk)
        if not expected or digest.hexdigest() != expected:
            raise ValueError("Source SHA256 mismatch or missing checksum")
        with connect(db_file) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""UPDATE inbox_item SET stage='dedupe_checked',status='awaiting_ai',
                          failed_stage=NULL,last_error=NULL,updated_at=CURRENT_TIMESTAMP
                          WHERE inbox_item_id=? AND stage='captured' AND status='processing'""",(ident,))
            db.execute("UPDATE inbox_queue_attempt SET finished_at=CURRENT_TIMESTAMP WHERE inbox_item_id=?",(ident,))
            db.commit()
    except Exception as exc:
        with connect(db_file) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""UPDATE inbox_item SET status='failed',failed_stage='captured',
                          last_error=?,updated_at=CURRENT_TIMESTAMP
                          WHERE inbox_item_id=? AND status='processing'""",(str(exc)[:400],ident))
            db.execute("UPDATE inbox_queue_attempt SET finished_at=CURRENT_TIMESTAMP WHERE inbox_item_id=?",(ident,))
            db.commit()
    return True

def worker_loop(db_file, source_dir):
    recover(db_file)
    while True:
        if not process_one(db_file, source_dir):
            _wakeup.wait(2)
            _wakeup.clear()

def launch(db_file, source_dir):
    with _worker_lock:
        if getattr(launch,'thread',None) and launch.thread.is_alive():
            return
        launch.thread = threading.Thread(target=worker_loop,args=(db_file,source_dir),daemon=True,name='inbox-worker')
        launch.thread.start()
