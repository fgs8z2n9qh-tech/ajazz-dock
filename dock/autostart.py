"""Start-with-Windows toggle.

The app runs elevated (admin) so it can read CPU temperature, and Windows will NOT auto-elevate
an HKCU Run-key entry at logon — so autostart uses a Scheduled Task with 'onlogon /rl highest'
(runs elevated, no UAC prompt at login). Creating/removing the task needs admin, which the
running app has.
"""
from __future__ import annotations

import os
import subprocess
import sys
import winreg

APP_NAME = "Hexpad"          # Run-key value name / scheduled-task name (display-level id)
TASK_NAME = "Hexpad"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_NOWIN = 0x08000000          # CREATE_NO_WINDOW (no console flash)


def _tray_command(exe_path: str | None = None) -> str:
    if exe_path:
        return f'"{exe_path}" --tray'
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    pyw = pyw if os.path.exists(pyw) else sys.executable
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f'"{pyw}" "{os.path.join(root, "run.py")}" --tray'


def _schtasks(*args: str) -> bool:
    try:
        r = subprocess.run(["schtasks", *args], capture_output=True, text=True, creationflags=_NOWIN)
        return r.returncode == 0
    except Exception:
        return False


def _remove_run_key() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
    except FileNotFoundError:
        pass


def enable(exe_path: str | None = None) -> None:
    _remove_run_key()                                   # retire any legacy Run-key autostart
    _schtasks("/create", "/tn", TASK_NAME, "/tr", _tray_command(exe_path),
              "/sc", "onlogon", "/rl", "highest", "/f")


def disable() -> None:
    _remove_run_key()
    _schtasks("/delete", "/tn", TASK_NAME, "/f")


def is_enabled() -> bool:
    return _schtasks("/query", "/tn", TASK_NAME)


def toggle(exe_path: str | None = None) -> bool:
    """Flip autostart; returns the new state (True = enabled)."""
    if is_enabled():
        disable()
        return False
    enable(exe_path)
    return True


def _run_key_present() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def migrate(exe_path: str | None = None) -> None:
    """Carry an old Run-key autostart over to the elevated task (the Run-key one can't elevate)."""
    if _run_key_present() and not is_enabled():
        enable(exe_path)
    elif _run_key_present():
        _remove_run_key()
