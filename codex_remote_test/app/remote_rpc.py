"""Fixed local Unix-socket RPCs to the same app-server we supervise.

No TCP listener, user-supplied address/method or raw provider error reaches UI.
websocket-client is supplied by Debian, and imported lazily for offline unit tests.
"""
import json
import socket
import time

METHODS = {'remoteControl/enable', 'remoteControl/status/read', 'remoteControl/pairing/start'}


class RemoteError(Exception):
    def __init__(self, kind='transport', code=None):
        self.kind, self.code = kind, code if type(code) is int else None
        super().__init__('Local Codex RPC failed')


def _connect(path, timeout):
    import websocket
    transport = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    transport.settimeout(timeout)
    try:
        transport.connect(str(path))
        return websocket.create_connection('ws://localhost/', socket=transport,
                                           timeout=timeout, suppress_origin=True)
    except Exception:
        transport.close()
        raise


def request(path, method, params=None, timeout=10):
    if method not in METHODS:
        raise RemoteError('method')
    connection = None
    deadline = time.monotonic() + timeout
    try:
        connection = _connect(path, timeout)
        def receive(identifier):
            for _ in range(64):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RemoteError('timeout')
                connection.settimeout(remaining)
                raw = connection.recv()
                if not isinstance(raw, (str, bytes)) or len(raw) > 65536:
                    raise RemoteError('protocol')
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise RemoteError('protocol')
                if message.get('id') != identifier:
                    continue  # Ignore notifications; the next status read is authoritative.
                if 'error' in message:
                    error = message['error']
                    raise RemoteError('rpc', error.get('code') if isinstance(error, dict) else None)
                result = message.get('result')
                if not isinstance(result, dict):
                    raise RemoteError('protocol')
                return result
            raise RemoteError('protocol')
        connection.send(json.dumps({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'home-agent-codex-test', 'title': 'Codex Remote Test', 'version': '0.1.3'},
            'capabilities': {'experimentalApi': True}}}))
        receive(1)
        connection.send(json.dumps({'method': 'initialized'}))
        message = {'id': 2, 'method': method}
        if params is not None:
            message['params'] = params
        connection.send(json.dumps(message))
        return receive(2)
    except RemoteError:
        raise
    except Exception:
        raise RemoteError('transport') from None
    finally:
        if connection is not None:
            try:
                connection.close(timeout=0)
            except Exception:
                pass
