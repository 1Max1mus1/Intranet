from __future__ import annotations

import hashlib
import hmac
import socket
import threading
import time
from collections.abc import Callable

from .config import AppConfig, ConfigStore
from .network import receive_json, send_json


def pair_auth(code: str, *parts: str) -> str:
    digest = hmac.new(code.encode("ascii"), digestmod=hashlib.sha256)
    for part in parts:
        payload = part.encode("utf-8")
        digest.update(len(payload).to_bytes(4, "big"))
        digest.update(payload)
    return digest.hexdigest()


def parse_peer(value: str) -> tuple[str, int]:
    host, separator, port = value.rpartition(":")
    if not separator or not host:
        raise ValueError("对端地址应为 IP:端口")
    port_number = int(port)
    if not 1 <= port_number <= 65535:
        raise ValueError("端口无效")
    return host.strip("[]"), port_number


class PairingManager:
    def __init__(self, store: ConfigStore, config: AppConfig):
        self.store = store
        self.config = config
        self.key, self.certificate = store.ensure_identity(config)

    def offer(self, on_code: Callable[[str, int], None], on_done: Callable[[str], None]) -> None:
        threading.Thread(target=self._offer, args=(on_code, on_done), daemon=True).start()

    def _offer(self, on_code, on_done) -> None:
        registry = self.store.registry
        code = registry.issue_code(ttl_seconds=300)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("0.0.0.0", self.config.tcp_port))
            listener.listen(1)
            listener.settimeout(300)
            port = listener.getsockname()[1]
            on_code(code, port)
            try:
                connection, address = listener.accept()
                with connection:
                    message = receive_json(connection)
                    nonce = str(message["nonce"])
                    peer_certificate = str(message["certificate"]).encode("utf-8")
                    expected = pair_auth(code, "client", nonce, peer_certificate.decode("utf-8"))
                    if message.get("type") != "pair" or not hmac.compare_digest(expected, message.get("auth", "")):
                        raise PermissionError("配对认证失败")
                    registry.pair(code, peer_certificate)
                    self.store.peer_certificate.write_bytes(peer_certificate)
                    certificate = self.certificate.read_bytes()
                    response_auth = pair_auth(code, "server", nonce, peer_certificate.decode("utf-8"), certificate.decode("utf-8"))
                    send_json(connection, {"type": "paired", "certificate": certificate.decode("utf-8"), "auth": response_auth})
                    on_done(f"已与 {address[0]} 配对")
            except Exception as exc:
                on_done(f"配对失败：{exc}")

    def join(self, peer: str, code: str, on_done: Callable[[str], None]) -> None:
        threading.Thread(target=self._join, args=(peer, code, on_done), daemon=True).start()

    def _join(self, peer: str, code: str, on_done) -> None:
        try:
            host, port = parse_peer(peer)
            nonce = hashlib.sha256(f"{time.time_ns()}:{self.config.device_id}".encode()).hexdigest()
            certificate = self.certificate.read_bytes()
            with socket.create_connection((host, port), timeout=10) as connection:
                auth = pair_auth(code, "client", nonce, certificate.decode("utf-8"))
                send_json(connection, {"type": "pair", "nonce": nonce, "certificate": certificate.decode("utf-8"), "auth": auth})
                response = receive_json(connection)
                peer_certificate = str(response["certificate"]).encode("utf-8")
                expected = pair_auth(code, "server", nonce, certificate.decode("utf-8"), peer_certificate.decode("utf-8"))
                if response.get("type") != "paired" or not hmac.compare_digest(expected, response.get("auth", "")):
                    raise PermissionError("对端配对认证失败")
            self.store.registry.register(peer_certificate)
            self.store.peer_certificate.write_bytes(peer_certificate)
            on_done("配对成功")
        except Exception as exc:
            on_done(f"配对失败：{exc}")
