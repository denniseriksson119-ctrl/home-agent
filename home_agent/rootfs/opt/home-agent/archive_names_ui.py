"""Owner review of dates, descriptions and exact local archive destinations."""
import hmac
import sqlite3
import re
from urllib.parse import parse_qs, urlparse, urlencode

import archive_names as names
import codex_read
import source_migration
import ui
import yaml


def page(controller, db_path, root, directory, query='', error=None):
    args = parse_qs(query, strict_parsing=True)
    if set(args) - {'after', 'plan'} or any(len(v) != 1 for v in args.values()):
        raise ValueError('Ogiltig vy.')
    body = '<h1>Granska arkivnamn</h1><p>Välj högst tio original åt gången. Granska datum och beskrivning; nästa steg visar exakt gammal och ny sökväg innan något ändras.</p>'
    if 'plan' in args:
        plan = source_migration.read_plan(directory, args['plan'][0])
        body += '<h2>Förhandsgranskning</h2><p>Source-ID, originalfilnamn, kopplingar och originalbyte bevaras. Bara lagringsreferensen och arkivnamnet ändras.</p>'
        if plan.get('error'):
            body += '<p>' + ui.esc(plan['error']) + '</p>'
        labels = dict(pending='Väntar på godkännande', working='Pågår', complete='Klar', unchanged='Redan rätt namn',
                      cleanup_pending='Ny referens sparad; äldre filalias behöver kontrolleras', error='Stoppad')
        for item in plan['items']:
            body += "<section class='card'><h2>%s</h2><p>Source-ID: %s</p><p>Från: <code>%s</code></p><p>Till: <code>%s</code></p><p>%s</p>" % (
                ui.esc(item['original_name']), ui.esc(item['source_id']), ui.esc(item['from_path']), ui.esc(item['to_path']), labels[item['status']])
            if item['date_basis'] == 'filename_candidate':
                body += '<p>Datumet är ett förslag från originalfilnamnet. Kontrollera att det är rätt datum för källan.</p>'
            if item['date'] is None:
                body += '<p>Datum är uttryckligen okänt. Namnet får undated; bilder placeras i Photos/Undated.</p>'
            if item.get('error'):
                body += '<p>' + ui.esc(item['error']) + '</p>'
            body += '</section>'
        if controller.running():
            body += '<p>Arbetar med en fil åt gången. Uppdatera sidan för status. Omstart av tillägget kräver att du återupptar planen här.</p>'
        elif any(x['status'] not in ('complete', 'unchanged') for x in plan['items']):
            body += ("<form method='post' action='/archive/names'><input type='hidden' name='csrf' value='%s'>"
                     "<input type='hidden' name='plan' value='%s'><button name='action' value='apply'>Godkänn och genomför dessa namnbyten</button></form>" % (ui.esc(controller.csrf), ui.esc(plan['id'])))
        body += "<p><a href='/archive/names?plan=%s'>Uppdatera status</a></p>" % ui.esc(plan['id'])
    else:
        items, after = names.candidates(db_path, root, args.get('after', [None])[0])
        body += ("<form method='post' action='/archive/names'><input type='hidden' name='csrf' value='%s'>"
                 "<input type='hidden' name='action' value='preview'>" % ui.esc(controller.csrf))
        for item in items:
            sid = item['id']
            body += "<section class='card'><label><input type='checkbox' name='selected' value='%s'> <strong>%s</strong></label><p>Nu: <code>%s</code></p>" % (
                ui.esc(sid), ui.esc(item['name']), ui.esc(item['from'] or 'Säker lokal referens saknas — välj inte denna källa'))
            body += "<label>Datum för källan<input type='date' name='date_%s' value='%s'></label>" % (ui.esc(sid), ui.esc(item['date']))
            if item['date_basis'] == 'filename_candidate':
                body += '<p>Förslag från filnamn, inte ett verifierat fotograferingsdatum. Bekräfta eller ändra.</p>'
            elif item['date_basis'] == 'registered_capture':
                body += '<p>Förslag från registrerat källdatum. Bekräfta eller ändra.</p>'
            elif item['date_basis'] == 'existing_archive_name':
                body += '<p>Förslag från nuvarande arkivnamn. Kontrollera innan en eventuell ny ändring.</p>'
            else:
                body += '<p>Källdatum saknas. Ange känt datum eller markera uttryckligen okänt.</p>'
            body += "<label><input type='checkbox' name='unknown_%s' value='yes'> Datum är okänt (töm datumfältet)</label>" % ui.esc(sid)
            body += "<label>Kort beskrivning<input name='description_%s' maxlength='300' value='%s'></label>" % (ui.esc(sid), ui.esc(item['description']))
            if not item['description']:
                body += '<p>En entydig dokumentbeskrivning saknas; skriv en beskrivning innan källan väljs.</p>'
            body += '<p>Arkivkategori: %s</p></section>' % ui.esc(', '.join(item['folders']))
        body += '<button>Förhandsgranska valda namn</button></form>'
        if after:
            body += "<p><a href='/archive/names?%s'>Nästa sida</a></p>" % ui.esc(urlencode({'after': after}))
        for file in sorted(directory.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
            body += "<p><a href='/archive/names?plan=%s'>Öppna sparad namnplan %s</a></p>" % (ui.esc(file.stem), ui.esc(file.stem[:8]))
    body += "<p><a href='/archive/names'>Tillbaka till källistan</a> · <a href='/archive/check'>Skrivskyddad arkivkontroll</a></p>"
    return ui.shell('Granska arkivnamn', body, active='more', error=error)


def handle(handler, controller, db_path, root, directory, slot, import_running=False, post=False):
    status = 200
    try:
        if post:
            if import_running:
                raise ValueError('Vänta tills pågående originalimport är klar.')
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 < length <= 32768 or not handler.headers.get('Content-Type', '').startswith('application/x-www-form-urlencoded'):
                raise ValueError('Ogiltigt formulär.')
            handler.connection.settimeout(20)
            raw = handler.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Formuläret avbröts.')
            fields = parse_qs(raw.decode(), keep_blank_values=True, strict_parsing=True)
            if any(len(v) != 1 for k, v in fields.items() if k != 'selected'):
                raise ValueError('Dubblerade formulärfält.')
            if (not hmac.compare_digest(fields.get('csrf', [''])[0].encode(), controller.csrf.encode())
                    or handler.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or not codex_read.same_origin(handler.headers.get('Origin'), handler.headers.get('Host', ''))):
                raise ValueError('Öppna sidan på nytt och försök igen.')
            action = fields.get('action', [''])[0]
            allowed = {'csrf', 'action', 'selected'} if action == 'preview' else {'csrf', 'action', 'plan'}
            if any(k not in allowed and not (action == 'preview' and re.fullmatch(r'(date|description|unknown)_[A-Za-z0-9_-]{1,100}', k)) for k in fields):
                raise ValueError('Otillåtna formulärfält.')
            if action == 'preview':
                if controller.running():
                    raise ValueError('Vänta tills pågående namnbyten är klara.')
                choices = [dict(source_id=sid, date=fields.get('date_' + sid, [''])[0],
                    unknown_date=fields.get('unknown_' + sid) == ['yes'],
                    description=fields.get('description_' + sid, [''])[0]) for sid in fields.get('selected', [])]
                plan = names.build_plan(db_path, root, choices)
                source_migration.save_plan(directory, plan)
                ident = plan['id']
            elif action == 'apply':
                ident = fields.get('plan', [''])[0]
                controller.start(db_path, root, directory, ident, slot)
            else:
                raise ValueError('Ogiltig åtgärd.')
            handler.send_response(303)
            handler.send_header('Location', '/archive/names?plan=' + ident)
            handler.send_header('Cache-Control', 'no-store')
            handler.end_headers()
            return
        body = page(controller, db_path, root, directory, urlparse(handler.path).query)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError, yaml.YAMLError) as exc:
        status = 400
        body = ui.shell('Granska arkivnamn', "<h1>Granska arkivnamn</h1><p><a href='/archive/names'>Tillbaka</a></p>",
                        error=str(exc)[:300] if type(exc) is ValueError else 'Planen kunde inte läsas eller sparas. Öppna sidan igen och kontrollera lokal lagring.')
    handler.send_response(status)
    for key, value in [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body))),
                       ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                       ('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'self'")]:
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)
