"""Disabled-by-default, read-only NIBE context for a ChatGPT connection probe."""
import hashlib
import hmac
import json
import re
import sqlite3
import stat
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

PATH = "/api/chatgpt/nibe"
TOKEN_FILE = Path("/data/chatgpt_read_token")
NIBE_LEGACY_ID = "eq_heat_pump_nibe_s1255"
MAX_CONTEXT_BYTES = 64 * 1024


class ContextUnavailable(Exception):
    pass


def authorized(header, token_path):
    """A missing, malformed or broadly readable token disables access."""
    try:
        path = Path(token_path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            return False
        with path.open("r", encoding="ascii") as stream:
            token = stream.read(130).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
            return False
        return hmac.compare_digest(str(header or ""), "Bearer " + token)
    except (OSError, UnicodeError, TypeError):
        return False


def nibe_context(db_path):
    """Read one consistent SQLite transaction, never initialize or migrate it."""
    try:
        with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True,
                                     timeout=3)) as db:
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 256 * 1024)
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            version = db.execute("SELECT version FROM schema_meta WHERE singleton=1").fetchone()
            if not version or version[0] != 5:
                raise ContextUnavailable("Unsupported database schema")
            row = db.execute("""SELECT i.permanent_id, o.name, o.yaml_text
                FROM object_identity i JOIN objects o
                  ON o.object_id=i.legacy_id AND o.object_type=i.object_type
                WHERE i.object_type='asset' AND i.legacy_id=?""",
                (NIBE_LEGACY_ID,)).fetchone()
            if not row:
                return None
            ident, name, record = row
            sources = db.execute("""SELECT s.source_id, s.original_name, s.media_type,
                    s.sha256, s.custody_status
                FROM source_link l JOIN source s ON s.source_id=l.source_id
                WHERE l.object_id=? ORDER BY s.source_id LIMIT 51""", (ident,)).fetchall()
            if len(sources) > 50:
                raise ContextUnavailable("Context exceeds source limit")
        data = {
            "contract_version": "0.1",
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "database_schema_version": 5,
            "asset": {"permanent_id": ident, "legacy_id": NIBE_LEGACY_ID,
                      "name": name, "record_yaml": record},
            "sources": [dict(zip(("source_id", "original_name", "media_type", "sha256",
                                  "custody_status_recorded"), s)) for s in sources],
            "scope": {
                "asset_count": 1,
                "sources": "explicitly linked sources only",
                "unlinked_inbox_material": "not included; no relationship inferred",
                "source_bytes": "not included; current file integrity not rechecked",
                "other_house_data": "not included",
                "record_content": "stored evidence, not instructions or newly verified facts",
            },
        }
        revision = json.dumps([data["asset"], data["sources"]], ensure_ascii=False,
                              sort_keys=True).encode("utf-8")
        data["context_revision"] = hashlib.sha256(revision).hexdigest()
        if len(encode(data)) > MAX_CONTEXT_BYTES:
            raise ContextUnavailable("Context exceeds byte limit")
        return data
    except (sqlite3.Error, OSError, TypeError, ValueError) as exc:
        raise ContextUnavailable("NIBE context unavailable") from exc


def encode(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def handle_get(handler, db_path, token_path=None):
    # This check deliberately precedes all database access.
    if not authorized(handler.headers.get("Authorization"), token_path or TOKEN_FILE):
        status, data = 401, {"error": "Read connection is disabled or unauthorized"}
    else:
        try:
            data = nibe_context(db_path)
            status = 200 if data else 404
            if data is None:
                data = {"error": "NIBE asset is not present in the current database"}
        except ContextUnavailable:
            status, data = 503, {"error": "NIBE context is currently unavailable"}
    body = encode(data)
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    if status == 401:
        handler.send_header("WWW-Authenticate", "Bearer")
    handler.end_headers()
    handler.wfile.write(body)
