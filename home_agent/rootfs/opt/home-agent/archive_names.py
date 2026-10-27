"""Reviewed, recoverable local original renaming. No automatic startup writes."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import threading
import time

import source_archive as archive
import source_migration
import yaml

MAX_FILE = 256 * 1024 * 1024


def metadata(db, sid):
    if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', sid):
        raise ValueError('Ogiltigt Source-ID.')
    row = db.execute('''SELECT source_id,original_name,media_type,sha256,custody_status,storage_ref,captured_at
        FROM source WHERE source_id=?''', (sid,)).fetchone()
    if not row or any(v is not None and (not isinstance(v, str) or len(v) > 4096) for v in row):
        raise ValueError('Källan saknas eller kan inte läsas.')
    links = db.execute('''SELECT l.object_id,i.object_type,substr(o.name,1,300),
        CASE WHEN i.object_type='document' THEN substr(o.yaml_text,1,65537) ELSE NULL END
        FROM source_link l LEFT JOIN object_identity i ON i.permanent_id=l.object_id
        LEFT JOIN objects o ON o.object_id=i.legacy_id AND o.object_type=i.object_type
        WHERE l.source_id=? ORDER BY l.object_id LIMIT 101''', (sid,)).fetchall()
    if len(links) > 100:
        raise ValueError('För många kopplingar för namnförhandsgranskningen.')
    names, folders = set(), set()
    for _, kind, name, text in links:
        if kind == 'document' and text:
            if len(text) > 65536:
                raise ValueError('Dokumentposten är för stor.')
            doc = yaml.safe_load(text)
            if not isinstance(doc, dict) or not isinstance(doc.get('type', ''), str):
                raise ValueError('Dokumenttypen kan inte läsas.')
            folders.add(archive.category(row[2] or '', doc.get('type', '')))
            if name:
                names.add(name)
    if not folders:
        folders.add(archive.category(row[2] or ''))
    fingerprint = hashlib.sha256(source_migration.canonical([row, links])).hexdigest()
    return dict(id=row[0], original_name=row[1] or '', media=row[2] or '', sha256=row[3], custody=row[4],
                storage=row[5], captured_at=row[6], names=sorted(names), folders=sorted(folders), fingerprint=fingerprint)


def relative(root, storage):
    try:
        path = Path(storage).relative_to(Path(root).absolute())
        if not path.parts or '..' in path.parts or path.is_absolute():
            raise ValueError()
        return path.as_posix()
    except (ValueError, TypeError):
        raise ValueError('Källan saknar en säker referens inom källagret.') from None


def suggestion(record):
    existing = archive.archive_fields(record['id'], record['media'], Path(record['storage'] or '').name)
    if existing:
        return dict(date=existing['date'] or '', date_basis='existing_archive_name', description=existing['description'])
    when, basis = '', 'unknown'
    if record['captured_at']:
        try:
            when = archive.archive_date(record['captured_at'][:10])
            basis = 'registered_capture'
        except ValueError:
            pass
    if not when:
        match = re.match(r'(\d{4})(\d{2})(\d{2})_', record['original_name'])
        if match:
            try:
                when = archive.archive_date('-'.join(match.groups()))
                basis = 'filename_candidate'
            except ValueError:
                pass
    description = ''
    if len(record['names']) == 1:
        try:
            description = archive.description_slug(record['names'][0])
        except ValueError:
            pass
    return dict(date=when, date_basis=basis, description=description)


def candidates(db_path, root, after=None, completed=False):
    """Snapshot of the naming worklist; no file reads or mutation.

    Completion means an unambiguous, locally registered archive destination,
    not verification of the physical file. The archive audit keeps that job.
    Filter before pagination so completed IDs cannot consume the next batch.
    """
    if after is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', after):
        raise ValueError('Ogiltig sidmarkör.')
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        ids = [r[0] for r in db.execute('SELECT source_id FROM source ORDER BY source_id LIMIT 2001')]
        if len(ids) > 2000:
            raise ValueError('För många källor för namnlistan (högst 2000).')
        items, remaining, done = [], 0, 0
        for sid in ids:
            record = metadata(db, sid)
            try:
                current = relative(root, record['storage'])
            except ValueError:
                current = None
            layout, name, _ = archive.name_checks(current or '', sid, record['original_name'],
                                                  record['media'], record['folders'])
            finished = (current is not None and len(record['folders']) == 1
                        and record['custody'] == 'local_verified'
                        and re.fullmatch(r'[0-9a-f]{64}', record['sha256'] or '') is not None
                        and layout in ('architectural', 'architectural_undated') and name == layout)
            done += int(finished)
            remaining += int(not finished)
            if finished != completed or sid <= (after or '') or len(items) >= 11:
                continue
            items.append(dict(id=sid, name=record['original_name'], **suggestion(record),
                              folders=record['folders'], **{'from': current}))
    return dict(items=items[:10], next_after=items[9]['id'] if len(items) > 10 else None,
                remaining=remaining, completed=done, total=len(ids))


def build_plan(db_path, root, choices):
    if not isinstance(choices, list) or not 0 < len(choices) <= 10:
        raise ValueError('Välj högst tio original per plan.')
    items, used = [], set()
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        for choice in choices:
            sid = choice.get('source_id')
            if sid in used:
                raise ValueError('Dubblerad källa.')
            used.add(sid)
            record = metadata(db, sid)
            if record['custody'] != 'local_verified' or not re.fullmatch(r'[0-9a-f]{64}', record['sha256'] or ''):
                raise ValueError('Källan saknar verifierad lokal custody/checksumma.')
            if len(record['folders']) != 1:
                raise ValueError('Källans dokumenttyper ger olika arkivkategorier. Utred kopplingarna först.')
            unknown = choice.get('unknown_date') is True
            when = choice.get('date') or ''
            if unknown and when:
                raise ValueError('Välj antingen ett datum eller uttryckligen okänt datum.')
            when = None if unknown else archive.archive_date(when)
            description = archive.description_slug(choice.get('description', ''))
            folder = record['folders'][0]
            target = archive.archive_relative(sid, record['media'], folder, when, description)
            proposed = suggestion(record)
            basis = 'unknown_approved' if unknown else proposed['date_basis'] if when == proposed['date'] else 'owner'
            items.append(dict(source_id=sid, original_name=record['original_name'], media=record['media'],
                sha256=record['sha256'], fingerprint=record['fingerprint'], from_path=relative(root, record['storage']),
                to_path=target, date=when, date_basis=basis, description=description, folder=folder, status='pending'))
    return dict(id=secrets.token_hex(16), format=1, items=items)


def parent_fd(root, path, create=False):
    """Open only real directories under the configured Source root."""
    parts = Path(path).parts
    if not parts or Path(path).is_absolute() or any(p in ('.', '..') for p in parts):
        raise ValueError('Ogiltig relativ sökväg.')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in parts[:-1]:
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd, parts[-1]
    except Exception:
        os.close(fd)
        raise


def signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def verified_fd(fd, filename, digest):
    descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
            raise ValueError('Originalet är inte en stödd vanlig fil.')
        deadline, hashed, total = time.monotonic() + 8, hashlib.sha256(), 0
        while True:
            if time.monotonic() >= deadline:
                raise ValueError('Originalet kunde inte verifieras inom tidsgränsen.')
            block = os.read(descriptor, 256 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_FILE:
                raise ValueError('Originalet överskrider storleksgränsen.')
            hashed.update(block)
        if (hashed.hexdigest() != digest or total != before.st_size
                or signature(before) != signature(os.fstat(descriptor))):
            raise ValueError('Originalet ändrades eller matchar inte registrerad checksumma.')
        return descriptor, before
    except Exception:
        os.close(descriptor)
        raise


def operation_done(db, sid, plan_id, target):
    for value, in db.execute("SELECT new_value FROM change_log WHERE object_id=? AND field_name='archive_name' ORDER BY id DESC LIMIT 100", (sid,)):
        data = json.loads(value)
        if data.get('plan_id') == plan_id and data.get('to') == target:
            return True
    return False


def apply_item(db_path, root, plan_id, item):
    """Publish a verified hard link, atomically update reference+audit, then clean old alias.

    The saved plan is a write-ahead journal. Replaying either crash boundary is
    safe. No existing destination is overwritten; only our exact old inode is
    unlinked after the committed database no longer references that old path.
    """
    sid, target = item['source_id'], item['to_path']
    if target != archive.archive_relative(sid, item['media'], item['folder'], item['date'], item['description']):
        raise ValueError('Importplanens mål är ogiltigt.')
    root = Path(root).absolute()
    before_path, target_path = str(root / item['from_path']), str(root / target)
    old_parent = new_parent = original_fd = None
    created, committed, promoted_identity = False, False, None
    with closing(sqlite3.connect(db_path, timeout=3)) as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            current = metadata(db, sid)
            if current['sha256'] != item['sha256'] or current['original_name'] != item['original_name']:
                raise ValueError('Källmetadata har ändrats. Förhandsgranska på nytt.')
            if current['storage'] == target_path and before_path != target_path:
                if not operation_done(db, sid, plan_id, target):
                    raise ValueError('Källan har flyttats av en annan åtgärd.')
                new_parent, new_name = parent_fd(root, target)
                original_fd, verified = verified_fd(new_parent, new_name, item['sha256'])
                db.commit()
                committed = True
            else:
                if current['fingerprint'] != item['fingerprint'] or current['storage'] != before_path:
                    raise ValueError('Källan eller kopplingarna har ändrats. Förhandsgranska på nytt.')
                old_parent, old_name = parent_fd(root, item['from_path'])
                original_fd, verified = verified_fd(old_parent, old_name, item['sha256'])
                if before_path == target_path:
                    db.rollback()
                    return 'unchanged'
                new_parent, new_name = parent_fd(root, target, create=True)
                try:
                    os.link(old_name, new_name, src_dir_fd=old_parent, dst_dir_fd=new_parent, follow_symlinks=False)
                    created = True
                    promoted = os.stat(new_name, dir_fd=new_parent, follow_symlinks=False)
                    promoted_identity = promoted.st_dev, promoted.st_ino
                except FileExistsError:
                    # Recover promotion before a crash/SQLite rollback, never
                    # adopt or replace a different file even if bytes match.
                    existing = os.stat(new_name, dir_fd=new_parent, follow_symlinks=False)
                    if (existing.st_dev, existing.st_ino) != (verified.st_dev, verified.st_ino):
                        raise ValueError('Målfilen finns redan. Ingenting skrivs över.')
                installed = os.stat(new_name, dir_fd=new_parent, follow_symlinks=False)
                # Creating a hard link changes ctime; mtime/size/inode must stay.
                if (installed.st_dev, installed.st_ino, installed.st_size, installed.st_mtime_ns) != (
                        verified.st_dev, verified.st_ino, verified.st_size, verified.st_mtime_ns):
                    raise ValueError('Originalet ändrades under namnbytet.')
                checked_fd, checked = verified_fd(new_parent, new_name, item['sha256'])
                os.close(original_fd)
                original_fd, verified = checked_fd, checked
                os.fsync(new_parent)
                db.execute('UPDATE source SET storage_ref=? WHERE source_id=?', (target_path, sid))
                evidence = dict(plan_id=plan_id, source_id=sid, **{'from': item['from_path'], 'to': target},
                    date=item['date'], date_basis=item['date_basis'], description=item['description'], sha256=item['sha256'])
                db.execute('''INSERT INTO change_log(object_id,field_name,old_value,new_value)
                    VALUES(?,'archive_name',?,?)''', (sid, item['from_path'], source_migration.canonical(evidence).decode()))
                db.commit()
                committed = True
            if old_parent is None:
                try:
                    old_parent, old_name = parent_fd(root, item['from_path'])
                except FileNotFoundError:
                    return 'complete'
            other = db.execute('SELECT 1 FROM source WHERE storage_ref=? LIMIT 1', (before_path,)).fetchone()
            try:
                old = os.stat(old_name, dir_fd=old_parent, follow_symlinks=False)
            except FileNotFoundError:
                return 'complete'
            if other or (old.st_dev, old.st_ino) != (verified.st_dev, verified.st_ino):
                return 'cleanup_pending'
            os.unlink(old_name, dir_fd=old_parent)
            os.fsync(old_parent)
            return 'complete'
        except Exception:
            db.rollback()
            # A failed/ambiguous commit must never remove the only target that
            # the durable database might already reference.
            if created and not committed:
                try:
                    durable = db.execute('SELECT storage_ref FROM source WHERE source_id=?', (sid,)).fetchone()
                    promoted = os.stat(new_name, dir_fd=new_parent, follow_symlinks=False)
                    if durable and durable[0] != target_path and (promoted.st_dev, promoted.st_ino) == promoted_identity:
                        os.unlink(new_name, dir_fd=new_parent)
                        os.fsync(new_parent)
                except (OSError, sqlite3.Error):
                    pass
            raise
        finally:
            for fd in (original_fd, old_parent, new_parent):
                if fd is not None:
                    os.close(fd)


class Controller:
    def __init__(self):
        self.csrf = secrets.token_hex(32)
        self.lock = threading.Lock()
        self.worker = None

    def running(self):
        return self.worker is not None and self.worker.is_alive()

    def start(self, db_path, root, directory, ident, slot):
        with self.lock:
            if self.running():
                raise ValueError('Ett namnbyte pågår redan.')
            plan = source_migration.read_plan(directory, ident)
            if plan.get('format') != 1:
                raise ValueError('Ogiltig namnplan.')
            self.worker = threading.Thread(target=self.run, args=(db_path, root, directory, ident, slot), daemon=True)
            self.worker.start()

    def run(self, db_path, root, directory, ident, slot):
        plan = source_migration.read_plan(directory, ident)
        try:
            source_migration.backup(db_path, directory, ident)
            plan.pop('error', None)
            for item in plan['items']:
                if item['status'] in ('complete', 'unchanged'):
                    continue
                if not slot.acquire(timeout=1):
                    raise ValueError('En läsning pågår. Försök igen när den är klar.')
                try:
                    item['status'] = 'working'
                    item.pop('error', None)
                    source_migration.save_plan(directory, plan)
                    item['status'] = apply_item(db_path, root, ident, item)
                    source_migration.save_plan(directory, plan)
                except (ValueError, OSError, sqlite3.Error, yaml.YAMLError) as exc:
                    item['status'] = 'error'
                    item['error'] = str(exc)[:300] if type(exc) is ValueError else 'Namnbytet stoppades. Kontrollera originalet och lokal lagring; inga befintliga målfiler skrivs över.'
                    source_migration.save_plan(directory, plan)
                    break
                finally:
                    slot.release()
        except (ValueError, OSError, sqlite3.Error, yaml.YAMLError):
            plan['error'] = 'Åtgärden kunde inte startas. Kontrollera lagring och försök igen när inga läsningar/importer pågår.'
            source_migration.save_plan(directory, plan)
