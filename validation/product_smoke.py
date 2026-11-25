from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import time
from pathlib import Path

from intranet.config import AppConfig, ConfigStore, network_id
from intranet.pairing import PairingManager
from intranet.service import IntranetService


def main() -> None:
    parser = argparse.ArgumentParser(description="Intranet 产品隔离冒烟验证")
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    root = (Path(__file__).resolve().parent.parent / ".validation-data" / "product-smoke").resolve()
    shutil.rmtree(root, ignore_errors=True)
    result = {"pairing": False, "a_to_b": False, "b_to_a": False, "text_a_to_b": False, "text_b_to_a": False, "pause_resume": False, "gui": False}
    try:
        store_a = ConfigStore(root / "A-data")
        store_b = ConfigStore(root / "B-data")
        config_a = AppConfig(
            device_id="product-A", device_name="A", folder=str(root / "A"), tcp_port=47661,
            discovery_port=47811, static_peers=["127.0.0.1:47662"], trusted_networks=[network_id()], setup_complete=True,
        )
        config_b = AppConfig(
            device_id="product-B", device_name="B", folder=str(root / "B"), tcp_port=47662,
            discovery_port=47812, static_peers=["127.0.0.1:47661"], trusted_networks=[network_id()], setup_complete=True,
        )
        codes, done = queue.Queue(), queue.Queue()
        PairingManager(store_a, config_a).offer(lambda code, port: codes.put(code), lambda text: done.put(text))
        code = codes.get(timeout=10)
        PairingManager(store_b, config_b).join("127.0.0.1:47661", code, lambda text: done.put(text))
        outcomes = [done.get(timeout=15), done.get(timeout=15)]
        assert all(text == "配对成功" or text.startswith("已与") for text in outcomes), outcomes
        result["pairing"] = True
        a = IntranetService(store_a, config_a)
        b = IntranetService(store_b, config_b)
        a.start()
        b.start()
        try:
            (root / "A" / "from-A.txt").write_text("A content", encoding="utf-8")
            wait_for(root / "B" / "from-A.txt")
            result["a_to_b"] = True
            (root / "B" / "from-B.txt").write_text("B content", encoding="utf-8")
            wait_for(root / "A" / "from-B.txt")
            result["b_to_a"] = True
            a.send_text("第一行\nfrom A")
            assert wait_text(b) == "第一行\nfrom A"
            result["text_a_to_b"] = True
            b.send_text("来自 B\nsecond line")
            assert wait_text(a) == "来自 B\nsecond line"
            result["text_b_to_a"] = True
            b.toggle_pause()
            (root / "A" / "paused.txt").write_text("resume", encoding="utf-8")
            time.sleep(2)
            assert not (root / "B" / "paused.txt").exists()
            b.toggle_pause()
            wait_for(root / "B" / "paused.txt")
            result["pause_resume"] = True
        finally:
            a.stop()
            b.stop()
        if args.gui:
            import tkinter as tk
            from intranet.app import IntranetApp
            os.environ["INTRANET_DATA_DIR"] = str(root / "gui-data")
            window = tk.Tk()
            window.withdraw()
            app = IntranetApp(window, store=ConfigStore(root / "gui-data"))
            app.show_page("transfer")
            window.update_idletasks()
            window.update()
            assert ":" in app.local_endpoint.get()
            app.shutdown()
            window.update()
            result["gui"] = True
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def wait_text(service: IntranetService, timeout: float = 15) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            event = service.events.get(timeout=0.1)
        except queue.Empty:
            continue
        if event["type"] == "text_received":
            return event["text"]
    raise TimeoutError("等待即时文字超时")


def wait_for(path: Path, timeout: float = 15) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline and not path.exists():
        time.sleep(0.1)
    assert path.exists(), f"等待文件超时：{path}"


if __name__ == "__main__":
    main()
