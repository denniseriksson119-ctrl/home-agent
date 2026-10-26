"""Read-boundary regression tests using a real synthetic SQLite house and sources."""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'codex_remote_test/app'))
sys.path.insert(0, str(ROOT / 'home_agent/rootfs/opt/home-agent'))
import codex_read
import home_agent_mcp as client
import house_context
import chatgpt_export
import server as home_server
from controller import Controller


class Reply(codex_read.ReadHandler):
    def __init__(self, service, path='/v1/context', token=''):
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


class ReadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / 'home.db'
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        data = {'homes': [{'id': 'home', 'name': 'Synthetic home', 'assets': [
            {'id': house_context.NIBE_LEGACY_ID, 'name': 'Synthetic NIBE', 'model': 'S1255',
             'credentials': 'never-export-secret'},
            {'id': 'other', 'name': 'Other asset', 'notes': 'unrelated-private-note'}]}]}
        with patch.object(home_server, 'DB_FILE', self.db):
            home_server.import_database(data, 'synthetic')
        with sqlite3.connect(self.db) as db:
            ident = db.execute('SELECT permanent_id FROM object_identity WHERE legacy_id=?', (house_context.NIBE_LEGACY_ID,)).fetchone()[0]
            for sid, mime, body in [('photo', 'image/png', b'synthetic png'), ('manual', 'application/pdf', b'%PDF-synthetic'), ('inbox', 'text/plain', b'private unlinked inbox')]:
                path = self.sources / sid
                path.write_bytes(body)
                db.execute("INSERT INTO source(source_id,source_type,media_type,original_name,sha256,storage_ref,custody_status) VALUES(?,'file',?,?,?,?, 'local_verified')", (sid, mime, sid, hashlib.sha256(body).hexdigest(), str(path)))
                if sid != 'inbox':
                    db.execute('INSERT INTO source_link(source_id,object_id) VALUES(?,?)', (sid, ident))
        self.service = codex_read.ReadService(self.db, self.sources, self.root / 'state.json', 'local-home-agent')
        self.ticket = self.service.create_ticket()
        self.config = client.ticket_config(self.ticket)
        self.config_path = self.root / 'client.json'
        self.config_path.write_text(json.dumps(self.config))
        self.config_path.chmod(0o600)

    def get(self, path='/v1/context', token=None):
        reply = Reply(self.service, path, token if token is not None else 'Bearer ' + self.config['token'])
        reply.do_GET()
        return reply

    def transport(self, config, path, limit):
        reply = self.get(path, 'Bearer ' + config['token'])
        if reply.code != 200:
            raise client.ReadError('Read rejected')
        body = reply.wfile.getvalue()
        self.assertLessEqual(len(body), limit)
        return body, reply.response_headers['Content-Type']

    def test_default_disabled_missing_wrong_rotated_and_revoked_keys_are_rejected(self):
        self.assertEqual(self.get(token='').code, 401)
        self.assertEqual(self.get(token='Bearer wrong').code, 401)
        self.service.create_ticket()
        self.assertEqual(self.get().code, 401)
        self.config = client.ticket_config(self.service.create_ticket())
        self.assertEqual(self.get().code, 200)
        self.service.revoke()
        self.assertEqual(self.get().code, 401)
        self.service.state_path.unlink()
        self.assertEqual(self.get().code, 401)

    def test_context_has_provenance_without_secrets_storage_or_unlinked_sources(self):
        before = self.db.read_bytes()
        reply = self.get()
        self.assertEqual(reply.code, 200)
        raw = reply.wfile.getvalue().decode()
        for value in ('never-export-secret', 'unrelated-private-note', 'private unlinked inbox', str(self.root), self.config['token']):
            self.assertNotIn(value, raw)
        result = json.loads(raw)
        self.assertEqual({s['id'] for s in result['sources']}, {'photo', 'manual'})
        self.assertTrue(result['nibe']['id'])
        self.assertEqual(len(result['revision']), 64)
        self.assertEqual(reply.response_headers['Cache-Control'], 'no-store')
        self.assertEqual(before, self.db.read_bytes())

    def test_mutation_and_arbitrary_routes_never_fall_through_to_domain_handlers(self):
        before = self.db.read_bytes()
        for path in ('/asset/drive-import', '/v1/source/inbox', '/v1/source/../../auth.json', '/v1/context?path=/data/home.db'):
            self.assertEqual(self.get(path).code, 404)
        for method in ('do_POST', 'do_PUT', 'do_PATCH', 'do_DELETE'):
            reply = Reply(self.service)
            getattr(reply, method)()
            self.assertEqual(reply.code, 405)
        self.assertEqual(before, self.db.read_bytes())

    def test_original_hash_custody_and_storage_boundary_are_enforced(self):
        self.assertEqual(self.get('/v1/source/photo').wfile.getvalue(), b'synthetic png')
        (self.sources / 'photo').write_bytes(b'tampered')
        self.assertEqual(self.get('/v1/source/photo').code, 503)
        (self.sources / 'photo').unlink()
        outside = self.root / 'outside'
        outside.write_bytes(b'synthetic png')
        (self.sources / 'photo').symlink_to(outside)
        self.assertEqual(self.get('/v1/source/photo').code, 503)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE source SET custody_status='pending' WHERE source_id='manual'")
        self.assertEqual(self.get('/v1/source/manual').code, 503)

    def test_tools_retrieve_image_and_pdf_into_workspace_without_database_changes(self):
        before = self.db.read_bytes()
        with patch.object(client, 'fetch', side_effect=self.transport):
            index = client.call('home_agent_index', {'query': 'NIBE'}, self.config_path, self.workspace)
            self.assertEqual(len(index['matches']), 1)
            nibe = client.call('home_agent_nibe', {}, self.config_path, self.workspace)
            self.assertNotIn('index', nibe)
            for sid, suffix in [('photo', '.png'), ('manual', '.pdf')]:
                result = client.call('home_agent_source', {'source_id': sid}, self.config_path, self.workspace)
                path = Path(result['local_path'])
                self.assertTrue(path.is_relative_to(self.workspace))
                self.assertEqual(path.suffix, suffix)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), result['sha256'])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(self.config['token'], json.dumps(result))
            with self.assertRaises(client.ReadError):
                client.call('home_agent_source', {'source_id': 'inbox'}, self.config_path, self.workspace)
        self.assertEqual(before, self.db.read_bytes())

    def test_bad_download_and_symlink_cache_cannot_produce_accepted_file(self):
        with patch.object(client, 'fetch', side_effect=self.transport):
            original = client.fetch
            def changed(config, path, limit):
                return (b'wrong', 'image/png') if path.startswith('/v1/source/') else original(config, path, limit)
            with patch.object(client, 'fetch', side_effect=changed), self.assertRaises(client.ReadError):
                client.download(self.config, 'photo', self.workspace)
            self.assertFalse((self.workspace / 'home-agent-sources').exists())
            (self.workspace / 'home-agent-sources').symlink_to(self.root)
            with self.assertRaises(client.ReadError):
                client.download(self.config, 'photo', self.workspace)

    def test_connection_verifies_key_before_replacing_private_configuration(self):
        before = self.config_path.read_bytes()
        with patch.object(client, 'context', side_effect=client.ReadError('rejected')):
            with self.assertRaises(client.ReadError):
                client.connect(self.ticket, self.config_path)
        self.assertEqual(before, self.config_path.read_bytes())
        with patch.object(client, 'fetch', side_effect=self.transport):
            client.connect(self.ticket, self.config_path)
        self.assertEqual(client.load_config(self.config_path), self.config)
        self.assertEqual(self.config_path.stat().st_mode & 0o777, 0o600)

    def test_ticket_cannot_redirect_requests_to_other_hosts_urls_or_scopes(self):
        for host in ('127.0.0.1', 'example.com', 'local-home-agent.evil', 'local-home-agent:8099', 'http://local-home-agent', 'local-home-agent/../'):
            ticket = base64.urlsafe_b64encode(json.dumps({**self.config, 'host': host}).encode()).decode()
            with self.subTest(host=host), self.assertRaises(client.ReadError):
                client.ticket_config(ticket)
        for config in ({**self.config, 'scope': 'write'}, {**self.config, 'extra': True}):
            with self.assertRaises(client.ReadError):
                client.validate(config)
        self.assertIsNone(client.NoRedirect().redirect_request(None))

    def test_mcp_protocol_lists_only_read_tools_and_redacts_unexpected_errors(self):
        initialized = client.dispatch({'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}})
        self.assertEqual(initialized['protocolVersion'], '2025-06-18')
        tools = client.dispatch({'method': 'tools/list'})['tools']
        self.assertEqual({t['name'] for t in tools}, {'home_agent_index', 'home_agent_nibe', 'home_agent_source', 'home_agent_archive_audit'})
        for args in ({'url': 'http://other'}, {'source_id': 'photo'}):
            with self.assertRaises(client.ReadError):
                client.call('home_agent_nibe', args, self.config_path, self.workspace)
        with patch.object(client, 'call', side_effect=RuntimeError('secret raw provider body')):
            reply = client.dispatch({'method': 'tools/call', 'params': {'name': 'home_agent_nibe'}})
        self.assertTrue(reply['isError'])
        self.assertNotIn('secret', json.dumps(reply))

    def test_setup_ticket_is_only_in_csrf_authorized_post_response(self):
        def request(post=False, **fields):
            from urllib.parse import urlencode
            reply = Reply(self.service)
            body = urlencode(fields).encode()
            reply.rfile = io.BytesIO(body)
            reply.headers = {'Content-Length': str(len(body)), 'Host': 'local-home-agent:8099'}
            codex_read.handle_page(reply, self.service, post)
            return reply
        get = request()
        self.assertNotIn(self.config['token'].encode(), get.wfile.getvalue())
        self.assertEqual(request(True, csrf='wrong', action='revoke').code, 400)
        self.assertTrue(self.service.enabled())
        created = request(True, csrf=self.service.csrf, action='create')
        self.assertEqual(created.code, 200)
        self.assertIn(b'textarea', created.wfile.getvalue())
        self.assertEqual(created.response_headers['Cache-Control'], 'no-store')
        self.assertEqual(request(True, csrf=self.service.csrf, action='revoke').code, 200)
        self.assertFalse(self.service.enabled())

    def submit(self, csrf=None, **headers):
        from urllib.parse import urlencode
        reply = Reply(self.service)
        body = urlencode({'csrf': self.service.csrf if csrf is None else csrf, 'action': 'create'}).encode()
        reply.rfile = io.BytesIO(body)
        reply.headers = {'Content-Length': str(len(body)), 'Host': '192.0.2.20:8099', **headers}
        codex_read.handle_page(reply, self.service, post=True)
        return reply

    def test_same_origin_and_opaque_or_missing_origin_forms_can_create_ticket(self):
        for headers in ({'Origin': 'http://192.0.2.20:8099', 'Sec-Fetch-Site': 'same-origin'},
                        {'Origin': 'null', 'Sec-Fetch-Site': 'same-origin'},
                        {'Origin': 'null'}, {}):
            with self.subTest(headers=headers):
                reply = self.submit(**headers)
                self.assertEqual(reply.code, 200)
                self.assertIn(b'textarea', reply.wfile.getvalue())
                self.assertEqual(reply.response_headers['Referrer-Policy'], 'same-origin')
                self.assertEqual(reply.response_headers['Cache-Control'], 'no-store')

    def test_opaque_origin_never_bypasses_csrf_or_explicit_cross_site_rejection(self):
        before = self.service.state_path.read_bytes()
        for csrf in ('wrong', '', 'ogiltig-åäö'):
            reply = self.submit(csrf=csrf, Origin='null')
            self.assertEqual(reply.code, 400)
            self.assertNotIn(b'textarea', reply.wfile.getvalue())
            self.assertEqual(self.service.state_path.read_bytes(), before)
        for headers in ({'Origin': 'http://other.invalid'}, {'Origin': 'http://192.0.2.20'},
                        {'Origin': 'https://192.0.2.20:8099'}, {'Origin': 'http://user@192.0.2.20:8099'},
                        {'Origin': 'http://192.0.2.20:8099/path'}, {'Origin': 'http://192.0.2.20:bad'},
                        {'Origin': 'null', 'Sec-Fetch-Site': 'cross-site'},
                        {'Origin': 'http://192.0.2.20:8099', 'Sec-Fetch-Site': 'cross-site'}):
            with self.subTest(headers=headers):
                reply = self.submit(**headers)
                self.assertEqual(reply.code, 400)
                self.assertEqual(self.service.state_path.read_bytes(), before)

    def test_equivalent_default_port_and_hostname_case_are_same_origin(self):
        self.assertTrue(codex_read.same_origin('http://LOCAL-HOME-AGENT:80', 'local-home-agent'))
        self.assertTrue(codex_read.same_origin('http://[::1]:8099', '[::1]:8099'))
        self.assertFalse(codex_read.same_origin('http://local-home-agent:8100', 'local-home-agent:8099'))
        self.assertFalse(codex_read.same_origin('http://local-home-agent:0', 'local-home-agent'))


class MigrationTests(unittest.TestCase):
    def test_development_role_upgrades_archive_instruction_only_for_exact_seed(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Controller(Path(folder))
            instructions = first.workspace / 'AGENTS.md'
            instructions.write_bytes((ROOT / 'codex_remote_test/app/seed/AGENTS.development-0.1.6.md').read_bytes())
            first.close()
            second = Controller(Path(folder))
            self.assertIn('home_agent_archive_audit', instructions.read_text())
            instructions.write_text('owner custom instructions')
            second.close()
            third = Controller(Path(folder))
            self.assertEqual(instructions.read_text(), 'owner custom instructions')
            third.close()

    def test_read_only_role_upgrade_preserves_custom_guide_project_and_read_key(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = Controller(root)
            instructions = first.workspace / 'AGENTS.md'
            instructions.write_bytes((ROOT / 'codex_remote_test/app/seed/AGENTS.read-only.md').read_bytes())
            guide = first.workspace / 'DEVELOPMENT.md'
            guide.write_text('owner-custom development guide')
            project = first.projects / 'existing-project'
            project.mkdir()
            code = project / 'work.py'
            code.write_text('print("keep local changes")')
            key = first.home / 'home-agent-read.json'
            key.write_text('{"synthetic":"private cached read key"}')
            key.chmod(0o600)
            before = key.read_bytes()
            first.close()
            second = Controller(root)
            self.assertIn('Utveckling av Home Agent', instructions.read_text())
            self.assertEqual(guide.read_text(), 'owner-custom development guide')
            self.assertEqual(code.read_text(), 'print("keep local changes")')
            self.assertEqual(key.read_bytes(), before)
            second.close()

    def test_project_directory_symlink_is_rejected_without_changing_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = Controller(root)
            first.projects.rmdir()
            outside = root / 'outside'
            outside.mkdir()
            first.projects.symlink_to(outside)
            first.close()
            from controller import TestError
            with self.assertRaises(TestError):
                Controller(root)
            self.assertEqual(list(outside.iterdir()), [])

    def test_generated_instructions_upgrade_but_custom_files_and_auth_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            controller = Controller(root)
            legacy = ROOT / 'codex_remote_test/app/seed/AGENTS.connection-test.md'
            instructions = controller.workspace / 'AGENTS.md'
            instructions.write_bytes(legacy.read_bytes())
            auth = controller.codex_home / 'auth.json'
            auth.write_text('synthetic credential cache')
            controller.close()
            other = Controller(root)
            self.assertIn('home_agent_nibe', instructions.read_text())
            instructions.write_text('custom instructions')
            other.close()
            last = Controller(root)
            self.assertEqual(instructions.read_text(), 'custom instructions')
            self.assertEqual(auth.read_text(), 'synthetic credential cache')
            last.close()

    def test_drive_worker_is_paused_without_deleting_credentials(self):
        self.assertTrue(chatgpt_export.status()['paused'])
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.return_value = True
        with patch.object(chatgpt_export, 'publish_once') as publish:
            chatgpt_export.run('not-opened', 'not-opened', stop)
        publish.assert_not_called()


if __name__ == '__main__':
    unittest.main()
