from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import ssl
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


class PairingError(PermissionError):
    pass


def create_identity(root: Path, common_name: str) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    key_path = root / "device-key.pem"
    certificate_path = root / "device-cert.pem"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return key_path, certificate_path


def fingerprint(certificate_pem: bytes) -> str:
    certificate = x509.load_pem_x509_certificate(certificate_pem)
    return certificate.fingerprint(hashes.SHA256()).hex()


class PairingRegistry:
    def __init__(self, path: Path):
        self.path = path
        self.allowed: set[str] = set()
        self._salt = b""
        self._code_hash = b""
        self._expires = 0.0
        if path.exists():
            self.allowed = set(json.loads(path.read_text(encoding="utf-8"))["allowed"])

    def issue_code(self, ttl_seconds: float = 60) -> str:
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._salt = secrets.token_bytes(16)
        self._code_hash = self._hash(code)
        self._expires = time.monotonic() + ttl_seconds
        return code

    def _hash(self, code: str) -> bytes:
        return hmac.new(self._salt, code.encode("ascii"), hashlib.sha256).digest()

    def pair(self, code: str, peer_certificate: bytes) -> str:
        if time.monotonic() > self._expires or not self._salt:
            raise PairingError("配对码已过期")
        if not hmac.compare_digest(self._code_hash, self._hash(code)):
            raise PairingError("配对码错误")
        identity = fingerprint(peer_certificate)
        self.allowed.add(identity)
        self._salt = b""
        self._code_hash = b""
        self._expires = 0.0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"allowed": sorted(self.allowed)}), encoding="utf-8")
        return identity

    def allows(self, certificate_pem: bytes) -> bool:
        return fingerprint(certificate_pem) in self.allowed


class NetworkPolicy:
    def __init__(self):
        self.trusted_networks: set[str] = set()

    def trust(self, network_id: str) -> None:
        if not network_id:
            raise ValueError("网络标识不能为空")
        self.trusted_networks.add(network_id)

    def allows_sync(self, network_id: str, peer_paired: bool) -> bool:
        return peer_paired and network_id in self.trusted_networks


def server_context(key_path: Path, certificate_path: Path, peer_certificate: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certificate_path, key_path)
    context.load_verify_locations(cafile=str(peer_certificate))
    return context


def client_context(key_path: Path, certificate_path: Path, peer_certificate: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certificate_path, key_path)
    context.load_verify_locations(cafile=str(peer_certificate))
    return context
