from __future__ import annotations

import json
import os
import platform
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Config:
    device_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    device_name: str = field(default_factory=platform.node)
    folder: str = ""
    sync_key: str = ""
    tcp_port: int = 47621
    udp_port: int = 47620
    interval: float = 5.0
    manual_peers: list[str] = field(default_factory=list)

    @property
    def data_dir(self) -> Path:
        base = os.environ.get("APPDATA")
        return Path(base) / "Intranet" if base else Path.home() / ".intranet"


def config_path() -> Path:
    return Config().data_dir / "config.json"


def load_config() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        allowed = Config.__dataclass_fields__
        return Config(**{key: value for key, value in values.items() if key in allowed})
    except (OSError, ValueError, TypeError):
        return Config()


def save_config(config: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    values = asdict(config)
    values["sync_key"] = ""
    temporary.write_text(
        json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)
