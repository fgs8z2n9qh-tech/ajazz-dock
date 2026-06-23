"""Start-with-Windows toggle via the HKCU Run registry key."""
from __future__ import annotations

import os
import sys
import winreg

APP_NAME = "AjazzDock"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _target_command(exe_path: str | None = None) -> str:
    # --tray: start hidden to the system tray (no window popping up at login).
    if exe_path:
        return f'"{exe_path}" --tray'
    if getattr(sys, "frozen", False):
        # Running as the packaged AjazzDock.exe.
        return f'"{sys.executable}" --tray'
    # Dev fallback: pythonw run.py (so there's no console on login).
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f'"{pyw}" "{os.path.join(root, "run.py")}" --tray'


def enable(exe_path: str | None = None) -> None:
    cmd = _target_command(exe_path)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)


def disable() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
    except FileNotFoundError:
        pass


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def toggle(exe_path: str | None = None) -> bool:
    """Flip autostart; returns the new state (True = enabled)."""
    if is_enabled():
        disable()
        return False
    enable(exe_path)
    return True
