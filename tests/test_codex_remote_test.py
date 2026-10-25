"""Exercise real subprocesses and HTTP handlers with a synthetic, offline Codex."""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'codex_remote_test/app'
sys.path.insert(0, str(APP))
from controller import Controller, TestError, parse_pair

spec = importlib.util.spec_from_file_location('codex_test_web', APP / 'server.py')
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)

FAKE = r'''
import json,os,sys,time
from pathlib import Path
root=Path(os.environ['HOME'])
args=sys.argv[1:]
if args==['--version']:
    print('codex-cli 0.164.0')
elif args==['remote-control','--no-daemon','--help']:
    print('experimental remote-control')
elif args==['login','status']:
    if (root/'grant').exists():
        print('Logged in using ChatGPT')
    else:
        print('Not logged in');sys.exit(1)
elif args==['login','--device-auth']:
    print('https://auth.openai.com/codex/device\nABCD-EFGH',flush=True)
    for _ in range(1000):
        if (root/'grant').exists():
            print('Successfully logged in');sys.exit(0)
        time.sleep(.01)
    sys.exit(1)
elif args==['remote-control','--no-daemon']:
    print('secret-provider-diagnostic',flush=True)
    if (root/'remote-fail').exists():sys.exit(9)
    while True:time.sleep(.05)
elif args==['remote-control','pair','--json']:
    if (root/'bad-pair').exists():
        print('private-provider-error refresh_token=secret');sys.exit(3)
    print(json.dumps({'pairingCode':'DO-NOT-EXPOSE-CREDENTIAL','manualPairingCode':'TEST-PAIR',
                      'environmentId':'private-environment','expiresAt':time.time()+90}))
elif args==['probe-env']:
    print(json.dumps(dict(os.environ)))
elif args==['large']:
    print('x'*20000)
else:
    print('private unknown operation');sys.exit(2)
'''


def until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Timed out waiting for synthetic child process')


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binary = self.root / 'fake-codex'
        self.binary.write_text('#!' + sys.executable + '\n' + FAKE)
        self.binary.chmod(0o700)
        self.controller = self.new_controller()

    def new_controller(self):
        controller = Controller(self.root, self.binary)
        self.addCleanup(controller.close)
        return controller

    def initialize(self):
        self.controller.initialize()
        until(lambda: self.controller.status()['supported'])
        until(lambda: not any(t.is_alive() for t in self.controller.threads))

    def grant(self):
        (self.controller.home / 'grant').touch()
        self.controller.refresh_auth()

    def test_device_login_streams_code_before_process_exit_then_clears_it(self):
        self.initialize()
        self.controller.action('login')
        until(lambda: self.controller.status()['login_code'] == 'ABCD-EFGH')
        self.assertTrue(self.controller.status()['busy'])
        self.grant()
        until(lambda: not self.controller.status()['busy'])
        self.assertTrue(self.controller.status()['authenticated'])
        self.assertIsNone(self.controller.status()['login_code'])
        self.assertNotIn('grant', self.controller.status())

    def test_remote_pair_and_restart_preserve_workspace_without_exposing_credentials(self):
        self.initialize()
        self.grant()
        self.controller.action('start')
        self.controller.action('pair')
        until(lambda: not self.controller.status()['busy'])
        status = self.controller.status()
        self.assertEqual(status['pair_code'], 'TEST-PAIR')
        self.assertNotIn('DO-NOT-EXPOSE', json.dumps(status))
        self.assertNotIn('private-environment', json.dumps(status))
        self.assertNotIn('secret-provider-diagnostic', json.dumps(status))
        marker = self.controller.workspace / 'session-test.txt'
        marker.write_text('synthetic session note')
        self.controller.close()
        self.controller = self.new_controller()
        self.controller.initialize()
        until(lambda: self.controller.status()['remote_running'])
        self.assertEqual(marker.read_text(), 'synthetic session note')
        self.assertIsNone(self.controller.status()['pair_code'])
        self.assertEqual(self.controller.state_file.stat().st_mode & 0o777, 0o600)
        self.controller.action('stop')
        self.controller.close()
        stopped = self.new_controller()
        stopped.initialize()
        until(lambda: stopped.status()['supported'])
        until(lambda: not any(t.is_alive() for t in stopped.threads))
        self.assertFalse(stopped.status()['remote_running'])
        self.assertFalse(stopped.requested)

    def test_cancel_stops_login_and_late_output_cannot_replace_new_attempt(self):
        self.initialize()
        self.controller.action('login')
        until(lambda: self.controller.status()['login_code'])
        old = self.controller.job
        self.controller.action('cancel')
        self.assertIsNotNone(old.poll())
        self.assertIsNone(self.controller.status()['login_code'])
        self.controller.action('login')
        new = self.controller.job
        until(lambda: self.controller.status()['login_code'])
        self.assertIs(self.controller.job, new)
        self.controller.action('cancel')

    def test_duplicate_login_and_unauthenticated_start_are_rejected(self):
        self.initialize()
        with self.assertRaises(TestError):
            self.controller.action('start')
        self.controller.action('login')
        with self.assertRaises(TestError):
            self.controller.action('login')
        self.controller.action('cancel')
        with self.assertRaises(TestError):
            self.controller.action('arbitrary shell command')

    def test_failed_pair_and_remote_exit_are_sanitized(self):
        self.initialize()
        self.grant()
        self.controller.action('start')
        (self.controller.home / 'bad-pair').touch()
        self.controller.action('pair')
        until(lambda: not self.controller.status()['busy'])
        self.assertIsNone(self.controller.status()['pair_code'])
        self.assertNotIn('private-provider', self.controller.status()['message'])
        self.controller.action('stop')
        (self.controller.home / 'remote-fail').touch()
        self.controller.action('start')
        until(lambda: not self.controller.status()['remote_running'])
        until(lambda: 'kod 9' in self.controller.status()['message'])
        self.assertIsNone(self.controller.status()['pair_code'])

    def test_child_environment_excludes_supervisor_api_keys_and_parent_credentials(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'SUPERVISOR_TOKEN': 'private', 'OPENAI_API_KEY': 'private',
                                     'CODEX_ACCESS_TOKEN': 'private', 'GITHUB_TOKEN': 'private'}):
            code, result = self.controller._capture(['probe-env'])
        self.assertEqual(code, 0)
        environment = json.loads(result)
        self.assertNotIn('SUPERVISOR_TOKEN', environment)
        self.assertNotIn('OPENAI_API_KEY', environment)
        self.assertNotIn('CODEX_ACCESS_TOKEN', environment)
        self.assertNotIn('GITHUB_TOKEN', environment)
        self.assertEqual(environment['HOME'], str(self.controller.home))
        self.assertEqual(environment['CODEX_HOME'], str(self.controller.codex_home))

    def test_output_limit_kills_child_and_does_not_return_raw_output(self):
        with self.assertRaises(TestError):
            self.controller._capture(['large'])

    def test_restart_does_not_overwrite_files_or_accept_symlink_state(self):
        (self.controller.workspace / 'README.md').write_text('keep this')
        self.controller.close()
        other = self.new_controller()
        self.assertEqual((other.workspace / 'README.md').read_text(), 'keep this')
        other.close()
        self.controller.state_file.symlink_to(self.controller.workspace / 'README.md')
        with self.assertRaises(TestError):
            self.new_controller()

    def test_unexpired_manual_code_only_and_provider_expiry(self):
        code, expiry = parse_pair('{"manualPairingCode":"abcd-1234","expiresAt":1100}', 1000)
        self.assertEqual((code, expiry), ('abcd-1234', 1100))
        for value in ('{"pairingCode":"secret"}', '{"manualPairingCode":"<script>"}',
                      '{"manualPairingCode":"abcd-1234","expiresAt":900}', 'private invalid data'):
            with self.subTest(value=value), self.assertRaises(TestError):
                parse_pair(value, 1000)


class Reply(web.Handler):
    def __init__(self, controller, path='/', address='172.30.32.2', body=None, **headers):
        self.controller, self.path, self.client_address = controller, path, (address, 123)
        data = json.dumps(body).encode() if body is not None else b''
        self.rfile, self.wfile = io.BytesIO(data), io.BytesIO()
        self.headers = {'Content-Length': str(len(data)), 'Content-Type': 'application/json',
                        'X-CSRF-Token': controller.csrf, **headers}
        self.response_headers = {}

    def send_response(self, code):
        self.code = code

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.controller = Controller(Path(self.temp.name))
        self.addCleanup(self.controller.close)

    def test_ingress_only_even_when_headers_are_spoofed(self):
        for address in ('192.168.1.50', '172.17.0.1', '203.0.113.1'):
            reply = Reply(self.controller, address=address, **{'X-Ingress-Path': '/fake'})
            reply.do_GET()
            self.assertEqual(reply.code, 403)
            self.assertNotIn(self.controller.csrf.encode(), reply.wfile.getvalue())
        reply = Reply(self.controller)
        reply.do_GET()
        self.assertEqual(reply.code, 200)
        self.assertIn(self.controller.csrf.encode(), reply.wfile.getvalue())
        self.assertEqual(reply.response_headers['Cache-Control'], 'no-store')

    def test_get_is_readonly_and_post_requires_nonce_json_and_ingress(self):
        for path in ('/', '/api/status', '/health', '/api/action'):
            reply = Reply(self.controller, path=path)
            reply.do_GET()
            self.assertIsNone(self.controller.job)
            self.assertIsNone(self.controller.remote)
        for headers in ({'X-CSRF-Token': 'wrong'}, {'Content-Type': 'text/plain'},
                        {'Sec-Fetch-Site': 'cross-site'}):
            reply = Reply(self.controller, '/api/action', body={'action': 'start'}, **headers)
            reply.do_POST()
            self.assertEqual(reply.code, 403)

    def test_http_rejects_arbitrary_command_arguments_and_oversized_input(self):
        self.controller.supported = True
        for body in ({'action': 'exec'}, {'action': 'start', 'command': 'cat /data/home/.codex/auth.json'},
                     {'action': ['login']}, [], None):
            reply = Reply(self.controller, '/api/action', body=body)
            reply.do_POST()
            self.assertEqual(reply.code, 400)
        reply = Reply(self.controller, '/api/action', body={'action': 'start'}, **{'Content-Length': '9999'})
        reply.do_POST()
        self.assertEqual(reply.code, 400)

    def test_ui_has_relative_ingress_urls_no_external_scripts_or_token_input(self):
        page = (APP / 'index.html').read_text()
        self.assertIn("fetch('api/status'", page)
        self.assertIn("fetch('api/action'", page)
        self.assertNotIn('<script src=', page)
        self.assertNotIn('auth.json', page)
        self.assertNotIn('<input', page)


if __name__ == '__main__':
    unittest.main()
