"""CSRF-protected local preview and explicit start of a durable import plan."""
import cgi
import hmac
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile
import sqlite3
import yaml
from urllib.parse import parse_qs, urlparse

import codex_read
import source_migration as migration
import source_bundle
import ui


def page(controller, directory, ident='', error=None):
    body = '<h1>Överför äldre original</h1><p>Förhandsgranska filerna och deras registrerade kopplingar innan du kopierar från Drive. Originalen på Drive behålls.</p>'
    body += ("<form method='post' action='/sources/import' enctype='multipart/form-data'>"
             "<input type='hidden' name='csrf' value='%s'><input type='hidden' name='action' value='preview'>"
             "<label>Drive-inventering (JSON)<input type='file' name='inventory' accept='.json,application/json' required></label>"
             "<button>Förhandsgranska</button></form>" % ui.esc(controller.csrf))
    body += ("<h2>Kopiera med originalpaket</h2><p>Om Pi saknar åtkomst till den äldre Drive-mappen kan du ladda upp ett privat originalpaket. Drive-referenserna i paketet behandlas som uppgifter från dig.</p>"
             "<form method='post' action='/sources/import' enctype='multipart/form-data'>"
             "<input type='hidden' name='csrf' value='%s'><input type='hidden' name='action' value='bundle'>"
             "<label>Originalpaket (ZIP, högst 256 MB)<input type='file' name='bundle' accept='.zip,application/zip' required></label>"
             "<button>Förhandsgranska originalpaket</button></form>" % ui.esc(controller.csrf))
    if not ident:
        for file in sorted(Path(directory).glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
            body += "<p><a href='/sources/import?id=%s'>Visa sparad importplan %s</a></p>" % (ui.esc(file.stem), ui.esc(file.stem[:8]))
    else:
        plan = migration.read_plan(directory, ident)
        if plan.get('bundle'):
            body += '<p>Originalpaketet är sparat lokalt. Överföringen kräver ingen Drive-inloggning på Pi.</p>'
        else:
            body += '<p>Direktkopiering kräver separat verifierad Drive-importbehörighet på Pi. En fungerande Drive-anslutning i Codex bevisar inte denna åtkomst.</p>'
        if plan.get('error'):
            body += '<p>' + ui.esc(plan['error']) + '</p>'
        body += '<p>Markera först en manual och en bild för ett litet prov. Fortsätt sedan med resterande filer.</p>'
        body += '<p>En befintlig källa med samma checksumma återanvänds efter kontroll. Ändrade original och oklara referenser stoppas.</p>'
        body += ("<form method='post' action='/sources/import'><input type='hidden' name='csrf' value='%s'>"
                 "<input type='hidden' name='plan' value='%s'>" % (ui.esc(controller.csrf), ui.esc(ident)))
        labels = {'pending': 'Väntar', 'copying': 'Påbörjad', 'complete': 'Klar', 'error': 'Misslyckades'}
        for item in plan['items']:
            body += "<section class='card'><label>"
            if item['status'] != 'complete':
                body += "<input type='checkbox' name='selected' value='%s'> " % ui.esc(item['key'])
            body += '<strong>%s</strong> – %s</label><p>%s</p>' % (
                ui.esc(item['document']), labels[item['status']], ui.esc(item['file']['name']))
            body += '<p>Kopplas till: ' + ', '.join(ui.esc(t['name'] or t['type']) for t in item['targets']) + '</p>'
            if item['review']:
                body += '<p>Kompletterande bild: identifierad enbart med filnamn. Kontrollera att detta är rätt original innan du markerar den.</p>'
            if item['previous']:
                body += '<p>En tidigare Drive-källa finns registrerad. Lokal fil och checksumma kontrolleras vid överföring.</p>'
            if item.get('error'):
                body += '<p>' + ui.esc(item['error']) + '</p>'
            if item['status'] == 'complete':
                body += "<a href='/object?id=%s'>Öppna dokumentet</a>" % ui.esc(item['document_id'])
            body += '</section>'
        if controller.running():
            body += "<p>Överföring pågår. Uppdatera sidan för att se framsteg.</p><button name='action' value='pause'>Pausa efter aktuell fil</button>"
        else:
            body += "<button name='action' value='start'>Godkänn kopplingarna och överför markerade filer</button>"
        body += "</form><p><a href='/sources/import?id=%s'>Uppdatera status</a></p>" % ui.esc(ident)
        body += '<h2>Behöver utredas</h2>'
        for item in plan['unresolved']:
            body += '<p>%s: %s %s</p>' % (ui.esc(item['document']), ui.esc(item.get('filename', '')), ui.esc(item['reason']))
        body += '<h2>Övriga inventerade filer (%s)</h2><p>Dessa ingår inte i överföringen eftersom en säker dokumentkoppling saknas.</p>' % len(plan['unassigned'])
        for f in plan['unassigned']:
            body += '<p>' + ui.esc(f['path']) + '</p>'
    return ui.shell('Överför äldre original', body, active='more', error=error)


def handle(handler, controller, db_path, root, directory, credentials, new_id, post=False):
    status, error = 200, None
    ident = parse_qs(urlparse(handler.path).query).get('id', [''])[0]
    try:
        if post:
            size = int(handler.headers.get('Content-Length', '0'))
            if not 0 < size <= source_bundle.MAX_BUNDLE + 65536:
                raise ValueError('Inventeringen är tom eller för stor.')
            if handler.headers.get('Content-Type', '').startswith('multipart/form-data'):
                form = cgi.FieldStorage(fp=handler.rfile, headers=handler.headers,
                    environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': handler.headers.get('Content-Type', ''),
                             'CONTENT_LENGTH': str(size)}, limit=size)
                csrf, action = form.getfirst('csrf', ''), form.getfirst('action', '')
                fields = None
            else:
                if size > 65536:
                    raise ValueError('Formuläret är för stort.')
                fields = parse_qs(handler.rfile.read(size).decode())
                if any(len(v) != 1 for k, v in fields.items() if k != 'selected'):
                    raise ValueError('Ogiltigt formulär.')
                csrf, action = fields.get('csrf', [''])[0], fields.get('action', [''])[0]
            if (not hmac.compare_digest(str(csrf).encode(), controller.csrf.encode())
                    or handler.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or not codex_read.same_origin(handler.headers.get('Origin'), handler.headers.get('Host', ''))):
                raise ValueError('Öppna importsidan på nytt och försök igen.')
            if action in ('preview', 'bundle') and fields is None:
                if controller.running():
                    raise ValueError('Pausa pågående överföring först.')
                if action == 'bundle':
                    Path(directory).mkdir(parents=True, exist_ok=True, mode=0o700)
                    fd, stage = tempfile.mkstemp(prefix='.upload-', dir=directory)
                    try:
                        with os.fdopen(fd, 'wb') as out:
                            shutil.copyfileobj(form['bundle'].file, out, length=256 * 1024)
                            out.flush()
                            os.fsync(out.fileno())
                        inventory = source_bundle.inventory(stage)
                        plan = migration.build_plan(db_path, inventory)
                        plan['bundle'] = True
                        os.replace(stage, Path(directory) / (plan['id'] + '.zip'))
                    finally:
                        Path(stage).unlink(missing_ok=True)
                else:
                    raw = form['inventory'].file.read(migration.MAX_INVENTORY + 1)
                    if len(raw) > migration.MAX_INVENTORY:
                        raise ValueError('Inventeringen är för stor.')
                    plan = migration.build_plan(db_path, json.loads(raw))
                migration.save_plan(directory, plan)
                ident = plan['id']
            elif action == 'start' and fields is not None:
                ident = fields.get('plan', [''])[0]
                controller.start(db_path, root, directory, ident, fields.get('selected', []), credentials, new_id)
            elif action == 'pause' and fields is not None:
                ident = fields.get('plan', [''])[0]
                controller.stop.set()
            else:
                raise ValueError('Ogiltig åtgärd.')
            handler.send_response(303)
            handler.send_header('Location', '/sources/import?id=' + ident)
            handler.send_header('Cache-Control', 'no-store')
            handler.end_headers()
            return
        body = page(controller, directory, ident)
    except (ValueError, KeyError, TypeError, AttributeError, OSError, zipfile.BadZipFile,
            sqlite3.Error, yaml.YAMLError):
        status = 400
        error = 'Importplanen kunde inte läsas eller sparas. Kontrollera filformatet och öppna sidan på nytt.'
        body = page(controller, directory, error=error)
    handler.send_response(status)
    for key, value in [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body))),
                       ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                       ('Referrer-Policy', 'same-origin'), ('Content-Security-Policy',
                        "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'self'")]:
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)
