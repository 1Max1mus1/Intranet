from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import socket
import time
from dataclasses import asdict
from pathlib import Path

from .engine import SyncEngine
from .network import NodeServer, RemotePeer
from .security import PairingRegistry, create_identity
from .transport import receive_json, send_json


def pair_auth(code: str, *parts: str) -> str:
    digest = hmac.new(code.encode("ascii"), digestmod=hashlib.sha256)
    for part in parts:
        payload = part.encode("utf-8")
        digest.update(len(payload).to_bytes(4, "big"))
        digest.update(payload)
    return digest.hexdigest()


def validation_path(value: str) -> Path:
    project = Path(__file__).resolve().parent.parent
    path = Path(value).resolve()
    allowed = (project / ".validation-data").resolve()
    if not path.is_relative_to(allowed):
        raise ValueError(f"测试路径必须位于 {allowed}")
    return path


class NodeFiles:
    def __init__(self, root: str, device: str, metadata: str | None, excluded: tuple[str, ...] = ()):
        self.root = validation_path(root)
        self.metadata = validation_path(metadata) if metadata else self.root.parent / f"{self.root.name}-meta"
        self.identity = self.metadata / "identity"
        self.key = self.identity / "device-key.pem"
        self.certificate = self.identity / "device-cert.pem"
        self.peer_certificate = self.metadata / "peer-cert.pem"
        self.registry = PairingRegistry(self.metadata / "paired.json")
        if not self.key.exists():
            create_identity(self.identity, device)
        self.engine = SyncEngine(self.root, device, self.metadata / "engine", excluded=excluded)


def parse_peer(value: str) -> tuple[str, int]:
    host, separator, port = value.rpartition(":")
    if not separator or not host:
        raise ValueError("对端地址应为 IP:端口")
    return host, int(port)


def host_pair(args) -> None:
    files = NodeFiles(args.root, args.device, args.metadata, tuple(args.exclude))
    code = files.registry.issue_code(ttl_seconds=300)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", args.port))
        listener.listen(1)
        listener.settimeout(300)
        port = listener.getsockname()[1]
        print(f"PAIRING_CODE={code}", flush=True)
        print(f"PAIRING_PORT={port}", flush=True)
        connection, address = listener.accept()
        with connection:
            message = receive_json(connection)
            nonce = str(message["nonce"])
            peer_certificate = str(message["certificate"]).encode("utf-8")
            expected = pair_auth(code, "client", nonce, peer_certificate.decode("utf-8"))
            if message.get("type") != "pair" or not hmac.compare_digest(expected, message.get("auth", "")):
                raise PermissionError("配对认证失败")
            files.registry.pair(code, peer_certificate)
            files.peer_certificate.write_bytes(peer_certificate)
            certificate = files.certificate.read_bytes()
            response_auth = pair_auth(
                code, "server", nonce, peer_certificate.decode("utf-8"), certificate.decode("utf-8")
            )
            send_json(
                connection,
                {"type": "paired", "certificate": certificate.decode("utf-8"), "auth": response_auth},
            )
            print(f"PAIRED={address[0]}", flush=True)
    serve_files(files)


def join_pair(args) -> None:
    files = NodeFiles(args.root, args.device, args.metadata, tuple(args.exclude))
    host, port = parse_peer(args.peer)
    nonce = hashlib.sha256(f"{time.time_ns()}:{args.device}".encode()).hexdigest()
    certificate = files.certificate.read_bytes()
    with socket.create_connection((host, port), timeout=10) as connection:
        auth = pair_auth(args.code, "client", nonce, certificate.decode("utf-8"))
        send_json(
            connection,
            {"type": "pair", "nonce": nonce, "certificate": certificate.decode("utf-8"), "auth": auth},
        )
        response = receive_json(connection)
        peer_certificate = str(response["certificate"]).encode("utf-8")
        expected = pair_auth(
            args.code, "server", nonce, certificate.decode("utf-8"), peer_certificate.decode("utf-8")
        )
        if response.get("type") != "paired" or not hmac.compare_digest(expected, response.get("auth", "")):
            raise PermissionError("对端配对认证失败")
    files.registry.register(peer_certificate)
    files.peer_certificate.write_bytes(peer_certificate)
    print("PAIRED=true", flush=True)
    if args.sync:
        sync_files(files, host, port)


def serve_files(files: NodeFiles) -> None:
    server = NodeServer(
        files.engine,
        files.key,
        files.certificate,
        files.peer_certificate,
        files.registry,
        port=args_global_port,
    )
    server.start()
    print(f"TLS_READY={server.port}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.close()


def sync_files(files: NodeFiles, host: str, port: int) -> None:
    last_error = None
    for _ in range(30):
        try:
            peer = RemotePeer(host, port, files.key, files.certificate, files.peer_certificate)
            break
        except OSError as exc:
            last_error = exc
            time.sleep(0.5)
    else:
        raise ConnectionError(f"无法连接 TLS 服务：{last_error}")
    try:
        stats = files.engine.sync_from(peer)
        print(json.dumps({"type": "sync_result", "stats": asdict(stats)}, ensure_ascii=False), flush=True)
    finally:
        peer.close()


args_global_port = 47630


def main() -> None:
    global args_global_port
    parser = argparse.ArgumentParser(description="Intranet 双机 TLS 技术验证，不是产品服务")
    parser.add_argument("command", choices=("host", "join", "serve", "sync"))
    parser.add_argument("--root", required=True, help="隔离同步目录，必须在 .validation-data 内")
    parser.add_argument("--metadata", help="隔离元数据目录，必须在 .validation-data 内")
    parser.add_argument("--device", required=True)
    parser.add_argument("--peer", help="对端 IP:端口，join/sync 必需")
    parser.add_argument("--code", help="一次性配对码，join 必需")
    parser.add_argument("--port", type=int, default=47630)
    parser.add_argument("--sync", action="store_true", help="join 配对后立即同步")
    parser.add_argument("--exclude", action="append", default=[], help="本机排除的相对路径，可重复")
    parser.add_argument("--trusted-network", action="store_true", help="明确确认当前网络受信任")
    args = parser.parse_args()
    if not args.trusted_network:
        parser.error("必须使用 --trusted-network 明确确认当前网络受信任")
    args_global_port = args.port
    if args.command in ("join", "sync") and not args.peer:
        parser.error("join/sync 需要 --peer IP:端口")
    if args.command == "join" and not args.code:
        parser.error("join 需要 --code")
    if args.command == "host":
        host_pair(args)
    elif args.command == "join":
        join_pair(args)
    elif args.command == "serve":
        serve_files(NodeFiles(args.root, args.device, args.metadata, tuple(args.exclude)))
    else:
        host, port = parse_peer(args.peer)
        sync_files(NodeFiles(args.root, args.device, args.metadata, tuple(args.exclude)), host, port)


if __name__ == "__main__":
    main()
