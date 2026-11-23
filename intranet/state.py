from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO


@dataclass
class Record:
    path: str
    version: int
    device: str
    deleted: bool = False
    size: int = 0
    mtime_ns: int = 0
    sha256: str = ""

    @property
    def order(self) -> tuple[int, str]:
        return self.version, self.device

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> Record:
        path = safe_relative_path(str(value["path"]))
        version = int(value["version"])
        size = int(value.get("size", 0))
        mtime_ns = int(value.get("mtime_ns", 0))
        if version < 1 or size < 0:
            raise ValueError("无效文件版本")
        record = cls(
            path=path,
            version=version,
            device=str(value["device"]),
            deleted=bool(value.get("deleted", False)),
            size=size,
            mtime_ns=mtime_ns,
            sha256=str(value.get("sha256", "")),
        )
        if not record.device or (not record.deleted and len(record.sha256) != 64):
            raise ValueError("无效文件记录")
        return record


def safe_relative_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("无效相对路径")
    if path.parts[0].endswith(":"):
        raise ValueError("不允许使用绝对路径")
    return path.as_posix()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class FileState:
    def __init__(self, folder: Path, device_id: str, data_dir: Path):
        self.folder = folder.resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.device_id = device_id
        identity = hashlib.sha256(str(self.folder).lower().encode("utf-8")).hexdigest()[:20]
        self.state_path = data_dir / f"state-{identity}.json"
        self.records: dict[str, Record] = {}
        self.lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if Path(payload["folder"]).resolve() != self.folder:
                return
            self.records = {
                item["path"]: Record.from_dict(item) for item in payload.get("records", [])
            }
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            self.records = {}

    def _save_locked(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"folder": str(self.folder), "records": [r.to_dict() for r in self.records.values()]}
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.state_path)

    def path_for(self, relative: str) -> Path:
        normalized = safe_relative_path(relative)
        destination = self.folder.joinpath(*PurePosixPath(normalized).parts)
        if not destination.resolve().is_relative_to(self.folder):
            raise ValueError("路径超出同步目录")
        return destination

    @staticmethod
    def _ignored(path: Path) -> bool:
        return path.name.startswith(".intranet-") or path.name.startswith("~$")

    def _disk_files(self) -> dict[str, Path]:
        files: dict[str, Path] = {}
        for root, directories, names in os.walk(self.folder, followlinks=False):
            root_path = Path(root)
            directories[:] = [
                name for name in directories if not (root_path / name).is_symlink()
            ]
            for name in names:
                path = root_path / name
                if self._ignored(path) or path.is_symlink():
                    continue
                try:
                    relative = path.relative_to(self.folder).as_posix()
                    files[relative] = path
                except ValueError:
                    continue
        return files

    def scan(self) -> None:
        disk = self._disk_files()
        with self.lock:
            previous = dict(self.records)
            updated: dict[str, Record] = {}
            for relative in sorted(set(previous) | set(disk)):
                old = previous.get(relative)
                path = disk.get(relative)
                if path is None:
                    if old is not None:
                        updated[relative] = (
                            Record(relative, old.version + 1, self.device_id, deleted=True)
                            if not old.deleted
                            else old
                        )
                    continue
                try:
                    stat = path.stat()
                    if old and not old.deleted and old.size == stat.st_size and old.mtime_ns == stat.st_mtime_ns:
                        fingerprint = (old.sha256, stat.st_size, stat.st_mtime_ns)
                    else:
                        fingerprint = self._fingerprint(path)
                except OSError:
                    if old is not None:
                        updated[relative] = old
                    continue
                sha256, size, mtime_ns = fingerprint
                if old and not old.deleted and old.sha256 == sha256:
                    updated[relative] = Record(
                        relative, old.version, old.device, False, size, mtime_ns, sha256
                    )
                else:
                    updated[relative] = Record(
                        relative,
                        old.version + 1 if old else 1,
                        self.device_id,
                        False,
                        size,
                        mtime_ns,
                        sha256,
                    )
            if {key: value.to_dict() for key, value in updated.items()} != {
                key: value.to_dict() for key, value in self.records.items()
            }:
                self.records = updated
                self._save_locked()

    @staticmethod
    def _fingerprint(path: Path) -> tuple[str, int, int]:
        for _ in range(3):
            before = path.stat()
            sha256 = hash_file(path)
            after = path.stat()
            if before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns:
                return sha256, after.st_size, after.st_mtime_ns
        raise OSError("文件正在持续变化")

    def manifest(self) -> list[dict]:
        self.scan()
        with self.lock:
            return [record.to_dict() for record in self.records.values()]

    def get(self, relative: str) -> Record | None:
        with self.lock:
            return self.records.get(relative)

    def adopt(self, remote: Record) -> None:
        with self.lock:
            self.records[remote.path] = remote
            self._save_locked()

    def prepare_download(self, remote: Record) -> Path:
        destination = self.path_for(remote.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination.parent / f".intranet-{uuid.uuid4().hex}.tmp"

    def install(self, remote: Record, temporary: Path, preserve_local: bool) -> None:
        destination = self.path_for(remote.path)
        if temporary.stat().st_size != remote.size or hash_file(temporary) != remote.sha256:
            raise ValueError("文件校验失败")
        if preserve_local and destination.exists():
            self._make_conflict_copy(destination)
        os.replace(temporary, destination)
        try:
            os.utime(destination, ns=(remote.mtime_ns, remote.mtime_ns))
        except OSError:
            pass
        self.adopt(remote)

    def delete(self, remote: Record, preserve_local: bool) -> None:
        destination = self.path_for(remote.path)
        if preserve_local and destination.exists():
            self._make_conflict_copy(destination)
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
        self.adopt(remote)

    def _make_conflict_copy(self, source: Path) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = source.with_name(
            f"{source.stem}.conflict-{self.device_id[:8]}-{stamp}{source.suffix}"
        )
        destination = base
        counter = 1
        while destination.exists():
            destination = base.with_name(f"{base.stem}-{counter}{base.suffix}")
            counter += 1
        shutil.copy2(source, destination)

    def open_file(self, requested: Record) -> tuple[BinaryIO, Record]:
        self.scan()
        current = self.get(requested.path)
        if (
            current is None
            or current.deleted
            or current.order != requested.order
            or current.sha256 != requested.sha256
        ):
            raise FileNotFoundError("文件版本已变化，请重新同步")
        source = self.path_for(requested.path).open("rb")
        return source, current
