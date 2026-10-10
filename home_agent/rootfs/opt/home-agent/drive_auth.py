"""Refresh dedicated Google Drive import account tokens.

Provisioned credentials must come from the dedicated restricted account.
No Google account credentials are sent to ChatGPT.
"""
import json
import os
import stat
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class DriveAuthError(Exception):
    pass


def access_token(config_path):
    path = Path(config_path)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise DriveAuthError("Drive OAuth configuration must be owner-only (0600)")
    config = json.loads(path.read_text(encoding="utf-8"))
    required = ("client_id", "client_secret", "refresh_token", "expected_email")
    if any(not config.get(key) for key in required):
        raise DriveAuthError("Incomplete dedicated Drive import OAuth configuration")
    body = urlencode({
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "refresh_token": config["refresh_token"],
        "grant_type": "refresh_token",
    }).encode("utf-8")
    request = Request("https://oauth2.googleapis.com/token", data=body,
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            token = json.load(response)["access_token"]
        identity_request = Request("https://www.googleapis.com/oauth2/v3/userinfo",
                                   headers={"Authorization": "Bearer " + token})
        with urlopen(identity_request, timeout=30) as response:
            identity = json.load(response)
    except (OSError, ValueError, KeyError) as exc:
        raise DriveAuthError("Could not refresh or verify Google Drive import identity") from exc
    if not identity.get("email_verified") or identity.get("email", "").casefold() != config["expected_email"].casefold():
        raise DriveAuthError("Authenticated Google account does not match dedicated import account")
    return token
