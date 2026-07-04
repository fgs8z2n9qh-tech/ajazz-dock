"""External-monitor brightness control via DDC/CI (Windows Monitor Configuration API).

Works for monitors that expose VCP brightness over DDC/CI (most modern displays).
"""
from __future__ import annotations

import ctypes
import time
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


def read_percent(index=None):
    """Current brightness as 0..100 for monitor `index` (None = average of all), or None.
    Normalises the monitor's native min..max range. Slow (DDC) — call off the device loop."""
    phys = _enum_physical()
    try:
        if not phys:
            return None
        if index is not None and 0 <= index < len(phys):
            phys = [phys[index]]
        vals = []
        for pm in phys:
            r = _read(pm)
            if r:
                mn, cur, mx = r
                if mx > mn:
                    vals.append((cur - mn) / (mx - mn) * 100.0)
        return int(round(sum(vals) / len(vals))) if vals else None
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


class BrightnessSession:
    """A fast burst handle for an encoder spin: enumerate the target monitors + read each one's
    native min/max range ONCE, then `set_pct` issues ONLY the DDC SET (no per-set enumeration or
    read-back — those are what made a spun encoder lag). Call close() when the burst ends."""

    def __init__(self, index=None):
        self._phys = _enum_physical()
        self.targets = []                         # [handle, mn, rng, last_pct]
        for i, pm in enumerate(self._phys):
            if index is not None and i != index:
                continue
            r = _read(pm)
            if r:
                mn, cur, mx = r
                rng = (mx - mn) or 100
                self.targets.append([pm.handle, mn, rng, (cur - mn) * 100.0 / rng])

    def current_pct(self):
        if not self.targets:
            return None
        return int(round(sum(t[3] for t in self.targets) / len(self.targets)))

    def set_pct(self, pct) -> None:
        pct = max(0.0, min(100.0, float(pct)))
        for t in self.targets:
            try:
                _dxva2.SetMonitorBrightness(t[0], int(t[1] + t[2] * pct / 100))
                t[3] = pct
            except Exception:
                pass

    def close(self) -> None:
        _destroy(self._phys)
        self._phys = []
        self.targets = []


# ---- smooth transitions -----------------------------------------------------------------------
def _collect(phys, index):
    """Snapshot the target monitors' min/max/range + current % (one enumeration for the whole fade)."""
    out = []
    for i, pm in enumerate(phys):
        if index is not None and i != index:
            continue
        r = _read(pm)
        if not r:
            continue
        mn, cur, mx = r
        rng = (mx - mn) or 100
        out.append({"pm": pm, "mn": mn, "mx": mx, "rng": rng, "start": (cur - mn) * 100.0 / rng})
    return out


def _write_pct(t, pct):
    pct = max(0.0, min(100.0, pct))
    _dxva2.SetMonitorBrightness(t["pm"].handle, int(t["mn"] + t["rng"] * pct / 100.0))


def _ramp(targets, duration, should_abort=None):
    """Ease each target from its 'start' to its 'end' percent over `duration` (smoothstep)."""
    maxd = max((abs(t["end"] - t["start"]) for t in targets), default=0.0)
    if maxd < 1.0:                                   # already there -> one direct write, no fade
        for t in targets:
            _write_pct(t, t["end"])
        return
    steps = max(2, min(12, int(round(maxd / 5.0))))
    dt = duration / steps
    for s in range(1, steps + 1):
        if should_abort and should_abort():          # a newer request arrived -> bail to it
            return
        f = s / steps
        e = f * f * (3 - 2 * f)                       # smoothstep ease-in/out
        for t in targets:
            _write_pct(t, t["start"] + (t["end"] - t["start"]) * e)
        if s < steps:
            time.sleep(dt)


def fade_brightness(percent: int, index=None, duration: float = 0.28, should_abort=None) -> None:
    """Smoothly ramp to an absolute `percent` (0..100) on monitor `index` (None = all)."""
    percent = max(0.0, min(100.0, float(percent)))
    phys = _enum_physical()
    try:
        targets = _collect(phys, index)
        for t in targets:
            t["end"] = percent
        if targets:
            _ramp(targets, duration, should_abort)
    finally:
        _destroy(phys)


def fade_adjust(delta: int, index=None, duration: float = 0.24, should_abort=None) -> None:
    """Smoothly ramp by a relative `delta` percent (each monitor from its own current)."""
    phys = _enum_physical()
    try:
        targets = _collect(phys, index)
        for t in targets:
            t["end"] = max(0.0, min(100.0, t["start"] + delta))
        if targets:
            _ramp(targets, duration, should_abort)
    finally:
        _destroy(phys)
