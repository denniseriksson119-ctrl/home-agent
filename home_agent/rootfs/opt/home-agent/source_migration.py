"""Explicit, resumable legacy Drive-original import. Never modifies Drive.

Plans are private runtime artifacts. The current local object records, not an
uploaded replacement house model, determine document identity and relationships.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading

import yaml
import drive_import
import drive_auth
import source_archive
import source_bundle
import zipfile

MAX_INVENTORY = 2 * 1024 * 1024
MAX_FILES = 2000


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def objects(db):
    rows = db.execute('''SELECT i.permanent_id,i.legacy_id,i.object_type,o.name,o.yaml_text
        FROM object_identity i JOIN objects o
        ON o.object_id=i.legacy_id AND o.object_type=i.object_type
        ORDER BY i.permanent_id''').fetchall()
    return rows, hashlib.sha256(canonical(rows)).hexdigest()


def build_plan(db_path, inventory):
    if not isinstance(inventory, dict):
        raise ValueError('Inventeringen måste vara ett JSON-objekt.')
    payload = inventory.get('drive', inventory)
    if not isinstance(payload, dict):
        raise ValueError('Ogiltig inventering.')
    files = payload.get('files')
    if not isinstance(files, list) or len(files) > MAX_FILES:
        raise ValueError('Inventeringen saknar en begränsad fillista.')
    clean, seen = [], set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError('Ogiltig filpost.')
        fid, path = item.get('id'), item.get('path')
        name, media = item.get('name'), item.get('mime')
        if (not isinstance(fid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', fid)
                or fid in seen or not isinstance(path, str) or len(path) > 2000
                or not isinstance(name, str) or not name or len(name) > 500
                or not isinstance(media, str) or len(media) > 100):
            raise ValueError('Ogiltig eller dubblerad filreferens.')
        seen.add(fid)
        size = int(item.get('size') or 0)
        if size < 0 or size > drive_import.MAX_FILE_BYTES:
            raise ValueError('En fil överstiger importgränsen.')
        entry = dict(id=fid, path=path, name=name, mime=media, size=size)
        if item.get('sha256'):
            if not isinstance(item['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['sha256']):
                raise ValueError('Ogiltig checksumma i inventeringen.')
            entry['sha256'] = item['sha256']
        clean.append(entry)
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        rows, revision = objects(db)
        existing = db.execute('''SELECT s.source_id,s.sha256,s.custody_status,s.storage_ref,
            i.external_ref FROM source s JOIN ingest_occurrence i ON i.source_id=s.source_id
            WHERE i.external_provider='google_drive' ''').fetchall()
    aliases = {}
    for row in rows:
        aliases.setdefault(row[1], []).append(row)
    items, unresolved, used = [], [], set()
    for pid, legacy, obj_type, name, text in rows:
        if obj_type != 'document':
            continue
        doc = yaml.safe_load(text)
        if not isinstance(doc, dict):
            raise ValueError('En dokumentpost kan inte läsas.')
        refs = doc.get('related_object_refs', []) or []
        if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
            raise ValueError('Ogiltiga dokumentrelationer.')
        targets = [dict(id=pid, type='document', name=name)]
        unknown = []
        for ref in refs:
            candidates = aliases.get(ref, [])
            if len(candidates) != 1:
                unknown.append(ref)
            else:
                r = candidates[0]
                targets.append(dict(id=r[0], type=r[2], name=r[3]))
        source = doc.get('source_file', {}) or {}
        if not isinstance(source, dict):
            unresolved.append(dict(document=name, reason='Dokumentet saknar strukturerad originalreferens.'))
            continue
        matches = [f for f in clean if
                   (source.get('google_drive_file_id') == f['id']) or
                   (source.get('drive_path') == f['path'])]
        # If both references exist they must agree, not silently prefer either.
        if source.get('google_drive_file_id') and source.get('drive_path'):
            matches = [f for f in matches if f['id'] == source['google_drive_file_id']
                       and f['path'] == source['drive_path']]
        requests = [(matches, False, source.get('original_filename', ''))]
        extra = source.get('additional_project_source_images', []) or []
        if not isinstance(extra, list) or any(not isinstance(x, str) for x in extra):
            raise ValueError('Ogiltiga kompletterande bildreferenser.')
        # These are explicit legacy references, but filename-only identification
        # is separately labelled for human review and never preselected.
        requests += [([f for f in clean if f['name'] == filename], True, filename) for filename in extra]
        for found, review, filename in requests:
            if len(found) != 1 or unknown:
                unresolved.append(dict(document=name, filename=filename,
                    reason='Okända/tvetydiga mål: ' + ', '.join(unknown) if unknown else
                           'Original saknas eller referensen är tvetydig.'))
                continue
            f = found[0]
            if f['mime'].startswith('application/vnd.google-apps.'):
                unresolved.append(dict(document=name, filename=f['name'], reason='Google-native original stöds inte.'))
                continue
            previous = [dict(id=r[0], custody=r[2]) for r in existing if r[4] == f['id']]
            items.append(dict(key=str(len(items)), file=f, document_id=pid, document=name,
                              kind=str(doc.get('type') or ''), targets=targets,
                              review=review, previous=previous, status='pending'))
            used.add(f['id'])
    return dict(format=1, id=secrets.token_hex(16), revision=revision, items=items,
                unresolved=unresolved, unassigned=[f for f in clean if f['id'] not in used])


def save_plan(directory, plan):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (plan['id'] + '.json')
    temp = directory / (plan['id'] + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(canonical(plan))
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_plan(directory, ident):
    if not re.fullmatch(r'[0-9a-f]{32}', ident or ''):
        raise ValueError('Ogiltig importplan.')
    return json.loads((Path(directory) / (ident + '.json')).read_text())


def register(db_path, root, downloaded, item, revision, new_id, channel='legacy_drive_migration', reserved_id=None):
    """Commit verified bytes, all explicit links, provenance and audit together.

    A crash after commit but before plan progress is saved is safe to retry.
    Existing originals are verified and reused without relocation or ID changes.
    """
    temp = Path(downloaded['temporary_path'])
    digest = downloaded['sha256']
    source_archive.verified_path(temp, root, digest)
    f = item['file']
    if (downloaded['drive_id'] != f['id'] or downloaded['original_name'] != f['name']
            or downloaded['size'] != f['size'] or downloaded['media_type'] != f['mime']
            or (f.get('sha256') and f['sha256'] != digest)):
        raise ValueError('Drive-filen har ändrats. Skapa en ny förhandsgranskning.')
    installed = None
    with closing(sqlite3.connect(db_path, timeout=30)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            rows, current = objects(db)
            if current != revision:
                raise ValueError('Registret har ändrats. Skapa en ny förhandsgranskning.')
            ids = {r[0] for r in rows}
            if not item['targets'] or any(t['id'] not in ids for t in item['targets']):
                raise ValueError('Ett kopplingsmål saknas.')
            # A provider file changing bytes must not silently replace evidence.
            prior = db.execute('''SELECT s.sha256 FROM ingest_occurrence i JOIN source s
                ON s.source_id=i.source_id WHERE i.external_provider='google_drive'
                AND i.external_ref=?''', (f['id'],)).fetchall()
            if any(r[0] != digest for r in prior):
                raise ValueError('Drive-originalet skiljer sig från tidigare registrerad källa.')
            row = db.execute('SELECT source_id,storage_ref,custody_status FROM source WHERE sha256=?',
                             (digest,)).fetchone()
            if row:
                sid, storage, custody = row
                if custody != 'local_verified':
                    raise ValueError('Befintlig källa saknar verifierad lokal kopia.')
                source_archive.verified_path(storage, root, digest)
            else:
                sid = reserved_id or new_id()
                target_path = source_archive.destination(root, sid, f['name'], f['mime'], item['kind'])
                if reserved_id and target_path.exists():
                    # Recover a file promotion that preceded a process crash and
                    # an uncommitted SQLite transaction, using the persisted ID.
                    source_archive.verified_path(target_path, root, digest)
                else:
                    source_archive.install(temp, target_path, digest)
                    installed = target_path
                db.execute('''INSERT INTO source(source_id,source_type,media_type,original_name,
                    sha256,storage_ref,custody_status) VALUES(?,?,?,?,?,?,?)''',
                    (sid, 'file', f['mime'], f['name'], digest, str(target_path), 'local_verified'))
            occurrence = db.execute('''SELECT occurrence_id FROM ingest_occurrence
                WHERE source_id=? AND external_provider='google_drive' AND external_ref=?
                AND channel=? ''', (sid, f['id'], channel)).fetchone()
            if not occurrence:
                db.execute('''INSERT INTO ingest_occurrence(occurrence_id,source_id,channel,
                    external_provider,external_ref,cleanup_status) VALUES(?,?,?,?,?,?)''',
                    (new_id(), sid, channel, 'google_drive', f['id'], 'not_required'))
            changed = not occurrence
            for target in item['targets']:
                cur = db.execute('INSERT OR IGNORE INTO source_link(source_id,object_id) VALUES(?,?)',
                                 (sid, target['id']))
                changed = changed or bool(cur.rowcount)
            if changed:
                db.execute('''INSERT INTO change_log(object_id,field_name,old_value,new_value)
                    VALUES(?,?,NULL,?)''', (item['document_id'], 'source_import',
                    canonical(dict(source_id=sid, drive_id=f['id'], legacy_path=f['path'], channel=channel,
                                   target_ids=[t['id'] for t in item['targets']])).decode()))
            db.commit()
            return sid
        except Exception:
            db.rollback()
            if installed is not None:
                installed.unlink(missing_ok=True)
            raise


def backup(db_path, directory, ident):
    """Consistent pre-import SQLite checkpoint, not a complete source backup."""
    target = Path(directory) / (ident + '-before-import.sqlite')
    if target.exists():
        with closing(sqlite3.connect(target)) as db:
            if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                raise ValueError('Kontrollkopian kunde inte verifieras.')
        return
    temp = target.with_suffix('.tmp')
    with closing(sqlite3.connect(db_path)) as source, closing(sqlite3.connect(temp)) as dest:
        source.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Kontrollkopian kunde inte verifieras.')
    os.chmod(temp, 0o600)
    os.replace(temp, target)


class Controller:
    def __init__(self):
        self.csrf = secrets.token_hex(32)
        self.lock = threading.Lock()
        self.worker = None
        self.stop = threading.Event()

    def running(self):
        return self.worker is not None and self.worker.is_alive()

    def start(self, db_path, root, directory, ident, selected, credentials, new_id):
        with self.lock:
            if self.running():
                raise ValueError('En överföring pågår redan.')
            plan = read_plan(directory, ident)
            keys = {x['key'] for x in plan['items'] if x['status'] != 'complete'}
            if not selected or not set(selected).issubset(keys):
                raise ValueError('Välj filer i förhandsgranskningen.')
            self.stop.clear()
            self.worker = threading.Thread(target=self.run, args=(db_path, root, directory,
                ident, set(selected), credentials, new_id), daemon=True)
            self.worker.start()

    def run(self, db_path, root, directory, ident, selected, credentials, new_id):
        plan = read_plan(directory, ident)
        try:
            with closing(sqlite3.connect(db_path)) as db:
                if objects(db)[1] != plan['revision']:
                    raise ValueError('Registret har ändrats. Skapa en ny förhandsgranskning.')
            backup(db_path, directory, ident)
            plan.pop('error', None)
            for item in plan['items']:
                if item['key'] not in selected or item['status'] == 'complete' or self.stop.is_set():
                    continue
                temp = None
                try:
                    item['status'] = 'copying'
                    item.pop('error', None)
                    item.setdefault('reserved_id', new_id())
                    save_plan(directory, plan)
                    # Fresh token per file; actual ancestry is rechecked, never
                    # inferred from the uploaded inventory's claimed paths.
                    channel = 'legacy_drive_migration'
                    if plan.get('bundle'):
                        downloaded = source_bundle.download(Path(directory) / (ident + '.zip'), item, root)
                        channel = 'legacy_bundle_migration'
                    else:
                        token, root_id = credentials()
                        drive_import.assert_under_shared_root(item['file']['id'], root_id, token)
                        downloaded = drive_import.download_original(item['file']['id'], token, root)
                    temp = Path(downloaded['temporary_path'])
                    sid = register(db_path, root, downloaded, item, plan['revision'], new_id,
                                   channel, reserved_id=item['reserved_id'])
                    item.update(status='complete', source_id=sid)
                    save_plan(directory, plan)
                except (ValueError, OSError, sqlite3.Error, drive_import.DriveImportError,
                        drive_auth.DriveAuthError, zipfile.BadZipFile, KeyError):
                    item.update(status='error', error='Överföringen misslyckades. Kontrollera Drive-åtkomst, ledigt utrymme och att registret/originalet inte ändrats.')
                    save_plan(directory, plan)
                    break
                finally:
                    if temp:
                        temp.unlink(missing_ok=True)
        except (ValueError, OSError, sqlite3.Error):
            plan['error'] = 'Överföringen kunde inte startas. Kontrollera lokal lagring och skapa en ny förhandsgranskning om registret ändrats.'
            save_plan(directory, plan)
