"""External-monitor brightness control via DDC/CI (Windows Monitor Configuration API).

Works for monitors that expose VCP brightness over DDC/CI (most modern displays).
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes, byref, POINTER, Structure

_dxva2 = ctypes.windll.dxva2
_user32 = ctypes.windll.user32


class _PhysMon(Structure):
    _fields_ = [("handle", wintypes.HANDLE), ("description", wintypes.WCHAR * 128)]


_MONENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                  POINTER(wintypes.RECT), wintypes.LPARAM)


def _enum_physical():
    hmons = []

    def _cb(hmon, hdc, lprc, lparam):
        hmons.append(hmon)
        return True

    _user32.EnumDisplayMonitors(None, None, _MONENUMPROC(_cb), 0)
    phys = []
    for h in hmons:
        n = wintypes.DWORD()
        if _dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(h, byref(n)) and n.value:
            arr = (_PhysMon * n.value)()
            if _dxva2.GetPhysicalMonitorsFromHMONITOR(h, n.value, arr):
                phys.extend(arr)
    return phys


def _destroy(phys):
    for pm in phys:
        try:
            _dxva2.DestroyPhysicalMonitor(pm.handle)
        except Exception:
            pass


def _read(pm):
    mn, cur, mx = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    if _dxva2.GetMonitorBrightness(pm.handle, byref(mn), byref(cur), byref(mx)):
        return mn.value, cur.value, mx.value
    return None


def read_all():
    """Return [(index, description, min, cur, max) | (index, description, None)]."""
    phys = _enum_physical()
    try:
        out = []
        for i, pm in enumerate(phys):
            r = _read(pm)
            out.append((i, pm.description, *(r if r else (None,))))
        return out
    finally:
        _destroy(phys)


def count():
    phys = _enum_physical()
    try:
        return len(phys)
    finally:
        _destroy(phys)


def set_brightness(percent: int, index=None) -> None:
    """Set brightness 0..100 on monitor `index` (None = all DDC/CI monitors)."""
    percent = max(0, min(100, int(percent)))
    phys = _enum_physical()
    try:
        for i, pm in enumerate(phys):
            if index is not None and i != index:
                continue
            r = _read(pm)
            if not r:
                continue
            mn, _cur, mx = r
            _dxva2.SetMonitorBrightness(pm.handle, int(mn + (mx - mn) * percent / 100))
    finally:
        _destroy(phys)


def adjust_brightness(delta: int, index=None) -> None:
    """Nudge brightness by `delta` percent on monitor `index` (None = all)."""
    phys = _enum_physical()
    try:
        for i, pm in enumerate(phys):
            if index is not None and i != index:
                continue
            r = _read(pm)
            if not r:
                continue
            mn, cur, mx = r
            rng = (mx - mn) or 100
            cur_pct = (cur - mn) * 100.0 / rng
            _dxva2.SetMonitorBrightness(pm.handle, int(mn + rng * max(0, min(100, cur_pct + delta)) / 100))
    finally:
        _destroy(phys)
