"""Synthetic contract and handler tests; never use private household fixtures."""
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "home_agent/rootfs/opt/home-agent"))
import chatgpt_read
import server

TOKEN = "t" * 43


class Reply:
    def __init__(self, token=TOKEN):
        self.headers = {"Authorization": "Bearer " + token}
        self.path = chatgpt_read.PATH
        self.wfile = io.BytesIO()
        self.response_headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "home.db"
        self.token = self.root / "token"
        self.token.write_text(TOKEN)
        self.token.chmod(0o600)
        self.record = "id: eq_heat_pump_nibe_s1255\nname: Synthetic NIBE\nmodel: S1255\n"
        with sqlite3.connect(self.db_path) as db:
            db.executescript("""
                CREATE TABLE schema_meta(singleton INTEGER PRIMARY KEY, version INTEGER);
                INSERT INTO schema_meta VALUES(1,5);
                CREATE TABLE objects(object_id TEXT PRIMARY KEY, object_type TEXT, name TEXT, yaml_text TEXT);
                CREATE TABLE object_identity(permanent_id TEXT PRIMARY KEY, object_type TEXT, legacy_id TEXT);
                CREATE TABLE source(source_id TEXT PRIMARY KEY, original_name TEXT, media_type TEXT, sha256 TEXT, custody_status TEXT);
                CREATE TABLE source_link(source_id TEXT, object_id TEXT);
            """)
            db.execute("INSERT INTO objects VALUES(?,?,?,?)", (chatgpt_read.NIBE_LEGACY_ID, "asset", "Synthetic NIBE", self.record))
            db.execute("INSERT INTO object_identity VALUES(?,?,?)", ("permanent-nibe", "asset", chatgpt_read.NIBE_LEGACY_ID))
            db.execute("INSERT INTO objects VALUES('unrelated','asset','Other asset','private: unrelated-data')")
            db.execute("INSERT INTO source VALUES('linked','synthetic.pdf','application/pdf',?,'local_verified')", ("a" * 64,))
            db.execute("INSERT INTO source VALUES('unlinked','unrelated.pdf','application/pdf',?,'local_verified')", ("b" * 64,))
            db.execute("INSERT INTO source_link VALUES('linked','permanent-nibe')")

    def reply(self, token=TOKEN):
        reply = Reply(token)
        chatgpt_read.handle_get(reply, self.db_path, self.token)
        return reply

    def test_read_is_bounded_consistent_and_does_not_write(self):
        before = self.db_path.read_bytes()
        data = chatgpt_read.nibe_context(self.db_path)
        self.assertEqual(data["asset"]["record_yaml"], self.record)
        self.assertEqual([s["source_id"] for s in data["sources"]], ["linked"])
        self.assertNotIn("unrelated", json.dumps(data))
        self.assertEqual(data["context_revision"], chatgpt_read.nibe_context(self.db_path)["context_revision"])
        self.assertEqual(before, self.db_path.read_bytes())

    def test_server_routes_real_endpoint_and_disables_caching(self):
        reply = Reply()
        with patch.object(server, "DB_FILE", self.db_path), patch.object(chatgpt_read, "TOKEN_FILE", self.token):
            server.Handler.do_GET(reply)
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.response_headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(reply.wfile.getvalue())["asset"]["permanent_id"], "permanent-nibe")

    def test_wrong_and_missing_tokens_do_not_open_database(self):
        with patch.object(chatgpt_read, "nibe_context") as read:
            self.assertEqual(self.reply("wrong").status, 401)
            reply = Reply()
            reply.headers = {}
            chatgpt_read.handle_get(reply, self.db_path, self.token)
            self.assertEqual(reply.status, 401)
            read.assert_not_called()

    def test_missing_permissive_symlink_and_invalid_config_disable_access(self):
        self.token.chmod(0o644)
        self.assertEqual(self.reply().status, 401)
        self.token.unlink()
        self.assertEqual(self.reply().status, 401)
        self.token.symlink_to(self.db_path)
        self.assertEqual(self.reply().status, 401)
        self.token.unlink()
        self.token.write_text("too-short")
        self.token.chmod(0o600)
        self.assertEqual(self.reply().status, 401)

    def test_missing_database_is_not_created(self):
        self.db_path.unlink()
        self.assertEqual(self.reply().status, 503)
        self.assertFalse(self.db_path.exists())

    def test_unsupported_schema_is_not_migrated(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE schema_meta SET version=6")
        before = self.db_path.read_bytes()
        self.assertEqual(self.reply().status, 503)
        self.assertEqual(before, self.db_path.read_bytes())

    def test_missing_asset_is_explicit_and_never_returns_another_asset(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM objects WHERE object_id=?", (chatgpt_read.NIBE_LEGACY_ID,))
        self.assertEqual(self.reply().status, 404)

    def test_large_record_fails_without_truncated_context(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE objects SET yaml_text=? WHERE object_id=?", ("x" * 70000, chatgpt_read.NIBE_LEGACY_ID))
        reply = self.reply()
        self.assertEqual(reply.status, 503)
        self.assertNotIn("record_yaml", reply.wfile.getvalue().decode())

    def test_revision_changes_when_selected_data_changes(self):
        old = chatgpt_read.nibe_context(self.db_path)["context_revision"]
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE objects SET yaml_text=? WHERE object_id=?", (self.record + "status: changed\n", chatgpt_read.NIBE_LEGACY_ID))
        self.assertNotEqual(old, chatgpt_read.nibe_context(self.db_path)["context_revision"])


if __name__ == "__main__":
    unittest.main()
