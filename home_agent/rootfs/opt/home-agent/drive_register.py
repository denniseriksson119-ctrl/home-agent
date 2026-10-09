"""Transactional registration of downloaded Google Drive originals in Home Agent.

Import is explicit and linked to an existing permanent Asset ID. The Google
transport and OAuth authentication are handled by separate layers.
"""
import hashlib
import os
import sqlite3
from pathlib import Path


def register_drive_original(db_path, source_dir, downloaded, asset_id, new_id):
    """Register a verified temporary download, provenance and asset relation.

    `new_id` is the application's UUIDv7 generator. Returns (source_id, duplicate).
    The caller must first authorize the Drive file's shared-root ancestry.
    """
    temp = Path(downloaded["temporary_path"])
    source_dir = Path(source_dir)
    if not temp.is_file() or not temp.resolve().is_relative_to(source_dir.resolve()):
        raise ValueError("Download is not in the managed Source directory")
    digest = hashlib.sha256()
    with temp.open("rb") as stream:
        for block in iter(lambda: stream.read(256 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != downloaded["sha256"]:
        raise ValueError("Downloaded original checksum mismatch")
    drive_id = downloaded["drive_id"]
    if not drive_id or not all(c.isalnum() or c in "-_" for c in drive_id):
        raise ValueError("Invalid Drive ID")
    with sqlite3.connect(db_path, timeout=30) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        asset = db.execute("""SELECT 1 FROM object_identity i JOIN objects o
                              ON o.object_id=i.legacy_id AND o.object_type=i.object_type
                              WHERE i.permanent_id=? AND i.object_type='asset'""",
                           (asset_id,)).fetchone()
        if not asset:
            raise ValueError("Unknown Asset")
        row = db.execute("SELECT source_id, custody_status FROM source WHERE sha256=?",
                         (digest.hexdigest(),)).fetchone()
        if row and row[1] != 'local_verified':
            raise ValueError('Matching Source is not locally verified')
        duplicate = bool(row)
        installed_path = None
        if row:
            source_id = row[0]
        else:
            source_id = new_id()
            installed_path = source_dir / source_id
            os.replace(temp, installed_path)
            db.execute("""INSERT INTO source
                          (source_id,source_type,media_type,original_name,sha256,storage_ref,custody_status)
                          VALUES(?,?,?,?,?,?,?)""",
                       (source_id, "file", downloaded["media_type"],
                        downloaded["original_name"], digest.hexdigest(),
                        str(installed_path), "local_verified"))
        try:
            db.execute("""INSERT INTO ingest_occurrence
                          (occurrence_id,source_id,channel,external_provider,external_ref,cleanup_status)
                          VALUES(?,?,?,?,?,?)""",
                       (new_id(), source_id, "google_drive_import", "google_drive", drive_id, "not_required"))
            db.execute("INSERT OR IGNORE INTO source_link(source_id,object_id) VALUES(?,?)",
                       (source_id, asset_id))
            db.commit()
        except Exception:
            db.rollback()
            if installed_path is not None:
                installed_path.unlink(missing_ok=True)
            raise
    temp.unlink(missing_ok=True)
    return source_id, duplicate
