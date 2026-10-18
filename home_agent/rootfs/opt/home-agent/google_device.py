"""Google device authorization for a headless Pi; no OAuth secrets in browser UI."""
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import stat
import threading
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, build_opener

import chatgpt_export
from drive_publish import NoRedirect

SCOPES = "openid email https://www.googleapis.com/auth/drive.file"
ACTIVE = ("requesting", "waiting")


class DeviceError(Exception):
    """Only locally constructed, user-safe messages."""


def google_request(endpoint, form=None, token=None):
    urls = {"code": "https://oauth2.googleapis.com/device/code",
            "token": "https://oauth2.googleapis.com/token",
            "identity": "https://www.googleapis.com/oauth2/v3/userinfo"}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(urls[endpoint], data=urlencode(form).encode() if form is not None else None,
                      headers=headers)
    try:
        try:
            response = build_opener(NoRedirect()).open(request, timeout=15)
        except HTTPError as exc:
            response = exc
        with response:
            code = response.code
            raw = response.read(64 * 1024 + 1)
    except OSError:
        raise DeviceError("Google kunde inte nås. Försök igen.") from None
    try:
        if len(raw) > 64 * 1024:
            raise ValueError()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise DeviceError("Google gav ett ogiltigt svar. Starta anslutningen igen.") from None
    # Error bodies are interpreted by code only, never displayed or logged.
    if code == 429 or code >= 500:
        raise DeviceError("Google är tillfälligt otillgängligt. Försök igen.")
    if ((code != 200 and not isinstance(value.get("error"), str))
            or ("error" in value and not isinstance(value["error"], str))):
        raise DeviceError("Google nekade anslutningen. Kontrollera Google-inställningarna.")
    return value


def options(path):
    try:
        path = Path(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 64 * 1024:
            raise ValueError()
        value = json.loads(path.read_text(encoding="utf-8"))["google_drive"]
        if not isinstance(value, dict):
            raise ValueError()
        result = {k: value.get(k, "").strip() for k in ("client_id", "client_secret", "expected_email")}
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+\.apps\.googleusercontent\.com", result["client_id"])
                or not 1 <= len(result["client_secret"]) <= 512
                or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", result["expected_email"])):
            raise ValueError()
        result["expected_email"] = result["expected_email"].casefold()
        return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise DeviceError("Fyll i Google Drive-inställningarna i Home Assistants konfiguration för Home Agent och starta om tillägget.") from None


def fingerprint(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def verification_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise DeviceError("Google gav en ogiltig inloggningslänk.")
    parsed = urlparse(value)
    if (parsed.scheme != "https" or parsed.netloc not in ("www.google.com", "google.com", "accounts.google.com")
            or parsed.fragment):
        raise DeviceError("Google gav en ogiltig inloggningslänk.")
    return value


def local_host(host):
    """Reject foreign Host names, including DNS rebinding to this local service."""
    try:
        parsed = urlparse("http://" + host)
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return False
        name = parsed.hostname or ""
        if name in ("localhost", "homeassistant") or name.endswith(".local"):
            return True
        addr = ipaddress.ip_address(name)
        return (addr.is_private or addr.is_loopback) and not addr.is_unspecified
    except (ValueError, TypeError):
        return False


class Controller:
    def __init__(self, options_path="/data/options.json", config_path=chatgpt_export.CONFIG,
                 state_path="/data/google_drive_pairing.json", request=google_request,
                 clock=time.time, connected=chatgpt_export.request_publish):
        self.options_path, self.config_path, self.state_path = map(Path, (options_path, config_path, state_path))
        self.request, self.clock, self.connected = request, clock, connected
        self.csrf = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.step_lock = threading.Lock()

    def read(self):
        return chatgpt_export.private_json(self.state_path) if self.state_path.exists() else {"phase": "idle"}

    def compatible(self, config):
        if self.config_path.exists():
            old = chatgpt_export.private_json(self.config_path)
            if (old.get("client_id") != config["client_id"]
                    or str(old.get("expected_email", "")).casefold() != config["expected_email"]):
                raise DeviceError("En annan Google-anslutning finns redan. Behåll dess inställningar; byte av konto eller klient kräver separat konfigurering.")

    def start(self):
        config = options(self.options_path)
        with self.lock:
            self.compatible(config)
            old = self.read()
            if old.get("phase") in ACTIVE and old.get("fingerprint") == fingerprint(config) and old.get("expires_at", 0) > self.clock():
                return
            chatgpt_export.save_state(self.state_path, {"phase": "requesting", "attempt": uuid.uuid4().hex,
                "fingerprint": fingerprint(config), "expires_at": self.clock() + 1800, "next_poll": 0})

    def cancel(self):
        with self.lock:
            chatgpt_export.save_state(self.state_path, {"phase": "cancelled"})

    def status(self):
        try:
            with self.lock:
                state = self.read()
                config = options(self.options_path)
                self.compatible(config)
                phase = state.get("phase", "idle")
                if phase in ACTIVE and state.get("fingerprint") != fingerprint(config):
                    return {"phase": "error", "message": "Google-inställningarna ändrades. Starta anslutningen igen."}
                if phase in ACTIVE and state.get("expires_at", 0) <= self.clock():
                    return {"phase": "expired", "message": "Koden har gått ut. Starta anslutningen igen."}
                result = {"phase": phase, "email": config["expected_email"], "message": state.get("message")}
                if phase == "waiting":
                    result.update(user_code=state["user_code"], verification_url=verification_url(state["verification_url"]))
                if phase not in ACTIVE and self.config_path.exists():
                    chatgpt_export.validate_config(chatgpt_export.private_json(self.config_path))
                    result["connected"] = True
                return result
        except DeviceError as exc:
            return {"phase": "setup", "message": str(exc)}
        except (OSError, ValueError, KeyError, TypeError, chatgpt_export.PublishError):
            return {"phase": "error", "message": "Anslutningens lokala inställningar behöver kontrolleras."}

    def finish(self, phase, message=None):
        chatgpt_export.save_state(self.state_path, {"phase": phase, "message": message})

    def step(self):
        if not self.step_lock.acquire(blocking=False):
            return
        try:
            self.advance()
        finally:
            self.step_lock.release()

    def advance(self):
        with self.lock:
            state = self.read()
            if state.get("phase") not in ACTIVE:
                return
            try:
                config = options(self.options_path)
            except DeviceError as exc:
                self.finish("error", str(exc))
                return
            if state.get("fingerprint") != fingerprint(config):
                self.finish("error", "Google-inställningarna ändrades. Starta anslutningen igen.")
                return
            if self.config_path.exists():
                saved = chatgpt_export.private_json(self.config_path)
                if saved.get("device_attempt") == state.get("attempt"):
                    chatgpt_export.validate_config(saved)
                    self.finish("connected", "Google-kontot är anslutet. Första publiceringen förbereds.")
                    self.connected()
                    return
            if self.clock() >= state["expires_at"]:
                self.finish("expired", "Koden har gått ut. Starta anslutningen igen.")
                return
            if self.clock() < state.get("next_poll", 0):
                return
        try:
            if state["phase"] == "requesting":
                response = self.request("code", {"client_id": config["client_id"], "scope": SCOPES})
            else:
                response = self.request("token", {"client_id": config["client_id"], "client_secret": config["client_secret"],
                    "device_code": state["device_code"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
            credentials = None
            if "access_token" in response:
                credentials = self.validated_credentials(response, config)
        except DeviceError as exc:
            response = {"retry_message": str(exc)}
            credentials = None
        with self.lock:
            current = self.read()
            if current.get("attempt") != state.get("attempt") or current.get("phase") not in ACTIVE:
                return  # cancelled/replaced while network request was running
            try:
                current_fingerprint = fingerprint(options(self.options_path))
            except DeviceError as exc:
                self.finish("error", str(exc))
                return
            if current_fingerprint != state["fingerprint"]:
                self.finish("error", "Google-inställningarna ändrades. Starta anslutningen igen.")
                return
            if self.clock() >= state["expires_at"]:
                self.finish("expired", "Koden har gått ut. Starta anslutningen igen.")
                return
            if credentials:
                self.compatible(config)
                credentials["device_attempt"] = state["attempt"]
                chatgpt_export.save_state(self.config_path, credentials)
                self.finish("connected", "Google-kontot är anslutet. Första publiceringen förbereds.")
                self.connected()
            elif "access_token" in response:
                self.finish("error", "Google-kontot eller behörigheterna kunde inte bekräftas. Kontrollera att du valde rätt konto och starta anslutningen igen.")
            elif response.get("error"):
                error = response["error"]
                if state["phase"] == "waiting" and error in ("authorization_pending", "slow_down"):
                    state["interval"] += 5 if error == "slow_down" else 0
                    state["next_poll"] = self.clock() + state["interval"]
                    state.pop("message", None)
                    chatgpt_export.save_state(self.state_path, state)
                else:
                    messages = {"access_denied": "Du nekade åtkomst. Ingen ny behörighet har sparats.",
                        "expired_token": "Koden har gått ut. Starta anslutningen igen.",
                        "invalid_client": "Kontrollera klient-ID och klienthemlighet. Klienttypen måste vara TVs and Limited Input devices.",
                        "invalid_scope": "Google-klienten stöder inte de begärda Drive-behörigheterna.",
                        "invalid_grant": "Inloggningen är inte längre giltig. Starta anslutningen igen."}
                    self.finish("error", messages.get(error, "Google nekade anslutningen. Kontrollera klient, målgrupp och testanvändare i Google Cloud."))
            elif response.get("retry_message"):
                state.update(next_poll=self.clock() + max(15, state.get("interval", 5)), message=response["retry_message"])
                chatgpt_export.save_state(self.state_path, state)
            elif state["phase"] == "requesting":
                try:
                    code = response["user_code"]
                    device = response["device_code"]
                    expiry, interval = response["expires_in"], response.get("interval", 5)
                    if (not isinstance(code, str) or not re.fullmatch(r"[\x21-\x7e]{1,64}", code)
                            or not isinstance(device, str) or not 1 <= len(device) <= 4096
                            or type(expiry) is not int or not 1 <= expiry <= 3600
                            or type(interval) is not int or not 1 <= interval <= 3600):
                        raise ValueError()
                    link = verification_url(response.get("verification_url", response.get("verification_uri")))
                    state.update(phase="waiting", user_code=code, device_code=device, verification_url=link,
                                 expires_at=self.clock() + expiry, interval=interval, next_poll=self.clock() + interval)
                    state.pop("message", None)
                    chatgpt_export.save_state(self.state_path, state)
                except (KeyError, ValueError, TypeError, DeviceError):
                    self.finish("error", "Google gav ett ogiltigt kodsvar. Starta anslutningen igen.")
            else:
                self.finish("error", "Google gav ett ofullständigt svar. Starta anslutningen igen.")

    def validated_credentials(self, response, config):
        scopes = set(str(response.get("scope", "")).split())
        if (response.get("token_type") != "Bearer" or "https://www.googleapis.com/auth/drive.file" not in scopes
                or "openid" not in scopes or not scopes.intersection(("email", "https://www.googleapis.com/auth/userinfo.email"))
                or any(not isinstance(response.get(k), str) or not re.fullmatch(r"[\x21-\x7e]{1,8192}", response[k])
                       for k in ("access_token", "refresh_token"))):
            return None
        try:
            identity = self.request("identity", token=response["access_token"])
        except DeviceError:
            return None  # code may already be consumed; start a fresh attempt
        if identity.get("email_verified") is not True or str(identity.get("email", "")).casefold() != config["expected_email"]:
            return None
        return {**config, "purpose": chatgpt_export.PURPOSE, "enabled": True, "refresh_token": response["refresh_token"]}

    def launch(self):
        stop = threading.Event()
        def run():
            reported = False
            while not stop.is_set():
                try:
                    self.step()
                    reported = False
                except Exception:
                    # Never log provider bodies, codes, tokens or options.
                    if not reported:
                        print("Home Agent: Google-anslutningen behöver kontrolleras.", flush=True)
                    reported = True
                    stop.wait(5)
                stop.wait(1)
        threading.Thread(target=run, name="google-device-auth", daemon=True).start()
        return stop


def send_page(handler, body, code=200):
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    handler.end_headers()
    handler.wfile.write(body)


def handle_get(handler, controller):
    import ui
    if not local_host(handler.headers.get("Host", "")):
        send_page(handler, ui.shell("Lokal anslutning krävs", "<p>Öppna Home Agent via dess lokala IP-adress för att ansluta Google.</p>"), 403)
        return
    send_page(handler, ui.google_connection_page(controller.status(), controller.csrf))


def handle_post(handler, controller, path):
    import ui
    try:
        host = handler.headers.get("Host", "")
        origin = urlparse(handler.headers.get("Origin", ""))
        length = int(handler.headers.get("Content-Length", "0"))
        if (not local_host(host) or origin.scheme not in ("http", "https") or origin.netloc.casefold() != host.casefold()
                or origin.path or origin.query or origin.fragment
                or not 0 < length <= 4096
                or handler.headers.get("Content-Type", "").split(";", 1)[0] != "application/x-www-form-urlencoded"):
            raise ValueError()
        fields = parse_qs(handler.rfile.read(length).decode("utf-8"), max_num_fields=4)
        supplied = fields.get("csrf", [])
        if len(supplied) != 1 or not hmac.compare_digest(supplied[0], controller.csrf):
            raise ValueError()
    except (ValueError, TypeError, UnicodeError):
        send_page(handler, ui.shell("Anslutningen avvisades", "<p>Öppna anslutningssidan igen via Home Agents lokala adress.</p>"), 403)
        return
    try:
        controller.start() if path.endswith("/start") else controller.cancel()
    except (DeviceError, OSError, ValueError, chatgpt_export.PublishError):
        send_page(handler, ui.google_connection_page(controller.status(), controller.csrf), 400)
        return
    handler.send_response(303)
    handler.send_header("Location", "/drive/connect")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
