from __future__ import annotations

import os
import shutil
import tkinter as tk
from pathlib import Path

import intranet.app as app_module
from intranet.app import IntranetApp
from intranet.config import ConfigStore
from intranet.tray import TrayController
import intranet.config as config_module
import intranet.service as service_module


def main() -> None:
    root_data = Path(".validation-data/ui-state-smoke").resolve()
    shutil.rmtree(root_data, ignore_errors=True)
    os.environ["INTRANET_DATA_DIR"] = str(root_data)
    failures = []
    current = "wifi:old"
    app_module.network_id = lambda: current
    root = tk.Tk()
    app = IntranetApp(root, store=ConfigStore(root_data), background=True)
    try:
        app_module.network_id = lambda: "wifi:new"
        app._poll()
        if "wifi:new" not in app.network.get():
            failures.append("network display did not refresh after network_id changed")
        if not hasattr(app, "pairing_state"):
            failures.append("pairing page has no persistent pairing state")
        else:
            app.store.peer_certificate.write_text("test certificate", encoding="utf-8")
            app.config.peer_address = "127.0.0.1:47630"
            app.refresh_pairing_state()
            if "127.0.0.1:47630" not in app.pairing_state.get():
                failures.append("paired endpoint not displayed")
            app_module.messagebox.askyesno = lambda *args, **kwargs: True
            app.disconnect_pairing()
            if app.store.peer_certificate.exists() or app.config.setup_complete:
                failures.append("disconnect did not clear pairing")
        tray = TrayController(lambda: None, lambda: None, lambda: None, lambda: None)
        calls = []
        tray.icon.notify = lambda text, title: calls.append(text)
        tray.notify("first")
        tray.notify("duplicate")
        if len(calls) != 1:
            failures.append(f"notification rate limit missing: {len(calls)} immediate notifications")
        creation_flags = []
        class Result:
            stdout = ""
        def hidden_check(*args, **kwargs):
            creation_flags.append(kwargs.get("creationflags", 0))
            return Result()
        config_module.subprocess.run = hidden_check
        config_module.network_id()
        config_module.ipv4_summary()
        if any(flag != config_module.subprocess.CREATE_NO_WINDOW for flag in creation_flags):
            failures.append("network subprocesses can create visible console windows")
        from types import SimpleNamespace
        checks = []
        service_module.network_id = lambda: checks.append(1) or "wifi:cached"
        service = service_module.IntranetService.__new__(service_module.IntranetService)
        service.config = SimpleNamespace(trusted_networks=["wifi:cached"])
        service._last_notice = 0
        service.last_network_check = 0
        service.current_network = "offline"
        service._allowed()
        service._allowed()
        if len(checks) != 1:
            failures.append(f"network checked {len(checks)} times without caching")
    finally:
        app.shutdown()
        root.update()
        shutil.rmtree(root_data, ignore_errors=True)
    if failures:
        for failure in failures:
            print("FAIL:", failure)
        raise SystemExit(1)
    print("PASS: live network, pairing state and notification rate limiting")


if __name__ == "__main__":
    main()
