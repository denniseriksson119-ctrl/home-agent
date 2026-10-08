"""SQLite queue smoke tests without Home Assistant or HTTP server."""
import hashlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "home_agent/rootfs/opt/home-agent"))
import inbox_queue

class QueueTests(unittest.TestCase):
    def test_persistence_pause_resume_dedupe_and_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_file = root / "test.db"
            with sqlite3.connect(db_file) as db:
                db.executescript("""
                    CREATE TABLE source(source_id TEXT PRIMARY KEY, storage_ref TEXT, sha256 TEXT);
                    CREATE TABLE inbox_item(
                        inbox_item_id TEXT PRIMARY KEY,source_id TEXT,stage TEXT,status TEXT,
                        failed_stage TEXT,last_error TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
                """)
                inbox_queue.migrate(db)
                digest = hashlib.sha256(b'example').hexdigest()
                (root/'original').write_bytes(b'example')
                db.execute("INSERT INTO source VALUES(?,?,?)",('source',str(root/'original'),digest))
                db.execute("INSERT INTO source VALUES(?,?,?)",('missing',str(root/'missing'),digest))
                db.executemany("INSERT INTO inbox_item(inbox_item_id,source_id,stage,status) VALUES(?,?,'captured','pending')",
                               [('a','source'),('b','source'),('c','missing')])
            inbox_queue.command(db_file,'start')
            inbox_queue.command(db_file,'start')
            inbox_queue.command(db_file,'pause')
            self.assertFalse(inbox_queue.process_one(db_file,root))
            inbox_queue.command(db_file,'resume')
            self.assertTrue(inbox_queue.process_one(db_file,root))
            inbox_queue.recover(db_file)
            self.assertTrue(inbox_queue.process_one(db_file,root))
            self.assertTrue(inbox_queue.process_one(db_file,root))
            self.assertFalse(inbox_queue.process_one(db_file,root))
            with sqlite3.connect(db_file) as db:
                rows = db.execute("SELECT inbox_item_id,stage,status FROM inbox_item ORDER BY inbox_item_id").fetchall()
                self.assertEqual(rows,[('a','dedupe_checked','awaiting_ai'),('b','dedupe_checked','awaiting_ai'),('c','captured','failed')])
                attempts = db.execute("SELECT attempts FROM inbox_queue_attempt ORDER BY inbox_item_id").fetchall()
                self.assertEqual(attempts,[(1,),(1,),(1,)])
if __name__ == '__main__':
    unittest.main()
