from __future__ import annotations

import os
import queue
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import autostart, theme
from .config import AppConfig, ConfigStore, network_id
from .pairing import PairingManager
from .service import IntranetService
from .tray import TrayController


class IntranetApp:
    def __init__(self, root: tk.Tk, store: ConfigStore | None = None, background: bool = False):
        self.root = root
        self.store = store or ConfigStore()
        self.config = self.store.load()
        self.service: IntranetService | None = None
        self.root.title("Intranet")
        self.root.geometry("1100x760")
        self.root.minsize(960, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        theme.apply(root)
        self.status = tk.StringVar(value="尚未启动")
        self.network = tk.StringVar(value=f"当前网络：{network_id()}")
        self.folder = tk.StringVar(value=self.config.folder)
        self.device_name = tk.StringVar(value=self.config.device_name)
        self.peer_address = tk.StringVar()
        self.pair_code = tk.StringVar()
        self.autostart_enabled = tk.BooleanVar(value=self.config.autostart)
        self.exclusions = tk.StringVar(value=", ".join(self.config.exclusions))
        self.static_peers = tk.StringVar(value=", ".join(self.config.static_peers))
        self.history_days = tk.IntVar(value=self.config.history_days)
        self.history_gb = tk.DoubleVar(value=self.config.history_bytes / 1024**3)
        self.pages: dict[str, ttk.Frame] = {}
        self.nav_buttons: dict[str, ttk.Button] = {}
        self._build()
        self.tray = TrayController(self.show, self.toggle_pause, self.open_folder, self.shutdown)
        self.tray.start()
        if background:
            self.root.withdraw()
        if self.config.setup_complete and self.store.peer_certificate.exists() and self.config.folder:
            self.start_service()
        self.root.after(300, self._poll)

    def _page(self, key: str, title: str, subtitle: str) -> ttk.Frame:
        page = ttk.Frame(self.content, padding=(8, 4, 24, 16))
        ttk.Label(page, text=title, style="Title.TLabel").pack(anchor=tk.W, pady=(4, 2))
        ttk.Label(page, text=subtitle, style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 18))
        self.pages[key] = page
        return page

    @staticmethod
    def _card(parent: ttk.Frame) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        card.pack(fill=tk.X, pady=(0, 14))
        card.columnconfigure(1, weight=1)
        return card

    def _build(self) -> None:
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)
        sidebar = ttk.Frame(container, style="Sidebar.TFrame", width=190, padding=(20, 26, 12, 20))
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="Intranet", font=("Segoe UI", 20, "bold")).pack(anchor=tk.W, padx=10, pady=(0, 2))
        ttk.Label(sidebar, text="文件，始终在身边", style="Muted.TLabel").pack(anchor=tk.W, padx=10, pady=(0, 28))
        for key, label in (("sync", "同步"), ("pairing", "设备配对"), ("history", "历史恢复"), ("settings", "设置")):
            button = ttk.Button(sidebar, text=label, style="Nav.TButton", command=lambda k=key: self.show_page(k))
            button.pack(fill=tk.X, pady=2)
            self.nav_buttons[key] = button
        ttk.Label(sidebar, textvariable=self.network, style="Muted.TLabel", wraplength=155).pack(side=tk.BOTTOM, anchor=tk.W, padx=10, pady=12)
        self.content = ttk.Frame(container, padding=(24, 22, 10, 10))
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_sync(self._page("sync", "同步", "在两台电脑之间，安静地保持文件一致。"))
        self._build_pairing(self._page("pairing", "设备配对", "确认一次身份，之后自动安全连接。"))
        self._build_history(self._page("history", "历史恢复", "被删除或覆盖的文件，可以在这里找回。"))
        self._build_settings(self._page("settings", "设置", "让同步按照你的使用习惯运行。"))
        self.show_page("sync")

    def show_page(self, key: str) -> None:
        for name, page in self.pages.items():
            page.pack_forget()
            self.nav_buttons[name].configure(style="Nav.TButton")
        self.pages[key].pack(fill=tk.BOTH, expand=True)
        self.nav_buttons[key].configure(style="ActiveNav.TButton")
        if key == "history":
            self.refresh_history()

    def _build_sync(self, page: ttk.Frame) -> None:
        card = self._card(page)
        ttk.Label(card, text="同步文件夹", style="Card.TLabel").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Entry(card, textvariable=self.folder).grid(row=0, column=1, sticky=tk.EW, padx=12)
        ttk.Button(card, text="浏览…", style="Secondary.TButton", command=self.choose_folder).grid(row=0, column=2)
        ttk.Label(card, text="设备名称", style="Card.TLabel").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Entry(card, textvariable=self.device_name).grid(row=1, column=1, sticky=tk.EW, padx=12)
        ttk.Label(card, textvariable=self.network, style="CardMuted.TLabel").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=8)
        ttk.Button(card, text="信任此网络", style="Secondary.TButton", command=self.trust_network).grid(row=2, column=2)
        actions = ttk.Frame(page)
        actions.pack(fill=tk.X, pady=(0, 12))
        ttk.Button(actions, text="启动同步", style="Accent.TButton", command=self.start_service).pack(side=tk.LEFT)
        ttk.Button(actions, text="暂停 / 恢复", style="Secondary.TButton", command=self.toggle_pause).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="打开文件夹", style="Secondary.TButton", command=self.open_folder).pack(side=tk.LEFT)
        ttk.Label(page, textvariable=self.status, style="Status.TLabel", wraplength=680).pack(anchor=tk.W, pady=(0, 12))
        log_card = self._card(page)
        ttk.Label(log_card, text="运行日志", style="Section.TLabel").pack(anchor=tk.W, pady=(0, 8))
        self.log = scrolledtext.ScrolledText(log_card, height=15, state=tk.DISABLED, wrap=tk.WORD, bd=0, bg="#FFFFFF", fg="#1D1D1F", font=("Microsoft YaHei UI", 9))
        self.log.pack(fill=tk.BOTH, expand=True)

    def _build_pairing(self, page: ttk.Frame) -> None:
        host = self._card(page)
        ttk.Label(host, text="在这台电脑上生成配对码", style="Section.TLabel").grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        ttk.Label(host, text="另一台电脑输入后，即可完成配对。", style="CardMuted.TLabel").grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
        ttk.Button(host, text="生成配对码并等待", style="Accent.TButton", command=self.host_pair).grid(row=2, column=0, sticky=tk.W)
        join = self._card(page)
        ttk.Label(join, text="使用另一台电脑的配对码", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        ttk.Label(join, text="对端 IP:端口", style="Card.TLabel").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Entry(join, textvariable=self.peer_address).grid(row=1, column=1, sticky=tk.EW)
        ttk.Label(join, text="配对码", style="Card.TLabel").grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Entry(join, textvariable=self.pair_code).grid(row=2, column=1, sticky=tk.EW)
        ttk.Button(join, text="完成配对", style="Accent.TButton", command=self.join_pair).grid(row=3, column=1, sticky=tk.W, pady=(10, 0))
        self.pair_status = tk.StringVar(value="两台电脑只需配对一次")
        ttk.Label(page, textvariable=self.pair_status, style="Status.TLabel", wraplength=650).pack(anchor=tk.W, pady=8)

    def _build_history(self, page: ttk.Frame) -> None:
        actions = ttk.Frame(page)
        actions.pack(fill=tk.X, pady=(0, 12))
        ttk.Button(actions, text="刷新", style="Secondary.TButton", command=self.refresh_history).pack(side=tk.LEFT)
        ttk.Button(actions, text="恢复选中文件", style="Accent.TButton", command=self.restore_history).pack(side=tk.LEFT, padx=8)
        card = self._card(page)
        self.history = ttk.Treeview(card, columns=("path", "date", "size", "reason"), show="headings", height=16)
        for key, title, width in (("path", "原路径", 320), ("date", "时间", 150), ("size", "大小", 90), ("reason", "原因", 120)):
            self.history.heading(key, text=title)
            self.history.column(key, width=width)
        self.history.pack(fill=tk.BOTH, expand=True)

    def _build_settings(self, page: ttk.Frame) -> None:
        network = self._card(page)
        ttk.Label(network, text="排除路径", style="Card.TLabel").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Entry(network, textvariable=self.exclusions).grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(network, text="相对路径，逗号分隔；排除不传播删除", style="CardMuted.TLabel").grid(row=1, column=1, sticky=tk.W)
        ttk.Label(network, text="静态设备地址", style="Card.TLabel").grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Entry(network, textvariable=self.static_peers).grid(row=2, column=1, sticky=tk.EW)
        ttk.Label(network, text="IP:端口，逗号分隔，广播不可用时使用", style="CardMuted.TLabel").grid(row=3, column=1, sticky=tk.W)
        history = self._card(page)
        ttk.Label(history, text="历史保留天数", style="Card.TLabel").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(history, from_=1, to=365, textvariable=self.history_days).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(history, text="历史上限（GB）", style="Card.TLabel").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(history, from_=1, to=100, textvariable=self.history_gb).grid(row=1, column=1, sticky=tk.W)
        ttk.Checkbutton(history, text="登录 Windows 时自动启动", variable=self.autostart_enabled).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=10)
        ttk.Button(page, text="保存设置", style="Accent.TButton", command=self.save_settings).pack(anchor=tk.W)

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.folder.get() or str(Path.home()))
        if selected:
            self.folder.set(selected)

    def save_config(self) -> AppConfig:
        folder = self.folder.get().strip()
        if not folder:
            raise ValueError("请选择同步文件夹")
        Path(folder).mkdir(parents=True, exist_ok=True)
        self.config.folder = folder
        self.config.device_name = self.device_name.get().strip() or "Windows 设备"
        self.config.exclusions = [item.strip().replace("\\", "/") for item in self.exclusions.get().split(",") if item.strip()]
        self.config.static_peers = [item.strip() for item in self.static_peers.get().split(",") if item.strip()]
        self.config.history_days = int(self.history_days.get())
        self.config.history_bytes = int(float(self.history_gb.get()) * 1024**3)
        self.config.autostart = bool(self.autostart_enabled.get())
        self.store.save(self.config)
        autostart.set_enabled(self.config.autostart)
        return self.config

    def save_settings(self) -> None:
        try:
            self.save_config()
            self.status.set("设置已保存；重启同步服务后全部生效")
        except (OSError, ValueError, tk.TclError) as exc:
            messagebox.showerror("保存失败", str(exc))

    def trust_network(self) -> None:
        current = network_id()
        if current == "offline":
            self.status.set("未检测到可信任的 Wi-Fi")
            return
        if current not in self.config.trusted_networks:
            self.config.trusted_networks.append(current)
            self.store.save(self.config)
        self.status.set(f"已信任 {current}")

    def host_pair(self) -> None:
        try:
            self.save_config()
            manager = PairingManager(self.store, self.config)
            manager.offer(self._pair_code_ready, self._pair_done)
            self.pair_status.set("正在等待另一台电脑输入配对码…")
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法配对", str(exc))

    def _pair_code_ready(self, code: str, port: int) -> None:
        self.root.after(0, lambda: self.pair_status.set(f"配对码：{code}　端口：{port}（5 分钟内有效）"))

    def join_pair(self) -> None:
        if not self.peer_address.get().strip() or not self.pair_code.get().strip():
            messagebox.showerror("无法配对", "请输入对端地址和配对码")
            return
        try:
            self.save_config()
            manager = PairingManager(self.store, self.config)
            manager.join(self.peer_address.get().strip(), self.pair_code.get().strip(), self._pair_done)
            self.pair_status.set("正在配对…")
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法配对", str(exc))

    def _pair_done(self, text: str) -> None:
        def complete() -> None:
            self.pair_status.set(text)
            if text == "配对成功" or text.startswith("已与"):
                self.config.setup_complete = True
                self.store.save(self.config)
                self.start_service()
        self.root.after(0, complete)

    def start_service(self) -> None:
        if self.service and self.service.running:
            self.status.set("同步服务已在运行")
            return
        try:
            self.save_config()
            if not self.store.peer_certificate.exists():
                raise ValueError("请先在“设备配对”页面完成配对")
            self.service = IntranetService(self.store, self.config)
            self.service.start()
            self.status.set("后台同步已启动")
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法启动", str(exc))

    def toggle_pause(self) -> None:
        if self.service:
            self.service.toggle_pause()
            self.tray.set_paused(self.service.paused)

    def open_folder(self) -> None:
        if self.folder.get() and Path(self.folder.get()).is_dir():
            os.startfile(self.folder.get())

    def _poll(self) -> None:
        if self.service:
            while True:
                try:
                    event = self.service.events.get_nowait()
                except queue.Empty:
                    break
                kind = event["type"]
                if kind in ("status", "network", "retry", "error"):
                    self.status.set(event.get("text", kind))
                elif kind == "discovered":
                    self.status.set(f"已发现设备 {event['device']}")
                elif kind == "sync":
                    stats = event["stats"]
                    if stats.get("conflicts"):
                        self.status.set(f"发现 {stats['conflicts']} 个文件冲突，请检查冲突副本")
                        self.tray.notify(self.status.get())
                    else:
                        self.status.set(f"最近同步：{time.strftime('%H:%M:%S', time.localtime(event['timestamp']))}")
                    self._append_log(event)
                elif kind == "history_cleanup":
                    self.status.set(event["text"])
                    self.tray.notify(event["text"])
                if kind in ("status", "network", "retry", "error", "discovered"):
                    self._append_log(event)
            self.tray.set_status(self.status.get())
        if self.root.winfo_exists():
            self.root.after(500, self._poll)

    def _append_log(self, event: dict) -> None:
        text = time.strftime("%H:%M:%S", time.localtime(event["timestamp"])) + "  " + str(event.get("text", event))
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.configure(state=tk.DISABLED)
        self.log.see(tk.END)

    def refresh_history(self) -> None:
        self.history.delete(*self.history.get_children())
        if not self.service:
            return
        for entry in reversed(self.service.history_entries()):
            date = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["stored_at_ns"] / 1e9))
            self.history.insert("", tk.END, iid=entry["id"], values=(entry["original_path"], date, entry["size"], entry["reason"]))

    def restore_history(self) -> None:
        selected = self.history.selection()
        if not selected or not self.service:
            return
        try:
            path = self.service.restore(selected[0])
            self.status.set(f"已恢复到 {path}")
            self.refresh_history()
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("恢复失败", str(exc))

    def hide(self) -> None:
        self.root.withdraw()

    def show(self) -> None:
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def shutdown(self) -> None:
        if self.service:
            self.service.stop()
        self.tray.stop()
        self.root.after(0, self.root.destroy)


def run(background: bool = False) -> None:
    root = tk.Tk()
    IntranetApp(root, background=background)
    root.mainloop()
