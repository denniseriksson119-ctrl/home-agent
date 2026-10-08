from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
import cgi
import copy
import difflib
import html
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
import yaml

HOST = "0.0.0.0"
PORT = 8099
DATA_FILE = Path("/data/home.yaml")
DB_FILE = Path("/data/home_agent.db")
PENDING_FILE = Path("/data/pending_change.yaml")
MAX_UPLOAD = 5 * 1024 * 1024
DB_SCHEMA_VERSION = 2

def load_yaml(path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def uuid7():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    value = (now_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= (uuid.uuid4().int & ((1 << 76) - 1))
    value &= ~(0b11 << 62)
    value |= 0b10 << 62
    return str(uuid.UUID(int=value))

def migrate_db(db):
    db.execute("CREATE TABLE IF NOT EXISTS schema_meta (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), version INTEGER NOT NULL)")
    row = db.execute("SELECT version FROM schema_meta WHERE singleton=1").fetchone()
    version = int(row[0]) if row else 0
    if version > DB_SCHEMA_VERSION:
        raise RuntimeError("Database schema is newer than this Home Agent version.")
    if version < 1:
        db.execute("CREATE TABLE IF NOT EXISTS object_identity (permanent_id TEXT PRIMARY KEY, object_type TEXT NOT NULL, legacy_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(object_type, legacy_id))")
        existing = db.execute("SELECT object_id, object_type FROM objects").fetchall()
        for legacy_id, object_type in existing:
            db.execute("INSERT OR IGNORE INTO object_identity(permanent_id, object_type, legacy_id) VALUES(?,?,?)", (uuid7(), str(object_type), str(legacy_id)))
        db.execute("INSERT INTO schema_meta(singleton, version) VALUES(1,1) ON CONFLICT(singleton) DO UPDATE SET version=excluded.version")
        version = 1
    if version < 2:
        db.execute("CREATE TABLE IF NOT EXISTS object_relation (source_id TEXT NOT NULL, relation_type TEXT NOT NULL, target_id TEXT NOT NULL, legacy_source_ref TEXT, legacy_target_ref TEXT, PRIMARY KEY(source_id, relation_type, target_id))")
        db.execute("UPDATE schema_meta SET version=2 WHERE singleton=1")
        version = 2
    if version != DB_SCHEMA_VERSION:
        raise RuntimeError("Database schema migration did not reach expected version.")

def init_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS snapshot (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            schema_version TEXT,
            yaml_text TEXT NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS objects (
            object_id TEXT PRIMARY KEY,
            object_type TEXT NOT NULL,
            name TEXT,
            parent_id TEXT,
            yaml_text TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            committed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            object_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT NOT NULL
        )""")
        db.execute("BEGIN IMMEDIATE")
        try:
            migrate_db(db)
            db.commit()
        except Exception:
            db.rollback()
            raise

def object_rows(data):
    home = find_home(data)
    if not home:
        return []
    rows = []
    def add(item, kind, parent=None):
        if isinstance(item, dict) and item.get("id"):
            rows.append((str(item["id"]), kind, str(item.get("name", "")), parent,
                         yaml.safe_dump(item, allow_unicode=True, sort_keys=False)))
    add(home, "home")
    for floor in home.get("floors", []) or []:
        add(floor, "floor", str(home.get("id", "")))
        floor_id = str(floor.get("id", ""))
        for room in floor.get("rooms", []) or []:
            add(room, "room", floor_id)
        for space in floor.get("spaces", []) or []:
            add(space, "space", floor_id)
    for key in ("systems", "components", "assets", "documents", "events",
                "service_history", "maintenance", "projects", "costs",
                "suppliers", "reminders", "open_items"):
        for item in home.get(key, []) or []:
            add(item, key.rstrip("s"), str(home.get("id", "")))
    return rows

def import_database(data, text):
    init_db()
    rows = object_rows(data)
    with sqlite3.connect(DB_FILE) as db:
        db.execute("BEGIN")
        db.execute("DELETE FROM objects")
        db.executemany("INSERT INTO objects(object_id, object_type, name, parent_id, yaml_text) VALUES(?,?,?,?,?)", rows)
        for legacy_id, object_type, _name, _parent, _yaml in rows:
            db.execute("INSERT OR IGNORE INTO object_identity(permanent_id, object_type, legacy_id) VALUES(?,?,?)", (uuid7(), object_type, legacy_id))
        db.execute("""INSERT INTO snapshot(id, schema_version, yaml_text, imported_at)
                      VALUES(1, ?, ?, CURRENT_TIMESTAMP)
                      ON CONFLICT(id) DO UPDATE SET schema_version=excluded.schema_version,
                      yaml_text=excluded.yaml_text, imported_at=CURRENT_TIMESTAMP""",
                   (str(data.get("schema_version", "")), text))
        db.commit()

def bootstrap_database():
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        exists = db.execute("SELECT 1 FROM snapshot WHERE id=1").fetchone()
    if not exists and DATA_FILE.exists():
        text = DATA_FILE.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        error = validate_snapshot(data)
        if not error:
            import_database(data, text)

def load_home():
    try:
        bootstrap_database()
        with sqlite3.connect(DB_FILE) as db:
            row = db.execute("SELECT yaml_text FROM snapshot WHERE id=1").fetchone()
        if not row:
            return None, None
        return yaml.safe_load(row[0]), None
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

def find_room(data, room_id):
    home = find_home(data)
    if not home:
        return None, None
    floors = home.get("floors", [])
    if isinstance(floors, dict):
        floors = list(floors.values())
    for floor in floors or []:
        rooms = floor.get("rooms", [])
        if isinstance(rooms, dict):
            rooms = list(rooms.values())
        for room in rooms or []:
            if str(room.get("id", "")) == room_id:
                return floor, room
    return None, None

def save_working_data(data):
    import_database(data, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

def pending_change():
    return yaml.safe_load(PENDING_FILE.read_text(encoding="utf-8")) if PENDING_FILE.exists() else None

def add_room_note(data, room_id, note):
    note = note.strip()
    if not note:
        raise ValueError("Note cannot be empty.")
    floor, room = find_room(data, room_id)
    if not room:
        raise ValueError("Room not found.")
    existing = room.get("notes")
    if isinstance(existing, str) and existing.strip():
        room["notes"] = [{"id": "note_legacy_" + uuid.uuid4().hex[:12],
                          "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "text": existing.strip(), "source": "legacy_local"}]
    elif not isinstance(existing, list):
        room["notes"] = []
    entry = {"id": "note_" + uuid.uuid4().hex[:12],
             "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "text": note, "source": "user"}
    room["notes"].append(entry)
    save_working_data(data)
    with sqlite3.connect(DB_FILE) as db:
        db.execute("INSERT INTO change_log(object_id, field_name, old_value, new_value) VALUES(?,?,?,?)",
                   (room_id, "note_added", None, note))
        db.commit()
    return entry


def room_history(object_id, limit=10):
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        return db.execute("""SELECT committed_at, field_name, old_value, new_value
                             FROM change_log WHERE object_id=?
                             ORDER BY id DESC LIMIT ?""", (object_id, limit)).fetchall()

def commit_pending(data):
    proposal = pending_change()
    if not proposal:
        raise ValueError("No pending change.")
    floor, room = find_room(data, str(proposal.get("room_id", "")))
    if not room:
        raise ValueError("Room not found.")
    new_value = str(proposal["new_value"])
    old = room.get("notes")
    if old == new_value:
        PENDING_FILE.unlink(missing_ok=True)
        return str(room.get("id")), False
    room["notes"] = new_value
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    rows = object_rows(data)
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM objects")
        db.executemany("INSERT INTO objects(object_id, object_type, name, parent_id, yaml_text) VALUES(?,?,?,?,?)", rows)
        db.execute("""INSERT INTO snapshot(id, schema_version, yaml_text, imported_at)
                      VALUES(1, ?, ?, CURRENT_TIMESTAMP)
                      ON CONFLICT(id) DO UPDATE SET schema_version=excluded.schema_version,
                      yaml_text=excluded.yaml_text, imported_at=CURRENT_TIMESTAMP""",
                   (str(data.get("schema_version", "")), text))
        db.execute("INSERT INTO change_log(object_id, field_name, old_value, new_value) VALUES(?,?,?,?)",
                   (str(room.get("id")), "notes", None if old is None else str(old), new_value))
        db.commit()
    PENDING_FILE.unlink(missing_ok=True)
    return str(room.get("id")), True

def room_page(data, room_id):
    floor, room = find_room(data, room_id)
    if not room:
        return b"<!doctype html><html><body><h1>Room not found</h1><p><a href='/'>Back</a></p></body></html>"
    home = find_home(data)
    name = html.escape(str(room.get("name", room_id)))
    floor_name = html.escape(str(floor.get("name", "")))

    def index(items):
        return {str(x.get("id")): x for x in (items or []) if isinstance(x, dict) and x.get("id")}

    def resolve(refs, items):
        idx = index(items)
        return [idx[r] for r in (refs or []) if r in idx]

    systems = resolve(room.get("system_refs"), home.get("systems"))
    components = resolve(room.get("component_refs"), home.get("components"))
    assets = resolve(room.get("asset_refs"), home.get("assets"))
    related_ids = {room_id}
    related_ids.update(str(x.get("id")) for x in systems + components + assets if x.get("id"))

    def related(items):
        return [x for x in (items or []) if isinstance(x, dict)
                and related_ids.intersection(set(x.get("related_object_refs", []) or []))]

    def section(title, items):
        if not items:
            return ""
        rows = []
        for item in items:
            label = str(item.get("name") or item.get("id") or "Unknown")
            rows.append("<li>" + html.escape(label) + "</li>")
        return "<h2>" + html.escape(title) + "</h2><ul>" + "".join(rows) + "</ul>"

    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>{name} - Home Agent</title></head><body>",
           "<p><a href='/'>← Espås Hills</a></p>",
           f"<h1>{name}</h1><p>{floor_name}</p>"]

    features = room.get("features", []) or []
    if features:
        out.append("<h2>Features</h2><ul>" + "".join("<li>" + html.escape(str(x)) + "</li>" for x in features) + "</ul>")

    out.append(section("Systems", systems))
    out.append(section("Assets", assets))
    out.append(section("Components", components))
    out.append(section("Documents", related(home.get("documents"))))
    out.append(section("History", related(home.get("events"))))
    out.append(section("Service", related(home.get("service_history"))))
    out.append(section("Maintenance", related(home.get("maintenance"))))
    out.append(section("Costs", related(home.get("costs"))))
    notes = room.get("notes")
    if notes:
        out.append("<h2>Notes</h2><ul>")
        if isinstance(notes, list):
            for note in reversed(notes):
                if isinstance(note, dict):
                    stamp = str(note.get("created_at", ""))
                    text_value = str(note.get("text", ""))
                    out.append("<li>" + html.escape(stamp) + " — " + html.escape(text_value) + "</li>")
                else:
                    out.append("<li>" + html.escape(str(note)) + "</li>")
        else:
            out.append("<li>" + html.escape(str(notes)) + "</li>")
        out.append("</ul>")
    history = room_history(room_id)
    if history:
        out.append("<h2>Local change history</h2><ul>")
        for committed_at, field_name, old_value, new_value in history:
            out.append("<li>" + html.escape(str(committed_at)) + " — " + html.escape(str(field_name)) + ": " + html.escape(str(new_value)) + "</li>")
        out.append("</ul>")
    out.append("<h2>Add note</h2><form method='post' action='/add-note'><input type='hidden' name='room_id' value='" + html.escape(room_id) + "'><input name='note' required><button type='submit'>Save</button></form>")
    out.append("<details><summary>Raw room data</summary><pre>")
    out.append(html.escape(yaml.safe_dump(room, allow_unicode=True, sort_keys=False)))
    out.append("</pre></details><p><em>Read-only. Only explicit snapshot relationships are shown.</em></p></body></html>")
    return "".join(out).encode("utf-8")

def render(data, error=None, notice=None):
    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           "<title>Home Agent</title></head><body>",
           "<h1>Home Agent</h1><p>Version 0.6.2</p>"]
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
                    room_id = str(room.get("id", ""))
                    room_name = html.escape(str(room.get("name", room_id or "Room")))
                    out.append(f"<li><a href='/room?id={quote(room_id)}'>{room_name}</a></li>")
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
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data, error = load_home()
        if parsed.path == "/room" and data and not error:
            room_id = parse_qs(parsed.query).get("id", [""])[0]
            self.send_page(room_page(data, room_id))
            return
        self.send_page(render(data, error))

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/add-note":
            try:
                data, error = load_home()
                if error or not data:
                    raise ValueError(error or "No data loaded.")
                length = int(self.headers.get("Content-Length", "0"))
                fields = parse_qs(self.rfile.read(length).decode("utf-8"))
                room_id = fields.get("room_id", [""])[0]
                add_room_note(data, room_id, fields.get("note", [""])[0])
                fresh, load_error = load_home()
                if load_error:
                    raise ValueError(load_error)
                body = room_page(fresh, room_id).decode("utf-8")
                body = body.replace("<h1>", "<p><strong>Note saved locally.</strong></p><h1>", 1)
                self.send_page(body.encode("utf-8"))
                return
            except Exception as exc:
                data, _ = load_home()
                self.send_page(render(data, error=str(exc)), 400)
                return
        if path != "/import":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_UPLOAD:
                raise ValueError("Upload is empty or larger than 5 MB.")
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")})
            raw = form["snapshot"].file.read(MAX_UPLOAD + 1)
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
                with os.fdopen(fd, "w", encoding="utf-8") as out:
                    out.write(text); out.flush(); os.fsync(out.fileno())
                os.replace(tmp_name, DATA_FILE)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            import_database(data, text)
            self.send_page(render(data, notice="Snapshot imported successfully into local SQLite."))
        except Exception as exc:
            data, existing_error = load_home()
            self.send_page(render(data, error=str(exc) if not existing_error else existing_error), 400)

    def log_message(self, format, *args):
        print(format % args)

HTTPServer((HOST, PORT), Handler).serve_forever()
