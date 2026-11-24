from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
import threading
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("无效相对路径")
    if path.parts[0].endswith(":"):
        raise ValueError("不允许绝对路径")
    return path.as_posix()


@dataclass
class Record:
    file_id: str
    path: str
    revision: int
    device: str
    deleted: bool
    size: int
    mtime_ns: int
    sha256: str
    native_id: str = ""

    @property
    def order(self) -> tuple[int, str]:
        return self.revision, self.device

    def wire(self) -> dict:
        value = asdict(self)
        value.pop("native_id")
        return value

    @classmethod
    def from_wire(cls, value: dict) -> Record:
        record = cls(**value)
        record.path = safe_path(record.path)
        if record.revision < 1 or not record.file_id or not record.device:
            raise ValueError("无效文件版本")
        if not record.deleted and (len(record.sha256) != 64 or record.size < 0):
            raise ValueError("无效文件内容记录")
        return record

    def same_payload(self, other: Record) -> bool:
        return self.wire() == other.wire()


@dataclass
class SyncStats:
    downloaded_files: int = 0
    downloaded_bytes: int = 0
    renames_without_download: int = 0
    deletes: int = 0
    conflicts: int = 0
    history_entries: int = 0

    def merge(self, other: SyncStats) -> None:
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))


class HistoryStore:
    def __init__(self, root: Path, retention_days: int = 30, max_bytes: int = 20 * 1024**3):
        self.root = root
        self.retention_ns = retention_days * 24 * 60 * 60 * 1_000_000_000
        self.max_bytes = max_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def preserve(self, source: Path, original_path: str, reason: str) -> str:
        entry_id = uuid.uuid4().hex
        destination = self.root / entry_id
        destination.mkdir()
        shutil.copy2(source, destination / source.name)
        metadata = {
            "id": entry_id,
            "original_path": original_path,
            "file_name": source.name,
            "stored_at_ns": time.time_ns(),
            "size": source.stat().st_size,
            "reason": reason,
        }
        (destination / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return entry_id

    def entries(self) -> list[dict]:
        result = []
        for path in self.root.glob("*/metadata.json"):
            try:
                result.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(result, key=lambda item: item["stored_at_ns"])

    def cleanup(self, now_ns: int | None = None) -> int:
        now_ns = now_ns or time.time_ns()
        removed = 0
        entries = self.entries()
        for entry in entries:
            if now_ns - int(entry["stored_at_ns"]) > self.retention_ns:
                shutil.rmtree(self.root / entry["id"], ignore_errors=True)
                removed += 1
        remaining = self.entries()
        total = sum(int(entry["size"]) for entry in remaining)
        for entry in remaining:
            if total <= self.max_bytes:
                break
            shutil.rmtree(self.root / entry["id"], ignore_errors=True)
            total -= int(entry["size"])
            removed += 1
        return removed

    def restore(self, entry_id: str, sync_root: Path) -> Path:
        entry = self.root / entry_id
        metadata = json.loads((entry / "metadata.json").read_text(encoding="utf-8"))
        source = entry / metadata["file_name"]
        destination = sync_root.joinpath(*PurePosixPath(safe_path(metadata["original_path"])).parts)
        if destination.exists():
            destination = destination.with_name(f"{destination.stem}.restored{destination.suffix}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination


class SyncEngine:
    def __init__(
        self,
        root: Path,
        device: str,
        metadata_root: Path,
        excluded: tuple[str, ...] = (),
        history_days: int = 30,
        history_bytes: int = 20 * 1024**3,
    ):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.device = device
        self.metadata_root = metadata_root
        self.metadata_root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.metadata_root / "state.json"
        self.excluded = tuple(safe_path(item) for item in excluded)
        self.history = HistoryStore(self.metadata_root / "history", history_days, history_bytes)
        self.records: dict[str, Record] = {}
        self.lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        try:
            values = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.records = {item["file_id"]: Record(**item) for item in values["records"]}
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError):
            self.records = {}

    def _save(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"records": [asdict(record) for record in self.records.values()]}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, self.state_path)

    def is_excluded(self, relative: str) -> bool:
        return any(relative == item or relative.startswith(item + "/") for item in self.excluded)

    def path_for(self, relative: str) -> Path:
        normalized = safe_path(relative)
        destination = self.root.joinpath(*PurePosixPath(normalized).parts)
        if not destination.resolve().is_relative_to(self.root):
            raise ValueError("路径超出同步目录")
        return destination

    def _disk(self) -> dict[str, tuple[Path, os.stat_result]]:
        result = {}
        for base, directories, files in os.walk(self.root, followlinks=False):
            parent = Path(base)
            directories[:] = [name for name in directories if not (parent / name).is_symlink()]
            for name in files:
                path = parent / name
                if path.is_symlink() or name.startswith(".intranet-spike-"):
                    continue
                relative = path.relative_to(self.root).as_posix()
                if self.is_excluded(relative):
                    continue
                try:
                    result[relative] = (path, path.stat())
                except OSError:
                    continue
        return result

    @staticmethod
    def _native_id(stat: os.stat_result) -> str:
        return f"{stat.st_dev}:{stat.st_ino}"

    def scan(self) -> None:
        with self.lock:
            self._scan_unlocked()

    def _scan_unlocked(self) -> None:
        self._load()
        disk = self._disk()
        previous = self.records
        previous_paths = {record.path: record for record in previous.values()}
        previous_native = {record.native_id: record for record in previous.values() if record.native_id}
        updated: dict[str, Record] = {}
        matched_old: set[str] = set()
        for relative, (path, stat) in sorted(disk.items()):
            native_id = self._native_id(stat)
            old = previous_paths.get(relative)
            if old is not None and old.native_id != native_id:
                old = None
            if old is None:
                candidate = previous_native.get(native_id)
                if candidate is not None and candidate.file_id not in matched_old:
                    old = candidate
            if old is not None and not old.deleted and old.size == stat.st_size and old.mtime_ns == stat.st_mtime_ns:
                sha256 = old.sha256
            else:
                sha256 = hash_file(path)
            matched_old.add(old.file_id) if old else None
            if old is None:
                record = Record(uuid.uuid4().hex, relative, 1, self.device, False, stat.st_size, stat.st_mtime_ns, sha256, native_id)
            else:
                changed = old.deleted or old.path != relative or old.sha256 != sha256
                record = Record(
                    old.file_id,
                    relative,
                    old.revision + 1 if changed else old.revision,
                    self.device if changed else old.device,
                    False,
                    stat.st_size,
                    stat.st_mtime_ns,
                    sha256,
                    native_id,
                )
            updated[record.file_id] = record
        for old in previous.values():
            if old.file_id in matched_old:
                continue
            if old.path in disk or self.is_excluded(old.path):
                continue
            if old.deleted:
                updated[old.file_id] = old
            else:
                updated[old.file_id] = Record(
                    old.file_id, old.path, old.revision + 1, self.device, True,
                    old.size, time.time_ns(), old.sha256, old.native_id,
                )
        self.records = updated
        self._save()

    def manifest(self) -> list[dict]:
        with self.lock:
            self.scan()
            return [record.wire() for record in self.records.values()]

    def _adopt(self, remote: Record) -> None:
        local = self.path_for(remote.path)
        native_id = ""
        if local.exists() and not remote.deleted:
            stat = local.stat()
            native_id = self._native_id(stat)
        self.records[remote.file_id] = Record(**remote.wire(), native_id=native_id)
        self._save()

    def _preserve_history(self, path: Path, relative: str, reason: str) -> None:
        if path.exists():
            self.history.preserve(path, relative, reason)

    def _conflict_copy(self, source: Path) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = source.with_name(f"{source.stem} (冲突-{self.device}-{stamp}){source.suffix}")
        counter = 1
        while target.exists():
            target = target.with_name(f"{source.stem} (冲突-{self.device}-{stamp}-{counter}){source.suffix}")
            counter += 1
        shutil.copy2(source, target)

    def _download_from(self, peer: SyncEngine, remote: Record, temporary: Path) -> int:
        source, current = peer.open_record(remote)
        with source, temporary.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        return current.size

    def open_record(self, requested: Record) -> tuple[BinaryIO, Record]:
        with self.lock:
            self.scan()
            current = self.records.get(requested.file_id)
            if current is None or current.deleted or current.wire() != requested.wire():
                raise FileNotFoundError("文件版本已变化")
            return self.path_for(current.path).open("rb"), current

    def sync_from(self, peer: SyncEngine) -> SyncStats:
        with self.lock:
            return self._sync_from_unlocked(peer)

    def _sync_from_unlocked(self, peer: SyncEngine) -> SyncStats:
        remote_records = [Record.from_wire(item) for item in peer.manifest()]
        self.scan()
        stats = SyncStats()
        for remote in sorted(remote_records, key=lambda item: item.path):
            if self.is_excluded(remote.path):
                continue
            local = self.records.get(remote.file_id)
            if local and remote.order < local.order:
                continue
            if local and remote.same_payload(local):
                continue
            preserve_conflict = False
            if local and local.revision == remote.revision and local.device != remote.device:
                remote_wins = (remote.mtime_ns, remote.device) > (local.mtime_ns, local.device)
                if not remote_wins:
                    continue
                preserve_conflict = local.sha256 != remote.sha256 or local.path != remote.path
            self._apply(peer, remote, local, stats, preserve_conflict)
        self.scan()
        return stats

    def _apply(self, peer: SyncEngine, remote: Record, local: Record | None, stats: SyncStats, conflict: bool) -> None:
        destination = self.path_for(remote.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        local_path = self.path_for(local.path) if local else destination
        path_collision = self.records.get(next((item for item in self.records if self.records[item].path == remote.path), ""))
        if path_collision and path_collision.file_id != remote.file_id and not path_collision.deleted:
            conflict = True
        if remote.deleted:
            if local_path.exists():
                self._preserve_history(local_path, local.path if local else remote.path, "sync-delete")
                stats.history_entries += 1
                local_path.unlink()
            self._adopt(remote)
            stats.deletes += 1
            return
        if local and local.path != remote.path and local.sha256 == remote.sha256 and local_path.exists():
            if destination.exists() and destination != local_path:
                self._preserve_history(destination, remote.path, "path-replaced")
                destination.unlink()
            os.replace(local_path, destination)
            self._adopt(remote)
            stats.renames_without_download += 1
            return
        if conflict and local_path.exists():
            self._conflict_copy(local_path)
            stats.conflicts += 1
        if destination.exists():
            self._preserve_history(destination, remote.path, "sync-overwrite")
            stats.history_entries += 1
        temporary = destination.parent / f".intranet-spike-{uuid.uuid4().hex}.tmp"
        try:
            stats.downloaded_bytes += self._download_from(peer, remote, temporary)
            if temporary.stat().st_size != remote.size or hash_file(temporary) != remote.sha256:
                raise ValueError("文件内容校验失败")
            os.replace(temporary, destination)
            os.utime(destination, ns=(remote.mtime_ns, remote.mtime_ns))
            self._adopt(remote)
            stats.downloaded_files += 1
        finally:
            temporary.unlink(missing_ok=True)

    def restore(self, entry_id: str) -> Path:
        restored = self.history.restore(entry_id, self.root)
        self.scan()
        return restored
