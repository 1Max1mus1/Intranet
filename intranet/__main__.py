from __future__ import annotations

import argparse

from .app import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Intranet 局域网双向文件同步")
    parser.add_argument("--background", action="store_true", help="启动时隐藏到系统托盘")
    args = parser.parse_args()
    run(background=args.background)


if __name__ == "__main__":
    main()
