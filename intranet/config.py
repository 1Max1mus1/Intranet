from __future__ import annotations

import ipaddress
import json
import os
import platform
import re
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .security import PairingRegistry, create_identity


@dataclass
class AppConfig:
    device_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    device_name: str = field(default_factory=platform.node)
    folder: str = ""
    tcp_port: int = 47630
    discovery_port: int = 47620
    static_peers: list[str] = field(default_factory=list)
    trusted_networks: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    history_days: int = 30
    history_bytes: int = 20 * 1024**3
    autostart: bool = True
    setup_complete: bool = False


class ConfigStore:
    def __init__(self, data_dir: Path | None = None):
        override = os.environ.get("INTRANET_DATA_DIR")
        base = Path(data_dir) if data_dir else Path(override) if override else Path(os.environ.get("APPDATA", str(Path.home()))) / "Intranet"
        self.data_dir = base.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            values = json.loads(self.path.read_text(encoding="utf-8"))
            return AppConfig(**{key: value for key, value in values.items() if key in AppConfig.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def ensure_identity(self, config: AppConfig) -> tuple[Path, Path]:
        key = self.data_dir / "identity" / "device-key.pem"
        certificate = self.data_dir / "identity" / "device-cert.pem"
        if not key.exists() or not certificate.exists():
            create_identity(self.identity_dir, config.device_name or config.device_id)
        return key, certificate

    @property
    def identity_dir(self) -> Path:
        return self.data_dir / "identity"

    @property
    def peer_certificate(self) -> Path:
        return self.data_dir / "peer-cert.pem"

    @property
    def registry(self) -> PairingRegistry:
        return PairingRegistry(self.data_dir / "paired.json")


def network_id() -> str:
    try:
        result = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, errors="replace", timeout=5)
        for line in result.stdout.splitlines():
            match = re.match(r"^\s*SSID\s*:\s*(.+?)\s*$", line)
            if match:
                return f"wifi:{match.group(1)}"
    except (OSError, subprocess.SubprocessError):
        pass
    return "offline"


def ipv4_summary() -> dict:
    script = (
        "Get-NetIPConfiguration | Where-Object {$_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up'} | "
        "Select-Object InterfaceAlias,@{N='IPv4';E={$_.IPv4Address.IPAddress}},"
        "@{N='Prefix';E={$_.IPv4Address.PrefixLength}},@{N='Gateway';E={$_.IPv4DefaultGateway.NextHop}} | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, errors="replace", timeout=8)
        value = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(value, dict):
            value = [value]
        return {"interfaces": value}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"interfaces": []}


def broadcast_for(address: str, prefix: int) -> str:
    interface = ipaddress.IPv4Interface(f"{address}/{prefix}")
    return str(interface.network.broadcast_address)
