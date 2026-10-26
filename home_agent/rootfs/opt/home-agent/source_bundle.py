"""Explicit local upload fallback when Pi OAuth cannot read the legacy Drive root.

ZIP entries are never extracted by pathname. Provider references in a bundle
are user-supplied provenance, not proof of live Google account access.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

MAX_BUNDLE = 256 * 1024 * 1024
MAX_MANIFEST = 2 * 1024 * 1024


def inventory(path):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if (len(entries) > 2001 or len({e.filename for e in entries}) != len(entries)
                or sum(e.file_size for e in entries) > MAX_BUNDLE):
            raise ValueError('Originalpaketet är för stort eller har dubblerade poster.')
        entry = archive.getinfo('manifest.json')
        if entry.file_size > MAX_MANIFEST:
            raise ValueError('Manifestet är för stort.')
        data = json.loads(archive.read(entry))
        if not isinstance(data, dict) or not isinstance(data.get('files'), list):
            raise ValueError('Ogiltigt paketmanifest.')
        for f in data['files']:
            if not isinstance(f, dict) or not isinstance(f.get('id'), str):
                raise ValueError('Ogiltig filreferens i paketet.')
            e = archive.getinfo('originals/' + f['id'])
            digest = f.get('sha256', '')
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(c not in '0123456789abcdef' for c in digest)
                    or e.file_size != int(f['size'])):
                raise ValueError('Paketet saknar verifierbart original.')
        expected = {'manifest.json'} | {'originals/' + f['id'] for f in data['files']}
        if {e.filename for e in entries} != expected:
            raise ValueError('Paketet innehåller oväntade filer.')
        return data


def download(path, item, root):
    """Stream a single selected original, verify SHA-256, retain original bytes."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.bundle-', dir=root)
    f = item['file']
    try:
        with os.fdopen(fd, 'wb') as out, zipfile.ZipFile(path) as archive:
            with archive.open('originals/' + f['id']) as src:
                shutil.copyfileobj(src, out, length=256 * 1024)
            out.flush()
            os.fsync(out.fileno())
        digest = hashlib.sha256()
        with open(temporary, 'rb') as src:
            for block in iter(lambda: src.read(256 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != f['sha256'] or Path(temporary).stat().st_size != f['size']:
            raise ValueError('Paketoriginalets checksumma stämmer inte.')
        return dict(temporary_path=temporary, sha256=digest.hexdigest(), size=f['size'],
                    drive_id=f['id'], original_name=f['name'], media_type=f['mime'])
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
