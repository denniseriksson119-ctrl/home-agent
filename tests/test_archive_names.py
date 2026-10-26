"""Synthetic owner-reviewed archive names and both filesystem/SQLite crash boundaries."""
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'home_agent/rootfs/opt/home-agent'))
import archive_names as names
import archive_names_ui
import archive_audit
import source_archive
import source_migration
import server
import test_archive_audit as fixtures


class NamingTests(unittest.TestCase):
    add_source = fixtures.ArchiveTests.add_source

    def setUp(self):
        fixtures.ArchiveTests.setUp(self)
        self.directory = self.root / 'name-plans'
        self.controller = names.Controller()

    def plan(self, when='2026-09-14', description='Synthetic manual', unknown=False):
        return names.build_plan(self.db, self.sources, [dict(source_id='src-01', date=when,
                    description=description, unknown_date=unknown)])

    def storage(self):
        with sqlite3.connect(self.db) as db:
            return db.execute("SELECT storage_ref FROM source WHERE source_id='src-01'").fetchone()[0]

    def apply(self, plan):
        return names.apply_item(self.db, self.sources, plan['id'], plan['items'][0])

    def counts(self):
        with sqlite3.connect(self.db) as db:
            return [db.execute('SELECT count(*) FROM ' + t).fetchone()[0] for t in ('source', 'source_link', 'change_log')]

    def test_preview_changes_no_domain_data_or_files_and_requires_dates(self):
        before = self.db.read_bytes(), self.path.read_bytes(), sorted(str(x) for x in self.sources.rglob('*'))
        plan = self.plan()
        self.assertRegex(plan['items'][0]['to_path'], r'^Documents/Manuals/2026-09-14_synthetic-manual__src-[a-f0-9]{10}\.pdf$')
        self.assertEqual(before, (self.db.read_bytes(), self.path.read_bytes(), sorted(str(x) for x in self.sources.rglob('*'))))
        with self.assertRaises(ValueError):
            self.plan(when='')
        with self.assertRaises(ValueError):
            self.plan(when='2026-02-30')
        with self.assertRaises(ValueError):
            self.plan(when='2026-09-14', unknown=True)
        with self.assertRaises(ValueError):
            self.plan(description='20260914')

    def test_rename_preserves_identity_original_metadata_links_and_bytes(self):
        plan = self.plan()
        with sqlite3.connect(self.db) as db:
            before = db.execute('SELECT source_id,original_name,sha256,captured_at FROM source').fetchall()
            links = db.execute('SELECT * FROM source_link ORDER BY object_id').fetchall()
        self.assertEqual(self.apply(plan), 'complete')
        target = Path(self.storage())
        self.assertFalse(self.path.exists())
        self.assertEqual(target.read_bytes(), self.body)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(before, db.execute('SELECT source_id,original_name,sha256,captured_at FROM source').fetchall())
            self.assertEqual(links, db.execute('SELECT * FROM source_link ORDER BY object_id').fetchall())
            audit = json.loads(db.execute("SELECT new_value FROM change_log WHERE field_name='archive_name'").fetchone()[0])
        self.assertEqual(audit['from'], plan['items'][0]['from_path'])
        self.assertEqual(audit['to'], plan['items'][0]['to_path'])
        report = archive_audit.report(self.db, self.sources)['entries'][0]
        self.assertEqual(report['name_check'], 'architectural')
        self.assertEqual(report['checksum_check'], 'matches')
        self.assertEqual(report['status'], 'verified')
        # A fresh plan for the identical destination does not create another audit.
        again = self.plan()
        self.assertEqual(self.apply(again), 'unchanged')
        self.assertEqual(self.counts(), [1, 3, 1])

    def test_image_date_proposal_is_not_capture_fact_and_unknown_is_explicit(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET original_name='20260914_213851.jpg',media_type='image/jpeg' WHERE source_id='src-01'")
        with sqlite3.connect(self.db) as db:
            record = names.metadata(db, 'src-01')
        self.assertEqual(names.suggestion(record)['date_basis'], 'filename_candidate')
        plan = self.plan()
        self.assertTrue(plan['items'][0]['to_path'].startswith('Photos/2026/09/'))
        self.assertEqual(plan['items'][0]['date_basis'], 'filename_candidate')
        self.assertEqual(self.apply(plan), 'complete')
        self.assertEqual(archive_audit.report(self.db, self.sources)['entries'][0]['name_check'], 'architectural')
        unknown = self.plan(when='', unknown=True)
        self.assertTrue(unknown['items'][0]['to_path'].startswith('Photos/Undated/undated_'))
        self.assertEqual(unknown['items'][0]['date_basis'], 'unknown_approved')
        self.assertEqual(self.apply(unknown), 'complete')
        self.assertEqual(archive_audit.report(self.db, self.sources)['entries'][0]['name_check'], 'architectural_undated')

    def test_collision_never_replaces_or_removes_existing_target(self):
        plan = self.plan()
        target = self.sources / plan['items'][0]['to_path']
        target.write_bytes(b'keep this unrelated file')
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertEqual(target.read_bytes(), b'keep this unrelated file')
        self.assertEqual(Path(self.storage()), self.path)
        self.assertEqual(self.path.read_bytes(), self.body)
        self.assertEqual(self.counts(), [1, 3, 0])

    def test_failure_before_commit_rolls_back_reference_and_only_own_link(self):
        plan = self.plan()
        target = self.sources / plan['items'][0]['to_path']
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TRIGGER reject_audit BEFORE INSERT ON change_log BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.Error):
            self.apply(plan)
        self.assertFalse(target.exists())
        self.assertEqual(Path(self.storage()), self.path)
        self.assertEqual(self.path.read_bytes(), self.body)
        self.assertEqual(self.counts(), [1, 3, 0])

    def test_replay_after_promotion_before_database_commit(self):
        plan = self.plan()
        target = self.sources / plan['items'][0]['to_path']
        os.link(self.path, target)
        self.assertEqual(self.apply(plan), 'complete')
        self.assertEqual(Path(self.storage()), target)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.counts(), [1, 3, 1])

    def test_replay_after_commit_before_old_alias_cleanup(self):
        plan = self.plan()
        original_unlink = os.unlink
        def fail_cleanup(path, *args, **kwargs):
            if path == self.path.name:
                raise OSError('synthetic process exit at cleanup')
            return original_unlink(path, *args, **kwargs)
        with patch.object(names.os, 'unlink', side_effect=fail_cleanup):
            with self.assertRaises(OSError):
                self.apply(plan)
        target = self.sources / plan['items'][0]['to_path']
        self.assertEqual(Path(self.storage()), target)
        self.assertTrue(self.path.exists())
        self.assertTrue(target.exists())
        self.assertEqual(self.apply(plan), 'complete')
        self.assertFalse(self.path.exists())
        self.assertEqual(self.counts(), [1, 3, 1])

    def test_changed_file_or_stale_metadata_stops_without_mutation(self):
        plan = self.plan()
        self.path.write_bytes(b'corrupt source')
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertEqual(Path(self.storage()), self.path)
        self.path.write_bytes(self.body)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE objects SET name='Changed title' WHERE object_id='manual-doc'")
        with self.assertRaises(ValueError):
            self.apply(plan)
        self.assertEqual(self.counts(), [1, 3, 0])

    def test_symlink_destination_and_original_never_followed(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET media_type='image/jpeg' WHERE source_id='src-01'")
        plan = self.plan()
        outside = self.root / 'outside'
        outside.mkdir()
        (self.sources / 'Photos').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            self.apply(plan)
        self.assertFalse(list(outside.iterdir()))
        self.path.unlink()
        secret = self.root / 'do-not-read'
        secret.write_bytes(self.body)
        self.path.symlink_to(secret)
        with self.assertRaises(OSError):
            self.apply(plan)
        self.assertEqual(secret.read_bytes(), self.body)

    def test_controller_is_explicit_resumable_and_creates_checkpoint(self):
        plan = self.plan()
        source_migration.save_plan(self.directory, plan)
        slot = threading.BoundedSemaphore(1)
        self.assertFalse(names.Controller().running())
        self.controller.start(self.db, self.sources, self.directory, plan['id'], slot)
        self.controller.worker.join(5)
        saved = source_migration.read_plan(self.directory, plan['id'])
        self.assertEqual(saved['items'][0]['status'], 'complete')
        self.assertTrue((self.directory / (plan['id'] + '-before-import.sqlite')).exists())
        restarted = names.Controller()
        restarted.start(self.db, self.sources, self.directory, plan['id'], slot)
        restarted.worker.join(5)
        self.assertEqual(self.counts(), [1, 3, 1])

    def test_unknown_and_ambiguous_description_never_invented(self):
        with sqlite3.connect(self.db) as db:
            record = names.metadata(db, 'src-01')
        record['names'] = []
        self.assertEqual(names.suggestion(record)['description'], '')
        record['names'] = ['one manual', 'another document']
        self.assertEqual(names.suggestion(record)['description'], '')
        self.assertEqual(names.suggestion(record)['date'], '')

    def test_existing_archive_choice_is_not_replaced_by_old_filename_guess(self):
        plan = self.plan(when='2027-01-03', description='Owner reviewed description')
        self.assertEqual(self.apply(plan), 'complete')
        items, _ = names.candidates(self.db, self.sources)
        self.assertEqual(items[0]['date'], '2027-01-03')
        self.assertEqual(items[0]['description'], 'owner-reviewed-description')
        self.assertEqual(items[0]['date_basis'], 'existing_archive_name')

    def test_shared_old_reference_is_preserved_as_cleanup_pending(self):
        with sqlite3.connect(self.db) as db:
            db.execute('''INSERT INTO source(source_id,source_type,media_type,original_name,sha256,storage_ref,custody_status)
                VALUES('other-ref','file','application/pdf','other.pdf',?,?,'local_verified')''',
                (hashlib.sha256(b'other evidence').hexdigest(), str(self.path)))
        self.assertEqual(self.apply(self.plan()), 'cleanup_pending')
        self.assertTrue(self.path.exists())
        self.assertEqual(Path(self.storage()).read_bytes(), self.body)

    def test_same_source_urls_still_open_and_busy_reads_fail_cleanly(self):
        class Reply:
            def __init__(self, path):
                self.path = path
                self.wfile = io.BytesIO()
                self.headers = {}
            def send_response(self, status): self.code = status
            def send_header(self, *args): pass
            def end_headers(self): pass
            def send_error(self, status, *args): self.code = status
        url = '/source/file?object=' + self.ids['manual-doc'] + '&id=src-01'
        before = Reply(url)
        with patch.object(server, 'DB_FILE', self.db), patch.object(server, 'SOURCE_DIR', self.sources), patch.object(server, 'CODEX_READ', self.service):
            server.Handler.do_GET(before)
            self.assertEqual(before.code, 200)
            self.assertEqual(self.apply(self.plan()), 'complete')
            after = Reply(url)
            server.Handler.do_GET(after)
            self.assertEqual(after.code, 200)
            self.assertEqual(after.wfile.getvalue(), before.wfile.getvalue())
            self.service.slot.acquire()
            try:
                busy = Reply(url)
                server.Handler.do_GET(busy)
                self.assertEqual(busy.code, 503)
            finally:
                self.service.slot.release()

    def test_http_preview_then_apply_requires_owner_csrf_and_does_not_auto_run(self):
        class Reply:
            path = '/archive/names'
            def __init__(self, body, csrf):
                self.rfile, self.wfile = io.BytesIO(body), io.BytesIO()
                self.connection = Mock()
                self.headers = {'Content-Length': str(len(body)), 'Host': 'local-home-agent',
                                'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'null'}
                self.sent = {}
            def send_response(self, code): self.code = code
            def send_header(self, key, value): self.sent[key] = value
            def end_headers(self): pass
        fields = dict(action='preview', csrf='wrong', selected='src-01', **{'date_src-01':'2026-09-14', 'description_src-01':'Synthetic manual'})
        before = self.db.read_bytes()
        reply = Reply(urlencode(fields).encode(), 'wrong')
        archive_names_ui.handle(reply, self.controller, self.db, self.sources, self.directory, self.service.slot, post=True)
        self.assertEqual(reply.code, 400)
        self.assertEqual(before, self.db.read_bytes())
        fields['csrf'] = self.controller.csrf
        reply = Reply(urlencode(fields).encode(), fields['csrf'])
        archive_names_ui.handle(reply, self.controller, self.db, self.sources, self.directory, self.service.slot, post=True)
        self.assertEqual(reply.code, 303)
        ident = reply.sent['Location'].split('plan=')[1]
        self.assertEqual(before, self.db.read_bytes())
        self.assertFalse(self.controller.running())
        body = archive_names_ui.page(self.controller, self.db, self.sources, self.directory, 'plan=' + ident)
        self.assertIn(b'Godk', body)
        fields = dict(action='apply', csrf=self.controller.csrf, plan=ident)
        reply = Reply(urlencode(fields).encode(), fields['csrf'])
        archive_names_ui.handle(reply, self.controller, self.db, self.sources, self.directory, self.service.slot, post=True)
        self.assertEqual(reply.code, 303)
        self.controller.worker.join(5)
        self.assertEqual(source_migration.read_plan(self.directory, ident)['items'][0]['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
