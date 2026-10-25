#!/usr/bin/env python3
"""Independent release guard for the new add-on; Home Agent keeps its version."""
import argparse
import re
import subprocess
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    args = parser.parse_args()
    path = 'codex_remote_test/config.yaml'
    config = yaml.safe_load(Path(path).read_text())
    version = str(config.get('version', ''))
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise SystemExit('Codex test version must be MAJOR.MINOR.PATCH')
    # No production data mounts, host listeners, Docker, host networking or HA API.
    for key in ('map', 'ports', 'host_network', 'docker_api', 'hassio_api',
                'homeassistant_api', 'privileged', 'full_access', 'devices'):
        if config.get(key):
            raise SystemExit('Connection test must not request ' + key)
    if config.get('boot') != 'manual' or config.get('ingress') is not True:
        raise SystemExit('Connection test must use Ingress and manual boot')
    subprocess.run(['git', 'cat-file', '-e', args.base + '^{commit}'], check=True)
    old = subprocess.run(['git', 'show', args.base + ':' + path], capture_output=True, text=True)
    if old.returncode == 0:
        base = str(yaml.safe_load(old.stdout)['version'])
        changes = subprocess.check_output(['git', 'diff', '--name-only', args.base + '...HEAD'], text=True).splitlines()
        runtime = any(p.startswith('codex_remote_test/') and not p.endswith('.md') for p in changes)
        if runtime and tuple(map(int, version.split('.'))) <= tuple(map(int, base.split('.'))):
            raise SystemExit('Codex test runtime changed without a version increase')
    print('Codex test version/isolation guard passed:', version)


if __name__ == '__main__':
    main()
