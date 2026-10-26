"""CI-only synthetic two-container acceptance, with no OpenAI/network egress."""
import base64
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlencode


def seed():
    sys.path.insert(0, '/opt/home-agent')
    import server
    import house_context
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(80):
        try:
            with opener.open('http://127.0.0.1:8099/health', timeout=1) as response:
                assert response.status == 200
            break
        except OSError:
            if attempt == 79:
                raise
            time.sleep(.25)
    data = {'homes': [{'id': 'synthetic-home', 'name': 'Synthetic home',
             'assets': [{'id': house_context.NIBE_LEGACY_ID, 'name': 'Synthetic NIBE', 'model': 'S1255'}]}]}
    server.import_database(data, 'synthetic CI data')
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jB1kAAAAASUVORK5CYII=')
    # A minimal genuine PDF with extractable text and valid object/xref offsets.
    text = b'BT /F1 12 Tf 30 70 Td (CODEX_NIBE_PDF_OK) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 100] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length ' + str(len(text)).encode() + b' >>\nstream\n' + text + b'\nendstream']
    pdf, offsets = b'%PDF-1.4\n', [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += str(number).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    start = len(pdf)
    pdf += b'xref\n0 6\n0000000000 65535 f \n' + b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    pdf += b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(start).encode() + b'\n%%EOF\n'
    server.SOURCE_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(server.DB_FILE) as db:
        asset = db.execute('SELECT permanent_id FROM object_identity WHERE legacy_id=?', (house_context.NIBE_LEGACY_ID,)).fetchone()[0]
        for ident, mime, body in [('ci-photo', 'image/png', png), ('ci-manual', 'application/pdf', pdf)]:
            path = server.SOURCE_DIR / ident
            path.write_bytes(body)
            db.execute("INSERT INTO source(source_id,source_type,media_type,original_name,sha256,storage_ref,custody_status) VALUES(?,'file',?,?,?,?, 'local_verified')", (ident, mime, ident, hashlib.sha256(body).hexdigest(), str(path)))
            db.execute('INSERT INTO source_link(source_id,object_id) VALUES(?,?)', (ident, asset))
    # Exercise the actual setup page/form. A direct create_ticket() call missed
    # the browser's opaque-origin behavior in the original smoke test.
    with opener.open('http://127.0.0.1:8099/codex/connect') as response:
        assert response.headers['Referrer-Policy'] == 'same-origin'
        csrf = re.search(rb'name="csrf" value="([0-9a-f]{64})"', response.read()).group(1).decode()
    form = urllib.request.Request('http://127.0.0.1:8099/codex/connect',
        urlencode({'csrf': csrf, 'action': 'create'}).encode(),
        headers={'Origin': 'null', 'Content-Type': 'application/x-www-form-urlencoded'})
    with opener.open(form) as response:
        ticket_text = re.search(rb'<textarea[^>]*>([^<]+)</textarea>', response.read()).group(1).decode()
    ticket = Path('/data/ci-ticket')
    ticket.write_text(ticket_text)
    ticket.chmod(0o600)
    Path('/data/ci-db-sha').write_text(hashlib.sha256(server.DB_FILE.read_bytes()).hexdigest())
    print('PASS: real setup GET and CSRF-authorized opaque-origin POST create read key; synthetic PDF and PNG seeded')


def verify(reconnect=True):
    sys.path.insert(0, '/app')
    from controller import Controller
    controller = Controller()
    try:
        code, raw = controller._capture(['mcp', 'list', '--json'])
        assert code == 0
        assert any(item['name'] == 'home_agent' and item['enabled'] for item in json.loads(raw))
    finally:
        controller.close()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ticket = Path('/tmp/ci-ticket').read_text()
    if reconnect:
        with opener.open('http://127.0.0.1:8099/') as response:
            csrf = re.search(rb"const csrf='([0-9a-f]{64})'", response.read()).group(1).decode()
        request = urllib.request.Request('http://127.0.0.1:8099/api/home-agent', json.dumps({'ticket': ticket}).encode(), headers={'Content-Type': 'application/json', 'X-CSRF-Token': csrf})
        with opener.open(request) as response:
            assert json.load(response)['connected']
    messages = [
        {'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
        {'method': 'notifications/initialized'}, {'id': 2, 'method': 'tools/list'},
        {'id': 3, 'method': 'tools/call', 'params': {'name': 'home_agent_nibe', 'arguments': {}}},
        {'id': 4, 'method': 'tools/call', 'params': {'name': 'home_agent_source', 'arguments': {'source_id': 'ci-manual'}}},
        {'id': 5, 'method': 'tools/call', 'params': {'name': 'home_agent_source', 'arguments': {'source_id': 'ci-photo'}}}]
    process = subprocess.run(['python3', '/app/home_agent_mcp.py'], input=''.join(json.dumps({'jsonrpc': '2.0', **m}) + '\n' for m in messages), text=True, capture_output=True, timeout=60, check=True)
    assert ticket not in process.stdout
    responses = {item['id']: item for item in map(json.loads, process.stdout.splitlines())}
    for ident in (3, 4, 5):
        assert not responses[ident]['result'].get('isError'), 'MCP read failed: ' + str(ident)
    nibe = json.loads(responses[3]['result']['content'][0]['text'])
    assert nibe['nibe']['records'][0]['stored_fields']['model'] == 'S1255'
    manual = json.loads(responses[4]['result']['content'][0]['text'])
    photo = json.loads(responses[5]['result']['content'][0]['text'])
    text = subprocess.check_output(['pdftotext', manual['local_path'], '-'])
    assert b'CODEX_NIBE_PDF_OK' in text
    assert Path(photo['local_path']).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    for source in (manual, photo):
        assert hashlib.sha256(Path(source['local_path']).read_bytes()).hexdigest() == source['sha256']
    print('PASS: real CLI MCP configuration, Ingress key setup, stdio tools, authenticated read API, verified PDF extraction and image download')


if __name__ == '__main__':
    if sys.argv[1] == 'seed':
        seed()
    elif sys.argv[1] == 'verify':
        verify()
    elif sys.argv[1] == 'resumed':
        verify(False)
    elif sys.argv[1] == 'unchanged':
        assert hashlib.sha256(Path('/data/home_agent.db').read_bytes()).hexdigest() == Path('/data/ci-db-sha').read_text()
        print('PASS: no domain/database mutations from the Codex read connection')
