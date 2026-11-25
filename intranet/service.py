from __future__ import annotations

import json
import queue
import socket
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import AppConfig, ConfigStore, broadcast_for, ipv4_summary, network_id
from .engine import SyncEngine
from .network import NodeServer, RemotePeer
from .pairing import parse_peer
from .security import fingerprint


@dataclass
class DiscoveredPeer:
    device: str
    host: str
    port: int
    last_seen: float


class DiscoveryService:
    def __init__(self, device: str, tls_port: int, certificate, registry, listen_port: int, broadcast_host: str):
        self.device = device
        self.tls_port = tls_port
        self.identity = fingerprint(certificate.read_bytes())
        self.registry = registry
        self.listen_port = listen_port
        self.broadcast_host = broadcast_host
        self.peers: dict[str, DiscoveredPeer] = {}
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.bind(("0.0.0.0", listen_port))
        self.socket.settimeout(1)
        self.threads = [
            threading.Thread(target=self._receive_loop, daemon=True),
            threading.Thread(target=self._announce_loop, daemon=True),
        ]

    def start(self) -> None:
        for thread in self.threads:
            thread.start()

    def _receive_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                payload, address = self.socket.recvfrom(65535)
                message = json.loads(payload.decode("utf-8"))
                if (
                    message.get("type") != "intranet-validation-discovery"
                    or message.get("device") == self.device
                    or message.get("fingerprint") not in self.registry.allowed
                ):
                    continue
                peer = DiscoveredPeer(str(message["device"]), address[0], int(message["port"]), time.monotonic())
                with self.lock:
                    self.peers[peer.device] = peer
            except socket.timeout:
                continue
            except (OSError, ValueError, KeyError, UnicodeDecodeError):
                continue

    def _announce_loop(self) -> None:
        message = json.dumps(
            {"type": "intranet-validation-discovery", "device": self.device, "port": self.tls_port, "fingerprint": self.identity}
        ).encode("utf-8")
        while not self.stop_event.is_set():
            try:
                self.socket.sendto(message, (self.broadcast_host, self.listen_port))
            except OSError:
                pass
            self.stop_event.wait(1)

    def current_peers(self) -> list[DiscoveredPeer]:
        cutoff = time.monotonic() - 5
        with self.lock:
            self.peers = {key: peer for key, peer in self.peers.items() if peer.last_seen >= cutoff}
            return list(self.peers.values())

    def close(self) -> None:
        self.stop_event.set()
        self.socket.close()


class IntranetService:
    def __init__(self, store: ConfigStore, config: AppConfig):
        if not config.folder:
            raise ValueError("请选择同步文件夹")
        if not store.peer_certificate.exists():
            raise ValueError("请先完成设备配对")
        self.store = store
        self.config = config
        self.engine = SyncEngine(
            Path(config.folder),
            config.device_id,
            store.data_dir / "engine",
            excluded=tuple(config.exclusions),
            history_days=config.history_days,
            history_bytes=config.history_bytes,
        )
        self.key, self.certificate = store.ensure_identity(config)
        self.registry = store.registry
        self.events: queue.Queue[dict] = queue.Queue()
        self.stop_event = threading.Event()
        self.server: NodeServer | None = None
        self.discovery: DiscoveryService | None = None
        self.worker: threading.Thread | None = None
        self.running = False
        self.paused = False
        self.known: set[str] = set()
        self.last_attempt: dict[str, float] = {}
        self.last_scan = 0.0
        self.last_sync = ""
        self.last_cleanup = 0.0

    def emit(self, kind: str, **values) -> None:
        self.events.put({"type": kind, "timestamp": time.time(), **values})

    def start(self) -> None:
        if self.running:
            return
        self.stop_event.clear()
        self.running = True
        self.engine.scan()
        self.worker = threading.Thread(target=self._loop, name="intranet-product", daemon=True)
        self.worker.start()
        removed = self.engine.history.cleanup()
        self.last_cleanup = time.monotonic()
        if removed:
            self.emit("history_cleanup", text=f"已清理 {removed} 个历史文件", removed=removed)
        self.emit("status", text="服务已启动")

    def _allowed(self) -> bool:
        current = network_id()
        allowed = current in self.config.trusted_networks
        if not allowed:
            self.emit_throttled("network", f"当前网络未受信任：{current}")
        return allowed

    def emit_throttled(self, kind: str, text: str) -> None:
        now = time.monotonic()
        if now - getattr(self, "_last_notice", 0) > 15:
            self._last_notice = now
            self.emit(kind, text=text)

    def _broadcast(self) -> str:
        for item in ipv4_summary()["interfaces"]:
            try:
                return broadcast_for(item["IPv4"], int(item["Prefix"]))
            except (ValueError, KeyError, TypeError):
                continue
        return "255.255.255.255"

    def _start_io(self) -> None:
        if self.server:
            return
        self.server = NodeServer(
            self.engine,
            self.key,
            self.certificate,
            self.store.peer_certificate,
            self.registry,
            port=self.config.tcp_port,
            on_text=lambda text: self.emit("text_received", text=text),
        )
        self.server.start()
        self.discovery = DiscoveryService(
            self.config.device_id,
            self.server.port,
            self.certificate,
            self.registry,
            self.config.discovery_port,
            self._broadcast(),
        )
        self.discovery.start()
        self.emit("status", text=f"TLS 服务已启动，端口 {self.server.port}")

    def _stop_io(self) -> None:
        if self.discovery:
            self.discovery.close()
            self.discovery = None
        if self.server:
            self.server.close()
            self.server = None
        self.known.clear()

    def _peers(self) -> list[DiscoveredPeer]:
        result = self.discovery.current_peers() if self.discovery else []
        existing = {(peer.host, peer.port) for peer in result}
        for value in self.config.static_peers:
            try:
                host, port = parse_peer(value)
            except ValueError:
                continue
            if (host, port) not in existing:
                result.append(DiscoveredPeer(f"static-{host}", host, port, time.monotonic()))
        return result

    def _sync(self, peer: DiscoveredPeer) -> None:
        try:
            remote = RemotePeer(peer.host, peer.port, self.key, self.certificate, self.store.peer_certificate)
            try:
                stats = self.engine.sync_from(remote)
            finally:
                remote.close()
            self.last_sync = time.strftime("%Y-%m-%d %H:%M:%S")
            if any(asdict(stats).values()):
                self.emit("sync", device=peer.device, stats=asdict(stats))
        except (OSError, ValueError, ConnectionError) as exc:
            self.emit_throttled("retry", f"{peer.device}：{exc}")

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            if time.monotonic() - self.last_cleanup > 86400:
                removed = self.engine.history.cleanup()
                self.last_cleanup = time.monotonic()
                if removed:
                    self.emit("history_cleanup", text=f"已清理 {removed} 个历史文件", removed=removed)
            if self.paused or not self._allowed():
                self._stop_io()
                if time.monotonic() - self.last_scan > 5:
                    self.engine.scan()
                    self.last_scan = time.monotonic()
                self.stop_event.wait(1)
                continue
            try:
                self._start_io()
                current = {peer.device for peer in self._peers()}
                for device in current - self.known:
                    self.emit("discovered", device=device)
                self.known = current
                for peer in self._peers():
                    now = time.monotonic()
                    if now - self.last_attempt.get(peer.device, 0) < 1:
                        continue
                    self.last_attempt[peer.device] = now
                    self._sync(peer)
            except (OSError, ValueError) as exc:
                self.emit_throttled("error", str(exc))
                self._stop_io()
            self.stop_event.wait(0.2)

    def send_text(self, text: str) -> None:
        if not text.strip():
            raise ValueError("请输入要传输的文字")
        if self.paused or not self._allowed():
            raise ValueError("请先恢复同步并连接受信任网络")
        threading.Thread(target=self._send_text, args=(text,), daemon=True).start()

    def _send_text(self, text: str) -> None:
        peers = self._peers()
        if not peers:
            self.emit("error", text="尚未发现可传输文字的设备")
            return
        peer = peers[0]
        try:
            remote = RemotePeer(peer.host, peer.port, self.key, self.certificate, self.store.peer_certificate)
            try:
                remote.send_text(text)
            finally:
                remote.close()
            self.emit("text_sent", text=text)
        except (OSError, ValueError, ConnectionError) as exc:
            self.emit("error", text=f"文字发送失败：{exc}")

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.emit("status", text="已暂停" if self.paused else "已恢复")

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self.stop_event.set()
        self._stop_io()
        self.engine.scan()
        self.emit("status", text="服务已停止")

    def history_entries(self) -> list[dict]:
        return self.engine.history.entries()

    def restore(self, entry_id: str) -> Path:
        return self.engine.restore(entry_id)
