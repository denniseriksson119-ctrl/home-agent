"""One-time OAuth setup on the user's own computer (not on the Pi).

Requires a Google Cloud OAuth Desktop client. Opens a local loopback callback,
verifies state and PKCE, then writes a 0600 configuration file. Never prints tokens.
Run with: python3 drive_oauth_setup.py CLIENT_ID CLIENT_SECRET EXPECTED_EMAIL
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen

SCOPES = "openid email https://www.googleapis.com/auth/drive.readonly"


def setup(client_id, client_secret, expected_email, output):
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(32)
    result = {}
    finished = threading.Event()

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlparse(self.path).path != "/callback":
                self.send_error(404)
                return
            params = parse_qs(urlparse(self.path).query)
            if params.get("state", [""])[0] != state:
                self.send_error(400, "State mismatch")
                return
            result["code"] = params.get("code", [""])[0]
            result["error"] = params.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Authorization received. Return to the terminal.")
            finished.set()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Callback)
    redirect = "http://127.0.0.1:%d/callback" % server.server_port
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPES, "access_type": "offline", "prompt": "consent select_account",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state})
    print("Opening Google authorization in your browser. Sign in ONLY with the dedicated import account.")
    webbrowser.open(url)
    server.timeout = 1
    for _ in range(180):
        if finished.is_set():
            break
        server.handle_request()
    server.server_close()
    if not result.get("code"):
        raise RuntimeError("Google authorization failed or timed out: " + result.get("error", ""))
    payload = urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "code": result["code"], "redirect_uri": redirect,
        "code_verifier": verifier, "grant_type": "authorization_code"}).encode()
    with urlopen(Request("https://oauth2.googleapis.com/token", data=payload), timeout=30) as response:
        tokens = json.load(response)
    if not tokens.get("refresh_token"):
        raise RuntimeError("No refresh token returned; revoke old consent and retry")
    with urlopen(Request("https://www.googleapis.com/oauth2/v3/userinfo",
                         headers={"Authorization": "Bearer " + tokens["access_token"]}), timeout=30) as response:
        identity = json.load(response)
    if not identity.get("email_verified") or identity.get("email", "").casefold() != expected_email.casefold():
        raise RuntimeError("Wrong Google account: credentials NOT saved")
    config = {"client_id": client_id, "client_secret": client_secret,
              "refresh_token": tokens["refresh_token"], "expected_email": expected_email}
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(output, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(config, stream)
    print("Credentials saved with mode 0600 to", output)
    print("Transfer securely to /data/drive_import_oauth.json on the Pi; never share in chat.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python3 drive_oauth_setup.py CLIENT_ID CLIENT_SECRET EXPECTED_EMAIL")
    setup(sys.argv[1], sys.argv[2], sys.argv[3], Path("drive_import_oauth.json"))
