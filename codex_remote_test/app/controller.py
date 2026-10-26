"""Fixed Codex operations. Raw process output and credentials never reach HTTP/logs."""
import datetime
import json
import os
import re
import secrets
import signal
import stat
import subprocess
import threading
import time
from pathlib import Path

DEVICE_URL = 'https://auth.openai.com/codex/device'
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
MAX_OUTPUT = 16384


class TestError(Exception):
    pass


def private_write(path, value):
    temp = path.with_name(path.name + '.' + secrets.token_hex(8))
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def parse_pair(raw, now):
    """Only expose the manual code, never pairing credentials/environment IDs."""
    clean = ANSI.sub('', raw).strip()
    candidates = [clean] + clean.splitlines()
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        code = data.get('manualPairingCode')
        if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9 -]{4,128}', code):
            continue
        expiry = now + 120
        supplied = data.get('expiresAt')
        try:
            if isinstance(supplied, str):
                expiry = min(expiry, datetime.datetime.fromisoformat(supplied.replace('Z', '+00:00')).timestamp())
            elif type(supplied) in (int, float):
                expiry = min(expiry, supplied / 1000 if supplied > 10**11 else supplied)
        except (ValueError, OverflowError, TypeError):
            raise TestError('Parkoden hade en ogiltig giltighetstid.') from None
        if expiry <= now:
            raise TestError('Parkoden har redan gått ut. Skapa en ny.')
        return code, expiry
    raise TestError('Codex gav ingen stödd manuell parkod. Mobilkopplingen behöver undersökas.')


class Controller:
    def __init__(self, root=Path('/data'), binary='/usr/local/bin/codex', clock=time.time):
        self.root, self.binary, self.clock = Path(root), str(binary), clock
        self.home = self.root / 'home'
        self.workspace = self.root / 'workspace'
        self.codex_home = self.home / '.codex'
        self.state_file = self.home / 'remote-test.json'
        self.lock = threading.RLock()
        self.auth_lock = threading.RLock()
        self.csrf = secrets.token_hex(32)
        self.closed = False
        self.authenticated = False
        self.auth_state = 'checking'
        self.auth_note = 'Kontrollerar sparad inloggning…'
        self.auth_checking = False
        self.auth_checked_at = None
        self.auth_epoch = 0
        self.pending_login = False
        self.started_at = self.clock()
        self.version = 'Kontrollerar…'
        self.supported = False
        self.message = ''
        self.job = None
        self.remote = None
        self.login_code = None
        self.login_expires = 0
        self.pair_code = None
        self.pair_expires = 0
        self.requested = False
        self.threads = []
        self._seed()

    def _seed(self):
        for path in (self.home, self.workspace, self.codex_home):
            path.mkdir(mode=0o700, exist_ok=True)
            if not stat.S_ISDIR(path.lstat().st_mode):
                raise TestError('Testets datakatalog är ogiltig.')
        seed = Path(__file__).parent / 'seed'
        for name, target in [('README.md', self.workspace / 'README.md'),
                             ('AGENTS.md', self.workspace / 'AGENTS.md'),
                             ('config.toml', self.codex_home / 'config.toml')]:
            try:
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                if not stat.S_ISREG(target.lstat().st_mode):
                    raise TestError('Testets startfiler är ogiltiga.') from None
            else:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write((seed / name).read_bytes())
        if self.state_file.exists() or self.state_file.is_symlink():
            info = self.state_file.lstat()
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 1024:
                raise TestError('Testets tillstånd måste vara en privat fil.')
            try:
                self.requested = json.loads(self.state_file.read_text()).get('remote_enabled') is True
            except (ValueError, AttributeError):
                raise TestError('Testets tillstånd kunde inte läsas.') from None

    def env(self):
        # Do not pass Supervisor tokens, API keys, task credentials or runtime hooks.
        return {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
                'HOME': str(self.home), 'CODEX_HOME': str(self.codex_home), 'NO_COLOR': '1', 'TERM': 'dumb'}

    def _spawn(self, args):
        return subprocess.Popen([self.binary, '-c', 'cli_auth_credentials_store="file"',
                                 '-c', 'forced_login_method="chatgpt"', *args], cwd=self.workspace, env=self.env(),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True)

    @staticmethod
    def terminate(process):
        if process is None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=3)

    def _capture(self, args, timeout=10):
        process = self._spawn(args)
        chunks = []
        total = [0]
        def read():
            while True:
                chunk = os.read(process.stdout.fileno(), 1024)
                if not chunk:
                    break
                total[0] += len(chunk)
                if total[0] > MAX_OUTPUT:
                    self.terminate(process)
                    break
                chunks.append(chunk)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.terminate(process)
            raise TestError('Codex svarade inte i tid. Försök igen.') from None
        finally:
            reader.join(4)
            process.stdout.close()
        if total[0] > MAX_OUTPUT:
            raise TestError('Codex gav ett för stort svar.')
        return code, b''.join(chunks).decode('utf-8', 'replace')

    def _thread(self, function):
        thread = threading.Thread(target=function, daemon=True)
        self.threads.append(thread)
        thread.start()

    def initialize(self):
        def work():
            try:
                code, version = self._capture(['--version'])
                match = re.search(r'codex-cli ([0-9]+\.[0-9]+\.[0-9]+)', version)
                if code or not match:
                    raise TestError('Codex kunde inte startas på denna enhet.')
                with self.lock:
                    self.version = match.group(1)
                code, _ = self._capture(['remote-control', '--no-daemon', '--help'])
                if code:
                    raise TestError('Installerad Codex saknar stödet för detta fjärrprov.')
                with self.lock:
                    self.supported = True
                self.refresh_auth()
                with self.lock:
                    if self.requested and self.authenticated and not self.closed:
                        self._start_remote()
            except (TestError, OSError) as error:
                with self.lock:
                    self.message = str(error) if isinstance(error, TestError) else 'Codex kunde inte startas.'
        self._thread(work)

    def refresh_auth(self):
        """Re-read the CLI credential store; a failed probe is never a logout."""
        with self.auth_lock:
            with self.lock:
                if self.closed:
                    return
                epoch = self.auth_epoch
                self.auth_checking = True
                self.auth_state = 'checking'
                self.authenticated = False
            try:
                code, text = self._capture(['login', 'status'])
                lines = [line.strip().casefold() for line in ANSI.sub('', text).splitlines()]
                if code == 0 and 'logged in using chatgpt' in lines:
                    state, note = 'signed_in', 'Sparad ChatGPT-inloggning hittades av Codex.'
                elif code == 1 and lines and lines[-1] == 'not logged in':
                    state, note = 'signed_out', 'Codex hittar ingen sparad inloggning.'
                elif code == 0:
                    state, note = 'wrong_method', 'Codex använder en annan inloggningsmetod än ChatGPT. Ingen ny inloggning har startats.'
                else:
                    state, note = 'error', 'Kunde inte kontrollera sparad inloggning (returkod %s). Inget har raderats. Tryck Kontrollera sparad inloggning.' % code
            except (TestError, OSError):
                state, note = 'error', 'Kontrollen av sparad inloggning misslyckades. Inget har raderats. Försök kontrollera igen.'
            with self.lock:
                self.auth_checking = False
                if epoch == self.auth_epoch and not self.closed:
                    self.auth_state, self.auth_note = state, note
                    self.authenticated = state == 'signed_in'
                    self.auth_checked_at = self.clock()

    def credential_file_state(self):
        """Only stat metadata; never read or return an auth file's contents."""
        try:
            info = (self.codex_home / 'auth.json').lstat()
            return 'present' if stat.S_ISREG(info.st_mode) else 'unexpected_type'
        except FileNotFoundError:
            return 'missing'
        except OSError:
            return 'unreadable'

    def status(self):
        with self.lock:
            now = self.clock()
            running = self.remote is not None and self.remote.poll() is None
            if self.pair_expires <= now or not running:
                self.pair_code = None
            if self.login_expires <= now:
                self.login_code = None
            return {'version': self.version, 'supported': self.supported,
                    'authenticated': self.authenticated, 'auth_state': self.auth_state,
                    'auth_note': self.auth_note, 'auth_checked_at': self.auth_checked_at,
                    'credential_file': self.credential_file_state(), 'started_at': self.started_at,
                    'busy': self.job is not None or self.pending_login or self.auth_checking or self.auth_state == 'checking',
                    'operation_active': self.job is not None or self.pending_login,
                    'remote_running': running, 'remote_enabled': self.requested,
                    'login_code': self.login_code,
                    'login_url': DEVICE_URL if self.login_code else None,
                    'pair_code': self.pair_code,
                    'pair_expires': self.pair_expires if self.pair_code else None,
                    'message': self.message, 'workspace': str(self.workspace)}

    def action(self, action):
        with self.lock:
            if self.closed or not self.supported:
                raise TestError('Vänta tills kontrollen av Codex är färdig.')
            if action == 'cancel':
                self.auth_epoch += 1
                self.pending_login = False
                if self.job:
                    self.terminate(self.job)
                    self.job = None
                self.login_code = self.pair_code = None
                self.message = 'Försöket avbröts. En redan sparad inloggning återkallas inte.'
                self.auth_state = 'checking'
                self.authenticated = False
                self._thread(self.refresh_auth)
                return
            if action == 'stop':
                self.requested = False
                private_write(self.state_file, {'remote_enabled': False})
                self.terminate(self.remote)
                self.remote = None
                self.pair_code = None
                self.message = 'Fjärrprocessen är stoppad. Testfiler och sessioner finns kvar.'
                return
            if self.job or self.pending_login or self.auth_checking:
                raise TestError('Ett försök pågår redan.')
            if action == 'check':
                self.auth_state = 'checking'
                self.authenticated = False
                self._thread(self.refresh_auth)
                return
            if action == 'login':
                if self.remote and self.remote.poll() is None:
                    raise TestError('Stoppa fjärrprocessen före en ny inloggning.')
                if self.auth_state == 'signed_in':
                    raise TestError('Du är redan inloggad. Använd den sparade inloggningen och starta fjärranslutningen.')
                if self.auth_state != 'signed_out':
                    raise TestError('Kontrollera först den sparade inloggningen. En ny inloggning kan ersätta den gamla.')
                self.auth_epoch += 1
                epoch = self.auth_epoch
                self.pending_login = True
                self.auth_state = 'checking'
                self.authenticated = False
                self.message = 'Kontrollerar befintlig inloggning innan någon ny startas…'
                self._thread(lambda: self._begin_login(epoch))
                return
            if not self.authenticated:
                raise TestError('Logga först in med ditt ChatGPT-konto.')
            if action == 'start':
                self.requested = True
                private_write(self.state_file, {'remote_enabled': True})
                self._start_remote()
                return
            if action == 'pair':
                if self.remote is None or self.remote.poll() is not None:
                    raise TestError('Starta fjärrprocessen först.')
                self.pair_code = None
                # Reserve the operation before releasing the lock.
                process = self._spawn(['remote-control', 'pair', '--json'])
                self.job = process
                self.message = 'Begär parkod…'
                self._thread(lambda: self._pair(process))
                return
            raise TestError('Okänd åtgärd.')

    def _begin_login(self, epoch):
        # The real CLI clears/revokes existing auth before a new device login.
        # Recheck just before launch, including when the browser had stale state.
        try:
            with self.auth_lock:
                with self.lock:
                    if self.closed or epoch != self.auth_epoch or not self.pending_login:
                        return
                self.refresh_auth()
                with self.lock:
                    if self.closed or epoch != self.auth_epoch or not self.pending_login:
                        return
                    if self.auth_state == 'signed_in':
                        self.message = 'Sparad inloggning återanvänds. Starta fjärranslutningen.'
                        return
                    if self.auth_state != 'signed_out':
                        self.message = 'Ingen ny inloggning startades eftersom den sparade inloggningen inte kunde kontrolleras.'
                        return
                    self.login_code = self.pair_code = None
                    self.auth_state = 'signing_in'
                    self.auth_note = 'Inloggning pågår. Vänta på bekräftelsen från Codex.'
                    self.message = 'Begär inloggningskod från OpenAI…'
                    process = self._spawn(['login', '--device-auth'])
                    self.job = process
                    self.pending_login = False
                    self.login_expires = self.clock() + 600
            self._login(process)
        except OSError:
            with self.lock:
                if epoch == self.auth_epoch and not self.closed:
                    self.auth_state = 'error'
                    self.auth_note = 'Codex kunde inte starta inloggningen.'
        finally:
            with self.lock:
                if epoch == self.auth_epoch:
                    self.pending_login = False

    def _start_remote(self):
        if self.remote is not None and self.remote.poll() is None:
            return
        self.remote = self._spawn(['remote-control', '--no-daemon'])
        process = self.remote
        self.message = 'Fjärrprocessen startar. Skapa sedan en parkod.'
        def drain():
            try:
                while os.read(process.stdout.fileno(), 4096):
                    pass  # Discard provider output, never send it to logs/HTTP.
            finally:
                process.stdout.close()
                code = process.wait()
                with self.lock:
                    if not self.closed and self.remote is process:
                        self.message = 'Fjärrprocessen avslutades (kod %s). Direktanslutningen behöver kontrolleras.' % code
                        self.pair_code = None
        self._thread(drain)

    def _read_job(self, process, timeout, on_chunk=None):
        chunks = []
        size = 0
        timer = threading.Timer(timeout, lambda: self.terminate(process))
        timer.daemon = True
        timer.start()
        try:
            while True:
                chunk = os.read(process.stdout.fileno(), 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_OUTPUT:
                    self.terminate(process)
                    raise TestError('Codex gav ett för stort svar.')
                chunks.append(chunk)
                if on_chunk:
                    on_chunk(b''.join(chunks).decode('utf-8', 'replace'))
            return process.wait(), b''.join(chunks).decode('utf-8', 'replace')
        finally:
            timer.cancel()
            process.stdout.close()

    def _login(self, process):
        def update(raw):
            clean = ANSI.sub('', raw)
            code = re.search(r'\b[A-Z0-9]{4,8}-[A-Z0-9]{4,8}\b', clean)
            with self.lock:
                if self.job is process and DEVICE_URL in clean and code:
                    self.login_code = code.group()
                    self.message = 'Öppna OpenAI-länken och ange koden. Återvänd sedan hit.'
        try:
            code, _ = self._read_job(process, 600, update)
            with self.lock:
                if self.job is not process or self.closed:
                    return
            self.refresh_auth()
            with self.lock:
                if self.job is process:
                    self.message = 'ChatGPT-inloggningen är klar. Starta fjärrprocessen.' if not code and self.authenticated else 'Inloggningen blev inte klar. Kontrollera kontot och försök igen.'
        except (TestError, OSError):
            with self.lock:
                if self.job is process:
                    self.message = 'Inloggningen misslyckades. Försök igen.'
                    self.auth_state = 'error'
                    self.authenticated = False
                    self.auth_note = 'Försöket kunde inte slutföras. Kontrollera den sparade inloggningen innan du försöker igen.'
        finally:
            with self.lock:
                if self.job is process:
                    self.job = None
                    self.login_code = None

    def _pair(self, process):
        try:
            code, raw = self._read_job(process, 30)
            if code:
                raise TestError('Codex kunde inte skapa parkoden. Kontrollera fjärrstödet för ditt konto.')
            value, expiry = parse_pair(raw, self.clock())
            with self.lock:
                if self.job is process and not self.closed and self.remote and self.remote.poll() is None:
                    self.pair_code, self.pair_expires = value, expiry
                    self.message = 'Använd parkoden i ChatGPT-appens Remote/Codex-anslutning om kodinmatning finns. Saknas den är mobilstödet inte verifierat.'
        except (TestError, OSError) as error:
            with self.lock:
                if self.job is process:
                    self.message = str(error) if isinstance(error, TestError) else 'Parkoden kunde inte skapas.'
        finally:
            with self.lock:
                if self.job is process:
                    self.job = None

    def close(self):
        with self.lock:
            self.closed = True
            self.auth_epoch += 1
            self.pending_login = False
            self.terminate(self.job)
            self.terminate(self.remote)
            self.job = self.remote = None
            self.login_code = self.pair_code = None
