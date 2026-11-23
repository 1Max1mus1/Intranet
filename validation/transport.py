from __future__ import annotations

import hashlib
import json
import os
import socket
import struct
import threading
from pathlib import Path


class InjectedInterruption(RuntimeError):
    pass


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def send_json(sock: socket.socket, value: dict) -> None:
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    sock.sendall(struct.pack("!I", len(payload)) + payload)


def receive_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("连接中断")
        data.extend(chunk)
    return bytes(data)


def receive_json(sock: socket.socket) -> dict:
    size = struct.unpack("!I", receive_exact(sock, 4))[0]
    if size > 64 * 1024:
        raise ValueError("消息过大")
    return json.loads(receive_exact(sock, size).decode("utf-8"))


class ChunkServer:
    def __init__(self, source: Path, corrupt: bool = False):
        self.source = source
        self.size = source.stat().st_size
        self.sha256 = hash_file(source)
        self.corrupt = corrupt
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.2)
        self.port = self.listener.getsockname()[1]
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                try:
                    request = receive_json(connection)
                    offset = int(request["offset"])
                    length = min(int(request["length"]), self.size - offset)
                    if offset < 0 or offset > self.size or length < 0 or length > 4 * 1024 * 1024:
                        raise ValueError("无效块范围")
                    with self.source.open("rb") as source:
                        source.seek(offset)
                        payload = source.read(length)
                    if self.corrupt and payload:
                        payload = bytes([payload[0] ^ 0xFF]) + payload[1:]
                    send_json(
                        connection,
                        {"offset": offset, "size": len(payload), "total_size": self.size, "sha256": self.sha256},
                    )
                    connection.sendall(payload)
                except (OSError, ValueError, KeyError):
                    continue

    def close(self) -> None:
        self.stop_event.set()
        self.listener.close()
        self.thread.join(timeout=2)


class ResumableDownloader:
    def __init__(self, host: str, port: int, destination: Path, state_root: Path, transfer_id: str):
        self.host = host
        self.port = port
        self.destination = destination
        self.temporary = destination.parent / f".intranet-spike-{transfer_id}.part"
        self.checkpoint = state_root / f"{transfer_id}.json"
        self.state_root = state_root
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.destination.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> tuple[int, int, str]:
        if not self.checkpoint.exists():
            return 0, 0, ""
        value = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        offset = int(value["offset"])
        if not self.temporary.exists() or self.temporary.stat().st_size != offset:
            raise ValueError("断点与临时文件不一致")
        return offset, int(value["total_size"]), str(value["sha256"])

    def _save(self, offset: int, total_size: int, sha256: str) -> None:
        temporary = self.checkpoint.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"offset": offset, "total_size": total_size, "sha256": sha256}), encoding="utf-8"
        )
        os.replace(temporary, self.checkpoint)

    def _chunk(self, offset: int, length: int) -> tuple[dict, bytes]:
        with socket.create_connection((self.host, self.port), timeout=5) as connection:
            connection.settimeout(10)
            send_json(connection, {"offset": offset, "length": length})
            header = receive_json(connection)
            return header, receive_exact(connection, int(header["size"]))

    def download(
        self,
        chunk_size: int = 1024 * 1024,
        interrupt_at: int | None = None,
        before_replace=None,
        after_replace=None,
    ) -> dict:
        if self.destination.exists() and self.checkpoint.exists():
            destination_hash = hash_file(self.destination)
            expected = json.loads(self.checkpoint.read_text(encoding="utf-8"))["sha256"]
            if destination_hash == expected:
                self.temporary.unlink(missing_ok=True)
                self.checkpoint.unlink(missing_ok=True)
                return {"size": self.destination.stat().st_size, "sha256": destination_hash, "resumed": True}
        initial_offset, total_size, expected_hash = self._load()
        offset = initial_offset
        mode = "r+b" if self.temporary.exists() else "wb"
        with self.temporary.open(mode) as target:
            target.seek(offset)
            while offset < total_size or not self.checkpoint.exists():
                if interrupt_at is not None and offset >= interrupt_at:
                    target.flush()
                    os.fsync(target.fileno())
                    raise InjectedInterruption(f"在 {offset} 字节处中断")
                header, payload = self._chunk(offset, chunk_size)
                if int(header["offset"]) != offset:
                    raise ValueError("块偏移不一致")
                if total_size and (int(header["total_size"]) != total_size or header["sha256"] != expected_hash):
                    raise ValueError("源文件在续传期间发生变化")
                total_size = int(header["total_size"])
                expected_hash = str(header["sha256"])
                target.seek(offset)
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
                offset += len(payload)
                self._save(offset, total_size, expected_hash)
                if not payload and offset < total_size:
                    raise ConnectionError("空块导致无法继续")
        actual_hash = hash_file(self.temporary)
        if actual_hash != expected_hash or self.temporary.stat().st_size != total_size:
            raise ValueError("完整文件校验失败")
        if before_replace:
            before_replace()
        os.replace(self.temporary, self.destination)
        if after_replace:
            after_replace()
        self.checkpoint.unlink(missing_ok=True)
        return {"size": total_size, "sha256": actual_hash, "resumed": initial_offset > 0}
