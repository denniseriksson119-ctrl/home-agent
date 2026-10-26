"""Synthetic originals only: preview, custody, retry, navigation and HTTP gates."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import zipfile
import importlib.util
from email.message import Message

APP = Path(__file__).resolve().parents[1] / 'home_agent/rootfs/opt/home-agent'
sys.path.insert(0, str(APP))
import server
import source_migration as migration
import source_migration_ui
import source_archive
import source_bundle
import object_resources
import drive_import
import drive_auth
import house_context
import yaml


class Reply:
    def __init__(self, body=b'', headers=None, path='/sources/import'):
        self.path = path
        self.headers = Message()
        for key, value in {'Content-Length': str(len(body)), 'Content-Type': 'application/x-www-form-urlencoded',
                           'Host': 'local.test', **(headers or {})}.items():
            self.headers[key] = value
        self.rfile, self.wfile = io.BytesIO(body), io.BytesIO()
        self.sent = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.sent[key] = value

    def end_headers(self):
        pass

    def send_error(self, status, *args):
        self.status = status


class MigrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / 'home.db'
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        self.plans = self.root / 'plans'
        self.body = b'%PDF-1.4 synthetic original'
        self.file = dict(id='drive_manual', path='Legacy/Homes/Test/Manual.pdf', name='Manual.pdf',
                         mime='application/pdf', size=len(self.body))
        self.data = {'homes': [{'id': 'home', 'name': 'Synthetic home', 'floors': [
            {'id': 'floor', 'rooms': [{'id': 'room', 'name': 'Test room',
                                      'asset_refs': [house_context.NIBE_LEGACY_ID]}]}],
            'systems': [{'id': 'system', 'name': 'Heating'}],
            'assets': [{'id': house_context.NIBE_LEGACY_ID, 'name': 'Synthetic pump'}],
            'documents': [{'id': 'manual', 'name': 'Synthetic manual', 'type': 'user_manual',
                'related_object_refs': ['room', house_context.NIBE_LEGACY_ID, 'system'],
                'source_file': {'drive_path': self.file['path'], 'original_filename': self.file['name']}}]}]}
        with patch.object(server, 'DB_FILE', self.db):
            server.import_database(self.data, yaml.safe_dump(self.data))
        with sqlite3.connect(self.db) as db:
            self.ids = {legacy: pid for pid, legacy in db.execute('SELECT permanent_id,legacy_id FROM object_identity')}
        self.plan = migration.build_plan(self.db, {'files': [self.file]})

    def download(self, *args):
        with tempfile.NamedTemporaryFile(dir=self.sources, delete=False) as stream:
            path = Path(stream.name)
        path.write_bytes(self.body)
        return dict(temporary_path=str(path), sha256=hashlib.sha256(self.body).hexdigest(),
                    size=len(self.body), drive_id=self.file['id'], original_name=self.file['name'],
                    media_type=self.file['mime'])

    def register(self, item=None, downloaded=None):
        return migration.register(self.db, self.sources, downloaded or self.download(),
                                  item or self.plan['items'][0], self.plan['revision'], server.uuid7)

    def count(self, table):
        with sqlite3.connect(self.db) as db:
            return db.execute('SELECT count(*) FROM ' + table).fetchone()[0]

    def test_preview_read_only_and_targets_preserved(self):
        before = self.db.read_bytes()
        plan = migration.build_plan(self.db, {'files': [self.file]})
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(len(plan['items']), 1)
        self.assertEqual({t['id'] for t in plan['items'][0]['targets']},
                         {self.ids[k] for k in ['manual', 'room', 'system', house_context.NIBE_LEGACY_ID]})
        self.assertFalse(plan['unresolved'])

    def test_missing_and_ambiguous_reference_never_guessed(self):
        f = dict(self.file, path='Elsewhere/Manual.pdf')
        plan = migration.build_plan(self.db, {'files': [f]})
        self.assertFalse(plan['items'])
        self.assertEqual(len(plan['unresolved']), 1)
        with self.assertRaises(ValueError):
            migration.build_plan(self.db, {'files': [self.file, self.file]})

    def test_unknown_target_blocks_entire_document(self):
        with sqlite3.connect(self.db) as db:
            doc = copy.deepcopy(self.data['homes'][0]['documents'][0])
            doc['related_object_refs'].append('missing')
            db.execute("UPDATE objects SET yaml_text=? WHERE object_id='manual'", (yaml.safe_dump(doc),))
        plan = migration.build_plan(self.db, {'files': [self.file]})
        self.assertFalse(plan['items'])
        self.assertIn('missing', plan['unresolved'][0]['reason'])

    def test_register_retry_and_multi_object_file_open(self):
        sid = self.register()
        self.assertEqual(self.register(), sid)
        self.assertEqual(self.count('source'), 1)
        self.assertEqual(self.count('source_link'), 4)
        self.assertEqual(self.count('ingest_occurrence'), 1)
        self.assertEqual(self.count('change_log'), 1)
        with sqlite3.connect(self.db) as db:
            path = Path(db.execute('SELECT storage_ref FROM source').fetchone()[0])
        self.assertEqual(path.parent, self.sources / 'Documents/Manuals')
        self.assertEqual(path.read_bytes(), self.body)
        for key in ['room', 'system', 'manual', house_context.NIBE_LEGACY_ID]:
            page, status = object_resources.detail_page(self.db, self.ids[key])
            self.assertEqual(status, 200)
            self.assertIn(sid.encode(), page)
            reply = Reply(path='/source/file?object=' + self.ids[key] + '&id=' + sid)
            with patch.object(server, 'DB_FILE', self.db), patch.object(server, 'SOURCE_DIR', self.sources):
                server.Handler.do_GET(reply)
            self.assertEqual(reply.status, 200)
            self.assertEqual(reply.wfile.getvalue(), self.body)
        _, sources = house_context.read_context(self.db)
        self.assertEqual([s['id'] for s in sources], [sid])

    def test_unlinked_object_cannot_open_original(self):
        sid = self.register()
        reply = Reply(path='/source/file?object=' + self.ids['home'] + '&id=' + sid)
        with patch.object(server, 'DB_FILE', self.db):
            server.Handler.do_GET(reply)
        self.assertEqual(reply.status, 404)

    def test_existing_original_keeps_source_id_and_storage(self):
        sid = self.register()
        with sqlite3.connect(self.db) as db:
            original = db.execute('SELECT storage_ref FROM source').fetchone()[0]
        item = copy.deepcopy(self.plan['items'][0])
        item['file']['id'] = 'another_drive_id'
        downloaded = self.download()
        downloaded['drive_id'] = 'another_drive_id'
        self.assertEqual(self.register(item, downloaded), sid)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT storage_ref FROM source').fetchone()[0], original)
        self.assertEqual(self.count('source'), 1)
        self.assertEqual(self.count('ingest_occurrence'), 2)

    def test_stale_targets_and_changed_remote_bytes_rejected(self):
        self.register()
        new = self.download()
        Path(new['temporary_path']).write_bytes(b'changed original')
        new['sha256'] = hashlib.sha256(b'changed original').hexdigest()
        with self.assertRaises(ValueError):
            self.register(downloaded=new)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE objects SET name='Changed' WHERE object_id='room'")
        with self.assertRaises(ValueError):
            self.register()
        self.assertEqual(self.count('source'), 1)

    def test_corrupt_existing_original_not_overwritten(self):
        self.register()
        with sqlite3.connect(self.db) as db:
            path = Path(db.execute('SELECT storage_ref FROM source').fetchone()[0])
        path.write_bytes(b'corruption')
        with self.assertRaises(ValueError):
            self.register()
        self.assertEqual(path.read_bytes(), b'corruption')

    def test_collision_does_not_delete_existing_file(self):
        target = source_archive.destination(self.sources, 'collision', 'Manual.pdf', 'application/pdf', 'manual')
        target.write_bytes(b'keep me')
        with self.assertRaises(FileExistsError):
            migration.register(self.db, self.sources, self.download(), self.plan['items'][0],
                               self.plan['revision'], lambda: 'collision')
        self.assertEqual(target.read_bytes(), b'keep me')
        self.assertEqual(self.count('source'), 0)

    def test_worker_restart_replay_after_database_commit(self):
        migration.save_plan(self.plans, self.plan)
        self.register()  # simulate lost progress write after a successful commit
        controller = migration.Controller()
        with patch.object(drive_import, 'assert_under_shared_root', return_value=True), \
                patch.object(drive_import, 'download_original', side_effect=self.download):
            controller.start(self.db, self.sources, self.plans, self.plan['id'], ['0'],
                             lambda: ('synthetic-token', 'synthetic-root'), server.uuid7)
            controller.worker.join(5)
        result = migration.read_plan(self.plans, self.plan['id'])
        self.assertEqual(result['items'][0]['status'], 'complete')
        self.assertEqual(self.count('ingest_occurrence'), 1)
        self.assertEqual(self.count('source'), 1)
        self.assertTrue((self.plans / (self.plan['id'] + '-before-import.sqlite')).exists())

    def test_recover_promoted_file_before_database_commit(self):
        item = self.plan['items'][0]
        reserved = server.uuid7()
        target = source_archive.destination(self.sources, reserved, self.file['name'], self.file['mime'], item['kind'])
        target.write_bytes(self.body)  # process died after file promotion, before SQLite commit
        sid = migration.register(self.db, self.sources, self.download(), item,
                                 self.plan['revision'], server.uuid7, reserved_id=reserved)
        self.assertEqual(sid, reserved)
        self.assertEqual(self.count('source'), 1)
        self.assertEqual(len(list(target.parent.glob('*'))), 1)

    def test_failed_auth_durable_error_and_no_house_writes(self):
        migration.save_plan(self.plans, self.plan)
        controller = migration.Controller()
        def credentials():
            raise drive_auth.DriveAuthError('synthetic-secret-must-not-escape')
        controller.run(self.db, self.sources, self.plans, self.plan['id'], {'0'}, credentials, server.uuid7)
        result = migration.read_plan(self.plans, self.plan['id'])
        self.assertEqual(result['items'][0]['status'], 'error')
        self.assertNotIn('synthetic-secret', json.dumps(result))
        self.assertEqual(self.count('source'), 0)

    def bundle(self, digest=None):
        f = dict(self.file, sha256=digest or hashlib.sha256(self.body).hexdigest())
        bundle = self.root / 'originals.zip'
        with zipfile.ZipFile(bundle, 'w') as archive:
            archive.writestr('manifest.json', json.dumps({'files': [f]}))
            archive.writestr('originals/' + f['id'], self.body)
        return bundle

    def test_bundle_without_drive_credentials_and_checksum_failure(self):
        bundle = self.bundle()
        plan = migration.build_plan(self.db, source_bundle.inventory(bundle))
        plan['bundle'] = True
        migration.save_plan(self.plans, plan)
        (self.plans / (plan['id'] + '.zip')).write_bytes(bundle.read_bytes())
        migration.Controller().run(self.db, self.sources, self.plans, plan['id'], {'0'},
                                   lambda: self.fail('must not request OAuth'), server.uuid7)
        self.assertEqual(migration.read_plan(self.plans, plan['id'])['items'][0]['status'], 'complete')
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT channel FROM ingest_occurrence').fetchone()[0], 'legacy_bundle_migration')
        bad = self.bundle('0' * 64)
        bad_plan = migration.build_plan(self.db, source_bundle.inventory(bad))
        with self.assertRaises(ValueError):
            source_bundle.download(bad, bad_plan['items'][0], self.sources)
        self.assertFalse(list(self.sources.glob('.bundle-*')))

    def test_bundle_rejects_unexpected_paths(self):
        bundle = self.bundle()
        with zipfile.ZipFile(bundle, 'a') as archive:
            archive.writestr('../../outside', 'never extracted')
        with self.assertRaises(ValueError):
            source_bundle.inventory(bundle)

    def test_http_csrf_and_origin_gate(self):
        migration.save_plan(self.plans, self.plan)
        controller = migration.Controller()
        for csrf, origin, expected in [('wrong', 'http://local.test', 400),
                                       (controller.csrf, 'https://foreign.test', 400),
                                       (controller.csrf, 'null', 303)]:
            body = urlencode({'csrf': csrf, 'action': 'start', 'plan': self.plan['id'], 'selected': '0'}).encode()
            reply = Reply(body, {'Origin': origin})
            with patch.object(controller, 'start') as start:
                source_migration_ui.handle(reply, controller, self.db, self.sources,
                                           self.plans, lambda: None, server.uuid7, post=True)
            self.assertEqual(reply.status, expected)
            self.assertEqual(start.called, expected == 303)

    def test_room_and_asset_navigation(self):
        self.register()
        with patch.object(server, 'DB_FILE', self.db):
            page = server.room_page(self.data, 'room')
        self.assertIn(b'/object?id=', page)
        self.assertIn(b'/source/file?object=', page)
        page, _ = object_resources.detail_page(self.db, self.ids['system'])
        self.assertIn(self.ids['manual'].encode(), page)

    def test_bundle_http_upload_then_real_start_and_local_open(self):
        controller = migration.Controller()
        bundle = self.bundle()
        boundary = 'synthetic-boundary'
        body = b''
        for key, value in [('csrf', controller.csrf), ('action', 'bundle')]:
            body += ('--' + boundary + '\r\nContent-Disposition: form-data; name="' + key + '"\r\n\r\n' + value + '\r\n').encode()
        body += ('--' + boundary + '\r\nContent-Disposition: form-data; name="bundle"; filename="originals.zip"\r\nContent-Type: application/zip\r\n\r\n').encode()
        body += bundle.read_bytes() + ('\r\n--' + boundary + '--\r\n').encode()
        reply = Reply(body, {'Content-Type': 'multipart/form-data; boundary=' + boundary})
        with patch.object(server, 'DB_FILE', self.db), patch.object(server, 'SOURCE_DIR', self.sources), \
                patch.object(server, 'SOURCE_MIGRATION', controller):
            server.Handler.do_POST(reply)
        self.assertEqual(reply.status, 303)
        directory = self.root / 'source-imports'
        ident = reply.sent['Location'].split('id=')[1]
        plan = migration.read_plan(directory, ident)
        self.assertTrue(plan['bundle'])
        self.assertEqual(self.count('source'), 0)
        preview = source_migration_ui.page(controller, directory, ident)
        self.assertIn(b'Synthetic manual', preview)
        self.assertNotIn(b'checked', preview)
        body = urlencode({'csrf': controller.csrf, 'action': 'start', 'plan': ident, 'selected': '0'}).encode()
        started = Reply(body)
        with patch.object(server, 'DB_FILE', self.db), patch.object(server, 'SOURCE_DIR', self.sources), \
                patch.object(server, 'SOURCE_MIGRATION', controller):
            server.Handler.do_POST(started)
            controller.worker.join(5)
        self.assertEqual(started.status, 303)
        self.assertEqual(migration.read_plan(directory, ident)['items'][0]['status'], 'complete')
        # The durable plan can be reopened after constructing a fresh controller.
        self.assertIn(b'Klar', source_migration_ui.page(migration.Controller(), directory, ident))

    def test_bundle_builder_round_trip_and_no_overwrite(self):
        spec = importlib.util.spec_from_file_location('build_bundle', APP.parents[3] / 'scripts/build_source_bundle.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        originals = self.root / 'downloaded'
        originals.mkdir()
        (originals / self.file['id']).write_bytes(self.body)
        output = self.root / 'built.zip'
        self.assertEqual(module.build({'files': [self.file]}, originals, output), 1)
        self.assertEqual(source_bundle.inventory(output)['files'][0]['sha256'], hashlib.sha256(self.body).hexdigest())
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            module.build({'files': [self.file]}, originals, output)

    def test_drive_provider_checksum_is_verified(self):
        meta = dict(id=self.file['id'], name=self.file['name'], size=len(self.body),
                    mimeType='application/pdf', md5Checksum='0' * 32)
        with patch.object(drive_import, 'metadata', return_value=meta), \
                patch.object(drive_import, 'urlopen', return_value=io.BytesIO(self.body)):
            with self.assertRaises(drive_import.DriveImportError):
                drive_import.download_original(self.file['id'], 'synthetic-token', self.sources)
        self.assertFalse(list(self.sources.glob('.drive-*')))

    def test_symlink_source_and_failed_atomic_commit(self):
        original = self.download()
        temporary = Path(original['temporary_path'])
        link = self.sources / 'linked'
        link.symlink_to(temporary)
        original['temporary_path'] = str(link)
        with self.assertRaises(ValueError):
            self.register(downloaded=original)
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TRIGGER reject_link BEFORE INSERT ON source_link BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.Error):
            self.register()
        self.assertEqual(self.count('source'), 0)
        self.assertEqual(self.count('ingest_occurrence'), 0)
        self.assertEqual(self.count('change_log'), 0)
        self.assertFalse(list((self.sources / 'Documents/Manuals').glob('*')))


if __name__ == '__main__':
    unittest.main()
