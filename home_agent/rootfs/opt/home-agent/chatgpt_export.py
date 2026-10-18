"""Opt-in asynchronous publication. Drive never gates local domain commits."""
import hashlib
import json
import os
import re
import stat
import threading
import uuid
from pathlib import Path

import drive_auth
from drive_publish import DrivePublisher, PublishError, file_url
import house_context

CONFIG = Path("/data/chatgpt_drive_oauth.json")
STATE = Path("/data/chatgpt_drive_state.json")
INTERVAL = 15 * 60
PURPOSE = "home-agent-chatgpt-read"


def private_json(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 1024 * 1024:
        raise PublishError("Publiceringens konfiguration måste vara en privat fil (0600)")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublishError("Ogiltig publiceringskonfiguration")
    return value


def save_state(path, state):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def config_enabled(config):
    return config.get("purpose") == PURPOSE and config.get("enabled") is True


def validate_config(config):
    if any(not isinstance(config.get(k), str) or not config[k] for k in
           ("client_id", "client_secret", "refresh_token", "expected_email")):
        raise PublishError("Drive-anslutningen är ofullständig")


def publish_once(db_path, source_dir, config_path=CONFIG, state_path=STATE):
    config_path, state_path = Path(config_path), Path(state_path)
    if not config_path.exists():
        return False
    config = private_json(config_path)
    if not config_enabled(config):
        return False
    validate_config(config)
    state = private_json(state_path) if state_path.exists() else {"instance": uuid.uuid4().hex}
    if not re.fullmatch(r"[0-9a-f]{32}", state.get("instance", "")):
        raise PublishError("Publiceringens installationsidentitet är ogiltig")
    if state.get("account") and state["account"] != config["expected_email"].casefold():
        raise PublishError("Drive-kontot har ändrats; konfigurera publiceringen på nytt")
    state["account"] = config["expected_email"].casefold()
    save = lambda: save_state(state_path, state)
    save()  # installation identity survives a crash during the first Drive create
    try:
        context, sources = house_context.read_context(db_path)
        revision = hashlib.sha256(house_context.canonical(context)).hexdigest()
        checked_at = house_context.now()
        token = drive_auth.access_token(config_path)
        drive = DrivePublisher(token, state["instance"], state, save)
        root = drive.ensure("root", "Home Agent — ChatGPT läsunderlag")
        originals = drive.ensure("sources", "Källor", root)
        links = {}
        for source in sources:
            body = house_context.original_bytes(source, source_dir)
            # File naming is a convenience; permanent Source identity stays in the read model.
            name = str(source["name"] or "original").replace("\r", " ").replace("\n", " ")[:180]
            mime = source["media_type"] if source["media_type"] in (
                "application/pdf", "image/jpeg", "image/png", "image/webp", "text/plain") else "application/octet-stream"
            source_key = hashlib.sha256((source["id"] + "\0" + source["sha256"]).encode()).hexdigest()
            fid = drive.ensure("source-" + source_key,
                               name, originals, body, mime)
            links[source["id"]] = file_url(fid)
            del body
        generation = drive.ensure("generation-" + revision, "Läsunderlag " + revision[:12], root)
        # Store first-generation timestamp locally so retries produce identical bytes.
        stamps = state.setdefault("generation_times", {})
        stamps.setdefault(revision, checked_at)
        save()
        nibe_body = house_context.render_nibe(context, links, stamps[revision], revision)
        nibe_id = drive.ensure("nibe-" + revision, "Home Agent — NIBE S1255.txt", generation, nibe_body)
        # Commit marker is last. A failed earlier upload cannot publish a partial generation.
        index = house_context.render_index(context, file_url(nibe_id), checked_at, revision)
        index_id = drive.ensure("index", "Home Agent — husindex.txt", root, index, mutable=True)
        state.update(last_success=checked_at, revision=revision, index_url=file_url(index_id),
                     folder_url="https://drive.google.com/drive/folders/" + root, error=None)
        save()
        return True
    except Exception as exc:
        # Only messages constructed by our bounded adapters may reach the UI.
        reason = str(exc) if isinstance(exc, (house_context.ContextError, PublishError)) else "Drive-anslutningen behöver kontrolleras"
        state["error"] = reason + ". Tidigare läskopia kan vara inaktuell. Nytt försök sker automatiskt."
        try:
            save()
        except OSError:
            pass
        raise


def status(config_path=CONFIG, state_path=STATE):
    try:
        if not Path(config_path).exists():
            return {"enabled": False}
        config = private_json(config_path)
        if not config_enabled(config):
            return {"enabled": False}
        validate_config(config)
        state = private_json(state_path) if Path(state_path).exists() else {}
        result = {"enabled": True, "last_success": state.get("last_success"), "error": state.get("error")}
        if state.get("account") and state["account"] != config.get("expected_email", "").casefold():
            result["error"] = "Drive-kontot har ändrats; anslutningen behöver konfigureras på nytt."
            return result
        url = state.get("index_url", "")
        if re.fullmatch(r"https://drive\.google\.com/file/d/[A-Za-z0-9_-]{1,200}/view", url):
            result["index_url"] = url
        return result
    except (OSError, ValueError, TypeError, AttributeError, PublishError):
        return {"enabled": False, "error": "Drive-anslutningen behöver kontrolleras."}


def run(db_path, source_dir, stop):
    while not stop.is_set():
        try:
            publish_once(db_path, source_dir)
        except Exception:
            print("Home Agent: ChatGPT-publicering misslyckades; nytt försök om 15 minuter.", flush=True)
        stop.wait(INTERVAL)


def launch(db_path, source_dir):
    stop = threading.Event()
    threading.Thread(target=run, args=(db_path, source_dir, stop), daemon=True,
                     name="chatgpt-drive-export").start()
    return stop
