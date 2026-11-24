from __future__ import annotations

import socket
import ssl
import threading
from pathlib import Path

from .engine import Record, SyncEngine
from .security import (
    PairingRegistry,
    client_context,
    fingerprint,
    server_context,
)
from .transport import receive_json, send_json


class SocketReader:
    def __init__(self, peer: RemotePeer, size: int):
        self.peer = peer
        self.remaining = size

    def __enter__(self) -> SocketReader:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def read(self, size: int = -1) -> bytes:
        if self.remaining == 0:
            return b""
        requested = self.remaining if size < 0 else min(size, self.remaining)
        data = self.peer.connection.recv(requested)
        if not data:
            raise ConnectionError("文件传输中断")
        self.remaining -= len(data)
        return data

    def close(self) -> None:
        try:
            while self.remaining:
                data = self.peer.connection.recv(min(1024 * 1024, self.remaining))
                if not data:
                    raise ConnectionError("文件传输中断")
                self.remaining -= len(data)
        finally:
            self.peer.busy = False


class RemotePeer:
    def __init__(self, host: str, port: int, key_path: Path, certificate_path: Path, peer_certificate: Path):
        context = client_context(key_path, certificate_path, peer_certificate)
        raw = socket.create_connection((host, port), timeout=10)
        raw.settimeout(5)
        self.connection = context.wrap_socket(raw, server_hostname="validation-peer")
        expected = fingerprint(peer_certificate.read_bytes())
        actual = ssl.DER_cert_to_PEM_cert(self.connection.getpeercert(binary_form=True)).encode("ascii")
        if fingerprint(actual) != expected:
            self.connection.close()
            raise ssl.SSLError("对端证书与配对记录不一致")
        self.busy = False

    def manifest(self) -> list[dict]:
        send_json(self.connection, {"type": "manifest"})
        response = receive_json(self.connection)
        if response.get("type") != "manifest":
            raise ValueError("无法取得文件清单")
        return response["records"]

    def open_record(self, requested: Record, offset: int = 0) -> tuple[SocketReader, Record]:
        if self.busy:
            raise RuntimeError("上一个文件尚未读取完成")
        send_json(self.connection, {"type": "open", "record": requested.wire(), "offset": offset})
        response = receive_json(self.connection)
        if response.get("type") == "error":
            raise FileNotFoundError(response.get("message"))
        current = Record.from_wire(response["record"])
        if current.wire() != requested.wire() or int(response.get("offset", -1)) != offset:
            raise ValueError("文件版本或续传偏移在传输前发生变化")
        self.busy = True
        return SocketReader(self, current.size - offset), current

    def close(self) -> None:
        self.connection.close()


class NodeServer:
    def __init__(
        self,
        engine: SyncEngine,
        key_path: Path,
        certificate_path: Path,
        peer_certificate: Path,
        registry: PairingRegistry,
        host: str = "0.0.0.0",
        port: int = 47630,
    ):
        self.engine = engine
        self.registry = registry
        self.context = server_context(key_path, certificate_path, peer_certificate)
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.listener.listen()
        self.listener.settimeout(1)
        self.port = self.listener.getsockname()[1]
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._accept_loop, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _accept_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._handle, args=(connection,), daemon=True).start()

    def _handle(self, raw: socket.socket) -> None:
        try:
            with self.context.wrap_socket(raw, server_side=True) as connection:
                peer = ssl.DER_cert_to_PEM_cert(connection.getpeercert(binary_form=True)).encode("ascii")
                if not self.registry.allows(peer):
                    return
                while not self.stop_event.is_set():
                    request = receive_json(connection)
                    if request.get("type") == "manifest":
                        send_json(connection, {"type": "manifest", "records": self.engine.manifest()})
                    elif request.get("type") == "open":
                        requested = Record.from_wire(request["record"])
                        offset = int(request.get("offset", 0))
                        try:
                            source, current = self.engine.open_record(requested, offset=offset)
                        except (OSError, ValueError) as exc:
                            send_json(connection, {"type": "error", "message": str(exc)})
                            continue
                        with source:
                            send_json(connection, {"type": "file", "record": current.wire(), "offset": offset})
                            remaining = current.size - offset
                            while remaining:
                                chunk = source.read(min(1024 * 1024, remaining))
                                if not chunk:
                                    raise ConnectionError("源文件读取中断")
                                connection.sendall(chunk)
                                remaining -= len(chunk)
                    else:
                        raise ValueError("未知请求")
        except (ConnectionError, OSError, ValueError, KeyError, ssl.SSLError):
            return

    def close(self) -> None:
        self.stop_event.set()
        self.listener.close()
        self.thread.join(timeout=2)
