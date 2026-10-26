"""Offline toolchain check for the unprivileged Pi development workspace."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ENV = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/data/home'}


def version(command, flag='--version'):
    executable = shutil.which(command, path=ENV['PATH'])
    if not executable:
        return {'available': False}
    try:
        result = subprocess.run([executable, flag], capture_output=True, text=True, timeout=10, env=ENV)
        lines = (result.stdout + result.stderr).strip().splitlines()
        return {'available': result.returncode == 0, 'version': lines[0][:200] if lines else 'unknown'}
    except (OSError, subprocess.SubprocessError):
        return {'available': False}


def check(workspace=Path('/data/workspace')):
    checks = {'python': {'available': True, 'version': sys.version.split()[0]}}
    try:
        import yaml
        checks['PyYAML'] = {'available': yaml.safe_load('check: true') == {'check': True}, 'version': yaml.__version__}
    except ImportError:
        checks['PyYAML'] = {'available': False}
    for command in ('git', 'rg', 'node', 'npm'):
        checks[command] = version(command)
    for command in ('pdftotext', 'pdftoppm'):
        checks[command] = version(command, '-v')
    try:
        with tempfile.TemporaryDirectory(prefix='codex-venv-') as folder:
            environment = Path(folder) / 'venv'
            subprocess.run([sys.executable, '-m', 'venv', '--system-site-packages', str(environment)],
                           capture_output=True, timeout=40, check=True, env=ENV)
            subprocess.run([str(environment / 'bin/python'), '-c', 'import yaml; import pip'],
                           capture_output=True, timeout=10, check=True, env=ENV)
        checks['venv'] = {'available': True}
    except (OSError, subprocess.SubprocessError):
        checks['venv'] = {'available': False}
    projects = workspace / 'projects'
    checks['projects'] = {'available': projects.is_dir() and not projects.is_symlink() and os.access(projects, os.W_OK)}
    return {'ready': all(item['available'] for item in checks.values()), 'uid': os.geteuid(),
            'projects': str(projects), 'checks': checks,
            'external_connections': 'GitHub/Drive and actual PR permissions are not probed by this offline check.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.parse_args()
    report = check()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
