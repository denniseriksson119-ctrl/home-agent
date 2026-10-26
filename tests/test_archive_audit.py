"""Read-only archive checks with synthetic files and real SQLite/HTTP routing."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'codex_remote_test/app'))
sys.path.insert(0, str(ROOT / 'home_agent/rootfs/opt/home-agent'))
import archive_audit as audit
import codex_read
import home_agent_mcp as client
import house_context
import server
import source_archive
import yaml


class Reply(codex_read.ReadHandler):
    def __init__(self, service, path, token=''):
        self.service, self.path = service, path
        self.headers = {'Authorization': token}
        self.wfile, self.response_headers = io.BytesIO(), {}
        self.connection = Mock()

    def send_response(self, code):
        self.code = code

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db, self.sources = self.root / 'home.db', self.root / 'sources'
        self.sources.mkdir()
        data = {'homes': [{'id': 'home', 'name': 'Synthetic home', 'assets': [
            {'id': house_context.NIBE_LEGACY_ID, 'name': 'Synthetic pump', 'credentials': 'never-export-fact'}],
            'systems': [{'id': 'heating', 'name': 'Synthetic system'}],
            'documents': [{'id': 'manual-doc', 'name': 'Synthetic manual', 'type': 'user_manual'}]}]}
        with patch.object(server, 'DB_FILE', self.db):
            server.import_database(data, yaml.safe_dump(data))
        with sqlite3.connect(self.db) as db:
            self.ids = {legacy: pid for pid, legacy in db.execute('SELECT permanent_id,legacy_id FROM object_identity')}
        self.body = b'%PDF-synthetic-body-not-report-content'
        self.path = source_archive.destination(self.sources, 'src-01', 'manual.pdf', 'application/pdf', 'user_manual')
        self.path.write_bytes(self.body)
        self.add_source('src-01', self.path, 'manual.pdf')
        with sqlite3.connect(self.db) as db:
            for legacy in ('manual-doc', 'heating', house_context.NIBE_LEGACY_ID):
                db.execute('INSERT INTO source_link(source_id,object_id) VALUES(?,?)', ('src-01', self.ids[legacy]))
        self.service = codex_read.ReadService(self.db, self.sources, self.root / 'read.json', 'local-home-agent')
        self.config = client.ticket_config(self.service.create_ticket())
        self.config_file = self.root / 'client.json'
        self.config_file.write_text(json.dumps(self.config))
        self.config_file.chmod(0o600)

    def add_source(self, sid, path, name='extra.txt', digest=None, custody='local_verified'):
        with sqlite3.connect(self.db) as db:
            db.execute('''INSERT INTO source(source_id,source_type,media_type,original_name,sha256,
                storage_ref,custody_status) VALUES(?,'file','application/pdf',?,?,?,?)''',
                (sid, name, digest or hashlib.sha256(self.body if sid == 'src-01' else self.body + sid.encode()).hexdigest(), str(path), custody))

    def entry(self, ident='src-01'):
        return audit.report(self.db, self.sources, source_id=ident)['entries'][0]

    def transport(self, config, path, limit):
        reply = Reply(self.service, path, 'Bearer ' + config['token'])
        reply.do_GET()
        if reply.code != 200:
            raise client.ReadError('synthetic HTTP error')
        body = reply.wfile.getvalue()
        self.assertLessEqual(len(body), limit)
        return body, reply.response_headers['Content-Type']

    def test_read_only_current_layout_checksum_links_and_unknown_size(self):
        before = self.db.read_bytes(), self.path.read_bytes(), self.path.stat().st_mtime_ns
        result = audit.report(self.db, self.sources)
        entry = result['entries'][0]
        self.assertEqual(entry['relative_path'], 'Documents/Manuals/src-01__manual.pdf')
        self.assertEqual(entry['checksum_check'], 'matches')
        self.assertEqual(entry['size_bytes'], len(self.body))
        self.assertIsNone(entry['expected_size_bytes'])
        self.assertEqual(entry['size_check'], 'unknown_no_recorded_size')
        self.assertEqual(entry['layout_check'], 'current')
        self.assertEqual(entry['status'], 'verified')
        self.assertEqual({x['id'] for x in entry['links']}, set(self.ids[k] for k in ('manual-doc', 'heating', house_context.NIBE_LEGACY_ID)))
        body, status = audit.page(self.db, self.sources)
        self.assertEqual(status, 200)
        self.assertIn(b'Referensstorlek saknas', body)
        for secret in (str(self.root), 'storage_ref', 'never-export-fact', self.body.decode()):
            self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(before, (self.db.read_bytes(), self.path.read_bytes(), self.path.stat().st_mtime_ns))

    def test_missing_checksum_mismatch_and_custody_are_not_verified(self):
        self.path.write_bytes(b'altered')
        self.assertEqual(self.entry()['checksum_check'], 'mismatch')
        self.assertEqual(self.entry()['status'], 'not_verified')
        self.path.unlink()
        self.assertEqual(self.entry()['file_check'], 'missing')
        self.path.write_bytes(self.body)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET custody_status='pending' WHERE source_id='src-01'")
        self.assertEqual(self.entry()['custody_check'], 'not_verified')
        self.assertEqual(self.entry()['status'], 'not_verified')

    def test_symlink_parent_symlink_fifo_and_outside_never_read(self):
        outside = self.root / 'private-secret'
        outside.write_bytes(b'not allowed')
        for variant in ('file-symlink', 'parent-symlink', 'outside', 'fifo'):
            if variant == 'file-symlink':
                storage = self.sources / 'linked'
                storage.symlink_to(outside)
            elif variant == 'parent-symlink':
                parent = self.sources / 'linked-parent'
                parent.symlink_to(self.root, target_is_directory=True)
                storage = parent / outside.name
            elif variant == 'fifo':
                storage = self.sources / 'fifo'
                os.mkfifo(storage)
            else:
                storage = outside
            self.add_source(variant, storage)
            with patch.object(audit.os, 'read', side_effect=AssertionError('must not read unsafe file')):
                entry = self.entry(variant)
            self.assertNotEqual(entry['file_check'], 'regular_file')
            self.assertEqual(entry['checksum_check'], 'not_checked')
            if variant == 'outside':
                self.assertIsNone(entry['relative_path'])
                self.assertNotIn(str(outside), json.dumps(entry))

    def test_legacy_layout_is_distinct_from_deviation(self):
        flat = self.sources / 'legacy'
        flat.write_bytes(self.body)
        self.add_source('legacy', flat)
        entry = self.entry('legacy')
        self.assertEqual(entry['layout_check'], 'legacy_preserved')
        self.assertEqual(entry['name_check'], 'legacy_preserved')
        # Unlinked is separately reported even when the bytes are intact.
        self.assertEqual(entry['links_check'], 'unlinked')
        wrong = self.sources / 'wrong.pdf'
        wrong.write_bytes(self.body)
        self.add_source('wrong', wrong)
        self.assertEqual(self.entry('wrong')['layout_check'], 'deviation')

    def test_dangling_links_are_explicit(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO source_link(source_id,object_id) VALUES('src-01','missing-object')")
        entry = self.entry()
        self.assertEqual(entry['links_check'], 'dangling')
        self.assertEqual(entry['status'], 'deviation')

    def test_pagination_and_focus_do_not_skip_registered_sources(self):
        for n in range(2, 14):
            path = self.sources / ('src-%02d' % n)
            path.write_bytes(self.body)
            self.add_source('src-%02d' % n, path)
        first = audit.report(self.db, self.sources)
        second = audit.report(self.db, self.sources, after=first['next_after'])
        self.assertEqual(first['total_sources'], 13)
        self.assertEqual(len(first['entries']), 10)
        self.assertEqual(len(second['entries']), 3)
        self.assertIsNone(second['next_after'])
        self.assertEqual(first['revision'], second['revision'])
        self.assertEqual(len({e['source_id'] for e in first['entries'] + second['entries']}), 13)

    def test_time_size_and_changed_during_read_are_not_success(self):
        with patch.object(audit, 'PAGE_SECONDS', 0):
            self.assertEqual(self.entry()['checksum_check'], 'not_checked_time_limit')
        with patch.object(audit, 'MAX_BYTES', 1):
            self.assertEqual(self.entry()['checksum_check'], 'not_checked_size_limit')
        original_read = os.read
        changed = []
        def read(fd, size):
            result = original_read(fd, size)
            if not changed:
                changed.append(True)
                self.path.write_bytes(b'new bytes')
            return result
        with patch.object(audit.os, 'read', side_effect=read):
            self.assertEqual(self.entry()['checksum_check'], 'changed_during_check')

    def test_parameters_and_absent_database_fail_without_creation(self):
        for query in ('path=/private', 'source_id=../private', 'source_id=one&after=two',
                      'source_id=a&source_id=b', 'after='):
            with self.assertRaises(ValueError):
                audit.parameters(query)
        absent = self.root / 'does-not-exist.db'
        with self.assertRaises(audit.AuditError):
            audit.report(absent, self.sources)
        self.assertFalse(absent.exists())

    def test_invalid_checksum_and_metadata_limits_are_explicit(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET sha256='invalid' WHERE source_id='src-01'")
        entry = self.entry()
        self.assertEqual(entry['checksum_check'], 'invalid_recorded_checksum')
        self.assertIsNone(entry['expected_sha256'])
        with patch.object(audit, 'MAX_SOURCES', 0):
            with self.assertRaises(audit.AuditError):
                audit.report(self.db, self.sources)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET storage_ref=? WHERE source_id='src-01'", ('x' * 5000,))
        with patch.object(audit, 'inspect_file', side_effect=AssertionError('must not inspect oversized metadata')):
            with self.assertRaises(audit.AuditError):
                audit.report(self.db, self.sources)

    def test_separate_permission_and_revocation_keep_original_scope(self):
        token = 'Bearer ' + self.config['token']
        reply = Reply(self.service, '/v1/archive-audit', token)
        reply.do_GET()
        self.assertEqual(reply.code, 403)
        self.service.set_archive(True)
        reply = Reply(self.service, '/v1/archive-audit', token)
        reply.do_GET()
        self.assertEqual(reply.code, 200)
        inbox = self.sources / 'inbox'
        inbox.write_bytes(self.body)
        self.add_source('inbox', inbox)
        reply = Reply(self.service, '/v1/source/inbox', token)
        reply.do_GET()
        self.assertEqual(reply.code, 404)
        self.assertTrue(codex_read.ReadService(self.db, self.sources, self.service.state_path, 'local-home-agent').archive_enabled())
        self.service.set_archive(False)
        reply = Reply(self.service, '/v1/archive-audit', token)
        reply.do_GET()
        self.assertEqual(reply.code, 403)
        self.service.set_archive(True)
        self.service.create_ticket()
        self.assertFalse(self.service.archive_enabled())
        self.service.revoke()
        reply = Reply(self.service, '/v1/archive-audit', token)
        reply.do_GET()
        self.assertEqual(reply.code, 401)

    def test_mcp_validation_and_fixed_route(self):
        self.service.set_archive(True)
        with patch.object(client, 'fetch', side_effect=self.transport):
            report = client.call('home_agent_archive_audit', {'source_id': 'src-01'}, self.config_file)
            self.assertEqual(report['entries'][0]['source_id'], 'src-01')
            with self.assertRaises(client.ReadError):
                client.call('home_agent_archive_audit', {'path': '/private'}, self.config_file)
            with self.assertRaises(client.ReadError):
                client.call('home_agent_archive_audit', {'source_id': 'x', 'after': 'y'}, self.config_file)
        for field, value in [('relative_path', '/private/secret'), ('relative_path', '../secret'), ('storage_ref', 'secret')]:
            bad = copy.deepcopy(report)
            bad['entries'][0][field] = value
            with patch.object(client, 'fetch', return_value=(json.dumps(bad).encode(), 'application/json')):
                with self.assertRaises(client.ReadError):
                    client.archive_report(self.config, {})

    def test_report_route_read_only_and_single_reader_slot(self):
        self.service.set_archive(True)
        token = 'Bearer ' + self.config['token']
        for path in ('/v1/archive-audit?path=/private', '/v1/archive-audit?source_id=../private'):
            reply = Reply(self.service, path, token)
            reply.do_GET()
            self.assertEqual(reply.code, 503)
        self.service.slot.acquire()
        try:
            reply = Reply(self.service, '/v1/archive-audit', token)
            reply.do_GET()
            self.assertEqual(reply.code, 503)
        finally:
            self.service.slot.release()
        reply = Reply(self.service, '/v1/archive-audit', token)
        reply.do_POST()
        self.assertEqual(reply.code, 405)

    def test_archive_consent_form_requires_csrf_and_same_origin(self):
        for csrf, origin, expected in [('wrong', 'null', 400),
                                       (self.service.csrf, 'http://foreign.invalid', 400),
                                       (self.service.csrf, 'null', 200)]:
            body = urlencode({'csrf': csrf, 'action': 'archive_on'}).encode()
            reply = Reply(self.service, '/codex/connect')
            reply.rfile = io.BytesIO(body)
            reply.headers = {'Host': 'local-home-agent', 'Origin': origin, 'Content-Length': str(len(body))}
            codex_read.handle_page(reply, self.service, post=True)
            self.assertEqual(reply.code, expected)
            self.assertEqual(self.service.archive_enabled(), expected == 200)


if __name__ == '__main__':
    unittest.main()
