"""Opt-in read service, separate internal port, no domain mutations or Drive calls."""
import base64
import hashlib
import hmac
import html
import json
import re
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import chatgpt_export
import house_context
import ui
import archive_audit

STATE = Path('/data/codex_read.json')
PORT = 8100  # HA add-on network only; deliberately absent from host port mappings.
HOST_PATTERN = r'(?:[a-z0-9]{8}|local)-home-agent'
MEDIA = {'application/pdf', 'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'text/plain'}


class ReadService:
    def __init__(self, db_path, source_dir, state=STATE, hostname=None):
        self.db_path, self.source_dir, self.state_path = Path(db_path), Path(source_dir), Path(state)
        self.hostname = (hostname or socket.gethostname()).replace('_', '-')
        self.csrf = secrets.token_hex(32)
        self.lock = threading.Lock()
        self.slot = threading.BoundedSemaphore(1)

    def state(self):
        return chatgpt_export.private_json(self.state_path) if self.state_path.exists() else {}

    def enabled(self):
        try:
            value = self.state()
            return value.get('enabled') is True and bool(re.fullmatch(r'[0-9a-f]{64}', value.get('token', '')))
        except Exception:
            return False

    def authorized(self, header):
        try:
            value = self.state()
            expected = 'Bearer ' + value['token']
            return self.enabled() and hmac.compare_digest(header.encode(), expected.encode())
        except (OSError, ValueError, KeyError, TypeError, AttributeError, chatgpt_export.PublishError):
            return False

    def create_ticket(self):
        if not re.fullmatch(HOST_PATTERN, self.hostname):
            raise ValueError('Home Agents interna värdnamn kunde inte identifieras. Ingen läsnyckel skapades.')
        value = {'enabled': True, 'token': secrets.token_hex(32)}
        with self.lock:
            chatgpt_export.save_state(self.state_path, value)
        ticket = {'version': 1, 'scope': 'nibe-read', 'host': self.hostname, 'token': value['token']}
        return base64.urlsafe_b64encode(house_context.canonical(ticket)).decode()

    def revoke(self):
        with self.lock:
            chatgpt_export.save_state(self.state_path, {'enabled': False})

    def archive_enabled(self):
        try:
            return self.enabled() and self.state().get('archive_audit') is True
        except Exception:
            return False

    def set_archive(self, enabled):
        with self.lock:
            if not self.enabled():
                raise ValueError('Aktivera läsåtkomst först.')
            value = self.state()
            value['archive_audit'] = bool(enabled)
            chatgpt_export.save_state(self.state_path, value)

    def context(self):
        context, sources = house_context.read_context(self.db_path)
        return {**context, 'checked_at': house_context.now(),
                'revision': hashlib.sha256(house_context.canonical(context)).hexdigest()}, sources


class ReadHandler(BaseHTTPRequestHandler):
    service = None

    def log_message(self, *args):
        pass

    def reply(self, code, body, mime='application/json'):
        if isinstance(body, dict):
            body = house_context.canonical(body)
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.connection.settimeout(20)
        if not self.service.authorized(self.headers.get('Authorization', '')):
            self.reply(401, {'error': 'Läsanslutningen är avstängd eller nyckeln är ogiltig.'})
            return
        if not self.service.slot.acquire(blocking=False):
            self.reply(503, {'error': 'En läsning pågår. Försök igen.'})
            return
        try:
            if self.path == '/v1/context':
                context, _ = self.service.context()
                self.reply(200, context)
            elif urlparse(self.path).path == '/v1/archive-audit':
                if not self.service.archive_enabled():
                    self.reply(403, {'error': 'Arkivrapporten delas inte med Codex. Aktivera den separat i Home Agent.'})
                    return
                params = archive_audit.parameters(urlparse(self.path).query)
                self.reply(200, archive_audit.report(self.service.db_path, self.service.source_dir, **params))
            elif re.fullmatch(r'/v1/source/[A-Za-z0-9_-]{1,100}', self.path):
                ident = self.path.rsplit('/', 1)[1]
                _, sources = self.service.context()
                source = next((s for s in sources if s['id'] == ident), None)
                if not source or source['media_type'] not in MEDIA:
                    self.reply(404, {'error': 'Ingen stödd, uttryckligen NIBE-kopplad originalfil hittades.'})
                    return
                body = house_context.original_bytes(source, self.service.source_dir)
                self.reply(200, body, source['media_type'])
            else:
                self.reply(404, {'error': 'Läsfunktionen finns inte.'})
        except (house_context.ContextError, archive_audit.AuditError, OSError, ValueError, TypeError):
            self.reply(503, {'error': 'Läsunderlaget eller originalfilen kunde inte verifieras.'})
        finally:
            self.service.slot.release()

    def do_POST(self):
        self.reply(405, {'error': 'Läsanslutningen kan inte ändra Home Agent.'})

    do_PUT = do_DELETE = do_PATCH = do_POST


def launch(service):
    handler = type('BoundReadHandler', (ReadHandler,), {'service': service})
    server = ThreadingHTTPServer(('0.0.0.0', PORT), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True, name='codex-read').start()
    return server


def page(service, ticket=None, error=None):
    enabled = service.enabled()
    body = '<h1>Anslut Codex</h1><p class="sub">Läs och analysera husinformation från Codex-konversationen på mobilen.</p>'
    body += '<div class="card"><h2>%s</h2><p>Första versionen ger ett objektindex, NIBE-uppgifter och uttryckligen kopplade dokument och bilder. Ingen skrivåtkomst ingår.</p></div>' % ('Läsåtkomst aktiverad' if enabled else 'Läsåtkomst avstängd')
    if ticket:
        body += '<div class="card"><h2>Kopiera läsnyckeln</h2><p>Öppna Codex Remote Test, klistra in nyckeln under Home Agent och anslut. Nyckeln visas bara nu. Dela den inte i chatten.</p><textarea readonly rows="7" style="width:100%%">%s</textarea></div>' % html.escape(ticket)
    body += '<form method="post" action="/codex/connect"><input type="hidden" name="csrf" value="%s"><button name="action" value="create">%s</button><p>En ny nyckel ersätter den tidigare. Den gamla slutar fungera.</p><button name="action" value="revoke">Stäng av läsåtkomst</button></form>' % (service.csrf, 'Skapa ny läsnyckel' if enabled else 'Aktivera och skapa läsnyckel')
    body += '<p>Originalen och databasen stannar i Home Agent. Valda filer kan kopieras till Codex-tilläggets arbetsmapp och skickas till AI-modellen när du analyserar dem.</p>'
    if enabled:
        body += '<h2>Separat arkivrapport</h2><p>Delar kontrollresultat för alla registrerade original: relativa sökvägar, filnamn, checksummor och kopplade objekts namn/ID. Ger ingen ytterligare filhämtning eller skrivåtkomst.</p>'
        body += '<p>Status: %s</p>' % ('Delas med Codex' if service.archive_enabled() else 'Delas inte med Codex')
        body += '<form method="post" action="/codex/connect"><input type="hidden" name="csrf" value="%s"><button name="action" value="%s">%s</button></form>' % (service.csrf, 'archive_off' if service.archive_enabled() else 'archive_on', 'Stäng av delning av arkivrapport' if service.archive_enabled() else 'Dela arkivrapport med Codex')
    body += '<p><a href="/archive/check">Öppna lokal arkivkontroll</a></p>'
    return ui.shell('Anslut Codex', body, active='more', error=error)


def handle_page(handler, service, post=False):
    ticket, error, status = None, None, 200
    if post:
        try:
            size = int(handler.headers.get('Content-Length', '0'))
            if not 0 < size <= 256:
                raise ValueError('Ogiltigt formulär.')
            data = parse_qs(handler.rfile.read(size).decode(), strict_parsing=True)
            if set(data) != {'csrf', 'action'} or any(len(v) != 1 for v in data.values()) or not hmac.compare_digest(data['csrf'][0].encode(), service.csrf.encode()):
                raise ValueError('Öppna sidan på nytt och försök igen.')
            # Browsers can send Origin: null for a same-origin HTTP form, notably
            # with the old no-referrer policy. The valid unpredictable nonce is
            # mandatory even when origin/fetch metadata is opaque or absent.
            origin = handler.headers.get('Origin')
            if handler.headers.get('Sec-Fetch-Site') == 'cross-site' or not same_origin(origin, handler.headers.get('Host', '')):
                raise ValueError('Åtgärden måste startas från Home Agent.')
            if data['action'] == ['create']:
                ticket = service.create_ticket()
            elif data['action'] == ['revoke']:
                service.revoke()
            elif data['action'] in (['archive_on'], ['archive_off']):
                service.set_archive(data['action'] == ['archive_on'])
            else:
                raise ValueError('Ogiltig åtgärd.')
        except ValueError as exc:
            status, error = 400, str(exc)
        except OSError:
            status, error = 503, 'Läsanslutningen kunde inte sparas.'
    body = page(service, ticket, error)
    handler.send_response(status)
    for key, value in [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'), ('Referrer-Policy', 'same-origin'), ('X-Content-Type-Options', 'nosniff'), ('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'self'")]:
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)


def same_origin(origin, host):
    if origin in (None, 'null'):
        return True  # Only reached after successful CSRF validation.
    try:
        source, target = urlparse(origin), urlparse('http://' + host)
        return (source.scheme == 'http' and source.hostname is not None
                and source.hostname == target.hostname
                and (source.port if source.port is not None else 80) == (target.port if target.port is not None else 80)
                and source.username is None and source.password is None
                and target.username is None and target.password is None
                and not source.path and not source.params and not source.query and not source.fragment
                and not target.path and not target.params and not target.query and not target.fragment)
    except (ValueError, TypeError, AttributeError):
        return False
