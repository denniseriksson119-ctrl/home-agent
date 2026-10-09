"""Read-only Google Drive transport. No credentials are persisted by this module.

Authentication and authorization UI are deliberately separate. The caller must
supply a short-lived OAuth access token obtained for the dedicated import account.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://www.googleapis.com/drive/v3/files"
MAX_FILE_BYTES = 256 * 1024 * 1024
CHUNK = 256 * 1024


class DriveImportError(Exception):
    pass


def _request(url, token):
    if not token or not isinstance(token, str):
        raise DriveImportError("Missing Google OAuth access token")
    return Request(url, headers={"Authorization": "Bearer " + token,
                                 "Accept": "application/json"})


def metadata(file_id, token):
    """Read metadata; never call write-capable Google Drive APIs."""
    if not file_id or not all(c.isalnum() or c in "-_" for c in file_id):
        raise DriveImportError("Invalid Drive file ID")
    query = urlencode({"fields": "id,name,mimeType,size,md5Checksum,parents,trashed",
                       "supportsAllDrives": "true"})
    try:
        with urlopen(_request(API + "/" + file_id + "?" + query, token), timeout=30) as response:
            data = json.load(response)
    except (OSError, ValueError) as exc:
        raise DriveImportError("Unable to read Drive file metadata") from exc
    if data.get("trashed") or data.get("mimeType", "").startswith("application/vnd.google-apps."):
        raise DriveImportError("Trashed files and Google Workspace documents are not supported")
    return data


def download_original(file_id, token, destination, max_bytes=MAX_FILE_BYTES):
    """Stream one binary original into a private temporary file.

    Caller owns the returned temporary path and must move it into the local
    content-addressed store or delete it. This function never modifies Drive.
    """
    info = metadata(file_id, token)
    declared = info.get("size")
    if declared is not None and int(declared) > max_bytes:
        raise DriveImportError("Drive file exceeds import size limit")
    directory = Path(destination)
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".drive-", dir=str(directory))
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(fd, "wb") as out:
            with urlopen(_request(API + "/" + file_id + "?alt=media&supportsAllDrives=true", token),
                         timeout=60) as response:
                while True:
                    block = response.read(CHUNK)
                    if not block:
                        break
                    total += len(block)
                    if total > max_bytes:
                        raise DriveImportError("Drive download exceeds import size limit")
                    digest.update(block)
                    out.write(block)
            out.flush()
            os.fsync(out.fileno())
        if declared is not None and total != int(declared):
            raise DriveImportError("Incomplete Drive download")
        return {"temporary_path": temporary, "sha256": digest.hexdigest(),
                "size": total, "drive_id": info["id"], "original_name": info["name"],
                "media_type": info.get("mimeType", "application/octet-stream")}
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def assert_under_shared_root(file_id, root_id, token, max_depth=32):
    """Fail closed unless Drive parent metadata proves membership of shared root.

    Do not trust a filename, a browser-selected folder, or a supplied parent ID.
    """
    if not root_id or not all(c.isalnum() or c in "-_" for c in root_id):
        raise DriveImportError("Invalid configured shared root")
    if file_id == root_id:
        raise DriveImportError("Shared root is not an importable file")
    pending = [file_id]
    seen = set()
    for _ in range(max_depth):
        if not pending:
            break
        next_pending = []
        for current in pending:
            if current in seen:
                continue
            seen.add(current)
            info = metadata(current, token)
            for parent in info.get("parents", []):
                if parent == root_id:
                    return True
                if parent not in seen:
                    next_pending.append(parent)
        pending = next_pending
    raise DriveImportError("File is not verifiably inside the configured shared folder")
