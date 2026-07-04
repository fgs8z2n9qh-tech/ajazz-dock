"""App-aware auto-switching: watch the foreground Windows app and, when it matches a rule,
ask the controller to switch profile/page.

Runs as a lightweight daemon thread. It only *requests* a switch (sets a controller flag);
the actual switch happens on the device loop thread, which also applies suppression (don't
yank the dock mid-folder, mid-animation, or right after the user navigated by hand).
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Optional

try:
    import psutil
except Exception:                                  # psutil is optional
    psutil = None

_user32 = ctypes.windll.user32


def foreground_exe() -> Optional[str]:
    """Lower-cased exe name of the foreground window's process (e.g. 'obs64.exe'), or None."""
    if psutil is None:
        return None
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    try:
        return (psutil.Process(pid.value).name() or "").lower()
    except Exception:                              # process gone / access denied
        return None


def foreground_pid() -> Optional[int]:
    """PID of the foreground window's process, or None."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or None


def proc_name(pid: Optional[int]) -> str:
    if psutil is None or not pid:
        return ""
    try:
        return psutil.Process(pid).name() or ""
    except Exception:
        return ""


def running_app_names() -> list:
    """Distinct .exe names currently running (for the rule picker's dropdown)."""
    if psutil is None:
        return []
    names = set()
    for p in psutil.process_iter(["name"]):
        try:
            n = p.info.get("name") or ""
            if n.lower().endswith(".exe"):
                names.add(n)
        except Exception:
            pass
    return sorted(names, key=str.lower)


class ForegroundPoller:
    def __init__(self, controller, interval: float = 0.8) -> None:
        self.controller = controller
        self.interval = interval
        self._last_exe: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running or psutil is None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="app-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        self._last_exe = foreground_exe()          # seed: don't fire on the very first tick
        while self._running:
            time.sleep(self.interval)
            try:
                self._tick()
            except Exception:
                pass

    def _tick(self) -> None:
        data = self.controller.config.data
        if not data.get("auto_switch", False):
            self._last_exe = None                  # re-evaluate the current app when re-enabled
            return
        exe = foreground_exe()
        if not exe or exe == self._last_exe:
            return
        self._last_exe = exe
        rule = self._match(exe, data)
        if rule:
            self.controller.request_app_switch(rule.get("profile"), rule.get("page"))

    @staticmethod
    def _match(exe: str, data) -> Optional[dict]:
        for r in list(data.get("app_rules", [])):
            if (r.get("app") or "").lower() == exe:
                return r
        return None
