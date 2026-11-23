from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .transport import hash_file


def main() -> None:
    parser = argparse.ArgumentParser(description="测量隔离大文件的 Windows SMB 拷贝基线")
    parser.add_argument("--source-dir", required=True, help="只含合成测试文件的 SMB 共享目录")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", default="docs/evidence/smb-baseline.json")
    args = parser.parse_args()
    if not 1 <= args.runs <= 10:
        parser.error("runs 必须在 1–10 之间")
    project = Path(__file__).resolve().parent.parent
    destination = (project / ".validation-data" / "smb-copy").resolve()
    allowed = (project / ".validation-data").resolve()
    if not destination.is_relative_to(allowed):
        parser.error("目标目录必须位于 .validation-data")
    destination.mkdir(parents=True, exist_ok=True)
    source_file = Path(args.source_dir) / "deterministic.bin"
    if not source_file.is_file():
        parser.error(f"找不到隔离测试文件：{source_file}")
    expected_hash = hash_file(source_file)
    results = []
    for run in range(1, args.runs + 1):
        target = destination / "deterministic.bin"
        target.unlink(missing_ok=True)
        started = time.perf_counter()
        completed = subprocess.run(
            ["robocopy", args.source_dir, str(destination), "deterministic.bin", "/R:0", "/W:0", "/NP"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.perf_counter() - started
        if completed.returncode > 7:
            raise RuntimeError(f"robocopy 失败（{completed.returncode}）：\n{completed.stdout}\n{completed.stderr}")
        size = target.stat().st_size
        actual_hash = hash_file(target)
        if actual_hash != expected_hash:
            raise ValueError("SMB 拷贝哈希不一致")
        results.append(
            {
                "run": run,
                "seconds": elapsed,
                "bytes": size,
                "mbps": size * 8 / elapsed / 1_000_000,
                "sha256": actual_hash,
                "hash_match": True,
            }
        )
        target.unlink()
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_dir": args.source_dir,
        "file": "deterministic.bin",
        "results": results,
        "median_mbps": sorted(item["mbps"] for item in results)[len(results) // 2],
        "scope": "isolated synthetic file over Windows SMB; not an Intranet result",
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = project / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
