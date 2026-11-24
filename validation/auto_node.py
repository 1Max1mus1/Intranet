from __future__ import annotations

import argparse
import json
import socket
import threading
import time
from dataclasses import asdict, dataclass

from .dual_node import NodeFiles
from .network import NodeServer, RemotePeer
from .security import fingerprint


@dataclass
class DiscoveredPeer:
    device: str
    host: str
    port: int
    last_seen: float


class DiscoveryService:
    def __init__(
        self,
        device: str,
        tls_port: int,
        certificate,
        registry,
        listen_port: int,
        remote_port: int,
        broadcast_host: str,
    ):
        self.device = device
        self.tls_port = tls_port
        self.identity = fingerprint(certificate.read_bytes())
        self.registry = registry
        self.listen_port = listen_port
        self.remote_port = remote_port
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
                peer = DiscoveredPeer(
                    str(message["device"]), address[0], int(message["port"]), time.monotonic()
                )
                with self.lock:
                    self.peers[peer.device] = peer
            except socket.timeout:
                continue
            except (OSError, ValueError, KeyError, UnicodeDecodeError):
                continue

    def _announce_loop(self) -> None:
        message = json.dumps(
            {
                "type": "intranet-validation-discovery",
                "device": self.device,
                "port": self.tls_port,
                "fingerprint": self.identity,
            }
        ).encode("utf-8")
        while not self.stop_event.is_set():
            try:
                self.socket.sendto(message, (self.broadcast_host, self.remote_port))
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


class AutoNode:
    def __init__(self, files: NodeFiles, port: int, discovery_port: int, remote_discovery_port: int, broadcast: str, watch: list[str]):
        self.files = files
        self.started = time.monotonic()
        self.server = NodeServer(
            files.engine,
            files.key,
            files.certificate,
            files.peer_certificate,
            files.registry,
            port=port,
        )
        self.discovery = DiscoveryService(
            files.engine.device,
            self.server.port,
            files.certificate,
            files.registry,
            discovery_port,
            remote_discovery_port,
            broadcast,
        )
        self.watch = set(watch)
        self.stop_event = threading.Event()
        self.known: set[str] = set()
        self.last_attempt: dict[str, float] = {}
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)

    def emit(self, kind: str, **values) -> None:
        print(json.dumps({"type": kind, "timestamp": time.time(), **values}, ensure_ascii=False), flush=True)

    def start(self) -> None:
        self.server.start()
        self.discovery.start()
        self.thread.start()
        self.emit("AUTO_READY", tls_port=self.server.port)

    def _sync_loop(self) -> None:
        while not self.stop_event.is_set():
            current = {peer.device for peer in self.discovery.current_peers()}
            for device in current - self.known:
                self.emit("DISCOVERED", device=device, elapsed=time.monotonic() - self.started)
            for device in self.known - current:
                self.emit("PEER_LOST", device=device, elapsed=time.monotonic() - self.started)
            self.known = current
            for peer in self.discovery.current_peers():
                now = time.monotonic()
                if now - self.last_attempt.get(peer.device, 0) < 1:
                    continue
                self.last_attempt[peer.device] = now
                try:
                    remote = RemotePeer(
                        peer.host,
                        peer.port,
                        self.files.key,
                        self.files.certificate,
                        self.files.peer_certificate,
                    )
                    try:
                        stats = self.files.engine.sync_from(remote)
                    finally:
                        remote.close()
                    if any(asdict(stats).values()):
                        self.emit("SYNC_RESULT", device=peer.device, stats=asdict(stats))
                    if stats.downloaded_files:
                        for relative in self.watch:
                            path = self.files.engine.path_for(relative)
                            if path.exists():
                                value = path.read_text(encoding="utf-8").strip()
                                result = {"device": peer.device, "path": relative}
                                try:
                                    result["latency_seconds"] = time.time() - float(value)
                                except ValueError:
                                    pass
                                self.emit("WATCH_SYNCED", **result)
                except (OSError, ValueError, ConnectionError) as exc:
                    self.emit("SYNC_RETRY", device=peer.device, error=str(exc))
            self.stop_event.wait(0.2)

    def close(self) -> None:
        self.stop_event.set()
        self.discovery.close()
        self.server.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Intranet 自动发现与恢复技术验证")
    parser.add_argument("--root", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--port", type=int, default=47630)
    parser.add_argument("--discovery-port", type=int, default=47620)
    parser.add_argument("--remote-discovery-port", type=int)
    parser.add_argument("--broadcast", default="255.255.255.255")
    parser.add_argument("--watch", action="append", default=[])
    parser.add_argument("--trusted-network", action="store_true")
    args = parser.parse_args()
    if not args.trusted_network:
        parser.error("必须使用 --trusted-network")
    files = NodeFiles(args.root, args.device, args.metadata)
    node = AutoNode(
        files,
        args.port,
        args.discovery_port,
        args.remote_discovery_port or args.discovery_port,
        args.broadcast,
        args.watch,
    )
    node.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        node.close()


if __name__ == "__main__":
    main()
