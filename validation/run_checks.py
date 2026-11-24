from __future__ import annotations

import json
import os
import queue
import random
import shutil
import socket
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .engine import SyncEngine
from .security import (
    NetworkPolicy,
    PairingError,
    PairingRegistry,
    client_context,
    create_identity,
    server_context,
)
from .transport import ChunkServer, InjectedInterruption, ResumableDownloader, hash_file


def v1(root: Path) -> dict:
    a = SyncEngine(root / "A", "A", root / "meta-A")
    b = SyncEngine(root / "B", "B", root / "meta-B", excluded=("cache",))
    (root / "A" / "nested").mkdir(parents=True)
    (root / "A" / "nested" / "one.txt").write_text("one", encoding="utf-8")
    (root / "A" / "empty.bin").write_bytes(b"")
    (root / "A" / "cache").mkdir()
    (root / "A" / "cache" / "local.tmp").write_text("A cache", encoding="utf-8")
    (root / "B" / "cache").mkdir(parents=True)
    (root / "B" / "cache" / "local.tmp").write_text("B cache", encoding="utf-8")
    b.sync_from(a)
    assert (root / "B" / "nested" / "one.txt").read_text() == "one"
    assert (root / "B" / "empty.bin").exists()
    assert (root / "B" / "cache" / "local.tmp").read_text() == "B cache"
    (root / "B" / "nested" / "one.txt").write_text("two", encoding="utf-8")
    a.sync_from(b)
    assert (root / "A" / "nested" / "one.txt").read_text() == "two"
    old_id = next(record.file_id for record in a.records.values() if record.path == "nested/one.txt")
    (root / "A" / "nested" / "one.txt").replace(root / "A" / "nested" / "renamed.txt")
    stats = b.sync_from(a)
    assert stats.renames_without_download == 1 and stats.downloaded_bytes == 0
    assert (root / "B" / "nested" / "renamed.txt").read_text() == "two"
    assert not (root / "B" / "nested" / "one.txt").exists()
    assert next(record.file_id for record in b.records.values() if record.path == "nested/renamed.txt") == old_id
    (root / "A" / "nested" / "renamed.txt").unlink()
    a.sync_from(b)
    assert next(record for record in a.records.values() if record.file_id == old_id).deleted
    b.sync_from(a)
    assert not (root / "B" / "nested" / "renamed.txt").exists()
    (root / "A" / "cache" / "local.tmp").unlink()
    b.sync_from(a)
    assert (root / "B" / "cache" / "local.tmp").read_text() == "B cache"
    (root / "B" / "from-b.txt").write_text("B", encoding="utf-8")
    a.sync_from(b)
    assert (root / "A" / "from-b.txt").read_text() == "B"
    restarted = SyncEngine(root / "A", "A", root / "meta-A")
    assert any(record.deleted for record in restarted.records.values())
    shared_server = SyncEngine(root / "Shared", "S", root / "shared-meta")
    shared_writer = SyncEngine(root / "Shared", "S", root / "shared-meta")
    remote = SyncEngine(root / "Remote", "R", root / "remote-meta")
    (root / "Shared" / "shared.txt").write_text("base", encoding="utf-8")
    remote.sync_from(shared_writer)
    shared_server.scan()
    (root / "Remote" / "shared.txt").write_text("remote update", encoding="utf-8")
    shared_writer.sync_from(remote)
    reloaded = next(record for record in shared_server.manifest() if record["path"] == "shared.txt")
    assert reloaded["device"] == "R" and reloaded["revision"] == 2
    return {"status": "pass", "rename_download_bytes": stats.downloaded_bytes, "stale_process_reload": "pass", "scope": "two isolated roots in one process"}


def v2(root: Path) -> dict:
    a = SyncEngine(root / "A", "A", root / "meta-A")
    b = SyncEngine(root / "B", "B", root / "meta-B")
    (root / "A" / "report.txt").write_text("base", encoding="utf-8")
    b.sync_from(a)
    (root / "A" / "report.txt").write_text("A version", encoding="utf-8")
    (root / "B" / "report.txt").write_text("B newer", encoding="utf-8")
    os.utime(root / "A" / "report.txt", ns=(1_700_000_000_000_000_000,) * 2)
    os.utime(root / "B" / "report.txt", ns=(1_800_000_000_000_000_000,) * 2)
    stats = a.sync_from(b)
    assert stats.conflicts == 1
    assert (root / "A" / "report.txt").read_text() == "B newer"
    conflicts = [path for path in (root / "A").glob("report*.txt") if "-A-" in path.name]
    assert len(conflicts) == 1 and conflicts[0].read_text() == "A version"
    entries = a.history.entries()
    assert any((root / "meta-A" / "history" / entry["id"] / entry["file_name"]).read_text() == "A version" for entry in entries)
    b.sync_from(a)
    assert len([path for path in (root / "B").glob("report*.txt") if "-A-" in path.name]) == 1
    restored = a.restore(entries[0]["id"])
    assert restored.name == "report.restored.txt" and restored.read_text() == "A version"
    original_id = next(record.file_id for record in a.records.values() if record.path == "report.txt")
    (root / "A" / "report.txt").unlink()
    a.sync_from(b)
    a.sync_from(SyncEngine(root / "B", "B", root / "meta-B"))
    assert next(record for record in a.records.values() if record.file_id == original_id).deleted
    limited = SyncEngine(root / "C", "C", root / "meta-C", history_days=0, history_bytes=1)
    (root / "C" / "x.txt").write_text("x", encoding="utf-8")
    limited.scan()
    limited.history.preserve(root / "C" / "x.txt", "x.txt", "test")
    assert limited.history.cleanup(time.time_ns() + 10_000_000_000) >= 1
    assert limited.history.entries() == []
    assert next(record for record in limited.records.values() if record.path == "x.txt").file_id
    return {"status": "pass", "conflicts": stats.conflicts, "history_entries": len(entries), "scope": "isolated roots"}


def v3(root: Path) -> dict:
    source = root / "source.bin"
    source.write_bytes(random.Random(42).randbytes(8 * 1024 * 1024 + 123))
    destination = root / "destination.bin"
    destination.write_bytes(b"original-complete-content")
    server = ChunkServer(source)
    try:
        first = ResumableDownloader("127.0.0.1", server.port, destination, root / "state", "transfer")
        try:
            first.download(interrupt_at=3 * 1024 * 1024)
            raise AssertionError("interruption did not fire")
        except InjectedInterruption:
            pass
        assert destination.read_bytes() == b"original-complete-content"
        assert first.temporary.stat().st_size == 3 * 1024 * 1024
        resumed = ResumableDownloader("127.0.0.1", server.port, destination, root / "state", "transfer")
        result = resumed.download()
        assert result["resumed"] and hash_file(destination) == hash_file(source)
        assert not resumed.checkpoint.exists() and not resumed.temporary.exists()
    finally:
        server.close()
    server = ChunkServer(source)
    try:
        target = root / "before.bin"
        target.write_bytes(b"old")
        item = ResumableDownloader("127.0.0.1", server.port, target, root / "state", "before")
        def stop():
            raise InjectedInterruption("injected")
        try:
            item.download(before_replace=stop)
        except InjectedInterruption:
            pass
        assert target.read_bytes() == b"old"
        item.download()
        assert hash_file(target) == hash_file(source)
        target2 = root / "after.bin"
        item2 = ResumableDownloader("127.0.0.1", server.port, target2, root / "state", "after")
        try:
            item2.download(after_replace=stop)
        except InjectedInterruption:
            pass
        assert hash_file(target2) == hash_file(source) and item2.checkpoint.exists()
        item2.download()
        assert not item2.checkpoint.exists()
    finally:
        server.close()
    corrupt = ChunkServer(source, corrupt=True)
    try:
        safe = root / "safe.bin"
        safe.write_bytes(b"known-good")
        item = ResumableDownloader("127.0.0.1", corrupt.port, safe, root / "state", "corrupt")
        try:
            item.download()
            raise AssertionError("corruption was not detected")
        except ValueError as exc:
            assert "校验失败" in str(exc)
        assert safe.read_bytes() == b"known-good"
    finally:
        corrupt.close()
    return {"status": "pass", "source_bytes": source.stat().st_size, "resume_offset": 3 * 1024 * 1024, "scope": "real TCP over loopback"}


def v4(root: Path, corpus: Path) -> dict:
    source = root / "A"
    target = root / "B"
    a = SyncEngine(source, "A", root / "meta-A")
    b = SyncEngine(target, "B", root / "meta-B")
    large = source / "large.bin"
    large.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(corpus / "大文件" / "deterministic.bin", large)
    started = time.perf_counter()
    b.sync_from(a)
    elapsed = time.perf_counter() - started
    size = large.stat().st_size
    started = time.perf_counter()
    shutil.copyfile(large, root / "baseline.bin")
    baseline = time.perf_counter() - started
    (source / "small.txt").write_text("small latency probe", encoding="utf-8")
    started = time.perf_counter()
    b.sync_from(a)
    small_elapsed = time.perf_counter() - started
    return {
        "status": "informational",
        "large_bytes": size,
        "sync_seconds": elapsed,
        "sync_mbps": size * 8 / elapsed / 1_000_000,
        "local_copy_seconds": baseline,
        "ratio_to_local_copy": baseline / elapsed,
        "small_file_seconds": small_elapsed,
        "acceptance": "pending two physical computers and SMB baseline; these numbers are not V4 acceptance evidence",
    }


def v5(root: Path) -> dict:
    a_key, a_cert = create_identity(root / "A", "device-a")
    b_key, b_cert = create_identity(root / "B", "device-b")
    x_key, x_cert = create_identity(root / "X", "unpaired-x")
    registry = PairingRegistry(root / "paired.json")
    code = registry.issue_code()
    try:
        registry.pair("000000" if code != "000000" else "000001", b_cert.read_bytes())
        raise AssertionError("wrong pairing code accepted")
    except PairingError:
        pass
    registry.pair(code, b_cert.read_bytes())
    assert registry.allows(b_cert.read_bytes()) and not registry.allows(x_cert.read_bytes())
    policy = NetworkPolicy()
    assert not policy.allows_sync("unknown-wifi", True)
    assert not policy.allows_sync("home", False)
    policy.trust("home")
    assert policy.allows_sync("home", True)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    port = listener.getsockname()[1]
    server_ctx = server_context(a_key, a_cert, b_cert)
    client_ctx = client_context(b_key, b_cert, a_cert)
    received: queue.Queue = queue.Queue()
    def serve():
        try:
            raw, _ = listener.accept()
            with server_ctx.wrap_socket(raw, server_side=True) as connection:
                peer_pem = ssl.DER_cert_to_PEM_cert(connection.getpeercert(binary_form=True)).encode("ascii")
                assert registry.allows(peer_pem)
                received.put(connection.recv(5))
                connection.sendall(b"pong!")
            raw, _ = listener.accept()
            try:
                with server_ctx.wrap_socket(raw, server_side=True) as connection:
                    connection.recv(5)
            except ssl.SSLError:
                received.put("unpaired-rejected")
        except Exception as exc:
            received.put(exc)
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        with socket.create_connection(("127.0.0.1", port)) as raw:
            with client_ctx.wrap_socket(raw, server_hostname="device-a") as connection:
                assert connection.version() in ("TLSv1.2", "TLSv1.3")
                connection.sendall(b"ping!")
                assert connection.recv(5) == b"pong!"
        bad_ctx = client_context(x_key, x_cert, a_cert)
        try:
            with socket.create_connection(("127.0.0.1", port)) as raw:
                with bad_ctx.wrap_socket(raw, server_hostname="device-a") as connection:
                    connection.sendall(b"ping!")
                    connection.recv(5)
        except (ssl.SSLError, ConnectionError, OSError):
            pass
        thread.join(timeout=5)
        assert received.get_nowait() == b"ping!"
        assert received.get_nowait() == "unpaired-rejected"
    finally:
        listener.close()
    assert code not in (root / "paired.json").read_text()
    return {"status": "pass", "tls": "1.2/1.3 mutual authentication", "unknown_network": "denied", "scope": "temporary certificates and loopback"}


def main() -> None:
    project = Path(__file__).resolve().parent.parent
    work = project / ".validation-data" / "checks"
    evidence = project / "docs" / "evidence" / "local-results.json"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": "single-machine preliminary validation; two-computer acceptance remains pending",
        "checks": {},
    }
    for name, function in (("v1", v1), ("v2", v2), ("v3", v3), ("v5", v5)):
        target = work / name
        target.mkdir()
        try:
            results["checks"][name] = function(target)
        finally:
            shutil.rmtree(target, ignore_errors=True)
    try:
        target = work / "v4"
        target.mkdir()
        results["checks"]["v4"] = v4(target, project / ".validation-data" / "corpus")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"Evidence: {evidence}")


if __name__ == "__main__":
    main()
