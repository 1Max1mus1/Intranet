from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pystray
from PIL import Image, ImageDraw


class TrayController:
    def __init__(self, on_show: Callable, on_pause: Callable, on_open: Callable, on_exit: Callable):
        self.paused = False
        self.last_notification = 0.0
        image = Image.new("RGB", (64, 64), "#1769aa")
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 12, 48, 52), fill="white")
        draw.rectangle((22, 20, 42, 44), fill="#1769aa")
        self.icon = pystray.Icon(
            "Intranet",
            image,
            "Intranet",
            pystray.Menu(
                pystray.MenuItem("打开 Intranet", on_show, default=True),
                pystray.MenuItem(lambda _: "恢复同步" if self.paused else "暂停同步", on_pause),
                pystray.MenuItem("打开同步文件夹", on_open),
                pystray.MenuItem("退出", on_exit),
            ),
        )
        self.thread = threading.Thread(target=self.icon.run, name="intranet-tray", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def set_paused(self, value: bool) -> None:
        self.paused = value
        self.icon.update_menu()

    def set_status(self, text: str) -> None:
        self.icon.title = f"Intranet\n{text}"

    def notify(self, text: str) -> None:
        now = time.monotonic()
        if now - self.last_notification < 30:
            return
        self.last_notification = now
        self.icon.notify(text, "Intranet")

    def stop(self) -> None:
        self.icon.stop()
