"""Configuration model for the AKP03 controller.

The config is plain JSON so the UI can read/write it directly. A *binding* is keyed
by the device input id (matching dock.device.Event.input_id):

    LCD keys  : "key1".."key6"   (these also carry a visual face: label/icon/color)
    buttons   : "btn7".."btn9"
    encoders  : "enc0".."enc2"    (push)  and  "enc0+"/"enc0-" .. (twist cw/ccw)

A binding looks like:
    { "label": "Chrome", "icon": "C:/..png" or "🎵", "color": "#1e6fd0",
      "text_color": "#ffffff", "action": { "type": "...", ... } }

Faces (label/icon/color) only render on key1..key6; other ids use just "action".

Action types (see dock.actions): open, hotkey, text, media, volume, mic, page,
profile, brightness, macro.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import time
from typing import Any, Dict, List, Optional

APP_NAME = "AjazzDock"
LCD_KEYS = ["key1", "key2", "key3", "key4", "key5", "key6"]
BUTTONS = ["btn7", "btn8", "btn9"]
ENCODERS = ["enc0", "enc1", "enc2"]


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    # Allow override for dev/testing.
    return os.environ.get("AJAZZDOCK_CONFIG") or os.path.join(config_dir(), "config.json")


def backups_dir() -> str:
    d = os.path.join(config_dir(), "backups")
    os.makedirs(d, exist_ok=True)
    return d


def default_config() -> Dict[str, Any]:
    """A useful first-run config that demonstrates every feature, lean by default."""
    return {
        "version": 1,
        "brightness": 70,
        "show_labels": True,
        "press_fx": True,
        "press_anim": "bounce",
        "page_fx": True,
        # Per-key image geometry (the firmware anchors images top-right with a fixed margin;
        # these are tuned in the in-app display calibrator). w/h = tile px per key (the
        # physical cell is taller than wide, so width and height are independent).
        "display": {"w": 88, "h": 88, "dx": 0, "dy": 0},
        "active_profile": "Default",
        "profiles": [
            {
                "name": "Default",
                # Encoders + round buttons are GLOBAL (same on every page of this profile).
                "globals": {
                    "enc0+": {"action": {"type": "volume", "volume": "up"}},
                    "enc0-": {"action": {"type": "volume", "volume": "down"}},
                    "enc0": {"action": {"type": "volume", "volume": "mute"}},
                    "btn7": {"action": {"type": "page", "page": "prev"}},
                    "btn8": {"action": {"type": "page", "page": "next"}},
                    "btn9": {"action": {"type": "mic", "mic": "toggle"}},
                },
                "pages": [
                    {
                        "name": "Home",
                        "items": {
                            "key1": {"label": "Notepad", "icon": "📝", "color": "#2d6cdf",
                                     "action": {"type": "open", "target": "notepad.exe"}},
                            "key2": {"label": "Browser", "icon": "🌐", "color": "#1aa179",
                                     "action": {"type": "open", "target": "https://www.google.com"}},
                            "key3": {"label": "Files", "icon": "📁", "color": "#c8881f",
                                     "action": {"type": "hotkey", "keys": "win+e"}},
                            "key4": {"label": "Play", "icon": "⏯️", "color": "#7a3cc4",
                                     "action": {"type": "media", "media": "play_pause"}},
                            "key5": {"label": "Mic", "icon": "🎙️", "color": "#c0392b",
                                     "action": {"type": "mic", "mic": "toggle"}},
                            "key6": {"label": "Page →", "icon": "➡️", "color": "#444b55",
                                     "action": {"type": "page", "page": "next"}},
                        },
                    },
                    {
                        "name": "Media",
                        "items": {
                            "key1": {"label": "Prev", "icon": "⏮️", "color": "#34495e",
                                     "action": {"type": "media", "media": "prev"}},
                            "key2": {"label": "Play", "icon": "⏯️", "color": "#7a3cc4",
                                     "action": {"type": "media", "media": "play_pause"}},
                            "key3": {"label": "Next", "icon": "⏭️", "color": "#34495e",
                                     "action": {"type": "media", "media": "next"}},
                            "key4": {"label": "Vol -", "icon": "🔉", "color": "#27632a",
                                     "action": {"type": "volume", "volume": "down"}},
                            "key5": {"label": "Vol +", "icon": "🔊", "color": "#1aa179",
                                     "action": {"type": "volume", "volume": "up"}},
                            "key6": {"label": "Home", "icon": "🏠", "color": "#444b55",
                                     "action": {"type": "page", "page": "prev"}},
                        },
                    },
                ],
            }
        ],
    }


class Config:
    """Thin wrapper around the config dict with convenient accessors."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    # ---- persistence -------------------------------------------------------
    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        path = path or config_path()
        if os.path.exists(path):
            try:
                # utf-8-sig tolerates a leading BOM (some editors / PowerShell add one)
                # which plain json.load would choke on.
                with open(path, "r", encoding="utf-8-sig") as f:
                    return cls(_migrate(json.load(f)))
            except (json.JSONDecodeError, OSError, ValueError):
                # NEVER silently overwrite a config we can't parse — set it aside so the
                # user's bindings can be recovered instead of being clobbered by defaults.
                for suffix in (".corrupt", ".corrupt1", ".corrupt2"):
                    if not os.path.exists(path + suffix):
                        try:
                            os.replace(path, path + suffix)
                        except OSError:
                            pass
                        break
        cfg = cls(default_config())
        cfg.save(path)
        return cfg

    def save(self, path: Optional[str] = None) -> None:
        path = path or config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Keep a rolling backup of the last good config before overwriting it.
        try:
            if os.path.exists(path):
                shutil.copyfile(path, path + ".bak")
        except OSError:
            pass
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        # Throttled timestamped history so the config is recoverable over time.
        try:
            self._write_history(path)
        except OSError:
            pass

    @staticmethod
    def _write_history(path: str) -> None:
        d = backups_dir()
        snaps = sorted(f for f in os.listdir(d)
                       if f.startswith("config-") and f.endswith(".json"))
        if snaps:
            newest = os.path.getmtime(os.path.join(d, snaps[-1]))
            if time.time() - newest < 300:          # at most one snapshot / 5 min
                return
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copyfile(path, os.path.join(d, f"config-{stamp}.json"))
        snaps = sorted(f for f in os.listdir(d)
                       if f.startswith("config-") and f.endswith(".json"))
        for old in snaps[:-40]:                      # keep the most recent 40
            try:
                os.remove(os.path.join(d, old))
            except OSError:
                pass

    # ---- accessors ---------------------------------------------------------
    @property
    def brightness(self) -> int:
        return int(self.data.get("brightness", 70))

    @brightness.setter
    def brightness(self, v: int) -> None:
        self.data["brightness"] = max(0, min(100, int(v)))

    def display(self) -> Dict[str, Any]:
        """Per-key image geometry calibration: {w, h, dx, dy} (old configs may use `size`)."""
        d = self.data.setdefault("display", {})
        base = int(d.get("size", 88))            # back-compat: old single-axis "size"
        d.setdefault("w", base)
        d.setdefault("h", base)
        d.setdefault("dx", 0)
        d.setdefault("dy", 0)
        return d

    @property
    def profiles(self) -> List[Dict[str, Any]]:
        return self.data.setdefault("profiles", [])

    def profile_names(self) -> List[str]:
        return [p.get("name", f"Profile {i}") for i, p in enumerate(self.profiles)]

    def active_profile(self) -> Dict[str, Any]:
        name = self.data.get("active_profile")
        for p in self.profiles:
            if p.get("name") == name:
                return p
        # fall back to first
        if self.profiles:
            self.data["active_profile"] = self.profiles[0].get("name")
            return self.profiles[0]
        # empty -> seed a default
        self.data.update(default_config())
        return self.profiles[0]

    def set_active_profile(self, name: str) -> bool:
        if name in self.profile_names():
            self.data["active_profile"] = name
            return True
        return False

    def pages(self, profile: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        profile = profile or self.active_profile()
        return profile.setdefault("pages", [{"name": "Home", "items": {}}])

    def page(self, index: int, profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pages = self.pages(profile)
        if not pages:
            pages.append({"name": "Home", "items": {}})
        return pages[index % len(pages)]

    def globals_of(self, profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Profile-wide bindings (encoders + round buttons), shared across all pages."""
        profile = profile or self.active_profile()
        return profile.setdefault("globals", {})

    def folders_of(self, profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Sub-pages opened by a key's 'folder' action: {folder_id: {name, items}}."""
        profile = profile or self.active_profile()
        return profile.setdefault("folders", {})

    def folder(self, fid: str, profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.folders_of(profile).setdefault(fid, {"name": "Folder", "items": {}})


def _migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Forward-compatible defaults for older/partial config files."""
    data.setdefault("version", 1)
    data.setdefault("brightness", 70)
    data.setdefault("show_labels", True)
    data.setdefault("press_fx", True)
    data.setdefault("press_anim", "bounce")
    data.setdefault("page_fx", True)
    disp = data.setdefault("display", {})
    base = int(disp.get("size", 88))             # old configs only had a single "size"
    disp.setdefault("w", base)
    disp.setdefault("h", base)
    disp.setdefault("dx", 0)
    disp.setdefault("dy", 0)
    data.setdefault("profiles", default_config()["profiles"])
    if "active_profile" not in data and data["profiles"]:
        data["active_profile"] = data["profiles"][0].get("name", "Default")
    for p in data["profiles"]:
        p.setdefault("name", "Profile")
        g = p.setdefault("globals", {})
        p.setdefault("folders", {})
        p.setdefault("pages", [{"name": "Home", "items": {}}])
        for pg in p["pages"]:
            pg.setdefault("name", "Page")
            items = pg.setdefault("items", {})
            # Round buttons stay profile-global -> lift any out of per-page items (first wins).
            # Encoders are now PER-PAGE: they live in page items; globals[enc*] is the shared
            # default a page falls back to until it overrides the knob.
            for sid in [s for s in items if s.startswith("btn")]:
                g.setdefault(sid, items.pop(sid))
    return data
