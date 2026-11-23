from __future__ import annotations

import argparse
import json
import random
import struct
import zlib
from pathlib import Path


def png_bytes(width: int = 64, height: int = 64) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))

    raw = b"".join(
        b"\x00" + b"".join(bytes(((x * 3) % 256, (y * 5) % 256, 96)) for x in range(width))
        for y in range(height)
    )
    header = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def create_corpus(root: Path, large_size: int = 128 * 1024 * 1024, small_files: int = 200) -> dict:
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"测试目录必须为空：{root}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "文档").mkdir()
    (root / "文档" / "会议记录.txt").write_text("Intranet 隔离测试数据，不包含真实工作文件。\n" * 20, encoding="utf-8")
    (root / "代码").mkdir()
    (root / "代码" / "main.py").write_text("print('synthetic validation corpus')\n", encoding="utf-8")
    (root / "图片").mkdir()
    (root / "图片" / "测试图片.png").write_bytes(png_bytes())
    (root / "空文件.bin").write_bytes(b"")
    long_name = "长文件名-" + "项目资料_" * 20 + "版本.txt"
    (root / "文档" / long_name).write_text("long and unicode filename", encoding="utf-8")
    small = root / "大量小文件"
    small.mkdir()
    for index in range(small_files):
        (small / f"item-{index:04d}.txt").write_text(f"index={index}\n" * (index % 17 + 1), encoding="utf-8")
    large = root / "大文件" / "deterministic.bin"
    large.parent.mkdir()
    rng = random.Random(20261123)
    with large.open("wb") as target:
        remaining = large_size
        while remaining:
            payload = rng.randbytes(min(1024 * 1024, remaining))
            target.write(payload)
            remaining -= len(payload)
    return {
        "root": str(root.resolve()),
        "file_count": sum(1 for path in root.rglob("*") if path.is_file()),
        "bytes": sum(path.stat().st_size for path in root.rglob("*") if path.is_file()),
        "large_size": large_size,
        "small_files": small_files,
        "contains_real_user_files": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Intranet 隔离技术验证数据")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--large-size", type=int, default=128 * 1024 * 1024)
    parser.add_argument("--small-files", type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(create_corpus(args.root, args.large_size, args.small_files), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
