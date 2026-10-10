from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
import cgi
import ui
import inbox_queue
import drive_import
import drive_register
import drive_auth
import copy
import hashlib
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
SOURCE_DIR = Path("/data/sources")
MAX_UPLOAD = 5 * 1024 * 1024
MAX_SOURCE_UPLOAD = 25 * 1024 * 1024
MAX_CAPTURE_REQUEST = MAX_SOURCE_UPLOAD + 1024 * 1024
DB_SCHEMA_VERSION = 5
DRIVE_AUTH_FILE = Path('/data/drive_import_oauth.json')
DRIVE_ROOT_FILE = Path('/data/drive_import_root_id')

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
    if version < 3:
        db.execute("CREATE TABLE IF NOT EXISTS source (source_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, media_type TEXT, original_name TEXT, sha256 TEXT, captured_at TEXT, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, storage_ref TEXT, custody_status TEXT NOT NULL DEFAULT 'pending')")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_source_sha256 ON source(sha256) WHERE sha256 IS NOT NULL")
        db.execute("CREATE TABLE IF NOT EXISTS ingest_occurrence (occurrence_id TEXT PRIMARY KEY, source_id TEXT, channel TEXT NOT NULL, external_provider TEXT, external_ref TEXT, observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, cleanup_status TEXT NOT NULL DEFAULT 'not_required', FOREIGN KEY(source_id) REFERENCES source(source_id))")
        db.execute("CREATE TABLE IF NOT EXISTS inbox_item (inbox_item_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, occurrence_id TEXT, stage TEXT NOT NULL DEFAULT 'captured', status TEXT NOT NULL DEFAULT 'pending', failed_stage TEXT, last_error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at TEXT, FOREIGN KEY(source_id) REFERENCES source(source_id), FOREIGN KEY(occurrence_id) REFERENCES ingest_occurrence(occurrence_id))")
        db.execute("CREATE INDEX IF NOT EXISTS idx_ingest_source ON ingest_occurrence(source_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_inbox_source ON inbox_item(source_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_inbox_state ON inbox_item(status, stage)")
        db.execute("UPDATE schema_meta SET version=3 WHERE singleton=1")
        version = 3
    if version < 4:
        inbox_queue.migrate(db)
        db.execute("UPDATE schema_meta SET version=4 WHERE singleton=1")
        version = 4
    if version < 5:
        db.execute("""CREATE TABLE IF NOT EXISTS source_link (
            source_id TEXT NOT NULL REFERENCES source(source_id),
            object_id TEXT NOT NULL REFERENCES object_identity(permanent_id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(source_id, object_id))""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_source_link_object ON source_link(object_id)")
        db.execute("UPDATE schema_meta SET version=5 WHERE singleton=1")
        version = 5
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

def identity_map(db):
    return {str(legacy): str(permanent) for permanent, legacy in db.execute("SELECT permanent_id, legacy_id FROM object_identity").fetchall()}

def relation_rows(data, identities):
    home = find_home(data)
    if not home:
        return []
    result = set()
    def add(source, relation, target):
        source_id = identities.get(str(source))
        target_id = identities.get(str(target))
        if source_id and target_id:
            result.add((source_id, relation, target_id, str(source), str(target)))
    home_id = str(home.get("id", ""))
    for floor in home.get("floors", []) or []:
        floor_id = str(floor.get("id", ""))
        add(floor_id, "parent", home_id)
        for room in floor.get("rooms", []) or []:
            room_id = str(room.get("id", ""))
            add(room_id, "parent", floor_id)
            for field, relation in (("system_refs", "system"), ("component_refs", "component"), ("asset_refs", "asset")):
                for target in room.get(field, []) or []:
                    add(room_id, relation, target)
        for space in floor.get("spaces", []) or []:
            add(str(space.get("id", "")), "parent", floor_id)
    return sorted(result)

def import_database(data, text, audit_entry=None):
    init_db()
    rows = object_rows(data)
    with sqlite3.connect(DB_FILE) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM objects")
        db.executemany("INSERT INTO objects(object_id, object_type, name, parent_id, yaml_text) VALUES(?,?,?,?,?)", rows)
        for legacy_id, object_type, _name, _parent, _yaml in rows:
            db.execute("INSERT OR IGNORE INTO object_identity(permanent_id, object_type, legacy_id) VALUES(?,?,?)", (uuid7(), object_type, legacy_id))
        db.execute("DELETE FROM object_relation")
        db.executemany("INSERT INTO object_relation(source_id, relation_type, target_id, legacy_source_ref, legacy_target_ref) VALUES(?,?,?,?,?)", relation_rows(data, identity_map(db)))
        db.execute("""INSERT INTO snapshot(id, schema_version, yaml_text, imported_at)
                      VALUES(1, ?, ?, CURRENT_TIMESTAMP)
                      ON CONFLICT(id) DO UPDATE SET schema_version=excluded.schema_version,
                      yaml_text=excluded.yaml_text, imported_at=CURRENT_TIMESTAMP""",
                   (str(data.get("schema_version", "")), text))
        if audit_entry:
            db.execute("INSERT INTO change_log(object_id, field_name, old_value, new_value) VALUES(?,?,?,?)", audit_entry)
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

def database_diagnostics():
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        version = db.execute("SELECT version FROM schema_meta WHERE singleton=1").fetchone()
        objects = db.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
        identities = db.execute("SELECT COUNT(*) FROM object_identity").fetchone()[0]
        unmapped = db.execute("SELECT COUNT(*) FROM objects o LEFT JOIN object_identity i ON i.object_type=o.object_type AND i.legacy_id=o.object_id WHERE i.permanent_id IS NULL").fetchone()[0]
        relations = db.execute("SELECT COUNT(*) FROM object_relation").fetchone()[0]
        broken = db.execute("SELECT COUNT(*) FROM object_relation r LEFT JOIN object_identity s ON s.permanent_id=r.source_id LEFT JOIN object_identity t ON t.permanent_id=r.target_id WHERE s.permanent_id IS NULL OR t.permanent_id IS NULL").fetchone()[0]
        sources = db.execute("SELECT COUNT(*) FROM source").fetchone()[0]
        occurrences = db.execute("SELECT COUNT(*) FROM ingest_occurrence").fetchone()[0]
        inbox_items = db.execute("SELECT COUNT(*) FROM inbox_item").fetchone()[0]
        orphan_occurrences = db.execute("SELECT COUNT(*) FROM ingest_occurrence o LEFT JOIN source s ON s.source_id=o.source_id WHERE o.source_id IS NOT NULL AND s.source_id IS NULL").fetchone()[0]
        orphan_inbox = db.execute("SELECT COUNT(*) FROM inbox_item i LEFT JOIN source s ON s.source_id=i.source_id WHERE s.source_id IS NULL").fetchone()[0]
        duplicate_hashes = db.execute("SELECT COUNT(*) FROM (SELECT sha256 FROM source WHERE sha256 IS NOT NULL GROUP BY sha256 HAVING COUNT(*) > 1)").fetchone()[0]
    return version[0] if version else 0, objects, identities, unmapped, relations, broken, sources, occurrences, inbox_items, orphan_occurrences, orphan_inbox, duplicate_hashes

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
    import_database(data, yaml.safe_dump(data, allow_unicode=True, sort_keys=False), (room_id, "note_added", None, note))
    return entry


def capture_source(filename, media_type, raw):
    if not raw:
        raise ValueError("File is empty.")
    digest = hashlib.sha256(raw).hexdigest()
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT source_id, storage_ref FROM source WHERE sha256=?", (digest,)).fetchone()
            if row:
                source_id, storage_ref = row
            else:
                source_id = uuid7()
                storage_ref = str(SOURCE_DIR / source_id)
                tmp = SOURCE_DIR / (source_id + ".tmp")
                with tmp.open("wb") as out:
                    out.write(raw)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(tmp, storage_ref)
                db.execute("INSERT INTO source(source_id, source_type, media_type, original_name, sha256, storage_ref, custody_status) VALUES(?,?,?,?,?,?,?)",
                           (source_id, "file", media_type or None, filename or None, digest, storage_ref, "local_verified"))
            occurrence_id = uuid7()
            inbox_item_id = uuid7()
            db.execute("INSERT INTO ingest_occurrence(occurrence_id, source_id, channel, external_ref, cleanup_status) VALUES(?,?,?,?,?)",
                       (occurrence_id, source_id, "home_agent_upload", filename or None, "not_required"))
            db.execute("INSERT INTO inbox_item(inbox_item_id, source_id, occurrence_id, stage, status) VALUES(?,?,?,?,?)",
                       (inbox_item_id, source_id, occurrence_id, "captured", "pending"))
            db.commit()
            return source_id, occurrence_id, inbox_item_id, bool(row)
        except Exception:
            db.rollback()
            raise



def capture_source_stream(filename, media_type, stream):
    """Capture a bounded upload without holding the original in Raspberry Pi RAM."""
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".capture-", dir=str(SOURCE_DIR))
    digest = hashlib.sha256()
    total = 0
    promoted = None
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                block = stream.read(256 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAX_SOURCE_UPLOAD:
                    raise ValueError("File is larger than 25 MB.")
                digest.update(block)
                out.write(block)
            if not total:
                raise ValueError("File is empty.")
            out.flush()
            os.fsync(out.fileno())
        with sqlite3.connect(DB_FILE) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT source_id FROM source WHERE sha256=?", (digest.hexdigest(),)).fetchone()
                if row:
                    source_id = row[0]
                else:
                    source_id = uuid7()
                    promoted = str(SOURCE_DIR / source_id)
                    os.replace(tmp_name, promoted)
                    db.execute("INSERT INTO source(source_id, source_type, media_type, original_name, sha256, storage_ref, custody_status) VALUES(?,?,?,?,?,?,?)",
                               (source_id, "file", media_type or None, filename or None, digest.hexdigest(), promoted, "local_verified"))
                occurrence_id = uuid7()
                inbox_item_id = uuid7()
                db.execute("INSERT INTO ingest_occurrence(occurrence_id, source_id, channel, external_ref, cleanup_status) VALUES(?,?,?,?,?)",
                           (occurrence_id, source_id, "home_agent_upload", filename or None, "not_required"))
                db.execute("INSERT INTO inbox_item(inbox_item_id, source_id, occurrence_id, stage, status) VALUES(?,?,?,?,?)",
                           (inbox_item_id, source_id, occurrence_id, "captured", "pending"))
                db.commit()
                return source_id, occurrence_id, inbox_item_id, bool(row)
            except Exception:
                db.rollback()
                if promoted:
                    os.unlink(promoted)
                raise
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def import_drive_asset(asset_id, file_id):
    """Import only a file proven to descend from the configured shared root."""
    if not asset_detail(asset_id)[0]:
        raise ValueError("Unknown asset")
    token = drive_auth.access_token(DRIVE_AUTH_FILE)
    root_id = DRIVE_ROOT_FILE.read_text(encoding="utf-8").strip()
    if not token or not root_id:
        raise ValueError("Drive import account is not configured")
    drive_import.assert_under_shared_root(file_id, root_id, token)
    downloaded = drive_import.download_original(file_id, token, SOURCE_DIR)
    try:
        return drive_register.register_drive_original(DB_FILE, SOURCE_DIR, downloaded, asset_id, uuid7)
    finally:
        Path(downloaded["temporary_path"]).unlink(missing_ok=True)


def asset_detail(asset_id):
    """Resolve only an explicitly imported asset; never infer relationships from filenames."""
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        row = db.execute("""SELECT i.permanent_id, o.name, o.yaml_text
                            FROM object_identity i JOIN objects o
                              ON o.object_id=i.legacy_id AND o.object_type=i.object_type
                            WHERE i.permanent_id=? AND i.object_type='asset'""", (asset_id,)).fetchone()
        if not row:
            return None, []
        files = db.execute("""SELECT s.source_id,s.original_name,s.media_type
                              FROM source_link l JOIN source s ON s.source_id=l.source_id
                              WHERE l.object_id=? ORDER BY l.created_at DESC,s.source_id""",
                           (asset_id,)).fetchall()
        return {"id":row[0],"name":row[1],"data":yaml.safe_load(row[2])}, files

def link_asset_source(asset_id, source_id):
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        valid = db.execute("""SELECT 1 FROM object_identity i JOIN objects o
                              ON o.object_id=i.legacy_id AND o.object_type=i.object_type
                              WHERE i.permanent_id=? AND i.object_type='asset'""", (asset_id,)).fetchone()
        exists = db.execute("SELECT 1 FROM source WHERE source_id=? AND custody_status='local_verified'", (source_id,)).fetchone()
        if not valid or not exists:
            raise ValueError("Unknown asset or unverified source.")
        db.execute("INSERT OR IGNORE INTO source_link(source_id,object_id) VALUES(?,?)", (source_id,asset_id))
        db.commit()

def asset_candidates():
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        return db.execute("""SELECT i.permanent_id,o.name FROM object_identity i
                             JOIN objects o ON o.object_id=i.legacy_id AND o.object_type=i.object_type
                             WHERE i.object_type='asset' ORDER BY o.name""").fetchall()

def source_candidates():
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        return db.execute("""SELECT source_id,original_name,media_type FROM source
                             WHERE custody_status='local_verified' ORDER BY imported_at DESC LIMIT 200""").fetchall()

def verified_source(source_id):
    """Return verified file path and metadata without loading the file into RAM."""
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        row = db.execute("SELECT storage_ref,media_type,original_name,sha256 FROM source WHERE source_id=? AND custody_status='local_verified'", (source_id,)).fetchone()
    if not row:
        return None
    storage, media, name, digest = row
    try:
        file_path = Path(storage).resolve(strict=True)
        if not file_path.is_relative_to(SOURCE_DIR.resolve(strict=True)) or not file_path.is_file():
            return None
        calculated = hashlib.sha256()
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(256 * 1024), b""):
                calculated.update(block)
        if not digest or calculated.hexdigest() != digest:
            return None
        return file_path, media, name
    except OSError:
        return None

def inbox_source(inbox_id):
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        return db.execute("""SELECT s.storage_ref,s.media_type,s.original_name,s.sha256
                             FROM inbox_item i JOIN source s ON s.source_id=i.source_id
                             WHERE i.inbox_item_id=? AND i.status!='dismissed'""",
                          (inbox_id,)).fetchone()

def dismiss_inbox(inbox_id):
    init_db()
    with sqlite3.connect(DB_FILE, timeout=15) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM inbox_item WHERE inbox_item_id=?", (inbox_id,)).fetchone()
        if not row:
            db.rollback()
            return False
        db.execute("""UPDATE inbox_item SET status='dismissed',updated_at=CURRENT_TIMESTAMP
                      WHERE inbox_item_id=?""", (inbox_id,))
        db.commit()
        return True

def inbox_rows(limit=100):
    init_db()
    with sqlite3.connect(DB_FILE) as db:
        return db.execute("""SELECT i.inbox_item_id, i.created_at, i.stage, i.status,
                                    s.original_name, s.media_type, s.source_id,
                                    o.channel, o.occurrence_id
                             FROM inbox_item i
                             JOIN source s ON s.source_id=i.source_id
                             LEFT JOIN ingest_occurrence o ON o.occurrence_id=i.occurrence_id
                             WHERE i.status!='dismissed'
                             ORDER BY i.created_at DESC, i.inbox_item_id DESC
                             LIMIT ?""", (limit,)).fetchall()

def inbox_page():
    rows = inbox_rows()
    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           "<title>Inbox - Home Agent</title></head><body>",
           "<p><a href='/'>← Home</a></p><h1>Inbox</h1>",
           "<p><div class='ha-panel'><strong>Väntar på analys</strong><p>Filerna är tryggt sparade lokalt. Automatisk analys kommer i ett senare steg; inga uppgifter har registrerats.</p></div></p>"]
    if not rows:
        out.append("<p>Inbox är tom. Lägg till en fil från startsidan.</p>")
    else:
        out.append("<ul>")
        for inbox_id, created_at, stage, status, original_name, media_type, source_id, channel, occurrence_id in rows:
            out.append("<li><strong>" + html.escape(str(original_name or "Unnamed source")) + "</strong><br>")
            out.append(html.escape(str(created_at)) + " · " + html.escape(str(status)) + " / " + html.escape(str(stage)))
            if media_type:
                out.append(" · " + html.escape(str(media_type)))
            if channel:
                out.append(" · " + html.escape(str(channel)))
            out.append("<details><summary>Tekniska ID:n</summary><small>InboxItem " + html.escape(str(inbox_id)) +
                       "<br>Source " + html.escape(str(source_id)) +
                       "<br>IngestOccurrence " + html.escape(str(occurrence_id or "")) + "</small></details></li>")
        out.append("</ul>")
    out.append("</body></html>")
    return "".join(out).encode("utf-8")

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
        return ui.room_detail_page(room_id, None, None, {}, [])
    home = find_home(data)

    def index(items):
        return {str(x.get("id")): x for x in (items or []) if isinstance(x, dict) and x.get("id")}

    def resolve(refs, items):
        idx = index(items)
        return [idx[str(ref)] for ref in (refs or []) if str(ref) in idx]

    systems = resolve(room.get("system_refs"), home.get("systems"))
    components = resolve(room.get("component_refs"), home.get("components"))
    assets = resolve(room.get("asset_refs"), home.get("assets"))
    related_ids = {room_id}
    related_ids.update(str(x.get("id")) for x in systems + components + assets if x.get("id"))

    def related(items):
        return [x for x in (items or []) if isinstance(x, dict)
                and related_ids.intersection(set(str(ref) for ref in (x.get("related_object_refs", []) or [])))]

    sections = {
        "System": systems, "Utrustning": assets, "Komponenter": components,
        "Dokument": related(home.get("documents")),
        "Händelser": related(home.get("events")),
        "Service": related(home.get("service_history")),
        "Underhåll": related(home.get("maintenance")),
        "Kostnader": related(home.get("costs")),
    }
    return ui.room_detail_page(room_id, floor, room, sections, room_history(room_id))

def render(data, error=None, notice=None):
    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width,initial-scale=1'>",
           "<title>Home Agent</title></head><body>",
           "<h1>Home Agent</h1><p>Version 0.7.2</p><p><a href='/inbox'>Inbox</a></p>"]
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
    out.append("""<hr><h2>Lägg till i Inbox</h2>
<form method="post" action="/capture" enctype="multipart/form-data">
<input type="file" name="source" required>
<button type="submit">Spara i Inbox</button>
</form>
<p>The original file is stored locally before an Inbox item is created.</p>
<hr><h2>Import YAML snapshot</h2>
<form method="post" action="/import" enctype="multipart/form-data">
<input type="file" name="snapshot" accept=".yaml,.yml,text/yaml,application/x-yaml" required>
<button type="submit">Import</button>
</form>
<p>The file is validated and stored privately in this add-on's local data storage.</p>
</body></html>""")
    return "".join(out).encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def send_page(self, body, status=200):
        if b"<html" in body.lower() and b"class='app'" not in body:
            body = body.replace(b"</head>", b"<link rel='stylesheet' href='/ui.css'></head>", 1)
            nav = b"<nav class='ha-nav' aria-label='Navigation'><a href='/'>Hem</a><a href='/inbox'>Inbox</a></nav>"
            body = body.replace(b"</body>", nav + b"</body>", 1)
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/inbox", "/rooms", "/add", "/todo", "/search", "/more"):
            if parsed.path == "/inbox":
                self.send_page(ui.inbox_page(inbox_rows(), inbox_queue.state(DB_FILE)))
            elif parsed.path == "/add":
                self.send_page(ui.add_page())
            elif parsed.path == "/todo":
                self.send_page(ui.todo_page(len(inbox_rows())))
            elif parsed.path == "/search":
                self.send_page(ui.search_page())
            elif parsed.path == "/more":
                self.send_page(ui.more_page())
            else:
                data, error = load_home()
                if parsed.path == "/rooms":
                    self.send_page(ui.rooms_page(data))
                else:
                    self.send_page(ui.home_page(data, len(inbox_rows()), error=error))
            return
        if parsed.path == '/assets':
            self.send_page(ui.assets_page(asset_candidates()))
            return
        if parsed.path == '/asset':
            asset_id = parse_qs(parsed.query).get('id',[''])[0]
            asset, files = asset_detail(asset_id)
            self.send_page(ui.asset_page(asset, files, source_candidates()), 200 if asset else 404)
            return
        if parsed.path == '/source/file':
            source_id = parse_qs(parsed.query).get('id',[''])[0]
            if not any(row[0]==source_id for row in asset_detail(parse_qs(parsed.query).get('asset',[''])[0])[1]):
                self.send_error(404)
                return
            verified = verified_source(source_id)
            if not verified:
                self.send_error(404)
                return
            file_path,media,name = verified
            allowed = {'image/jpeg','image/png','image/gif','image/webp','application/pdf','text/plain'}
            content_type = media if media in allowed else 'application/octet-stream'
            self.send_response(200)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Disposition','inline' if content_type in allowed else 'attachment')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy','sandbox')
            self.send_header('Content-Length',str(file_path.stat().st_size))
            self.end_headers()
            with file_path.open('rb') as stream:
                for block in iter(lambda: stream.read(256 * 1024), b''):
                    self.wfile.write(block)
            return
        if parsed.path == "/inbox/file":
            inbox_id = parse_qs(parsed.query).get("id", [""])[0]
            source = inbox_source(inbox_id)
            if not source:
                self.send_error(404)
                return
            storage, media, filename, digest = source
            try:
                file_path = Path(storage).resolve(strict=True)
                if not file_path.is_relative_to(SOURCE_DIR.resolve(strict=True)) or not file_path.is_file():
                    raise ValueError("Invalid source location")
                raw = file_path.read_bytes()
                if not digest or hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError("Original checksum mismatch")
            except (OSError, ValueError):
                self.send_error(404, "Original unavailable")
                return
            allowed = {"image/jpeg","image/png","image/gif","image/webp","application/pdf","text/plain"}
            content_type = media if media in allowed else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", "inline" if content_type in allowed else "attachment")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "sandbox")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/ui.css":
            css = Path("/opt/home-agent/ui.css").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(css)))
            self.end_headers()
            self.wfile.write(css)
            return
        if parsed.path == "/health":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/diagnostics":
            schema, objects, identities, unmapped, relations, broken, sources, occurrences, inbox_items, orphan_occurrences, orphan_inbox, duplicate_hashes = database_diagnostics()
            body = ("schema_version=%s\nobjects=%s\nidentities=%s\nunmapped_objects=%s\nrelations=%s\nbroken_relations=%s\nsources=%s\ningest_occurrences=%s\ninbox_items=%s\norphan_occurrences=%s\norphan_inbox_items=%s\nduplicate_source_hashes=%s\n" % (schema, objects, identities, unmapped, relations, broken, sources, occurrences, inbox_items, orphan_occurrences, orphan_inbox, duplicate_hashes)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/inbox":
            self.send_page(inbox_page())
            return
        data, error = load_home()
        if parsed.path == "/room" and data and not error:
            room_id = parse_qs(parsed.query).get("id", [""])[0]
            self.send_page(room_page(data, room_id))
            return
        self.send_page(render(data, error))

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/asset/drive-import':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 4096:
                    raise ValueError('Invalid import form length')
                fields = parse_qs(self.rfile.read(length).decode('utf-8'))
                asset_id = fields.get('asset_id', [''])[0]
                file_id = fields.get('drive_file_id', [''])[0].strip()
                if not file_id:
                    raise ValueError('Missing Drive file ID')
                import_drive_asset(asset_id, file_id)
                self.send_response(303)
                self.send_header('Location', '/asset?id=' + quote(asset_id, safe=''))
                self.end_headers()
            except (ValueError, OSError, drive_import.DriveImportError, drive_auth.DriveAuthError) as exc:
                self.send_error(400, str(exc))
            return
        if path == '/asset/link':
            try:
                length = int(self.headers.get('Content-Length','0'))
                if length < 1 or length > 4096:
                    raise ValueError('Invalid form length.')
                fields = parse_qs(self.rfile.read(length).decode('utf-8'))
                asset_id = fields.get('asset_id',[''])[0]
                link_asset_source(asset_id, fields.get('source_id',[''])[0])
                self.send_response(303)
                self.send_header('Location','/asset?id='+quote(asset_id,safe=''))
                self.end_headers()
            except ValueError as exc:
                self.send_error(400,str(exc))
            return
        if path == '/asset/upload':
            try:
                length = int(self.headers.get('Content-Length','0'))
                if length <= 0 or length > MAX_UPLOAD:
                    raise ValueError('Upload is empty or larger than 5 MB.')
                form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD':'POST','CONTENT_TYPE':self.headers.get('Content-Type','')})
                asset_id = str(form.getfirst('asset_id',''))
                if not asset_detail(asset_id)[0]:
                    raise ValueError('Unknown asset.')
                item = form['source']
                raw = item.file.read(MAX_UPLOAD+1)
                if len(raw)>MAX_UPLOAD:
                    raise ValueError('File is larger than 5 MB.')
                source_id,_,_,_ = capture_source(item.filename,item.type,raw)
                link_asset_source(asset_id,source_id)
                self.send_response(303)
                self.send_header('Location','/asset?id='+quote(asset_id,safe=''))
                self.end_headers()
            except (ValueError,KeyError) as exc:
                self.send_error(400,str(exc))
            return
        if path == "/inbox/dismiss":
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 2048:
                self.send_error(400)
                return
            fields = parse_qs(self.rfile.read(length).decode("utf-8"))
            inbox_id = fields.get("id", [""])[0]
            if not dismiss_inbox(inbox_id):
                self.send_error(404)
                return
            self.send_response(303)
            self.send_header("Location", "/inbox")
            self.end_headers()
            return
        if path in ("/inbox/analyze", "/inbox/pause", "/inbox/resume"):
            action = {"/inbox/analyze": "start", "/inbox/pause": "pause", "/inbox/resume": "resume"}[path]
            inbox_queue.command(DB_FILE, action)
            self.send_response(303)
            self.send_header("Location", "/inbox")
            self.end_headers()
            return
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
                self.send_page(ui.home_page(data, len(inbox_rows()), error=str(exc)), 400)
                return
        if path == "/capture":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_CAPTURE_REQUEST:
                    raise ValueError("Upload is empty or larger than 26 MB.")
                form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")})
                item = form["source"]
                source_id, occurrence_id, inbox_item_id, duplicate = capture_source_stream(item.filename, item.type, item.file)
                data, error = load_home()
                notice = "Saved to Inbox locally." + (" Exact source already existed; new ingest occurrence recorded." if duplicate else "")
                self.send_page(ui.home_page(data, len(inbox_rows()), notice=notice, error=error))
                return
            except Exception as exc:
                data, existing_error = load_home()
                self.send_page(ui.home_page(data, len(inbox_rows()), error=str(exc) if not existing_error else existing_error), 400)
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
            self.send_page(ui.home_page(data, len(inbox_rows()), notice="Snapshot imported successfully into local SQLite."))
        except Exception as exc:
            data, existing_error = load_home()
            self.send_page(render(data, error=str(exc) if not existing_error else existing_error), 400)

    def log_message(self, format, *args):
        print(format % args)

if __name__ == "__main__":
    bootstrap_database()
    inbox_queue.launch(DB_FILE, SOURCE_DIR)
    HTTPServer((HOST, PORT), Handler).serve_forever()
