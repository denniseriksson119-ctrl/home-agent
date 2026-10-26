"""Local original storage; domain links never depend on archive directories."""
import hashlib
import os
from pathlib import Path
import re
import stat


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(256 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verified_path(storage, root, digest):
    path = Path(storage)
    if (not re.fullmatch(r'[0-9a-f]{64}', digest or '')
            or not stat.S_ISREG(path.lstat().st_mode)
            or not path.resolve().is_relative_to(Path(root).resolve(strict=True))
            or file_hash(path) != digest):
        raise ValueError('Originalet saknas eller matchar inte sin checksumma.')
    return path


def destination(root, source_id, name, media, kind=''):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', source_id):
        raise ValueError('Ogiltigt Source-ID.')
    if media.startswith('image/'):
        category = 'Photos'
    elif 'manual' in kind:
        category = 'Documents/Manuals'
    elif 'invoice' in kind:
        category = 'Documents/Invoices'
    else:
        category = 'Documents/Other'
    # A bounded, portable name. No untrusted separators or path components.
    label = re.sub(r'[^A-Za-z0-9._-]+', '_', Path(name).name).strip('._')[:100] or 'original'
    directory = Path(root) / category
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.resolve().is_relative_to(Path(root).resolve(strict=True)):
        raise ValueError('Ogiltig arkivkatalog.')
    return directory / (source_id + '__' + label)


def install(temp, target, digest):
    """Publish an fsynced original without ever replacing an existing file."""
    if file_hash(temp) != digest:
        raise ValueError('Originalets checksumma stämmer inte.')
    with Path(temp).open('rb') as stream:
        os.fsync(stream.fileno())
    os.link(temp, target)
    fd = os.open(Path(target).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    except Exception:
        Path(target).unlink(missing_ok=True)
        raise
    finally:
        os.close(fd)
