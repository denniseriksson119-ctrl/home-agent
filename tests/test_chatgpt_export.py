"""Synthetic end-to-end publication tests using SQLite and a fake Drive API."""
import copy
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

APP = Path(__file__).resolve().parents[1] / "home_agent/rootfs/opt/home-agent"
sys.path.insert(0, str(APP))
import chatgpt_export as export
import drive_publish
import house_context as context
import server
import ui


class FakeDrive:
    """Interpret the adapter's actual request metadata and multipart bytes."""
    def __init__(self):
        self.files = {}
        self.bodies = {}
        self.operations = []
        self.next_id = 0
        self.fail_key = None
        self.lose_reply_key = None
        self.sessions = {}

    def request(self, client, path, method="GET", data=None, content_type="application/json", upload=False, start=False, extra_headers=None):
        parsed = urlparse(path)
        params = parse_qs(parsed.query)
        if start:
            self.sessions["session"] = (json.loads(data), extra_headers, method, parsed.path)
            return {"session_path": "files?upload_id=session"}
        if parsed.path == "files/generateIds":
            self.next_id += 1
            return {"ids": ["file_" + str(self.next_id)]}
        if method == "GET" and parsed.path == "files":
            import re
            q = params["q"][0]
            instance, key = re.findall(r"value='([^']+)'", q)
            parent = re.search(r"'([^']+)' in parents", q)
            return {"files": [copy.deepcopy(item) for item in self.files.values()
                              if not item.get("trashed") and item["appProperties"] == {"ha_instance": instance, "ha_key": key}
                              and (not parent or item.get("parents") == [parent[1]])]}
        body = None
        if method == "PUT":
            meta, headers, method, original_path = self.sessions[params["upload_id"][0]]
            self.assert_upload_length(headers, data)
            parsed = urlparse(original_path)
            body = data
        elif upload:
            boundary = content_type.split("boundary=")[1].encode()
            parts = data.split(b"--" + boundary)
            meta = json.loads(parts[1].split(b"\r\n\r\n", 1)[1][:-2])
            body = parts[2].split(b"\r\n\r\n", 1)[1][:-2]
        else:
            meta = json.loads(data)
        key = meta["appProperties"]["ha_key"]
        if any(len((k + v).encode()) > 124 for k, v in meta["appProperties"].items()):
            raise AssertionError("Drive appProperties exceed the documented 124-byte limit")
        if key == self.fail_key:
            raise drive_publish.PublishError("Synthetic failure")
        if method == "POST":
            fid = meta["id"]
            if fid in self.files:
                raise drive_publish.PublishError("Synthetic duplicate ID")
            self.files[fid] = meta
        else:
            fid = parsed.path.split("/")[1]
            self.files[fid].update(meta)
        if body is not None:
            self.bodies[fid] = body
            self.files[fid]["md5Checksum"] = hashlib.md5(body, usedforsecurity=False).hexdigest()
        self.operations.append((method, key, fid))
        if key == self.lose_reply_key:
            self.lose_reply_key = None
            raise drive_publish.PublishError("Synthetic reply lost AFTER remote commit")
        return copy.deepcopy(self.files[fid])

    @staticmethod
    def assert_upload_length(headers, body):
        if headers["X-Upload-Content-Length"] != str(len(body)):
            raise AssertionError("Wrong upload length")

    def body(self, key):
        fid = next(fid for fid, value in self.files.items() if value["appProperties"]["ha_key"] == key)
        return self.bodies[fid]


class ExportTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(export, 'PAUSED_FOR_CODEX', False)
        guard.start()
        self.addCleanup(guard.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / "house.db"
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.config = self.root / "oauth.json"
        self.state = self.root / "state.json"
        export.save_state(self.config, {"purpose": export.PURPOSE, "enabled": True,
            "client_id": "synthetic", "client_secret": "never-export-this",
            "refresh_token": "never-export-this-either", "expected_email": "test@example.invalid"})
        self.home = {"schema": "home_agent", "schema_version": "synthetic", "homes": [{
            "id": "home", "name": "Synthetic home", "private": "unrelated-private-field",
            "floors": [{"id": "floor", "name": "Floor", "rooms": [{"id": "room", "name": "Utility",
                "asset_refs": [context.NIBE_LEGACY_ID]}]}],
            "assets": [{"id": context.NIBE_LEGACY_ID, "name": "Synthetic NIBE", "model": "S1255",
                        "notes": [{"text": "Synthetic observation"}], "credentials": "do-not-export"},
                       {"id": "other", "name": "Other asset", "notes": "unrelated-private-note"}],
            "service_history": [{"id": "service", "name": "Service", "asset_ref": context.NIBE_LEGACY_ID,
                                  "date": "2026-01-01", "summary": "Synthetic service"}],
            "maintenance": [{"id": "maintenance", "name": "Check", "asset_refs": [context.NIBE_LEGACY_ID],
                             "next_due": "2027-01-01"}]}]}
        with patch.object(server, "DB_FILE", self.db):
            server.import_database(self.home, "synthetic snapshot")
        with sqlite3.connect(self.db) as db:
            self.asset_id = db.execute("SELECT permanent_id FROM object_identity WHERE legacy_id=?", (context.NIBE_LEGACY_ID,)).fetchone()[0]
            for sid, body in (("linked", b"synthetic original PDF bytes"), ("unlinked", b"private inbox file")):
                path = self.sources / sid
                path.write_bytes(body)
                db.execute("INSERT INTO source(source_id,source_type,media_type,original_name,sha256,storage_ref,custody_status) VALUES(?, 'file','application/pdf',?,?,?,'local_verified')",
                           (sid, sid + ".pdf", hashlib.sha256(body).hexdigest(), str(path)))
            db.execute("INSERT INTO source_link(source_id,object_id) VALUES('linked',?)", (self.asset_id,))
        self.fake = FakeDrive()
        fake = self.fake
        self.addCleanup(patch.stopall)
        patch.object(drive_publish.DrivePublisher, "request", new=lambda client, *a, **k: fake.request(client, *a, **k)).start()
        self.auth = patch.object(export.drive_auth, "access_token", return_value="synthetic-token").start()

    def publish(self):
        return export.publish_once(self.db, self.sources, self.config, self.state)

    def test_read_publication_preserves_database_and_only_exports_selected_scope(self):
        before = self.db.read_bytes()
        self.assertTrue(self.publish())
        self.assertEqual(self.db.read_bytes(), before)
        state = export.private_json(self.state)
        index = self.fake.body("index").decode()
        nibe = self.fake.body("nibe-" + state["revision"]).decode()
        self.assertIn("Other asset", index)  # navigation only
        self.assertIn("Synthetic service", nibe)
        self.assertIn("2027-01-01", nibe)
        self.assertIn(self.asset_id, nibe)
        self.assertIn("Originalkällor", nibe)
        all_bytes = b"".join(self.fake.bodies.values()).decode()
        for forbidden in ("unrelated-private-field", "unrelated-private-note", "do-not-export", "private inbox file",
                          "never-export-this", "synthetic-token", str(self.root), "asset_ref"):
            self.assertNotIn(forbidden, all_bytes)
        self.assertEqual(self.fake.operations[-1][1], "index")
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.assertIn("index_url", export.status(self.config, self.state))

    def test_retry_and_restart_reuse_immutable_files_and_only_refresh_index(self):
        self.publish()
        count = len(self.fake.files)
        self.fake.operations.clear()
        self.publish()
        self.assertEqual(len(self.fake.files), count)
        self.assertEqual([(method, key) for method, key, _ in self.fake.operations], [("PATCH", "index")])

    def test_ambiguous_create_retries_without_duplicates(self):
        self.fake.lose_reply_key = "root"
        with self.assertRaises(drive_publish.PublishError):
            self.publish()
        reserved = export.private_json(self.state)["ids"]["root"]
        self.publish()
        roots = [f for f in self.fake.files.values() if f["appProperties"]["ha_key"] == "root"]
        self.assertEqual([f["id"] for f in roots], [reserved])

    def test_failure_keeps_old_index_and_timestamp_then_retry_publishes_new_revision(self):
        self.publish()
        before = self.fake.body("index")
        previous = export.private_json(self.state)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE objects SET yaml_text=yaml_text || '\nstatus: changed\n' WHERE object_id=?", (context.NIBE_LEGACY_ID,))
        data, _ = context.read_context(self.db)
        revision = hashlib.sha256(context.canonical(data)).hexdigest()
        self.fake.fail_key = "nibe-" + revision
        with self.assertRaises(drive_publish.PublishError):
            self.publish()
        self.assertEqual(self.fake.body("index"), before)
        failed = export.private_json(self.state)
        self.assertEqual(failed["last_success"], previous["last_success"])
        self.assertEqual(failed["revision"], previous["revision"])
        self.assertTrue(failed["error"])
        self.fake.fail_key = None
        self.publish()
        self.assertEqual(export.private_json(self.state)["revision"], revision)

    def test_missing_changed_outside_or_symlink_original_blocks_index(self):
        path = self.sources / "linked"
        path.write_bytes(b"changed")
        with self.assertRaises(context.ContextError):
            self.publish()
        path.unlink()
        with self.assertRaises(context.ContextError):
            self.publish()
        outside = self.root / "elsewhere"
        outside.write_bytes(b"synthetic original PDF bytes")
        path.symlink_to(outside)
        with self.assertRaises(context.ContextError):
            self.publish()
        path.unlink()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET storage_ref=? WHERE source_id='linked'", (str(outside),))
        with self.assertRaises(context.ContextError):
            self.publish()
        self.assertFalse(any(key == "index" for _, key, _ in self.fake.operations))

    def test_size_limit_and_invalid_custody_stop_before_index(self):
        with patch.object(context, "MAX_FILE", 4):
            with self.assertRaises(context.ContextError):
                self.publish()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET custody_status='pending' WHERE source_id='linked'")
        with self.assertRaises(context.ContextError):
            self.publish()
        self.assertFalse(any(key == "index" for _, key, _ in self.fake.operations))

    def test_missing_nibe_and_no_links_are_explicit(self):
        with sqlite3.connect(self.db) as db:
            db.execute("DELETE FROM source_link")
        self.publish()
        state = export.private_json(self.state)
        self.assertIn("Inga originalfiler", self.fake.body("nibe-" + state["revision"]).decode())
        with sqlite3.connect(self.db) as db:
            db.execute("DELETE FROM objects WHERE object_id=?", (context.NIBE_LEGACY_ID,))
            db.execute("DELETE FROM object_relation WHERE source_id=? OR target_id=?", (self.asset_id, self.asset_id))
        self.publish()
        state = export.private_json(self.state)
        self.assertIn("NIBE-objektet finns inte", self.fake.body("nibe-" + state["revision"]).decode())

    def test_missing_database_wrong_schema_and_limits_never_initialize_or_truncate(self):
        missing = self.root / "absent.db"
        with self.assertRaises(context.ContextError):
            context.read_context(missing)
        self.assertFalse(missing.exists())
        with patch.object(context, "MAX_OBJECTS", 1):
            with self.assertRaises(context.ContextError):
                self.publish()
        with patch.object(context, "MAX_TEXT", 10):
            with self.assertRaises(context.ContextError):
                self.publish()
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE schema_meta SET version=6")
        before = self.db.read_bytes()
        with self.assertRaises(context.ContextError):
            self.publish()
        self.assertEqual(self.db.read_bytes(), before)
        self.assertFalse(self.fake.operations)

    def test_disabled_malformed_or_permissive_configuration_never_authorizes(self):
        self.config.unlink()
        self.assertFalse(self.publish())
        export.save_state(self.config, {"purpose": "other", "enabled": True})
        self.assertFalse(self.publish())
        export.save_state(self.config, {"purpose": export.PURPOSE, "enabled": False})
        self.assertFalse(self.publish())
        self.config.chmod(0o644)
        with self.assertRaises(drive_publish.PublishError):
            self.publish()
        self.config.unlink()
        self.config.symlink_to(self.db)
        with self.assertRaises(drive_publish.PublishError):
            self.publish()
        self.auth.assert_not_called()

    def test_changed_account_stops_before_drive_and_status_hides_runtime_fields(self):
        self.publish()
        state = export.private_json(self.state)
        state["index_url"] = "javascript:alert(1)"
        export.save_state(self.state, state)
        status = export.status(self.config, self.state)
        self.assertNotIn("index_url", status)
        self.assertNotIn("account", status)
        self.assertNotIn("ids", status)
        config = export.private_json(self.config)
        config["expected_email"] = "other@example.invalid"
        export.save_state(self.config, config)
        self.auth.reset_mock()
        with self.assertRaises(drive_publish.PublishError):
            self.publish()
        self.auth.assert_not_called()

    def test_remote_tampering_is_not_silently_overwritten(self):
        self.publish()
        nibe = next(item for item in self.fake.files.values() if item["appProperties"]["ha_key"].startswith("nibe-"))
        nibe["md5Checksum"] = "tampered"
        before = self.fake.body("index")
        with self.assertRaises(drive_publish.PublishError):
            self.publish()
        self.assertEqual(self.fake.body("index"), before)

    def test_large_original_uses_resumable_upload_and_preserves_exact_bytes(self):
        body = b"pdf" * (2 * 1024 * 1024)
        (self.sources / "linked").write_bytes(body)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET sha256=? WHERE source_id='linked'", (hashlib.sha256(body).hexdigest(),))
        self.publish()
        self.assertTrue(self.fake.sessions)
        original_key = next(key for _, key, _ in self.fake.operations if key.startswith("source-"))
        self.assertEqual(self.fake.body(original_key), body)

    def test_user_interface_escapes_status_and_background_failures_are_isolated(self):
        page = ui.more_page({"enabled": True, "last_success": "<script>", "error": "<bad>"}).decode()
        self.assertNotIn("<bad>", page)
        self.assertIn("&lt;script&gt;", page)
        stop = threading.Event()
        def fail(*args):
            stop.set()
            raise RuntimeError("secret-provider-body")
        with patch.object(export, "publish_once", side_effect=fail), patch("builtins.print") as output:
            export.run(self.db, self.sources, stop)
        self.assertNotIn("secret-provider-body", str(output.call_args))


class TransportTests(unittest.TestCase):
    def test_http_transport_uses_fixed_origin_bounded_json_and_safe_errors(self):
        client = drive_publish.DrivePublisher("private-token", "a" * 32, {}, lambda: None)
        client.opener = Mock()
        response = io.BytesIO(b'{"files":[]}')
        client.opener.open.return_value = response
        self.assertEqual(client.request("files?fields=id"), {"files": []})
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://www.googleapis.com/drive/v3/files?fields=id")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-token")
        response = io.BytesIO(b"")
        response.headers = {"Location": "https://www.googleapis.com/upload/drive/v3/files?upload_id=session"}
        client.opener.open.return_value = response
        self.assertEqual(client.request("files", "POST", b"{}", upload=True, start=True), {"session_path": "files?upload_id=session"})
        client.opener.open.return_value = io.BytesIO(b"x" * (1024 * 1024 + 1))
        with self.assertRaises(drive_publish.PublishError):
            client.request("files")
        client.opener.open.side_effect = HTTPError(request.full_url, 403, "secret-provider-body", {}, None)
        with self.assertRaises(drive_publish.PublishError) as error:
            client.request("files")
        self.assertIn("403", str(error.exception))
        self.assertNotIn("secret", str(error.exception))

    def test_redirect_is_disabled_and_invalid_identifiers_fail(self):
        self.assertIsNone(drive_publish.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://other.invalid"))
        for value in (None, "../../other", "id?alt=media", "https://other.invalid"):
            with self.assertRaises(drive_publish.PublishError):
                drive_publish.file_url(value)
        for url in ("https://other.invalid/upload/drive/v3/files?upload_id=x",
                    "https://www.googleapis.com/other?upload_id=x", "http://www.googleapis.com/upload/drive/v3/files?upload_id=x"):
            with self.assertRaises(drive_publish.PublishError):
                drive_publish.session_path(url)
        self.assertEqual(drive_publish.session_path("https://www.googleapis.com/upload/drive/v3/files?upload_id=x"), "files?upload_id=x")


if __name__ == "__main__":
    unittest.main()
