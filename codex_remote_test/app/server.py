"""HA Ingress-only setup UI. No shell endpoint, token input or public host port."""
import hmac
import ipaddress
import json
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from controller import Controller, TestError


class Handler(BaseHTTPRequestHandler):
    controller = None

    def log_message(self, *args):
        pass  # Request paths may contain ingress credentials.

    def allowed(self):
        try:
            address = ipaddress.ip_address(self.client_address[0])
            return address.is_loopback or str(address) == '172.30.32.2'
        except ValueError:
            return False

    def reply(self, code, body, mime='application/json'):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'nonce-" + self.controller.csrf + "'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed():
            self.reply(403, {'error': 'Öppna tillägget via Home Assistant.'})
        elif self.path in ('/', '/index.html'):
            template = (Path(__file__).parent / 'index.html').read_text()
            self.reply(200, template.replace('__CSRF__', self.controller.csrf).encode(), 'text/html')
        elif self.path == '/api/status':
            self.reply(200, self.controller.status())
        elif self.path == '/health':
            self.reply(200, {'ready': True})
        else:
            self.reply(404, {'error': 'Sidan finns inte.'})

    def do_POST(self):
        # JSON + an unguessable custom header prevents cross-site form submissions.
        # Ingress is the authentication boundary; never trust X-Ingress-* alone.
        if (not self.allowed() or self.path != '/api/action'
                or self.headers.get('Content-Type') != 'application/json'
                or self.headers.get('Sec-Fetch-Site') == 'cross-site'
                or not hmac.compare_digest(self.headers.get('X-CSRF-Token', '').encode(), self.controller.csrf.encode())):
            self.reply(403, {'error': 'Åtgärden måste startas från tilläggets sida.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 256:
                raise ValueError()
            value = json.loads(self.rfile.read(length))
            if (not isinstance(value, dict) or set(value) != {'action'} or
                    value['action'] not in ('login', 'cancel', 'start', 'stop', 'pair')):
                raise ValueError()
        except (ValueError, TypeError):
            self.reply(400, {'error': 'Ogiltig åtgärd.'})
            return
        try:
            self.controller.action(value['action'])
            self.reply(202, {'accepted': True})
        except TestError as error:
            self.reply(409, {'error': str(error)})
        except OSError:
            self.reply(503, {'error': 'Codex kunde inte startas. Kontrollera tilläggets installation.'})


def main():
    controller = Controller()
    Handler.controller = controller
    server = ThreadingHTTPServer(('0.0.0.0', 8099), Handler)
    server.daemon_threads = True
    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    controller.initialize()
    print('Codex Remote Test: öppna webbgränssnittet från Home Assistant.', flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        controller.close()
        server.server_close()


if __name__ == '__main__':
    main()
