"""Root-only directory preparation; application and Codex then run unprivileged."""
import os
import stat
from pathlib import Path


def prepare(root=Path('/data'), uid=10001, gid=10001):
    for name in ('home', 'workspace'):
        folder = root / name
        folder.mkdir(mode=0o700, exist_ok=True)
        if not stat.S_ISDIR(folder.lstat().st_mode):
            raise RuntimeError('Persistent directory must not be a symlink')
        os.chown(folder, uid, gid)
        folder.chmod(0o700)


if __name__ == '__main__':
    prepare()
