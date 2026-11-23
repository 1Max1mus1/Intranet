from __future__ import annotations

import argparse
import json
import shutil
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .dual_node import NodeFiles, parse_peer, validation_path
from .engine import SyncEngine
from .network import RemotePeer
from .transport import hash_file


def main() -> None:
    parser = argparse.ArgumentParser(description="多轮双机 TLS 同步性能验证")
    parser.add_argument("--root", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--peer", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--smb-median-mbps", type=float, required=True)
    parser.add_argument("--output", default="docs/evidence/intranet-performance.json")
    parser.add_argument("--trusted-network", action="store_true")
    args = parser.parse_args()
    if not args.trusted_network:
        parser.error("必须使用 --trusted-network")
    if not 1 <= args.runs <= 10:
        parser.error("runs 必须在 1–10 之间")
    files = NodeFiles(args.root, args.device, args.metadata)
    host, port = parse_peer(args.peer)
    peer = RemotePeer(host, port, files.key, files.certificate, files.peer_certificate)
    results = []
    try:
        for run in range(1, args.runs + 1):
            run_root = files.root / f"run-{run}"
            engine = SyncEngine(run_root, args.device, files.metadata / "engine" / f"run-{run}")
            started = time.perf_counter()
            stats = engine.sync_from(peer)
            elapsed = time.perf_counter() - started
            target = run_root / "deterministic.bin"
            if stats.downloaded_files != 1 or not target.is_file():
                raise AssertionError(f"第 {run} 轮文件数量不符合预期：{asdict(stats)}")
            actual_hash = hash_file(target)
            results.append(
                {
                    "run": run,
                    "seconds": elapsed,
                    "bytes": stats.downloaded_bytes,
                    "mbps": stats.downloaded_bytes * 8 / elapsed / 1_000_000,
                    "sha256": actual_hash,
                    "stats": asdict(stats),
                }
            )
    finally:
        peer.close()
    expected_hash = "734546cb6c9f493ed1aed3d17e8a1c4c5ef282898313fef4403807163e9b4cef"
    if any(item["sha256"] != expected_hash for item in results):
        raise ValueError("Intranet 文件哈希不一致")
    median = sorted(item["mbps"] for item in results)[len(results) // 2]
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "peer": args.peer,
        "results": results,
        "median_mbps": median,
        "smb_median_mbps": args.smb_median_mbps,
        "ratio_to_smb": median / args.smb_median_mbps,
        "threshold": 0.70,
        "scope": f"same 128 MiB synthetic file, {args.runs} paired TLS runs on the private hotspot",
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).resolve().parent.parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    shutil.rmtree(validation_path(args.root), ignore_errors=True)


if __name__ == "__main__":
    main()
