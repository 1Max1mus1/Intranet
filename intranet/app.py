from __future__ import annotations

import os
import queue
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import autostart
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
        self.root.geometry("860x680")
        self.root.minsize(720, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
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
        self._build()
        self.tray = TrayController(self.show, self.toggle_pause, self.open_folder, self.shutdown)
        self.tray.start()
        if background:
            self.root.withdraw()
        if self.config.setup_complete and self.store.peer_certificate.exists() and self.config.folder:
            self.start_service()
        self.root.after(300, self._poll)

    def _build(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        main = ttk.Frame(notebook, padding=12)
        pairing = ttk.Frame(notebook, padding=12)
        history = ttk.Frame(notebook, padding=12)
        settings = ttk.Frame(notebook, padding=12)
        notebook.add(main, text="同步")
        notebook.add(pairing, text="设备配对")
        notebook.add(history, text="历史恢复")
        notebook.add(settings, text="设置")
        main.columnconfigure(1, weight=1)

        ttk.Label(main, text="同步文件夹").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main, textvariable=self.folder).grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Button(main, text="浏览…", command=self.choose_folder).grid(row=0, column=2)
        ttk.Label(main, text="设备名称").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main, textvariable=self.device_name).grid(row=1, column=1, sticky=tk.EW, padx=8)
        ttk.Label(main, textvariable=self.network).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=8)
        ttk.Button(main, text="信任此网络", command=self.trust_network).grid(row=2, column=2)
        actions = ttk.Frame(main)
        actions.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=6)
        ttk.Button(actions, text="启动同步", command=self.start_service).pack(side=tk.LEFT)
        ttk.Button(actions, text="暂停 / 恢复", command=self.toggle_pause).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="打开文件夹", command=self.open_folder).pack(side=tk.LEFT)
        ttk.Label(main, textvariable=self.status, foreground="#175a9c", wraplength=700).grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=8)
        ttk.Label(main, text="运行日志").grid(row=5, column=0, columnspan=3, sticky=tk.W)
        self.log = scrolledtext.ScrolledText(main, height=18, state=tk.DISABLED, wrap=tk.WORD)
        self.log.grid(row=6, column=0, columnspan=3, sticky=tk.NSEW)
        main.rowconfigure(6, weight=1)

        pairing.columnconfigure(1, weight=1)
        ttk.Label(pairing, text="方式一：本机显示配对码", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=6)
        ttk.Button(pairing, text="生成配对码并等待", command=self.host_pair).grid(row=1, column=0, columnspan=2, sticky=tk.W)
        ttk.Label(pairing, text="方式二：输入另一台电脑的地址和配对码", font=("Segoe UI", 11, "bold")).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(22, 6))
        ttk.Label(pairing, text="对端 IP:端口").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(pairing, textvariable=self.peer_address).grid(row=3, column=1, sticky=tk.EW)
        ttk.Label(pairing, text="配对码").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Entry(pairing, textvariable=self.pair_code).grid(row=4, column=1, sticky=tk.EW)
        ttk.Button(pairing, text="完成配对", command=self.join_pair).grid(row=5, column=1, sticky=tk.W, pady=8)
        self.pair_status = tk.StringVar(value="两台电脑只需配对一次")
        ttk.Label(pairing, textvariable=self.pair_status, wraplength=650, foreground="#175a9c").grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=12)

        history_actions = ttk.Frame(history)
        history_actions.pack(fill=tk.X)
        ttk.Button(history_actions, text="刷新", command=self.refresh_history).pack(side=tk.LEFT)
        ttk.Button(history_actions, text="恢复选中文件", command=self.restore_history).pack(side=tk.LEFT, padx=8)
        self.history = ttk.Treeview(history, columns=("path", "date", "size", "reason"), show="headings")
        for key, title, width in (("path", "原路径", 350), ("date", "时间", 150), ("size", "大小", 100), ("reason", "原因", 130)):
            self.history.heading(key, text=title)
            self.history.column(key, width=width)
        self.history.pack(fill=tk.BOTH, expand=True, pady=8)

        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="排除路径").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Entry(settings, textvariable=self.exclusions).grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(settings, text="相对路径，逗号分隔；排除不传播删除").grid(row=1, column=1, sticky=tk.W)
        ttk.Label(settings, text="静态设备地址").grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Entry(settings, textvariable=self.static_peers).grid(row=2, column=1, sticky=tk.EW)
        ttk.Label(settings, text="IP:端口，逗号分隔，广播不可用时使用").grid(row=3, column=1, sticky=tk.W)
        ttk.Label(settings, text="历史保留天数").grid(row=4, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(settings, from_=1, to=365, textvariable=self.history_days).grid(row=4, column=1, sticky=tk.W)
        ttk.Label(settings, text="历史上限（GB）").grid(row=5, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(settings, from_=1, to=100, textvariable=self.history_gb).grid(row=5, column=1, sticky=tk.W)
        ttk.Checkbutton(settings, text="登录 Windows 时自动启动", variable=self.autostart_enabled).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=10)
        ttk.Button(settings, text="保存设置", command=self.save_settings).grid(row=7, column=0, sticky=tk.W)

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
