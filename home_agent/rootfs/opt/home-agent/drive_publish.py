"""Drive adapter restricted to this installation's app-created exchange folder."""
import hashlib
import json
import re
import uuid
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import HTTPRedirectHandler, Request, build_opener


class PublishError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def file_url(file_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", file_id or ""):
        raise PublishError("Ogiltig Drive-referens")
    return "https://drive.google.com/file/d/" + file_id + "/view"


FIELDS = "id,name,mimeType,parents,appProperties,trashed,md5Checksum"
FOLDER = "application/vnd.google-apps.folder"


class DrivePublisher:
    def __init__(self, token, instance_id, state, save):
        self.token = token
        self.instance_id = instance_id
        self.state = state
        self.save = save
        self.opener = build_opener(NoRedirect())

    def request(self, path, method="GET", data=None, content_type="application/json", upload=False, start=False, extra_headers=None):
        origin = "https://www.googleapis.com/" + ("upload/drive/v3/" if upload else "drive/v3/")
        req = Request(origin + path, data=data, method=method,
                      headers={"Authorization": "Bearer " + self.token, "Content-Type": content_type,
                               **(extra_headers or {})})
        try:
            timeout = 120 if upload and data and len(data) > 5 * 1024 * 1024 else 30
            with self.opener.open(req, timeout=timeout) as response:
                if start:
                    return {"session_path": session_path(response.headers.get("Location", ""))}
                body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise PublishError("För stort svar från Drive")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("Expected object")
            return result
        except HTTPError as exc:
            # Never include the remote body, request headers or token in errors.
            code = exc.code
            exc.close()
            raise PublishError("Drive-anrop misslyckades (HTTP %s)" % code) from None
        except (OSError, ValueError) as exc:
            raise PublishError("Drive kunde inte nås eller gav ett ogiltigt svar") from exc

    def ensure(self, key, name, parent=None, body=None, mime="text/plain", mutable=False):
        """Persist a generated ID *before* create, making ambiguous retries safe."""
        if not re.fullmatch(r"[a-z0-9-]{1,180}", key):
            raise PublishError("Ogiltig publiceringsnyckel")
        if parent:
            file_url(parent)
        props = {"ha_instance": self.instance_id, "ha_key": key}
        q = "trashed=false and appProperties has { key='ha_instance' and value='%s' } and appProperties has { key='ha_key' and value='%s' }" % (self.instance_id, key)
        if parent:
            q += " and '%s' in parents" % parent
        result = self.request("files?" + urlencode({"q": q, "fields": "nextPageToken,files(" + FIELDS + ")", "pageSize": 2}))
        matches = result.get("files", [])
        if not isinstance(matches, list) or len(matches) > 1 or result.get("nextPageToken"):
            raise PublishError("Drive innehåller flera möjliga publiceringsobjekt")
        expected_mime = mime if body is not None else FOLDER
        current = matches[0] if matches else None
        if current:
            self.validate(current, props, parent, expected_mime)
            file_id = current["id"]
            if not mutable:
                self.verify_bytes(current, body)
                return file_id
        else:
            file_id = self.state.setdefault("ids", {}).get(key)
            if not file_id:
                file_id = self.request("files/generateIds?count=1&space=drive&type=files")["ids"][0]
                file_url(file_id)
                self.state["ids"][key] = file_id
                self.save()
            file_url(file_id)
        meta = {"name": name, "mimeType": expected_mime, "appProperties": props}
        if not current:
            meta["id"] = file_id
            if parent:
                meta["parents"] = [parent]
        path = "files" + ("/" + file_id if current else "")
        method = "PATCH" if current else "POST"
        if body is None:
            result = self.request(path + "?" + urlencode({"fields": FIELDS}), method, json.dumps(meta).encode())
        elif len(body) > 5 * 1024 * 1024:
            session = self.request(path + "?" + urlencode({"uploadType": "resumable", "fields": FIELDS}),
                                   method, json.dumps(meta).encode(), upload=True, start=True,
                                   extra_headers={"X-Upload-Content-Type": mime, "X-Upload-Content-Length": str(len(body))})
            result = self.request(session["session_path"], "PUT", body, mime, upload=True)
        else:
            boundary = "homeagent_" + uuid.uuid4().hex
            payload = ("--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n").encode()
            payload += json.dumps(meta).encode() + ("\r\n--" + boundary + "\r\nContent-Type: " + mime + "\r\n\r\n").encode()
            payload += body + ("\r\n--" + boundary + "--\r\n").encode()
            result = self.request(path + "?" + urlencode({"uploadType": "multipart", "fields": FIELDS}),
                                  method, payload, "multipart/related; boundary=" + boundary, upload=True)
        self.validate(result, props, parent, expected_mime)
        if result["id"] != file_id:
            raise PublishError("Drive skapade inte det reserverade objektet")
        self.verify_bytes(result, body)
        return file_id

    @staticmethod
    def validate(item, props, parent, mime):
        file_url(item.get("id"))
        if (item.get("trashed") or item.get("appProperties") != props or item.get("mimeType") != mime
                or (parent and item.get("parents") != [parent])):
            raise PublishError("Drive-objektet ligger inte i den förväntade publiceringen")

    @staticmethod
    def verify_bytes(item, body):
        if body is not None and item.get("md5Checksum") != hashlib.md5(body, usedforsecurity=False).hexdigest():
            raise PublishError("Drive-kopian kunde inte verifieras mot uppladdade byte")


def session_path(url):
    """The provider's upload Location may not redirect credentials to another host."""
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.netloc != "www.googleapis.com" or parsed.fragment
            or not re.fullmatch(r"/upload/drive/v3/files(?:/[A-Za-z0-9_-]+)?", parsed.path)
            or not parse_qs(parsed.query).get("upload_id")):
        raise PublishError("Ogiltig Drive-uppladdningssession")
    return parsed.path.removeprefix("/upload/drive/v3/") + "?" + parsed.query
