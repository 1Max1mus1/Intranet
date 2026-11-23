from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import Config
from .protocol import (
    ProtocolError,
    authentication,
    authentication_matches,
    copy_stream,
    receive_exact,
    receive_json,
    send_json,
)
from .state import FileState, Record

PROTOCOL_VERSION = 1
DISCOVERY_TYPE = "intranet-discovery-v1"


@dataclass
class Peer:
    device_id: str
    name: str
    host: str
    port: int
    last_seen: float


class SyncService:
    def __init__(self, config: Config, data_dir: Path | None = None):
        if not config.folder:
            raise ValueError("请选择同步文件夹")
        if not config.sync_key:
            raise ValueError("请设置同步密钥")
        self.config = config
        self.state = FileState(Path(config.folder), config.device_id, data_dir or config.data_dir)
        self.stop_event = threading.Event()
        self.sync_event = threading.Event()
        self.peers: dict[str, Peer] = {}
        self.peer_lock = threading.Lock()
        self.messages: deque[str] = deque(maxlen=200)
        self.threads: list[threading.Thread] = []
        self.server_socket: socket.socket | None = None
        self.discovery_socket: socket.socket | None = None
        self.running = False
        self.last_error = ""
        self.last_sync = ""

    @property
    def port(self) -> int:
        if self.server_socket:
            return int(self.server_socket.getsockname()[1])
        return self.config.tcp_port

    def log(self, message: str) -> None:
        self.messages.append(f"{datetime.now().strftime('%H:%M:%S')}  {message}")

    def start(self) -> None:
        if self.running:
            return
        self.stop_event.clear()
        self.state.scan()
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.config.tcp_port))
        server.listen(16)
        server.settimeout(1)
        self.server_socket = server
        discovery = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        discovery.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        discovery.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        discovery.bind(("0.0.0.0", self.config.udp_port))
        discovery.settimeout(1)
        self.discovery_socket = discovery
        self.running = True
        self.threads = [
            threading.Thread(target=self._accept_loop, name="intranet-server", daemon=True),
            threading.Thread(target=self._discovery_receive_loop, name="intranet-discovery", daemon=True),
            threading.Thread(target=self._discovery_send_loop, name="intranet-announce", daemon=True),
            threading.Thread(target=self._sync_loop, name="intranet-sync", daemon=True),
        ]
        for thread in self.threads:
            thread.start()
        self.log(f"服务已启动，TCP 端口 {self.port}")
        self.sync_event.set()

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self.stop_event.set()
        self.sync_event.set()
        for sock in (self.server_socket, self.discovery_socket):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        self.log("服务已停止")

    def _accept_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                connection, address = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_client,
                args=(connection, address),
                name="intranet-peer",
                daemon=True,
            ).start()

    def _handle_client(self, connection: socket.socket, address: tuple) -> None:
        with connection:
            try:
                connection.settimeout(45)
                nonce = uuid.uuid4().hex + uuid.uuid4().hex
                send_json(connection, {"type": "challenge", "version": PROTOCOL_VERSION, "nonce": nonce})
                hello = receive_json(connection)
                client_id = str(hello.get("device_id", ""))
                expected = authentication(self.config.sync_key, "client", nonce, client_id)
                if (
                    hello.get("type") != "hello"
                    or hello.get("version") != PROTOCOL_VERSION
                    or not client_id
                    or client_id == self.config.device_id
                    or not authentication_matches(expected, hello.get("auth"))
                ):
                    send_json(connection, {"type": "error", "message": "身份认证失败"})
                    return
                response_auth = authentication(
                    self.config.sync_key, "server", nonce, self.config.device_id, client_id
                )
                send_json(
                    connection,
                    {
                        "type": "welcome",
                        "version": PROTOCOL_VERSION,
                        "device_id": self.config.device_id,
                        "name": self.config.device_name,
                        "auth": response_auth,
                        "manifest": self.state.manifest(),
                    },
                )
                while not self.stop_event.is_set():
                    request = receive_json(connection)
                    if request.get("type") == "done":
                        return
                    if request.get("type") != "get":
                        raise ProtocolError("未知请求")
                    requested = Record.from_dict(request["record"])
                    try:
                        source, current = self.state.open_file(requested)
                    except (OSError, ValueError) as exc:
                        send_json(connection, {"type": "error", "message": str(exc)})
                        continue
                    with source:
                        send_json(connection, {"type": "file", "record": current.to_dict()})
                        copy_stream(source, connection, current.size)
            except (ConnectionError, socket.timeout):
                return
            except (OSError, ValueError, KeyError, ProtocolError) as exc:
                self.log(f"{address[0]} 的连接失败：{exc}")
                try:
                    send_json(connection, {"type": "error", "message": str(exc)})
                except OSError:
                    pass

    def _discovery_receive_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                payload, address = self.discovery_socket.recvfrom(65535)
                message = json.loads(payload.decode("utf-8"))
                if (
                    message.get("type") != DISCOVERY_TYPE
                    or message.get("device_id") == self.config.device_id
                ):
                    continue
                device_id = str(message["device_id"])
                port = int(message["port"])
                if not device_id or not 1 <= port <= 65535:
                    continue
                peer = Peer(
                    device_id=device_id,
                    name=str(message.get("name") or "未命名设备")[:80],
                    host=address[0],
                    port=port,
                    last_seen=time.time(),
                )
                with self.peer_lock:
                    is_new = device_id not in self.peers
                    self.peers[device_id] = peer
                if is_new:
                    self.log(f"发现设备 {peer.name}（{peer.host}）")
                    self.sync_event.set()
            except socket.timeout:
                continue
            except (OSError, ValueError, KeyError, UnicodeDecodeError, json.JSONDecodeError):
                continue

    def _discovery_send_loop(self) -> None:
        while not self.stop_event.is_set():
            message = json.dumps(
                {
                    "type": DISCOVERY_TYPE,
                    "device_id": self.config.device_id,
                    "name": self.config.device_name,
                    "port": self.port,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            try:
                self.discovery_socket.sendto(message, ("255.255.255.255", self.config.udp_port))
            except OSError:
                pass
            self.stop_event.wait(3)

    def _sync_loop(self) -> None:
        while not self.stop_event.is_set():
            self.sync_event.wait(self.config.interval)
            self.sync_event.clear()
            if self.stop_event.is_set():
                return
            self.sync_once()

    def known_peers(self) -> list[Peer]:
        cutoff = time.time() - 15
        with self.peer_lock:
            self.peers = {key: peer for key, peer in self.peers.items() if peer.last_seen >= cutoff}
            discovered = list(self.peers.values())
        manual: list[Peer] = []
        for value in self.config.manual_peers:
            try:
                host, port = self.parse_peer(value)
            except ValueError:
                continue
            if any(peer.host == host and peer.port == port for peer in discovered):
                continue
            manual.append(Peer(f"manual-{host}-{port}", host, host, port, time.time()))
        return discovered + manual

    @staticmethod
    def parse_peer(value: str) -> tuple[str, int]:
        host, separator, raw_port = value.strip().rpartition(":")
        if not separator or not host:
            raise ValueError("设备地址应为 IP:端口")
        port = int(raw_port)
        if not 1 <= port <= 65535:
            raise ValueError("端口无效")
        return host.strip("[]"), port

    def sync_now(self) -> None:
        self.sync_event.set()

    def sync_once(self) -> None:
        peers = self.known_peers()
        if not peers:
            self.last_error = ""
            return
        for peer in peers:
            if self.stop_event.is_set():
                return
            try:
                transferred = self.sync_with(peer.host, peer.port)
                self.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.last_error = ""
                if transferred:
                    self.log(f"与 {peer.name} 同步了 {transferred} 个文件")
            except (OSError, ValueError, KeyError, ConnectionError, ProtocolError) as exc:
                self.last_error = f"{peer.name}: {exc}"
                self.log(f"同步 {peer.name} 失败：{exc}")

    def sync_with(self, host: str, port: int) -> int:
        transferred = 0
        with socket.create_connection((host, port), timeout=15) as connection:
            connection.settimeout(45)
            challenge = receive_json(connection)
            if challenge.get("type") != "challenge" or challenge.get("version") != PROTOCOL_VERSION:
                raise ProtocolError("对方协议版本不兼容")
            nonce = str(challenge["nonce"])
            auth = authentication(self.config.sync_key, "client", nonce, self.config.device_id)
            send_json(
                connection,
                {
                    "type": "hello",
                    "version": PROTOCOL_VERSION,
                    "device_id": self.config.device_id,
                    "name": self.config.device_name,
                    "auth": auth,
                },
            )
            welcome = receive_json(connection)
            expected = authentication(
                self.config.sync_key, "server", nonce, str(welcome.get("device_id", "")), self.config.device_id
            )
            if welcome.get("type") == "error":
                raise ProtocolError(str(welcome.get("message", "对方拒绝连接")))
            if (
                welcome.get("type") != "welcome"
                or welcome.get("version") != PROTOCOL_VERSION
                or not authentication_matches(expected, welcome.get("auth"))
            ):
                raise ProtocolError("对方身份认证失败")
            remote_records = [Record.from_dict(item) for item in welcome.get("manifest", [])]
            self.state.scan()
            for remote in sorted(remote_records, key=lambda item: item.path):
                local = self.state.get(remote.path)
                if local and remote.order < local.order:
                    continue
                if local and remote.order == local.order:
                    if remote.sha256 == local.sha256 and remote.deleted == local.deleted:
                        if remote.device != local.device and remote.order > local.order:
                            self.state.adopt(remote)
                        continue
                preserve = bool(
                    local
                    and local.version == remote.version
                    and local.device != remote.device
                    and local.sha256 != remote.sha256
                )
                if remote.deleted:
                    self.state.delete(remote, preserve)
                else:
                    if local and not local.deleted and local.sha256 == remote.sha256:
                        self.state.adopt(remote)
                        continue
                    self._download(connection, remote)
                transferred += 1
            try:
                send_json(connection, {"type": "done"})
            except OSError:
                pass
        self.state.scan()
        return transferred

    def _download(self, connection: socket.socket, remote: Record) -> None:
        send_json(connection, {"type": "get", "record": remote.to_dict()})
        response = receive_json(connection)
        if response.get("type") == "error":
            raise ProtocolError(str(response.get("message", "下载失败")))
        if response.get("type") != "file":
            raise ProtocolError("对方返回了无效文件")
        actual = Record.from_dict(response["record"])
        if actual.to_dict() != remote.to_dict():
            raise ProtocolError("对方文件版本与清单不一致")
        temporary = self.state.prepare_download(remote)
        try:
            with temporary.open("wb") as target:
                remaining = remote.size
                while remaining:
                    chunk = receive_exact(connection, min(1024 * 1024, remaining))
                    target.write(chunk)
                    remaining -= len(chunk)
            local = self.state.get(remote.path)
            preserve = bool(
                local
                and local.version == remote.version
                and local.device != remote.device
                and local.sha256 != remote.sha256
            )
            self.state.install(remote, temporary, preserve)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
