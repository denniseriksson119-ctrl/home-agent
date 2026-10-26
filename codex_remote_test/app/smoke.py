"""Offline container check, never signs in or starts remote access."""
import json
import base64
import datetime
import hashlib
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def write_synthetic_auth():
    """Offline cache fixture, unsigned and unusable against OpenAI. CI only."""
    assert os.geteuid() == 10001
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {'sub': 'synthetic-user', 'email': 'synthetic@example.invalid',
              'exp': int(now.timestamp()) + 3600,
              'https://api.openai.com/auth': {'chatgpt_account_id': 'synthetic-account',
                                            'chatgpt_user_id': 'synthetic-user', 'chatgpt_plan_type': 'plus'}}
    jwt = encode({'alg': 'none', 'typ': 'JWT'}) + '.' + encode(claims) + '.synthetic-signature'
    path = Path('/data/home/.codex/auth.json')
    # Exclusive creation prevents this test helper from replacing existing auth.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump({'auth_mode': 'chatgpt', 'OPENAI_API_KEY': None,
                   'tokens': {'id_token': jwt, 'access_token': jwt,
                              'refresh_token': 'synthetic-not-a-token', 'account_id': 'synthetic-account',
                              'login_owner_id': '00000000-0000-4000-8000-000000000001'},
                   'last_refresh': now.isoformat()}, stream)


def main():
    if '--write-synthetic-auth' in sys.argv:
        write_synthetic_auth()
        return
    deadline = time.monotonic() + 40
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while True:
        try:
            with opener.open('http://127.0.0.1:8099/api/status', timeout=2) as response:
                state = json.load(response)
            if state['supported'] and state['auth_state'] != 'checking':
                break
        except OSError:
            pass
        if time.monotonic() > deadline:
            raise SystemExit('Setup UI or Codex CLI did not become ready')
        time.sleep(.25)
    assert state['version'] == '0.164.0', state['version']
    assert state['auth_state'] == ('signed_in' if '--expect-auth' in sys.argv else 'signed_out'), state['auth_state']
    assert not state['remote_running']
    with opener.open('http://127.0.0.1:8099/') as response:
        assert response.headers['Cache-Control'] == 'no-store'
        page = response.read()
        assert b'CODEX_PI_TEST_OK' in page
    found = False
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            command = (process / 'cmdline').read_bytes()
            status = (process / 'status').read_text()
        except (FileNotFoundError, PermissionError):
            continue
        if b'/app/server.py' in command:
            uid = next(line for line in status.splitlines() if line.startswith('Uid:')).split()[1]
            if uid == '10001':
                found = True
    assert found, 'Server must run unprivileged'
    assert Path('/data/workspace/README.md').read_text().find('CODEX_PI_TEST_OK') >= 0
    if '--seed-auth' in sys.argv:
        import re
        subprocess.run(['setpriv', '--reuid=10001', '--regid=10001', '--init-groups',
                        'python3', '/app/smoke.py', '--write-synthetic-auth'], check=True)
        auth_path = Path('/data/home/.codex/auth.json')
        before = hashlib.sha256(auth_path.read_bytes()).hexdigest()
        csrf = re.search(rb"const csrf='([0-9a-f]{64})'", page).group(1).decode()
        for _ in range(2):
            request = urllib.request.Request('http://127.0.0.1:8099/api/action',
                                            json.dumps({'action': 'check'}).encode(),
                                            headers={'Content-Type': 'application/json', 'X-CSRF-Token': csrf})
            with opener.open(request, timeout=2) as response:
                assert response.status == 202
            deadline = time.monotonic() + 20
            while True:
                with opener.open('http://127.0.0.1:8099/api/status') as response:
                    state = json.load(response)
                if state['auth_state'] == 'signed_in':
                    break
                if time.monotonic() > deadline:
                    raise SystemExit('Real CLI could not reload the synthetic credential cache: ' + state['auth_state'])
                time.sleep(.25)
        assert hashlib.sha256(auth_path.read_bytes()).hexdigest() == before
        print('PASS: real CLI re-reads synthetic cached ChatGPT auth without a new login or credential replacement')
    marker = Path('/data/workspace/container-persistence.txt')
    if '--after-restart' in sys.argv:
        assert marker.read_text() == 'synthetic persistent file'
    else:
        # Docker exec defaults to root; use the application identity for the write.
        subprocess.run(['setpriv', '--reuid=10001', '--regid=10001', '--init-groups',
                        'python3', '-c', "from pathlib import Path; Path('/data/workspace/container-persistence.txt').write_text('synthetic persistent file')"], check=True)
    print('PASS: real CLI, Ingress UI, unprivileged process, synthetic data and persistence')


if __name__ == '__main__':
    main()
