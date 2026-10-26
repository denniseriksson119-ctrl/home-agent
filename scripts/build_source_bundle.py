#!/usr/bin/env python3
"""Build a private upload ZIP from an explicit inventory and downloaded originals.

Input originals are named by their provider file ID, not legacy folder paths.
No network, credentials, house database or Google writes are used here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'home_agent/rootfs/opt/home-agent'))
import source_archive
import source_bundle
import source_migration


def build(inventory, originals, output):
    records = inventory.get('drive', inventory).get('files', [])
    if not isinstance(records, list) or not records or len(records) > source_migration.MAX_FILES:
        raise ValueError('Supply an explicit nonempty inventory.')
    clean, seen = [], set()
    for item in records:
        fid = item['id']
        if (not isinstance(fid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', fid)
                or fid in seen):
            raise ValueError('Invalid or duplicate provider file ID.')
        seen.add(fid)
        path = Path(originals) / fid
        if path.is_symlink() or not path.is_file():
            raise ValueError('An inventoried original is missing.')
        if path.stat().st_size != int(item['size']):
            raise ValueError('An original has a different size from the inventory.')
        digest = source_archive.file_hash(path)
        if item.get('sha256') and item['sha256'] != digest:
            raise ValueError('An original has a different checksum from the inventory.')
        clean.append({k: item[k] for k in ('id', 'path', 'name', 'mime', 'size')})
        clean[-1]['sha256'] = digest
    if sum(int(f['size']) for f in clean) > source_bundle.MAX_BUNDLE - source_bundle.MAX_MANIFEST:
        raise ValueError('Split originals into smaller explicit batches.')
    # Exclusive creation prevents accidental replacement of a previous package.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.writestr('manifest.json', json.dumps({'files': clean}, ensure_ascii=False))
                for f in clean:
                    archive.write(Path(originals) / f['id'], 'originals/' + f['id'])
            stream.flush()
            os.fsync(stream.fileno())
        source_bundle.inventory(output)
    except Exception:
        Path(output).unlink(missing_ok=True)
        raise
    return len(clean)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--originals', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    count = build(json.loads(args.inventory.read_text()), args.originals, args.output)
    print(f'Private original bundle created: {count} files. Keep it outside Git.')
