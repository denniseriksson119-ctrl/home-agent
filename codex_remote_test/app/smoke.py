"""Offline container check, never signs in or starts remote access."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def main():
    deadline = time.monotonic() + 40
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while True:
        try:
            with opener.open('http://127.0.0.1:8099/api/status', timeout=2) as response:
                state = json.load(response)
            if state['supported']:
                break
        except OSError:
            pass
        if time.monotonic() > deadline:
            raise SystemExit('Setup UI or Codex CLI did not become ready')
        time.sleep(.25)
    assert state['version'] == '0.164.0', state['version']
    assert not state['authenticated']
    assert not state['remote_running']
    with opener.open('http://127.0.0.1:8099/') as response:
        assert response.headers['Cache-Control'] == 'no-store'
        assert b'CODEX_PI_TEST_OK' in response.read()
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
