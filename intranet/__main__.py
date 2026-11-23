from __future__ import annotations

import argparse
import time

from .app import run
from .config import load_config
from .service import SyncService


def main() -> None:
    parser = argparse.ArgumentParser(description="Intranet 局域网双向文件同步")
    parser.add_argument("--headless", action="store_true", help="不显示图形界面")
    parser.add_argument("--folder", help="同步文件夹")
    parser.add_argument("--key", help="同步密钥，也可使用 INTRANET_KEY 环境变量")
    parser.add_argument("--name", help="设备名称")
    parser.add_argument("--peer", action="append", default=[], help="手动设备地址 IP:端口，可重复")
    parser.add_argument("--tcp-port", type=int, help="TCP 端口，默认 47621")
    parser.add_argument("--udp-port", type=int, help="UDP 发现端口，默认 47620")
    args = parser.parse_args()
    if not args.headless:
        run()
        return

    import os

    config = load_config()
    if args.folder:
        config.folder = args.folder
    if args.key or os.environ.get("INTRANET_KEY"):
        config.sync_key = args.key or os.environ["INTRANET_KEY"]
    if args.name:
        config.device_name = args.name
    if args.peer:
        config.manual_peers = args.peer
    if args.tcp_port is not None:
        config.tcp_port = args.tcp_port
    if args.udp_port is not None:
        config.udp_port = args.udp_port
    service = SyncService(config)
    service.start()
    print(f"Intranet 已启动，设备 {config.device_name}，TCP 端口 {service.port}，按 Ctrl+C 停止")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()
