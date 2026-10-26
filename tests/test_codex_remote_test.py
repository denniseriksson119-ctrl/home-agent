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
from remote_rpc import RemoteError

spec = importlib.util.spec_from_file_location('codex_test_web', APP / 'server.py')
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)

FAKE = r'''
import json,os,sys,time
from pathlib import Path
root=Path(os.environ['HOME'])
args=sys.argv[1:]
while args[:1]==['-c']:
    args=args[2:]
if args==['--version']:
    print('codex-cli 0.164.0')
elif args==['app-server','--help']:
    print('app-server --listen unix://PATH')
elif args==['login','status']:
    if (root/'status-error').exists():
        print('Error checking login status: private-provider-error secret-token');sys.exit(1)
    if (root/'grant').exists():
        print('Logged in using ChatGPT')
    else:
        print('Not logged in');sys.exit(1)
elif args==['login','--device-auth']:
    (root/'login-started').touch()
    (root/'grant').unlink(missing_ok=True)
    (root/'.codex/auth.json').unlink(missing_ok=True)
    print('https://auth.openai.com/codex/device\nABCD-EFGH',flush=True)
    for _ in range(1000):
        if (root/'grant').exists():
            (root/'.codex/auth.json').write_text('{"synthetic":true}')
            (root/'.codex/auth.json').chmod(0o600)
            print('Successfully logged in');sys.exit(0)
        time.sleep(.01)
    sys.exit(1)
elif args[:2]==['app-server','--listen']:
    print('secret-provider-diagnostic',flush=True)
    if (root/'remote-fail').exists():sys.exit(9)
    while True:time.sleep(.05)
elif args==['remote-control','pair','--json']:
    (root/'wrong-pair-server').touch()
    print('Wrong daemon, not the foreground server');sys.exit(3)
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
        controller = Controller(self.root, self.binary, rpc=self.rpc)
        self.addCleanup(controller.close)
        return controller

    def rpc(self, path, method, params):
        self.assertEqual(path, self.root / 'home/remote-test.sock')
        if method == 'remoteControl/pairing/start':
            if (self.root / 'home/bad-pair').exists():
                raise RemoteError('rpc', -32000)
            self.assertEqual(params, {'manualCode': True})
            return {'pairingCode': 'DO-NOT-EXPOSE-CREDENTIAL', 'manualPairingCode': 'TEST-PAIR',
                    'environmentId': 'private-environment', 'expiresAt': time.time()+90}
        status = 'connecting' if (self.root / 'home/connecting').exists() else 'connected'
        return {'status': status, 'serverName': 'private-host', 'environmentId': 'private-environment'}

    def initialize(self):
        self.controller.initialize()
        until(lambda: self.controller.status()['supported'])
        until(lambda: not any(t.is_alive() for t in self.controller.threads))

    def grant(self):
        (self.controller.home / 'grant').touch()
        if self.controller.job is None and not self.controller.pending_login:
            (self.controller.codex_home / 'auth.json').write_text('{"synthetic":true}')
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
        until(lambda: self.controller.status()['remote_status'] == 'connected')
        self.controller.action('pair')
        until(lambda: not self.controller.status()['busy'])
        status = self.controller.status()
        self.assertEqual(status['pair_code'], 'TEST-PAIR')
        self.assertNotIn('DO-NOT-EXPOSE', json.dumps(status))
        self.assertNotIn('private-environment', json.dumps(status))
        self.assertNotIn('secret-provider-diagnostic', json.dumps(status))
        self.assertFalse((self.controller.home / 'wrong-pair-server').exists())
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
        until(lambda: not self.controller.status()['busy'])
        self.controller.action('login')
        until(lambda: self.controller.status()['login_code'])
        new = self.controller.job
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
        until(lambda: self.controller.status()['remote_status'] == 'connected')
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

    def test_a_new_login_cannot_revoke_existing_confirmed_credentials(self):
        self.initialize()
        self.grant()
        original = (self.controller.codex_home / 'auth.json').read_bytes()
        with self.assertRaises(TestError):
            self.controller.action('login')
        self.assertFalse((self.controller.home / 'login-started').exists())
        self.assertEqual((self.controller.codex_home / 'auth.json').read_bytes(), original)
        self.assertEqual(self.controller.status()['auth_state'], 'signed_in')

    def test_pair_requires_connected_relay_not_merely_a_running_process(self):
        self.initialize()
        self.grant()
        marker = self.controller.home / 'connecting'
        marker.touch()
        self.controller.action('start')
        until(lambda: self.controller.status()['remote_status'] == 'connecting')
        self.assertTrue(self.controller.status()['remote_running'])
        with self.assertRaises(TestError):
            self.controller.action('pair')
        marker.unlink()
        until(lambda: self.controller.status()['remote_status'] == 'connected')
        self.controller.action('pair')
        until(lambda: not self.controller.status()['pair_pending'])
        self.assertEqual(self.controller.status()['pair_code'], 'TEST-PAIR')

    def test_cancel_discards_a_late_pairing_response(self):
        import threading
        self.initialize()
        self.grant()
        self.controller.action('start')
        until(lambda: self.controller.status()['remote_status'] == 'connected')
        entered, release = threading.Event(), threading.Event()
        def slow(path, method, params):
            if method == 'remoteControl/pairing/start':
                entered.set()
                release.wait(2)
            return self.rpc(path, method, params)
        self.controller.rpc = slow
        self.controller.action('pair')
        self.assertTrue(entered.wait(1))
        self.controller.action('cancel')
        release.set()
        until(lambda: not self.controller.status()['busy'])
        self.assertIsNone(self.controller.status()['pair_code'])

    def test_control_socket_symlink_is_not_followed_or_removed(self):
        self.initialize()
        self.grant()
        target = self.controller.workspace / 'README.md'
        before = target.read_bytes()
        self.controller.control_socket.symlink_to(target)
        with self.assertRaises(TestError):
            self.controller.action('start')
        self.assertEqual(target.read_bytes(), before)
        self.assertTrue(self.controller.control_socket.is_symlink())

    def test_stale_signed_out_state_is_rechecked_before_destructive_cli_login(self):
        self.initialize()
        (self.controller.home / 'grant').touch()  # Auth appeared after the last check.
        (self.controller.codex_home / 'auth.json').write_text('{"synthetic":true}')
        self.assertEqual(self.controller.auth_state, 'signed_out')
        self.controller.action('login')
        until(lambda: not self.controller.status()['busy'])
        self.assertEqual(self.controller.auth_state, 'signed_in')
        self.assertFalse((self.controller.home / 'login-started').exists())
        self.assertTrue((self.controller.codex_home / 'auth.json').exists())

    def test_status_error_is_unknown_and_never_false_logout_or_a_new_login(self):
        self.initialize()
        self.grant()
        marker = self.controller.home / 'status-error'
        marker.touch()
        self.controller.refresh_auth()
        status = self.controller.status()
        self.assertEqual(status['auth_state'], 'error')
        self.assertEqual(status['credential_file'], 'present')
        self.assertIn('returkod 1', status['auth_note'])
        self.assertNotIn('secret-token', json.dumps(status))
        self.assertNotIn('private-provider-error', json.dumps(status))
        with self.assertRaises(TestError):
            self.controller.action('login')
        marker.unlink()
        self.controller.action('check')
        until(lambda: self.controller.status()['auth_state'] == 'signed_in')
        self.assertFalse((self.controller.home / 'login-started').exists())

    def test_restart_starts_unknown_then_reads_persisted_credentials(self):
        self.initialize()
        self.grant()
        self.controller.close()
        self.controller = self.new_controller()
        self.assertEqual(self.controller.status()['auth_state'], 'checking')
        self.initialize()
        self.assertEqual(self.controller.status()['auth_state'], 'signed_in')
        self.assertEqual(self.controller.status()['credential_file'], 'present')

    def test_page_reload_and_explicit_check_do_not_start_or_clear_login(self):
        self.initialize()
        self.grant()
        before = (self.controller.codex_home / 'auth.json').read_bytes()
        for _ in range(2):
            page = Reply(self.controller)
            page.do_GET()
            status = Reply(self.controller, '/api/status')
            status.do_GET()
            self.assertTrue(json.loads(status.wfile.getvalue())['authenticated'])
            check = Reply(self.controller, '/api/action', body={'action': 'check'})
            check.do_POST()
            self.assertEqual(check.code, 202)
            until(lambda: self.controller.status()['auth_state'] == 'signed_in')
        self.assertEqual((self.controller.codex_home / 'auth.json').read_bytes(), before)
        self.assertFalse((self.controller.home / 'login-started').exists())

    def test_timeout_does_not_masquerade_as_a_missing_login(self):
        from unittest.mock import patch
        self.initialize()
        self.grant()
        with patch.object(self.controller, '_capture', side_effect=TestError('synthetic timeout')):
            self.controller.refresh_auth()
        self.assertEqual(self.controller.status()['auth_state'], 'error')
        self.assertEqual(self.controller.status()['credential_file'], 'present')

    def test_canceled_pending_check_never_launches_late_device_login(self):
        from unittest.mock import patch
        import threading
        self.initialize()
        entered, release = threading.Event(), threading.Event()
        capture = self.controller._capture
        def slow(args, **kwargs):
            if args == ['login', 'status']:
                entered.set()
                release.wait(2)
            return capture(args, **kwargs)
        with patch.object(self.controller, '_capture', side_effect=slow):
            self.controller.action('login')
            self.assertTrue(entered.wait(1))
            self.controller.action('cancel')
            release.set()
            until(lambda: not self.controller.status()['busy'])
        self.assertFalse((self.controller.home / 'login-started').exists())


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
        for headers in ({'X-CSRF-Token': 'wrong'}, {'X-CSRF-Token': 'ogiltig-åäö'}, {'Content-Type': 'text/plain'},
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

    def test_read_key_setup_requires_ingress_csrf_and_never_returns_the_key(self):
        from unittest.mock import patch
        import home_agent_mcp
        with patch.object(home_agent_mcp, 'connect') as connect:
            bad = Reply(self.controller, '/api/home-agent', body={'ticket': 'private-read-key'}, **{'X-CSRF-Token': 'wrong'})
            bad.do_POST()
            self.assertEqual(bad.code, 403)
            connect.assert_not_called()
            good = Reply(self.controller, '/api/home-agent', body={'ticket': 'private-read-key'})
            good.do_POST()
            self.assertEqual(good.code, 200)
            self.assertNotIn(b'private-read-key', good.wfile.getvalue())
            connect.assert_called_once_with('private-read-key', self.controller.home / 'home-agent-read.json')

    def test_ui_has_relative_ingress_urls_and_only_dedicated_read_key_input(self):
        page = (APP / 'index.html').read_text()
        self.assertIn("fetch('api/status'", page)
        self.assertIn("fetch('api/action'", page)
        self.assertNotIn('<script src=', page)
        self.assertNotIn('auth.json', page)
        self.assertIn('id="read-ticket" type="password"', page)
        self.assertNotIn('OPENAI_API_KEY', page)


class RPCTests(unittest.TestCase):
    def fake_socket(self, responses):
        from unittest.mock import Mock
        socket = Mock()
        socket.recv.side_effect = [json.dumps(response) for response in responses]
        return socket

    def test_protocol_initializes_experimental_api_and_uses_only_requested_local_method(self):
        from unittest.mock import patch
        from remote_rpc import request
        socket = self.fake_socket([{'id': 1, 'result': {}}, {'method': 'some/notification'},
                                   {'id': 2, 'result': {'status': 'connected'}}])
        with patch('remote_rpc._connect', return_value=socket) as connect:
            result = request(Path('/private/test.sock'), 'remoteControl/status/read')
        self.assertEqual(result, {'status': 'connected'})
        connect.assert_called_once_with(Path('/private/test.sock'), 10)
        messages = [json.loads(call.args[0]) for call in socket.send.call_args_list]
        self.assertTrue(messages[0]['params']['capabilities']['experimentalApi'])
        self.assertEqual(messages[-1]['method'], 'remoteControl/status/read')
        self.assertTrue(socket.close.called)

    def test_rpc_error_does_not_echo_provider_body(self):
        from unittest.mock import patch
        from remote_rpc import request
        socket = self.fake_socket([{'id': 1, 'result': {}},
                                   {'id': 2, 'error': {'code': -32000, 'message': 'private token content'}}])
        with patch('remote_rpc._connect', return_value=socket), self.assertRaises(RemoteError) as caught:
            request(Path('/private/test.sock'), 'remoteControl/pairing/start', {'manualCode': True})
        self.assertEqual(caught.exception.code, -32000)
        self.assertNotIn('private token content', str(caught.exception))

    def test_arbitrary_method_and_oversized_response_are_rejected(self):
        from unittest.mock import Mock, patch
        from remote_rpc import request
        with self.assertRaises(RemoteError):
            request(Path('/private/test.sock'), 'command/exec', {'command': 'arbitrary'})
        socket = Mock()
        socket.recv.return_value = 'x'*65537
        with patch('remote_rpc._connect', return_value=socket), self.assertRaises(RemoteError):
            request(Path('/private/test.sock'), 'remoteControl/status/read')


if __name__ == '__main__':
    unittest.main()
