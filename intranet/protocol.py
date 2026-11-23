from __future__ import annotations

import hashlib
import hmac
import json
import socket
import struct
from typing import BinaryIO

MAX_HEADER_SIZE = 64 * 1024 * 1024


class ProtocolError(RuntimeError):
    pass


def send_json(sock: socket.socket, message: dict) -> None:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_HEADER_SIZE:
        raise ProtocolError("消息过大")
    sock.sendall(struct.pack("!I", len(payload)) + payload)


def receive_json(sock: socket.socket) -> dict:
    size = struct.unpack("!I", receive_exact(sock, 4))[0]
    if size > MAX_HEADER_SIZE:
        raise ProtocolError("消息超过大小限制")
    try:
        message = json.loads(receive_exact(sock, size).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("收到无效消息") from exc
    if not isinstance(message, dict):
        raise ProtocolError("消息格式错误")
    return message


def receive_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("连接已关闭")
        chunks.extend(chunk)
    return bytes(chunks)


def authentication(key: str, *parts: str) -> str:
    digest = hmac.new(key.encode("utf-8"), digestmod=hashlib.sha256)
    for part in parts:
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def authentication_matches(expected: str, actual: object) -> bool:
    return isinstance(actual, str) and hmac.compare_digest(expected, actual)


def copy_stream(source: BinaryIO, sock: socket.socket, size: int) -> None:
    remaining = size
    while remaining:
        chunk = source.read(min(1024 * 1024, remaining))
        if not chunk:
            raise ProtocolError("文件在传输过程中被截断")
        sock.sendall(chunk)
        remaining -= len(chunk)
