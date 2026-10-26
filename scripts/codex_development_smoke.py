"""CI-only development acceptance inside the actual unprivileged add-on image."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, '/app')
from development import check

PROJECT = Path('/data/workspace/projects/home-agent')
MARKER = PROJECT / '.codex-ci-development'


def run(args, **kwargs):
    return subprocess.run(args, cwd=PROJECT, check=True, **kwargs)


def main():
    assert os.geteuid() == 10001
    if '--after-restart' in sys.argv:
        assert MARKER.read_text() == 'synthetic code work survives restart\n'
        branch = run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
        assert branch == 'ci-development'
        run(['git', 'diff', '--exit-code', 'HEAD', '--', MARKER.name])
        print('PASS: development branch, committed workspace file and project survive restart')
        return
    report = check()
    assert report['ready'], json.dumps(report)
    print('PASS: unprivileged Git/rg/Python/PyYAML/Node/npm/PDF tools and actual venv with pip available; Python ' + report['checks']['python']['version'])
    # Source archive contains public source only; no checkout .git credentials.
    PROJECT.mkdir()
    run(['tar', '--extract', '--file', '/tmp/codex-source.tar', '--no-same-owner'])
    run(['git', 'init', '--quiet', '--initial-branch=main'])
    run(['git', 'config', '--local', 'user.name', 'Synthetic CI'])
    run(['git', 'config', '--local', 'user.email', 'synthetic@example.invalid'])
    run(['git', 'add', '.'])
    run(['git', 'commit', '--quiet', '-m', 'Synthetic public-source checkout'])
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'home_agent/rootfs/opt/home-agent', '-p', 'test_*.py', '-v'])
    run(['git', 'switch', '--quiet', '-c', 'ci-development'])
    MARKER.write_text('synthetic code work survives restart\n')
    run(['git', 'add', '--', MARKER.name])
    run(['git', 'commit', '--quiet', '-m', 'Synthetic development change'])
    assert run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.strip() == ''
    print('PASS: entire project test suite runs inside the add-on and synthetic Git branch/edit/commit succeeds')


if __name__ == '__main__':
    main()
