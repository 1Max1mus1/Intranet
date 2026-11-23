from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .config import Config, load_config, save_config
from .service import SyncService


class IntranetApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = load_config()
        self.service: SyncService | None = None
        self.root.title("Intranet - 局域网双向同步")
        self.root.geometry("780x650")
        self.root.minsize(680, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.device_name = tk.StringVar(value=self.config.device_name)
        self.folder = tk.StringVar(value=self.config.folder)
        self.sync_key = tk.StringVar(value=self.config.sync_key)
        self.manual_peers = tk.StringVar(value=", ".join(self.config.manual_peers))
        self.status = tk.StringVar(value="未启动")
        self._build()
        self.root.after(500, self._refresh)

    def _build(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)
        settings = ttk.LabelFrame(container, text="同步设置", padding=12)
        settings.pack(fill=tk.X)
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="设备名称").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(settings, textvariable=self.device_name).grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=(10, 0), pady=5)
        ttk.Label(settings, text="同步文件夹").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(settings, textvariable=self.folder).grid(row=1, column=1, sticky=tk.EW, padx=(10, 8), pady=5)
        ttk.Button(settings, text="浏览…", command=self._choose_folder).grid(row=1, column=2, pady=5)
        ttk.Label(settings, text="同步密钥").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(settings, textvariable=self.sync_key, show="●").grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=(10, 0), pady=5)
        ttk.Label(settings, text="手动设备").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(settings, textvariable=self.manual_peers).grid(row=3, column=1, columnspan=2, sticky=tk.EW, padx=(10, 0), pady=5)
        ttk.Label(settings, text="可选，格式 IP:端口，多个地址用逗号分隔", foreground="#666").grid(row=4, column=1, columnspan=2, sticky=tk.W, padx=(10, 0))

        actions = ttk.Frame(container)
        actions.pack(fill=tk.X, pady=12)
        self.start_button = ttk.Button(actions, text="启动同步", command=self.start)
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = ttk.Button(actions, text="停止", command=self.stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=8)
        self.sync_button = ttk.Button(actions, text="立即同步", command=self.sync_now, state=tk.DISABLED)
        self.sync_button.pack(side=tk.LEFT)
        ttk.Button(actions, text="打开文件夹", command=self._open_folder).pack(side=tk.RIGHT)
        ttk.Label(container, textvariable=self.status, foreground="#175a9c").pack(anchor=tk.W, pady=(0, 8))

        peers_frame = ttk.LabelFrame(container, text="已发现设备", padding=8)
        peers_frame.pack(fill=tk.BOTH, expand=True)
        self.peers = ttk.Treeview(peers_frame, columns=("name", "address"), show="headings", height=5)
        self.peers.heading("name", text="设备")
        self.peers.heading("address", text="地址")
        self.peers.column("name", width=240)
        self.peers.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(container, text="运行日志", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.log = scrolledtext.ScrolledText(log_frame, height=12, state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.folder.get() or str(Path.home()))
        if selected:
            self.folder.set(selected)

    def _open_folder(self) -> None:
        folder = self.folder.get().strip()
        if folder and Path(folder).is_dir():
            os.startfile(folder)

    def _current_config(self) -> Config:
        tcp_port = self.config.tcp_port
        udp_port = self.config.udp_port
        peers = [value.strip() for value in self.manual_peers.get().replace("，", ",").split(",") if value.strip()]
        for peer in peers:
            SyncService.parse_peer(peer)
        return Config(
            device_id=self.config.device_id,
            device_name=self.device_name.get().strip() or "Windows 设备",
            folder=self.folder.get().strip(),
            sync_key=self.sync_key.get(),
            tcp_port=tcp_port,
            udp_port=udp_port,
            manual_peers=peers,
        )

    def start(self) -> None:
        try:
            self.config = self._current_config()
            if not self.config.folder:
                raise ValueError("请选择同步文件夹")
            if not self.config.sync_key:
                raise ValueError("请设置同步密钥；两台电脑必须使用相同密钥")
            self.service = SyncService(self.config)
            self.service.start()
            save_config(self.config)
        except (OSError, ValueError) as exc:
            self.service = None
            messagebox.showerror("无法启动", str(exc))
            return
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.sync_button.configure(state=tk.NORMAL)
        self.status.set("正在发现并同步设备…")

    def stop(self) -> None:
        if self.service:
            self.service.stop()
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.sync_button.configure(state=tk.DISABLED)
        self.status.set("已停止")

    def sync_now(self) -> None:
        if self.service:
            self.service.sync_now()

    def _refresh(self) -> None:
        if self.service:
            service = self.service
            peers = service.known_peers()
            self.peers.delete(*self.peers.get_children())
            for peer in peers:
                self.peers.insert("", tk.END, values=(peer.name, f"{peer.host}:{peer.port}"))
            if service.running:
                status = f"运行中 · {len(peers)} 台设备"
                if service.last_sync:
                    status += f" · 上次同步 {service.last_sync}"
                if service.last_error:
                    status += f" · {service.last_error}"
                self.status.set(status)
            self.log.configure(state=tk.NORMAL)
            self.log.delete("1.0", tk.END)
            self.log.insert(tk.END, "\n".join(service.messages))
            self.log.configure(state=tk.DISABLED)
            self.log.see(tk.END)
        if self.root.winfo_exists():
            self.root.after(500, self._refresh)

    def close(self) -> None:
        if self.service:
            self.service.stop()
        self.root.destroy()


def run() -> None:
    root = tk.Tk()
    IntranetApp(root)
    root.mainloop()
