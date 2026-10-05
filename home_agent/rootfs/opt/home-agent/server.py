from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse
import cgi
import html
import os
import tempfile
import yaml

HOST = "0.0.0.0"
PORT = 8099
DATA_FILE = Path("/data/home.yaml")
MAX_UPLOAD = 5 * 1024 * 1024

def load_yaml(path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_home():
    if not DATA_FILE.exists():
        return None, None
    try:
        return load_yaml(DATA_FILE), None
    except Exception as exc:
        return None, str(exc)

def find_home(data):
    if not isinstance(data, dict):
        return None
    homes = data.get("homes")
    if isinstance(homes, list) and homes:
        return homes[0]
    if isinstance(homes, dict) and homes:
        return next(iter(homes.values()))
    return None

def validate_snapshot(data):
    if not isinstance(data, dict):
        return "Top level must be a YAML mapping."
    if data.get("schema") != "home_agent":
        return "Expected schema: home_agent."
    home = find_home(data)
    if not home:
        return "No home found in snapshot."
    return None

def render(data, error=None, notice=None):
    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           "<title>Home Agent</title></head><body>",
           "<h1>Home Agent</h1><p>Version 0.2.1</p>"]
    if notice:
        out.append(f"<p><strong>{html.escape(notice)}</strong></p>")
    if error:
        out.append(f"<p><strong>Error:</strong> {html.escape(error)}</p>")
    if not data:
        out.append("<p>No Home Agent data imported yet.</p>")
    else:
        home = find_home(data)
        if home:
            out.append(f"<h2>{html.escape(str(home.get('name', home.get('id', 'Home'))))}</h2>")
            floors = home.get("floors", [])
            if isinstance(floors, dict):
                floors = list(floors.values())
            for floor in floors or []:
                out.append(f"<h3>{html.escape(str(floor.get('name', floor.get('id', 'Floor'))))}</h3><ul>")
                rooms = floor.get("rooms", [])
                if isinstance(rooms, dict):
                    rooms = list(rooms.values())
                for room in rooms or []:
                    out.append(f"<li>{html.escape(str(room.get('name', room.get('id', 'Room'))))}</li>")
                spaces = floor.get("spaces", [])
                if isinstance(spaces, dict):
                    spaces = list(spaces.values())
                for space in spaces or []:
                    out.append(f"<li>{html.escape(str(space.get('name', space.get('id', 'Space'))))} <em>(space)</em></li>")
                out.append("</ul>")
    out.append("""<hr><h2>Import YAML snapshot</h2>
<form method="post" action="/import" enctype="multipart/form-data">
<input type="file" name="snapshot" accept=".yaml,.yml,text/yaml,application/x-yaml" required>
<button type="submit">Import</button>
</form>
<p>The file is validated and stored privately in this add-on's local data storage.</p>
</body></html>""")
    return "".join(out).encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def send_page(self, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/health":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data, error = load_home()
        self.send_page(render(data, error))

    def do_POST(self):
        if urlparse(self.path).path != "/import":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_UPLOAD:
                raise ValueError("Upload is empty or larger than 5 MB.")
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
            )
            item = form["snapshot"]
            raw = item.file.read(MAX_UPLOAD + 1)
            if len(raw) > MAX_UPLOAD:
                raise ValueError("File is larger than 5 MB.")
            text = raw.decode("utf-8")
            data = yaml.safe_load(text)
            validation_error = validate_snapshot(data)
            if validation_error:
                raise ValueError(validation_error)

            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix="home-", suffix=".yaml", dir=str(DATA_FILE.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(text)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_name, DATA_FILE)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)

            self.send_page(render(data, notice="Snapshot imported successfully."))
        except Exception as exc:
            data, existing_error = load_home()
            self.send_page(render(data, error=str(exc) if not existing_error else existing_error), 400)

    def log_message(self, format, *args):
        print(format % args)

HTTPServer((HOST, PORT), Handler).serve_forever()
