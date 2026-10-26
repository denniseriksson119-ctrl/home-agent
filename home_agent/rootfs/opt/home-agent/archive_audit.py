"""Bounded read-only checks of registered originals, never a filesystem browser."""
from contextlib import closing
import errno
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from urllib.parse import parse_qs, urlencode

import house_context
import source_archive
import ui
import yaml

PAGE_SIZE = 10
MAX_SOURCES = 2000
MAX_LINKS = 10000
MAX_BYTES = 256 * 1024 * 1024
PAGE_SECONDS = 8
MAX_REPORT = 512 * 1024
ID = r'[A-Za-z0-9_-]{1,100}'


class AuditError(Exception):
    pass


def parameters(query):
    values = parse_qs(query, keep_blank_values=True, strict_parsing=True)
    if set(values) - {'source_id', 'after'} or len(values) > 1:
        raise ValueError('Välj ett Source-ID eller en sidmarkör.')
    if any(len(v) != 1 or not re.fullmatch(ID, v[0]) for v in values.values()):
        raise ValueError('Ogiltigt Source-ID eller sidmarkör.')
    return {key: value[0] for key, value in values.items()}


def inspect_file(root, storage, expected, deadline):
    result = dict(relative_path=None, size_bytes=None, expected_size_bytes=None,
                  size_check='unknown_no_recorded_size', checksum_check='not_checked')
    if not storage:
        return {**result, 'file_check': 'no_local_reference'}
    root = Path(root).absolute()
    try:
        relative = Path(storage).relative_to(root)
        if not relative.parts or any(p in ('.', '..') for p in relative.parts):
            raise ValueError()
    except (ValueError, TypeError):
        return {**result, 'file_check': 'outside_store'}
    result['relative_path'] = relative.as_posix()
    parent_fd = file_fd = None
    try:
        # Every component is opened relative to an already checked directory.
        # No symlink can escape the Source store, including during a path swap.
        parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for component in relative.parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = child
        file_fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            return {**result, 'file_check': 'not_regular_file'}
        result.update(file_check='regular_file', size_bytes=before.st_size)
        if not re.fullmatch(r'[0-9a-f]{64}', expected or ''):
            return {**result, 'checksum_check': 'invalid_recorded_checksum'}
        if before.st_size > MAX_BYTES:
            return {**result, 'checksum_check': 'not_checked_size_limit'}
        digest, total = hashlib.sha256(), 0
        while True:
            if time.monotonic() >= deadline:
                return {**result, 'checksum_check': 'not_checked_time_limit'}
            block = os.read(file_fd, 256 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_BYTES:
                return {**result, 'checksum_check': 'not_checked_size_limit'}
            digest.update(block)
        after = os.fstat(file_fd)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if total != before.st_size or signature(before) != signature(after):
            return {**result, 'checksum_check': 'changed_during_check'}
        return {**result, 'checksum_check': 'matches' if digest.hexdigest() == expected else 'mismatch'}
    except FileNotFoundError:
        return {**result, 'file_check': 'missing'}
    except OSError as exc:
        return {**result, 'file_check': 'unsafe_path' if exc.errno in (errno.ELOOP, errno.ENOTDIR) else 'unreadable'}
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if parent_fd is not None:
            os.close(parent_fd)


def report(db_path, root, source_id=None, after=None):
    if source_id and after or any(x is not None and not re.fullmatch(ID, x) for x in (source_id, after)):
        raise ValueError('Ogiltigt rapporturval.')
    started, deadline = house_context.now(), time.monotonic() + PAGE_SECONDS
    try:
        with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 2 * 1024 * 1024)
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            if db.execute('SELECT version FROM schema_meta WHERE singleton=1').fetchone() != (5,):
                raise AuditError('Databasschemat stöds inte av arkivkontrollen.')
            if db.execute('''SELECT 1 FROM source WHERE length(source_id)>100 OR length(original_name)>500
                OR length(media_type)>100 OR length(sha256)>64 OR length(custody_status)>100
                OR length(storage_ref)>4096 LIMIT 1''').fetchone():
                raise AuditError('Källmetadata överskrider rapportgränsen.')
            sources = db.execute('''SELECT source_id,original_name,media_type,sha256,custody_status,storage_ref
                FROM source ORDER BY source_id LIMIT ?''', (MAX_SOURCES + 1,)).fetchall()
            links = db.execute('''SELECT l.source_id,l.object_id,i.object_type,substr(o.name,1,300),o.object_id
                FROM source_link l LEFT JOIN object_identity i ON i.permanent_id=l.object_id
                LEFT JOIN objects o ON o.object_id=i.legacy_id AND o.object_type=i.object_type
                ORDER BY l.source_id,l.object_id LIMIT ?''', (MAX_LINKS + 1,)).fetchall()
            if len(sources) > MAX_SOURCES or len(links) > MAX_LINKS:
                raise AuditError('Arkivet är för stort för denna rapportversion.')
            if any(any(v is not None and (not isinstance(v, str) or len(v) > 4096) for v in s) for s in sources):
                raise AuditError('Källmetadata överskrider rapportgränsen.')
            candidates = [s for s in sources if (not source_id or s[0] == source_id) and (not after or s[0] > after)]
            page_ids = {s[0] for s in candidates[:PAGE_SIZE]}
            document_kinds = {}
            for _, oid, kind, _, exists in [r for r in links if r[0] in page_ids][:1000]:
                if kind != 'document' or not exists or oid in document_kinds:
                    continue
                record = db.execute('''SELECT substr(o.yaml_text,1,65537) FROM objects o JOIN object_identity i
                    ON o.object_id=i.legacy_id AND o.object_type=i.object_type WHERE i.permanent_id=?''', (oid,)).fetchone()
                if not record or not record[0] or len(record[0]) > 65536:
                    raise AuditError('En dokumentpost är för stor för kontrollen.')
                doc = yaml.safe_load(record[0])
                if not isinstance(doc, dict):
                    raise AuditError('En dokumentpost kan inte läsas.')
                kind = doc.get('type') or ''
                if not isinstance(kind, str) or len(kind) > 100:
                    raise AuditError('Dokumenttypen kan inte kontrolleras.')
                document_kinds[oid] = kind
        # Same source/link snapshot has the same revision across report pages.
        revision = hashlib.sha256(house_context.canonical([sources, links])).hexdigest()
        more = len(candidates) > PAGE_SIZE
        entries = []
        for sid, name, media, digest, custody, storage in candidates[:PAGE_SIZE]:
            if not isinstance(sid, str) or not re.fullmatch(ID, sid):
                raise AuditError('En källa saknar giltig permanent identitet.')
            related = [r for r in links if r[0] == sid]
            expected_dirs, public_links, bad_links = set(), [], False
            for _, oid, kind, label, object_key in related:
                if not isinstance(oid, str) or not re.fullmatch(ID, oid):
                    raise AuditError('En källkoppling har ogiltig identitet.')
                exists = kind is not None and object_key is not None
                bad_links = bad_links or not exists
                public_links.append(dict(id=oid, type=str(kind or 'unknown')[:100],
                                         name=str(label or '')[:300], exists=exists))
                if kind == 'document' and exists:
                    if oid not in document_kinds:
                        raise AuditError('För många dokumentkopplingar för en sida. Kontrollera ett Source-ID i taget.')
                    expected_dirs.add(source_archive.category(str(media or ''), document_kinds[oid]))
            if not expected_dirs:
                expected_dirs.add(source_archive.category(str(media or '')))
            checks = inspect_file(root, storage, digest, deadline)
            relative = checks['relative_path']
            layout, naming = 'not_checked', 'not_checked'
            if relative:
                path = Path(relative)
                if path.parent.as_posix() in expected_dirs:
                    layout = 'current'
                elif path.parent == Path('.') and path.name == sid:
                    layout = 'legacy_preserved'
                else:
                    layout = 'deviation'
                naming = ('current' if path.name == sid + '__' + source_archive.portable_name(str(name or ''))
                          else 'legacy_preserved' if layout == 'legacy_preserved' else 'deviation')
            verified = checks['file_check'] == 'regular_file' and checks['checksum_check'] == 'matches' and custody == 'local_verified'
            status = 'verified' if verified else 'not_verified'
            if verified and layout == naming == 'legacy_preserved':
                status = 'legacy_preserved'
            if bad_links or not related or layout == 'deviation' or naming == 'deviation':
                status = 'deviation'
            entries.append(dict(source_id=sid, original_name=str(name or '')[:500],
                media_type=str(media or '')[:100], custody_check='local_verified' if custody == 'local_verified' else 'not_verified',
                expected_sha256=digest if re.fullmatch(r'[0-9a-f]{64}', digest or '') else None,
                **checks, layout_check=layout, name_check=naming, expected_directories=sorted(expected_dirs),
                links=public_links[:100], link_count=len(public_links), links_truncated=len(public_links) > 100,
                links_check='dangling' if bad_links else 'linked' if related else 'unlinked', status=status))
        result = dict(contract_version='1', scope='registered-source-archive', rules_version='local-0.8.9',
                      checked_at=started, revision=revision, total_sources=len(sources), entries=entries,
                      next_after=entries[-1]['source_id'] if more else None,
                      coverage='registered_sources_only', read_only=True)
        if len(house_context.canonical(result)) > MAX_REPORT:
            raise AuditError('Rapporten är för stor. Kontrollera ett Source-ID i taget.')
        return result
    except (sqlite3.Error, OSError, ValueError, TypeError, yaml.YAMLError, RecursionError) as exc:
        raise AuditError('Arkivkontrollen kunde inte läsa ett giltigt underlag.') from exc


LABELS = dict(regular_file='Filen finns', missing='Filen saknas', unsafe_path='Osäker sökväg/symbolisk länk',
    outside_store='Utanför källagret — sökvägen visas inte', no_local_reference='Lokal referens saknas',
    not_regular_file='Inte en vanlig fil', unreadable='Filen kunde inte läsas', matches='Stämmer', mismatch='Stämmer inte',
    current='Följer lokal regel', legacy_preserved='Bevarat äldre format', deviation='Avvikelse',
    not_checked='Inte kontrollerat', not_checked_time_limit='Inte verifierat inom tidsgränsen — prova enskild kontroll',
    not_checked_size_limit='Inte verifierat — storleksgräns', invalid_recorded_checksum='Giltig referenschecksumma saknas',
    changed_during_check='Filen ändrades under kontrollen', local_verified='Verifierad lokal källa',
    not_verified='Inte verifierad', linked='Kopplad', unlinked='Saknar koppling', dangling='Ogiltigt kopplingsmål', verified='Verifierad')


def page(db_path, root, query=''):
    try:
        result = report(db_path, root, **parameters(query))
    except (AuditError, ValueError):
        return ui.shell('Arkivkontroll', '<h1>Arkivkontroll</h1>', error='Kontrollen kunde inte slutföras. Öppna sidan igen eller prova ett enskilt Source-ID.'), 503
    body = '<h1>Arkivkontroll</h1><p>Skrivskyddad kontroll av registrerade original. Inga filer flyttas eller döps om.</p>'
    body += '<p>Visar %s av %s registrerade källor. Kontrollerat: %s.</p>' % (len(result['entries']), result['total_sources'], ui.esc(result['checked_at']))
    body += '<p>Regler: lokalt arkiv 0.8.9. Datum/beskrivande arkivnamn och år/månad-mappar ingår inte i denna regel. Oregistrerade filer inventeras inte.</p>'
    for entry in result['entries']:
        body += "<section class='card'><h2>%s</h2><p>Source-ID: %s</p><p>Relativ sökväg: <code>%s</code></p>" % (ui.esc(entry['original_name']), ui.esc(entry['source_id']), ui.esc(entry['relative_path'] or 'Visas inte'))
        for label, key in [('Fil', 'file_check'), ('SHA-256', 'checksum_check'), ('Lokal custody', 'custody_check'),
                           ('Mapp', 'layout_check'), ('Filnamn', 'name_check'), ('Kopplingar', 'links_check')]:
            body += '<p>%s: %s</p>' % (label, ui.esc(LABELS[entry[key]]))
        body += '<p>Förväntad mapp enligt lokal regel: %s</p>' % ', '.join(ui.esc(x) for x in entry['expected_directories'])
        body += '<p>Uppmätt storlek: %s byte. Referensstorlek saknas i registret; separat storleksjämförelse är okänd.</p>' % ui.esc(entry['size_bytes'] if entry['size_bytes'] is not None else 'Okänd')
        body += '<p>Registrerad SHA-256: <code>%s</code></p>' % ui.esc(entry['expected_sha256'] or 'Saknas')
        for link in entry['links']:
            body += "<p><a href='/object?id=%s'>%s</a> (%s, %s)</p>" % (ui.esc(link['id']), ui.esc(link['name'] or link['id']), ui.esc(link['type']), ui.esc(link['id']))
        if entry['links_truncated']:
            body += '<p>Kopplingslistan är begränsad till 100 av %s kopplingar.</p>' % entry['link_count']
        body += "<p><a href='/archive/check?%s'>Kontrollera bara denna källa</a></p></section>" % ui.esc(urlencode({'source_id': entry['source_id']}))
    if result['next_after']:
        body += "<p><a href='/archive/check?%s'>Nästa sida</a></p>" % ui.esc(urlencode({'after': result['next_after']}))
    body += "<p><a href='/codex/connect'>Hantera separat delning av arkivrapport med Codex</a></p>"
    return ui.shell('Arkivkontroll', body, active='more'), 200
