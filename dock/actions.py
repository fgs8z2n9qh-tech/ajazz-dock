"""Action engine: execute a binding's action (launch/hotkey/media/volume/mic/nav)."""
from __future__ import annotations

import os
import shlex
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

import keyboard  # SendInput-based; sending keys does not require admin

# ---- name maps -------------------------------------------------------------
_HOTKEY_ALIASES = {
    "win": "windows", "cmd": "windows", "super": "windows", "meta": "windows",
    "opt": "alt", "option": "alt", "return": "enter", "esc": "escape",
    "del": "delete", "ins": "insert", "pgup": "page up", "pgdn": "page down",
}
_MEDIA_KEYS = {
    "play_pause": "play/pause media", "play": "play/pause media",
    "pause": "play/pause media", "next": "next track", "prev": "previous track",
    "previous": "previous track", "stop": "stop media",
}
_VOLUME_KEYS = {"up": "volume up", "down": "volume down", "mute": "volume mute"}

# "Quick actions": common Windows tasks as one-press presets. Most are really just a
# standard system shortcut; the rest (recycle bin, clipboard, settings) need a real call.
_QUICK_HOTKEYS = {
    "show_desktop": "windows+d", "minimize_all": "windows+m",
    "task_manager": "ctrl+shift+esc", "explorer": "windows+e",
    "run_dialog": "windows+r", "snip": "windows+shift+s",
    "clipboard_history": "windows+v", "emoji_panel": "windows+.",
    "project": "windows+p",
}


def _normalize_hotkey(spec: str) -> str:
    parts = [p.strip().lower() for p in spec.replace(" ", "").split("+") if p.strip()]
    return "+".join(_HOTKEY_ALIASES.get(p, p) for p in parts)


# ---- layout-independent scan-code sending ----------------------------------
# Some apps (e.g. Substance 3D Painter) bind shortcuts to PHYSICAL key positions. On a
# non-US layout (Hungarian QWERTZ: '[' needs AltGr, digits need Shift) `keyboard.send`
# sends the character, which never matches. Sending the raw Set-1 scan code presses the
# physical key directly, regardless of layout.
import ctypes
from ctypes import wintypes

_SCAN = {
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07, "7": 0x08,
    "8": 0x09, "9": 0x0A, "0": 0x0B, "minus": 0x0C, "equals": 0x0D, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14, "y": 0x15, "u": 0x16,
    "i": 0x17, "o": 0x18, "p": 0x19, "[": 0x1A, "]": 0x1B, "enter": 0x1C,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22, "h": 0x23, "j": 0x24,
    "k": 0x25, "l": 0x26, "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F, "b": 0x30,
    "n": 0x31, "m": 0x32, "space": 0x39, "esc": 0x01, "escape": 0x01,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F, "f6": 0x40,
    "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44, "f11": 0x57, "f12": 0x58,
}
_SCAN_MODS = {"ctrl": 0x1D, "control": 0x1D, "alt": 0x38, "shift": 0x2A,
              "win": 0x5B, "windows": 0x5B}
_SCAN_EXT = {0x5B}


class _KBDIN(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KBDIN)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _scan_event(code: int, down: bool) -> None:
    flags = 0x0008                                   # KEYEVENTF_SCANCODE
    if code in _SCAN_EXT:
        flags |= 0x0001                              # KEYEVENTF_EXTENDEDKEY
    if not down:
        flags |= 0x0002                              # KEYEVENTF_KEYUP
    inp = _INPUT(type=1)                              # INPUT_KEYBOARD
    inp.ki = _KBDIN(0, code, flags, 0, None)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def send_scancode_combo(spec: str) -> bool:
    """Press a hotkey by physical scan code. False (no-op) if any token is unmapped."""
    parts = [_HOTKEY_ALIASES.get(p.strip().lower(), p.strip().lower())
             for p in spec.split("+") if p.strip()]
    mods = [_SCAN_MODS[p] for p in parts if p in _SCAN_MODS]
    keys = []
    for p in parts:
        if p in _SCAN_MODS:
            continue
        sc = _SCAN.get(p)
        if sc is None:
            return False
        keys.append(sc)
    if not keys:
        return False
    for sc in mods:
        _scan_event(sc, True)
    for sc in keys:
        _scan_event(sc, True)
    time.sleep(0.012)
    for sc in reversed(keys):
        _scan_event(sc, False)
    for sc in reversed(mods):
        _scan_event(sc, False)
    return True


# ---- microphone (Core Audio via pycaw) -------------------------------------
class _Mic:
    """Lazily-bound default-communications capture endpoint volume control."""

    _EDATAFLOW_CAPTURE = 1
    _EROLE_COMMUNICATIONS = 2

    def __init__(self) -> None:
        self._endpoint = None

    def _ensure(self):
        if self._endpoint is not None:
            return self._endpoint
        import comtypes
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioEndpointVolume
        try:
            comtypes.CoInitialize()
        except OSError:
            pass
        dev = None
        try:
            from pycaw.pycaw import AudioUtilities
            dev = AudioUtilities.GetMicrophone()
        except Exception:
            dev = None
        if dev is None:
            # Manual enumerator fallback.
            from comtypes import CoCreateInstance
            from pycaw.constants import CLSID_MMDeviceEnumerator
            from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
            enum = CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL)
            dev = enum.GetDefaultAudioEndpoint(self._EDATAFLOW_CAPTURE, self._EROLE_COMMUNICATIONS)
        iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        self._endpoint = cast(iface, POINTER(IAudioEndpointVolume))
        return self._endpoint

    def set(self, muted: bool) -> None:
        self._ensure().SetMute(1 if muted else 0, None)

    def toggle(self) -> bool:
        ep = self._ensure()
        new = 0 if ep.GetMute() else 1
        ep.SetMute(new, None)
        return bool(new)

    def is_muted(self) -> Optional[bool]:
        try:
            return bool(self._ensure().GetMute())
        except Exception:
            return None


class _MonitorDimmer:
    """Coalesces monitor-brightness changes so a fast-spun encoder stays smooth.

    DDC/CI is slow (~tens of ms per monitor), so instead of one slow call per detent we
    accumulate the deltas and apply the batched total in a background worker.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: Dict[Any, int] = {}     # key -> accumulated delta
        self._target: Dict[Any, int] = {}      # key -> set-target percent
        self._wake = threading.Event()
        self._thread = None

    @staticmethod
    def _key(index):
        return "all" if index is None else int(index)

    def bump(self, delta, index) -> None:
        k = self._key(index)
        with self._lock:
            self._pending[k] = self._pending.get(k, 0) + delta
            self._target.pop(k, None)
        self._kick()

    def set(self, value, index) -> None:
        k = self._key(index)
        with self._lock:
            self._target[k] = value
            self._pending.pop(k, None)
        self._kick()

    def _kick(self) -> None:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
        self._wake.set()

    def _run(self) -> None:
        from . import monitors
        while True:
            if not self._wake.wait(timeout=3.0):
                return
            self._wake.clear()
            with self._lock:
                pend, self._pending = self._pending, {}
                targ, self._target = self._target, {}
            for k, delta in pend.items():
                if delta:
                    try:
                        monitors.adjust_brightness(delta, None if k == "all" else k)
                    except Exception:
                        pass
            for k, val in targ.items():
                try:
                    monitors.set_brightness(val, None if k == "all" else k)
                except Exception:
                    pass


class ActionEngine:
    def __init__(self, controller: Optional[Any] = None) -> None:
        self.controller = controller
        self.mic = _Mic()
        self._mon_dimmer = None

    def execute(self, action: Optional[Dict[str, Any]]) -> None:
        if not action:
            return
        try:
            self._dispatch(action)
        except Exception as e:  # never let a bad binding kill the event loop
            print(f"[action] error running {action!r}: {e}")

    # ------------------------------------------------------------------
    def _dispatch(self, action: Dict[str, Any]) -> None:
        t = (action.get("type") or "").lower()
        if t in ("open", "launch", "run"):
            self._open(action)
        elif t == "hotkey":
            keys = action.get("keys", "")
            if "mouse:" in keys:
                self._send_mouse(keys)
            else:
                keyboard.send(_normalize_hotkey(keys))
        elif t == "text":
            keyboard.write(action.get("text", ""), delay=0.005)
        elif t == "media":
            key = _MEDIA_KEYS.get((action.get("media") or "").lower())
            if key:
                keyboard.send(key)
        elif t == "volume":
            key = _VOLUME_KEYS.get((action.get("volume") or "").lower())
            if key:
                repeat = max(1, int(action.get("step", 1)))
                for _ in range(repeat):
                    keyboard.send(key)
        elif t == "mic":
            mode = (action.get("mic") or "toggle").lower()
            if mode == "toggle":
                self.mic.toggle()
            else:
                self.mic.set(mode == "mute")
        elif t == "page":
            self._page(action)
        elif t == "folder":
            self._call("enter_folder", action.get("folder"))
        elif t == "profile":
            self._call("set_profile", action.get("name"))
        elif t == "brightness":
            mode = (action.get("mode") or "set").lower()
            step = max(1, int(action.get("step", 10)))
            if mode == "up":
                self._call("adjust_brightness", step)
            elif mode == "down":
                self._call("adjust_brightness", -step)
            elif "delta" in action:
                self._call("adjust_brightness", int(action["delta"]))
            else:
                self._call("set_brightness", int(action.get("value", 70)))
        elif t == "system":
            self._system((action.get("system") or "lock").lower())
        elif t == "monitor":
            self._monitor(action)
        elif t == "sound":
            from . import sound
            sound.play(action.get("file", ""), action.get("device") or None,
                       bool(action.get("monitor", False)), float(action.get("gain", 1.0) or 1.0))
        elif t == "discord":
            keys = action.get("keys")
            if keys:
                keyboard.send(_normalize_hotkey(keys))   # mirror this key in Discord > Keybinds
        elif t == "substance":
            keys = action.get("keys", "")
            if "mouse:" in keys:
                self._send_mouse(keys)
            elif keys:
                # Send by physical scan code so Painter shortcuts ([ ] brush size, digits, …)
                # fire on any keyboard layout; fall back to character send if unmapped.
                if not send_scancode_combo(keys):
                    keyboard.send(_normalize_hotkey(keys))
        elif t == "quick":
            self._quick(action.get("op"))
        elif t == "macro":
            for step in action.get("steps", []):
                if (step.get("type") or "").lower() == "delay":
                    time.sleep(max(0, int(step.get("ms", 0))) / 1000.0)
                else:
                    self._dispatch(step)
        elif t in ("none", "", None):
            pass
        else:
            print(f"[action] unknown action type: {t!r}")

    def _quick(self, op: Optional[str]) -> None:
        op = (op or "").lower()
        if op == "recycle_empty":
            self._empty_recycle_bin()
        elif op == "recycle_open":
            subprocess.Popen(["explorer.exe", "shell:RecycleBinFolder"])
        elif op == "clipboard_clear":
            self._clear_clipboard()
        elif op == "settings":
            os.startfile("ms-settings:")
        elif op == "lock":
            self._system("lock")
        elif op in _QUICK_HOTKEYS:
            keyboard.send(_QUICK_HOTKEYS[op])
        else:
            print(f"[action] unknown quick action: {op!r}")

    @staticmethod
    def _empty_recycle_bin() -> None:
        # SHEmptyRecycleBin: no confirmation dialog + no progress UI, but keep the system
        # sound as audible feedback. Returns S_FALSE when already empty (ignored).
        SHERB_NOCONFIRMATION, SHERB_NOPROGRESSUI = 0x01, 0x02
        ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None, SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI)

    @staticmethod
    def _clear_clipboard() -> None:
        u = ctypes.windll.user32
        if u.OpenClipboard(0):
            try:
                u.EmptyClipboard()
            finally:
                u.CloseClipboard()

    def _system(self, what: str) -> None:
        import ctypes
        if what == "lock":
            ctypes.windll.user32.LockWorkStation()           # the proper way to do "Win+L"
        elif what == "sleep":
            ctypes.windll.powrprof.SetSuspendState(0, 0, 0)
        elif what in ("monitor_off", "screen_off"):
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)  # WM_SYSCOMMAND monitor off
        elif what == "screensaver":
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF140, 0)  # SC_SCREENSAVE
        else:
            print(f"[action] unknown system command: {what!r}")

    def _send_mouse(self, spec: str) -> None:
        """Send a mouse action (optionally with held modifiers), e.g. 'ctrl+mouse:wheel_up'."""
        import mouse
        parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
        mtoken = next((p for p in parts if p.startswith("mouse:")), "")
        mods = [_HOTKEY_ALIASES.get(p, p) for p in parts if not p.startswith("mouse:")]
        held = []
        for m in mods:
            try:
                keyboard.press(m)
                held.append(m)
            except Exception:
                pass
        try:
            act = mtoken.split(":", 1)[1] if ":" in mtoken else ""
            if act == "left":
                mouse.click("left")
            elif act == "right":
                mouse.click("right")
            elif act == "middle":
                mouse.click("middle")
            elif act == "double":
                mouse.double_click("left")
            elif act == "back":
                mouse.click("x")
            elif act == "forward":
                mouse.click("x2")
            elif act == "wheel_up":
                mouse.wheel(1)
            elif act == "wheel_down":
                mouse.wheel(-1)
        finally:
            for m in reversed(held):
                try:
                    keyboard.release(m)
                except Exception:
                    pass

    def _monitor(self, action: Dict[str, Any]) -> None:
        mode = (action.get("monitor") or "up").lower()
        idx = action.get("index")
        if idx in (None, "", "all", -1, "-1"):
            idx = None
        else:
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                idx = None
        step = max(1, int(action.get("step", 5)))
        if self._mon_dimmer is None:
            self._mon_dimmer = _MonitorDimmer()
        if mode == "set":
            self._mon_dimmer.set(int(action.get("value", 50)), idx)
        elif mode == "down":
            self._mon_dimmer.bump(-step, idx)
        else:
            self._mon_dimmer.bump(step, idx)

    # ------------------------------------------------------------------
    def _open(self, action: Dict[str, Any]) -> None:
        target = action.get("target") or action.get("path") or ""
        if not target:
            return
        args = action.get("args")
        if args:
            arglist: List[str] = args if isinstance(args, list) else shlex.split(args)
            subprocess.Popen([target, *arglist], shell=False)
        else:
            os.startfile(target)  # handles exe, file, folder, and URLs on Windows

    def _page(self, action: Dict[str, Any]) -> None:
        where = (action.get("page") or "next").lower()
        if where == "next":
            self._call("next_page")
        elif where == "prev":
            self._call("prev_page")
        elif where in ("goto", "set"):
            self._call("goto_page", int(action.get("target", 0)))

    def _call(self, method: str, *args) -> None:
        if self.controller and hasattr(self.controller, method):
            getattr(self.controller, method)(*args)
