"""Read-only navigation and original lists for permanent Home Graph objects."""
from contextlib import closing
from pathlib import Path
import sqlite3
from urllib.parse import quote

import yaml
import ui

KINDS = {'home', 'floor', 'room', 'space', 'asset', 'system', 'component', 'document',
         'event', 'service_history', 'maintenance', 'project', 'cost', 'supplier'}


def rows(db):
    return db.execute('''SELECT i.permanent_id,i.legacy_id,i.object_type,o.name,o.yaml_text
        FROM object_identity i JOIN objects o
        ON o.object_id=i.legacy_id AND o.object_type=i.object_type
        ORDER BY o.name,i.permanent_id''').fetchall()


def connect(db_path):
    return sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)


def url(ident):
    return '/object?id=' + quote(ident, safe='')


def list_page(db_path):
    with closing(connect(db_path)) as db:
        records = [r for r in rows(db) if r[2] in KINDS]
    body = '<h1>Dokument & objekt</h1><p>Öppna registrerade objekt och deras kopplade original.</p>'
    for kind in ('document', 'system', 'component', 'asset', 'room', 'space', 'home', 'floor'):
        selected = [r for r in records if r[2] == kind]
        if not selected:
            continue
        labels = dict(document='Dokument', system='System', component='Komponenter',
                      asset='Utrustning', room='Rum', space='Utrymmen', home='Hem', floor='Våningsplan')
        body += '<h2>' + labels[kind] + '</h2><ul>'
        for pid, legacy, _, name, _ in selected:
            body += "<li><a href='%s'>%s</a></li>" % (ui.esc(url(pid)), ui.esc(name or legacy))
        body += '</ul>'
    return ui.shell('Dokument & objekt', body, active='more')


def detail(db_path, ident):
    with closing(connect(db_path)) as db:
        db.execute('BEGIN')
        records = rows(db)
        record = next((r for r in records if r[0] == ident and r[2] in KINDS), None)
        if not record:
            return None, [], []
        sources = db.execute('''SELECT s.source_id,s.original_name,s.media_type
            FROM source_link l JOIN source s ON s.source_id=l.source_id
            WHERE l.object_id=? ORDER BY s.original_name,s.source_id''', (ident,)).fetchall()
        # Only display explicit local references, never infer by shared filenames.
        data = yaml.safe_load(record[4]) or {}
        refs = set()
        for key in ('related_object_refs', 'asset_refs', 'system_refs', 'component_refs'):
            value = data.get(key, [])
            if isinstance(value, list):
                refs.update(x for x in value if isinstance(x, str))
        related = [r for r in records if r[1] in refs and r[0] != ident]
        docs = db.execute('''SELECT DISTINCT i.permanent_id FROM source_link a
            JOIN source_link b ON a.source_id=b.source_id
            JOIN object_identity i ON i.permanent_id=b.object_id
            WHERE a.object_id=? AND i.object_type='document' ''', (ident,)).fetchall()
        related_ids = {r[0] for r in related} | {r[0] for r in docs}
        related = [r for r in records if r[0] in related_ids and r[0] != ident]
        return record, sources, related


def file_list(ident, sources):
    body = '<h2>Bilder &amp; dokument</h2>'
    if not sources:
        return body + '<p>Inga lokala original är kopplade till objektet.</p>'
    for sid, name, media in sources:
        href = '/source/file?object=%s&amp;id=%s' % (quote(ident, safe=''), quote(sid, safe=''))
        body += "<p><a target='_blank' rel='noopener' href='%s'>%s</a></p>" % (href, ui.esc(name or 'Öppna original'))
        if media in {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}:
            body += "<a target='_blank' rel='noopener' href='%s'><img loading='lazy' style='max-width:100%%;max-height:240px' src='%s' alt='%s'></a>" % (href, href, ui.esc(name or 'Bild'))
    return body


def detail_page(db_path, ident):
    record, sources, related = detail(db_path, ident)
    if not record:
        return ui.shell('Objekt saknas', '<h1>Objektet hittades inte</h1>'), 404
    pid, legacy, kind, name, _ = record
    body = "<a href='/objects'>← Dokument &amp; objekt</a><h1>%s</h1>" % ui.esc(name or legacy)
    if kind == 'room':
        body += "<p><a href='/room?id=%s'>Visa rummet</a></p>" % quote(legacy, safe='')
    if kind == 'asset':
        body += "<p><a href='/asset?id=%s'>Visa utrustningssidan</a></p>" % quote(pid, safe='')
    body += file_list(pid, sources)
    if related:
        body += '<h2>Relaterade objekt</h2><ul>'
        for r in related:
            body += "<li><a href='%s'>%s</a></li>" % (ui.esc(url(r[0])), ui.esc(r[3] or r[1]))
        body += '</ul>'
    return ui.shell(name or legacy, body), 200


def room_links(db_path, sections, room_id):
    with closing(connect(db_path)) as db:
        records = rows(db)
    # Type as well as legacy key matters when resolving existing identities.
    by_key = {(r[1], r[2]): r[0] for r in records}
    kinds = {'System': 'system', 'Utrustning': 'asset', 'Komponenter': 'component',
             'Dokument': 'document', 'Händelser': 'event', 'Service': 'service_history',
             'Underhåll': 'maintenance', 'Kostnader': 'cost'}
    result = {}
    for title, items in sections.items():
        result[title] = []
        for item in items:
            copied = dict(item)
            copied.pop('_url', None)
            pid = by_key.get((str(item.get('id', '')), kinds[title]))
            if pid:
                copied['_url'] = url(pid)
            result[title].append(copied)
    pid = by_key.get((room_id, 'room'))
    extra = ''
    if pid:
        _, sources, _ = detail(db_path, pid)
        extra = file_list(pid, sources)
    return result, extra
