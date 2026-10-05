from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse
import html
import yaml

HOST = "0.0.0.0"
PORT = 8099
DATA_FILE = Path("/data/home.yaml")

def load_home():
    if not DATA_FILE.exists():
        return None, None
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data, None
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

def page(data, error=None):
    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           "<title>Home Agent</title></head><body>",
           "<h1>Home Agent</h1><p>Version 0.2.0</p>"]
    if error:
        out.append(f"<p><strong>Could not read data:</strong> {html.escape(error)}</p>")
    elif not data:
        out.append("<p>No Home Agent data imported yet.</p>")
        out.append("<p>Place the current YAML snapshot at <code>/data/home.yaml</code>.</p>")
    else:
        home = find_home(data)
        if not home:
            out.append("<p>YAML loaded, but no home was found.</p>")
        else:
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
    out.append("</body></html>")
    return "".join(out).encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path == "/health":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
        else:
            data, error = load_home()
            body = page(data, error)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(format % args)

HTTPServer((HOST, PORT), Handler).serve_forever()
