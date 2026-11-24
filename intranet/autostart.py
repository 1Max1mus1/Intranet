from __future__ import annotations

import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Intranet"


def command() -> str:
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return f'"{executable}" --background'
    script = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{executable}" "{script}" --background'


def enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return bool(winreg.QueryValueEx(key, VALUE_NAME)[0])
    except FileNotFoundError:
        return False


def set_enabled(value: bool) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if value:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
