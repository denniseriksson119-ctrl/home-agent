"""Synthetic device authorization, HTTP boundary and exporter compatibility tests."""
import copy
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "home_agent/rootfs/opt/home-agent"))
import chatgpt_export
import drive_auth
import google_device as device
import server
import ui

CLIENT = {"client_id": "123-synthetic.apps.googleusercontent.com", "client_secret": "synthetic-client-secret",
          "expected_email": "owner@example.invalid"}
TOKENS = {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh", "token_type": "Bearer",
          "scope": "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive.file"}


class Google:
    def __init__(self):
        self.calls = []
        self.poll = {"error": "authorization_pending"}
        self.identity = {"email": CLIENT["expected_email"], "email_verified": True}
        self.hook = lambda endpoint: None
        self.code = {"user_code": "WWWWWWWWWWWWWWW", "device_code": "private-device-code",
                     "verification_url": "https://www.google.com/device", "expires_in": 120, "interval": 5}

    def request(self, endpoint, form=None, token=None):
        self.calls.append((endpoint, form, token))
        self.hook(endpoint)
        value = self.code if endpoint == "code" else self.poll if endpoint == "token" else self.identity
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)


class Reply:
    def __init__(self, path, csrf="", host="192.168.1.10:8099", origin="http://192.168.1.10:8099"):
        self.path = path
        self.headers = {"Host": host, "Origin": origin, "Content-Type": "application/x-www-form-urlencoded"}
        self.body = urlencode({"csrf": csrf}).encode()
        self.headers["Content-Length"] = str(len(self.body))
        self.rfile, self.wfile = io.BytesIO(self.body), io.BytesIO()
        self.response_headers = {}

    def send_response(self, code):
        self.code = code

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass


class DeviceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.options = self.root / "options.json"
        self.config = self.root / "oauth.json"
        self.state = self.root / "pairing.json"
        self.write_options(CLIENT)
        self.seconds = 1000
        self.google = Google()
        self.wake = Mock()
        self.controller = self.new_controller()

    def write_options(self, config):
        self.options.write_text(json.dumps({"google_drive": config}))

    def new_controller(self):
        return device.Controller(self.options, self.config, self.state, self.google.request,
                                 lambda: self.seconds, self.wake)

    def waiting(self):
        self.controller.start()
        self.assertFalse(self.google.calls)  # button handler never waits on Google
        self.controller.step()
        self.assertEqual(self.controller.status()["phase"], "waiting")

    def grant(self):
        self.google.poll = TOKENS
        self.seconds += 5
        self.controller.step()

    def route(self, path, csrf=None, **kwargs):
        reply = Reply(path, csrf if csrf is not None else self.controller.csrf, **kwargs)
        with patch.object(server, "GOOGLE_DEVICE", self.controller):
            if path == "/drive/connect":
                server.Handler.do_GET(reply)
            else:
                server.Handler.do_POST(reply)
        return reply

    def test_real_handler_happy_path_saves_private_credentials_and_works_with_existing_refresh(self):
        before = self.route("/drive/connect")
        self.assertEqual(before.code, 200)
        self.assertEqual(before.response_headers["Cache-Control"], "no-store")
        self.assertEqual(before.response_headers["X-Frame-Options"], "DENY")
        start = self.route("/drive/connect/start")
        self.assertEqual(start.code, 303)
        self.assertFalse(self.google.calls)
        self.controller.step()
        waiting = self.route("/drive/connect")
        self.assertIn(b"WWWWWWWWWWWWWWW", waiting.wfile.getvalue())
        self.grant()
        self.assertEqual(self.controller.status()["phase"], "connected")
        saved = chatgpt_export.private_json(self.config)
        chatgpt_export.validate_config(saved)
        self.assertTrue(chatgpt_export.config_enabled(saved))
        self.assertEqual(saved["refresh_token"], TOKENS["refresh_token"])
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.wake.assert_called_once_with()
        self.assertEqual(self.google.calls[0][1]["scope"], device.SCOPES)
        self.assertEqual(self.google.calls[1][1]["grant_type"], "urn:ietf:params:oauth:grant-type:device_code")
        replies = [io.BytesIO(b'{"access_token":"renewed"}'), io.BytesIO(json.dumps(self.google.identity).encode())]
        with patch.object(drive_auth, "urlopen", side_effect=replies) as request:
            self.assertEqual(drive_auth.access_token(self.config), "renewed")
        sent = parse_qs(request.call_args_list[0].args[0].data.decode())
        self.assertEqual(sent["refresh_token"], [TOKENS["refresh_token"]])
        page = self.route("/drive/connect").wfile.getvalue().decode()
        for secret in (CLIENT["client_secret"], TOKENS["access_token"], TOKENS["refresh_token"], "private-device-code"):
            self.assertNotIn(secret, page)
            self.assertNotIn(secret, self.state.read_text())

    def test_restart_resumes_same_attempt_and_respects_pending_and_slow_down(self):
        self.waiting()
        first = chatgpt_export.private_json(self.state)
        self.controller = self.new_controller()
        self.controller.start()  # duplicate click is idempotent
        self.assertEqual(chatgpt_export.private_json(self.state)["attempt"], first["attempt"])
        self.seconds += 4
        self.controller.step()
        self.assertEqual(len(self.google.calls), 1)
        self.seconds += 1
        self.controller.step()
        self.assertEqual(len(self.google.calls), 2)
        self.google.poll = {"error": "slow_down"}
        self.seconds += 5
        self.controller.step()
        slowed = chatgpt_export.private_json(self.state)
        self.assertEqual(slowed["interval"], 10)
        self.assertEqual(slowed["next_poll"], self.seconds + 10)
        self.seconds += 9
        self.controller.step()
        self.assertEqual(len(self.google.calls), 3)
        self.seconds += 1
        self.google.poll = TOKENS
        self.controller.step()
        self.assertTrue(self.config.exists())

    def test_device_credentials_drive_the_real_exporter_without_database_writes(self):
        from test_chatgpt_export import FakeDrive
        import drive_publish
        db_path = self.root / "home.db"
        with patch.object(server, "DB_FILE", db_path):
            server.import_database({"homes": [{"id": "synthetic-home", "name": "Synthetic home", "assets": [
                {"id": "eq_heat_pump_nibe_s1255", "name": "Synthetic NIBE", "model": "S1255"}]}]}, "synthetic")
        before = db_path.read_bytes()
        self.waiting()
        self.grant()
        fake = FakeDrive()
        with patch.object(chatgpt_export.drive_auth, "access_token", return_value="synthetic-token"), patch.object(
                drive_publish.DrivePublisher, "request", new=lambda client, *a, **k: fake.request(client, *a, **k)):
            self.assertTrue(chatgpt_export.publish_once(db_path, self.root, self.config, self.root / "publish-state.json"))
        self.assertIn(b"Synthetic NIBE", fake.body("index"))
        self.assertEqual(db_path.read_bytes(), before)

    def test_cancel_during_google_response_never_commits_tokens(self):
        self.waiting()
        self.google.hook = lambda endpoint: self.controller.cancel() if endpoint == "token" else None
        self.grant()
        self.assertEqual(self.controller.status()["phase"], "cancelled")
        self.assertFalse(self.config.exists())
        self.assertNotIn("device_code", self.state.read_text())
        self.wake.assert_not_called()

    def test_expiry_and_denial_clear_codes_and_allow_new_attempt(self):
        self.waiting()
        self.seconds += 120
        self.controller.step()
        self.assertEqual(self.controller.status()["phase"], "expired")
        self.assertEqual(len(self.google.calls), 1)
        self.controller.start()
        self.controller.step()
        self.google.poll = {"error": "access_denied", "error_description": "private-provider-body"}
        self.seconds += 5
        self.controller.step()
        status = self.controller.status()
        self.assertEqual(status["phase"], "error")
        self.assertNotIn("private-provider-body", json.dumps(status))
        self.assertNotIn("device_code", self.state.read_text())
        self.assertFalse(self.config.exists())

    def test_wrong_or_unverified_account_and_missing_scope_never_replace_existing_credentials(self):
        old = {**CLIENT, "purpose": chatgpt_export.PURPOSE, "enabled": True, "refresh_token": "old-refresh"}
        chatgpt_export.save_state(self.config, old)
        for identity, tokens in (({"email": "other@example.invalid", "email_verified": True}, TOKENS),
                                 ({"email": CLIENT["expected_email"], "email_verified": False}, TOKENS),
                                 (self.google.identity, {**TOKENS, "scope": "openid email"})):
            with self.subTest(identity=identity, scope=tokens["scope"]):
                self.controller.start()
                self.controller.step()
                self.google.identity = identity
                self.google.poll = tokens
                self.seconds += 5
                self.controller.step()
                self.assertEqual(self.controller.status()["phase"], "error")
                self.assertEqual(chatgpt_export.private_json(self.config), old)
        self.wake.assert_not_called()

    def test_changed_options_during_identity_check_cannot_save_old_attempt(self):
        self.waiting()
        self.google.hook = lambda endpoint: self.write_options({**CLIENT, "expected_email": "new@example.invalid"}) if endpoint == "identity" else None
        self.grant()
        self.assertFalse(self.config.exists())
        self.assertEqual(self.controller.status()["phase"], "error")

    def test_existing_different_client_is_preserved_and_no_account_switch_is_allowed(self):
        chatgpt_export.save_state(self.config, {**CLIENT, "client_id": "legacy.apps.googleusercontent.com", "refresh_token": "old"})
        before = self.config.read_bytes()
        with self.assertRaises(device.DeviceError):
            self.controller.start()
        self.assertEqual(before, self.config.read_bytes())
        self.assertFalse(self.google.calls)

    def test_restart_after_credential_commit_recovers_without_reusing_consumed_code(self):
        self.waiting()
        with patch.object(self.controller, "finish", side_effect=OSError("synthetic interrupted status write")):
            with self.assertRaises(OSError):
                self.grant()
        self.assertTrue(self.config.exists())
        calls = len(self.google.calls)
        self.controller = self.new_controller()
        self.controller.step()
        self.assertEqual(len(self.google.calls), calls)
        self.assertEqual(self.controller.status()["phase"], "connected")
        self.assertNotIn("device_code", self.state.read_text())

    def test_removing_options_during_pairing_ends_attempt_without_network_calls(self):
        self.waiting()
        self.options.unlink()
        self.controller.step()
        self.assertEqual(len(self.google.calls), 1)
        self.assertEqual(chatgpt_export.private_json(self.state)["phase"], "error")
        self.assertNotIn("device_code", self.state.read_text())

    def test_network_failure_backs_off_without_busy_polling(self):
        self.waiting()
        self.google.poll = device.DeviceError("Google kunde inte nås. Försök igen.")
        self.seconds += 5
        self.controller.step()
        self.assertEqual(chatgpt_export.private_json(self.state)["next_poll"], self.seconds + 15)
        for _ in range(5):
            self.controller.step()
        self.assertEqual(len(self.google.calls), 2)
        self.seconds += 15
        self.google.poll = TOKENS
        self.controller.step()
        self.assertTrue(self.config.exists())

    def test_invalid_client_and_malformed_or_foreign_verification_links_fail_safely(self):
        for code in ({"error": "invalid_client", "error_description": "private-provider-description"},
                     {**self.google.code, "verification_url": "https://attacker.invalid/device"},
                     {**self.google.code, "expires_in": True}, {**self.google.code, "interval": 0}):
            self.google.code = code
            self.controller.start()
            self.controller.step()
            self.assertEqual(self.controller.status()["phase"], "error")
            self.assertFalse(self.config.exists())
            self.assertNotIn("private-provider-description", json.dumps(self.controller.status()))

    def test_missing_or_invalid_ha_options_show_setup_without_touching_legacy_config(self):
        self.options.unlink()
        self.assertEqual(self.controller.status()["phase"], "setup")
        for config in ({}, {**CLIENT, "client_secret": []}, {**CLIENT, "expected_email": "invalid"}):
            self.write_options(config)
            self.assertEqual(self.route("/drive/connect").code, 200)
            self.assertEqual(self.route("/drive/connect/start").code, 400)
        self.assertFalse(self.google.calls)
        self.assertFalse(self.config.exists())

    def test_private_state_permissions_and_symlinks_are_enforced(self):
        self.waiting()
        self.state.chmod(0o644)
        self.assertEqual(self.controller.status()["phase"], "error")
        with self.assertRaises(chatgpt_export.PublishError):
            self.controller.step()
        self.state.unlink()
        self.state.symlink_to(self.options)
        self.assertEqual(self.controller.status()["phase"], "error")

    def test_http_rejects_cross_origin_foreign_host_missing_nonce_and_oversized_forms(self):
        for kwargs in ({"host": "attacker.invalid:8099"}, {"origin": "https://attacker.invalid"},
                       {"origin": ""}, {"csrf": "wrong"}):
            self.assertEqual(self.route("/drive/connect/start", **kwargs).code, 403)
        for field, value in (("Content-Length", "5000"), ("Content-Length", "bad"), ("Content-Type", "application/json")):
            reply = Reply("/drive/connect/start", self.controller.csrf)
            reply.headers[field] = value
            device.handle_post(reply, self.controller, reply.path)
            self.assertEqual(reply.code, 403)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.google.calls)
        page = self.route("/drive/connect", host="attacker.invalid:8099")
        self.assertEqual(page.code, 403)
        self.assertNotIn(self.controller.csrf.encode(), page.wfile.getvalue())

    def test_cancellation_route_and_html_escape(self):
        self.waiting()
        self.assertEqual(self.route("/drive/connect/cancel").code, 303)
        self.assertEqual(self.controller.status()["phase"], "cancelled")
        page = ui.google_connection_page({"phase": "waiting", "user_code": "<script>", "verification_url": "https://www.google.com/device"}, "nonce").decode()
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


class TransportTests(unittest.TestCase):
    def test_google_http_errors_are_parsed_but_never_echoed_and_hosts_are_fixed(self):
        opener = Mock()
        response = io.BytesIO(b'{"error":"authorization_pending","error_description":"secret"}')
        response.code = 428
        opener.open.side_effect = HTTPError("https://oauth2.googleapis.com/token", 428, "Error", {}, response)
        with patch.object(device, "build_opener", return_value=opener):
            value = device.google_request("token", {"client_id": "synthetic"})
        self.assertEqual(value["error"], "authorization_pending")
        self.assertEqual(opener.open.call_args.args[0].full_url, "https://oauth2.googleapis.com/token")
        for data in (b"not-json secret", b"x" * (64 * 1024 + 1)):
            response = io.BytesIO(data)
            response.code = 200
            opener.open.side_effect = None
            opener.open.return_value = response
            with patch.object(device, "build_opener", return_value=opener), self.assertRaises(device.DeviceError) as error:
                device.google_request("code", {})
            self.assertNotIn("secret", str(error.exception))
        opener.open.side_effect = OSError("private-network-error")
        with patch.object(device, "build_opener", return_value=opener), self.assertRaises(device.DeviceError) as error:
            device.google_request("code", {})
        self.assertNotIn("private-network-error", str(error.exception))

    def test_exporter_is_woken_without_waiting_fifteen_minutes(self):
        first, second, stop = threading.Event(), threading.Event(), threading.Event()
        def publish(*args):
            if first.is_set():
                second.set()
                stop.set()
            first.set()
        with patch.object(chatgpt_export, 'PAUSED_FOR_CODEX', False), patch.object(chatgpt_export, "publish_once", side_effect=publish):
            worker = threading.Thread(target=chatgpt_export.run, args=("unused", "unused", stop))
            worker.start()
            try:
                self.assertTrue(first.wait(2))
                chatgpt_export.request_publish()
                self.assertTrue(second.wait(3))
            finally:
                stop.set()
                worker.join(2)
                chatgpt_export.WAKE.clear()


if __name__ == "__main__":
    unittest.main()
