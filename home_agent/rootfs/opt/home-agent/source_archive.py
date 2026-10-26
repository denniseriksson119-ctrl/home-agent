"""Local original storage; domain links never depend on archive directories."""
import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata
from datetime import date

EXTENSIONS = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif',
              'image/webp': '.webp', 'application/pdf': '.pdf', 'text/plain': '.txt'}
CATEGORIES = {'Photos', 'Documents/Manuals', 'Documents/Invoices',
              'Documents/Receipts', 'Documents/Warranties', 'Documents/Other', 'Other'}


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


def category(media, kind=''):
    if media.startswith('image/'):
        return 'Photos'
    elif 'manual' in kind:
        return 'Documents/Manuals'
    elif 'invoice' in kind:
        return 'Documents/Invoices'
    elif 'receipt' in kind:
        return 'Documents/Receipts'
    elif 'warranty' in kind:
        return 'Documents/Warranties'
    return 'Documents/Other'


def description_slug(value):
    if not isinstance(value, str) or len(value) > 300:
        raise ValueError('Beskrivningen är för lång.')
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')[:80].rstrip('-')
    if sum(c.isalpha() for c in value) < 3:
        raise ValueError('Ange en kort beskrivning med minst tre bokstäver.')
    return value


def archive_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Ange datum som ÅÅÅÅ-MM-DD eller godkänn okänt datum.')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError('Datumet finns inte i kalendern.') from None


def short_id(source_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', source_id):
        raise ValueError('Ogiltigt Source-ID.')
    compact = re.sub(r'[^a-z0-9]', '', source_id.lower())
    return compact[-10:] if len(compact) >= 10 else hashlib.sha256(source_id.encode()).hexdigest()[:10]


def archive_relative(source_id, media, folder, when, description):
    """Pure reviewed naming policy. None is an explicitly approved unknown date."""
    if folder not in CATEGORIES or (media.startswith('image/') and folder != 'Photos'):
        raise ValueError('Ogiltig arkivkategori.')
    stamp = archive_date(when) if when is not None else 'undated'
    slug = description_slug(description)
    filename = stamp + '_' + slug + '__src-' + short_id(source_id) + EXTENSIONS.get(media, '.bin')
    directory = Path(folder)
    if folder == 'Photos':
        directory = directory / stamp[:4] / stamp[5:7] if when is not None else directory / 'Undated'
    return (directory / filename).as_posix()


def archive_fields(source_id, media, filename):
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}|undated)_([a-z0-9-]+)__src-([a-z0-9]{10})(\.[a-z0-9]+)', filename)
    if not match:
        return None
    stamp, slug, hint, extension = match.groups()
    try:
        when = None if stamp == 'undated' else archive_date(stamp)
        if hint == short_id(source_id) and extension == EXTENSIONS.get(media, '.bin') and description_slug(slug) == slug:
            return dict(date=when, description=slug)
    except ValueError:
        pass
    return None


def name_checks(relative, source_id, original_name, media, folders):
    """Distinguish reviewed archive names from old technical intake names."""
    path = Path(relative)
    fields = archive_fields(source_id, media, path.name)
    if fields:
        try:
            for folder in folders:
                expected = archive_relative(source_id, media, folder, fields['date'], fields['description'])
                if relative == expected:
                    label = 'architectural_undated' if fields['date'] is None else 'architectural'
                    return label, label, [Path(expected).parent.as_posix()]
        except ValueError:
            pass
    if path.parent == Path('.') and path.name == source_id:
        return 'legacy_preserved', 'legacy_preserved', sorted(folders)
    layout = 'technical_preserved' if path.parent.as_posix() in folders else 'deviation'
    name = 'technical_preserved' if path.name == source_id + '__' + portable_name(original_name) else 'deviation'
    return layout, name, sorted(folders)


def portable_name(name):
    # A bounded, portable name. No untrusted separators or path components.
    return re.sub(r'[^A-Za-z0-9._-]+', '_', Path(name).name).strip('._')[:100] or 'original'


def destination(root, source_id, name, media, kind=''):
    """Technical intake name; reviewed permanent names use archive_relative."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', source_id):
        raise ValueError('Ogiltigt Source-ID.')
    label = portable_name(name)
    directory = Path(root) / category(media, kind)
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
