"""DockController: bind device input events to actions and render pages."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .actions import ActionEngine
from .config import LCD_KEYS, Config
from .device import AKP03, Event
from .images import render_face, press_frames, page_swipe_frames

# Face shown on the last key while a folder sub-page is open.
_BACK_FACE = {"label": "Back", "icon": "⬅️", "color": "#222a33"}

# Lighter JPEG for in-motion animation frames (smaller -> faster transfer -> higher fps).
# The final settle frame is re-rendered at full quality.
_ANIM_Q = 72
_ANIM_SS = 2


def _log_error(where: str, exc: BaseException) -> None:
    """Append a traceback to %APPDATA%/AjazzDock/error.log (best-effort, never raises)."""
    try:
        import datetime
        import traceback
        from .config import config_dir
        with open(f"{config_dir()}\\error.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {where}\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass


def _log_debug(msg: str) -> None:
    """Append a one-line trace to %APPDATA%/AjazzDock/calib.log (best-effort)."""
    try:
        import datetime
        from .config import config_dir
        with open(f"{config_dir()}\\calib.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%H:%M:%S}] {msg}\n")
    except Exception:
        pass


class DockController:
    def __init__(self, config: Optional[Config] = None,
                 on_status: Optional[Callable[[], None]] = None) -> None:
        self.config = config or Config.load()
        self.dock = AKP03()
        self.engine = ActionEngine(self)
        self.on_status = on_status            # called when connection/page/profile changes

        self.page_index = 0
        self._folder: Optional[str] = None    # id of the open folder sub-page, or None
        self.connected = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # cross-thread requests, all serviced inside the event loop thread:
        self._render_requested = True
        self._reload_requested = False
        self._pending_brightness: Optional[int] = None
        self._anim = None                     # dict: index, page, frames, start, dur, last
        self._page_anim = None                # dict: frames(list of 6-face lists), start, dur, last
        self._pending_page = None             # (direction, new_index) requested from any thread
        self._calib = None                    # (w, h, dx, dy) live display-calibration preview
        self._calib_dirty = False
        self._calib_active = False            # True only while the calibration dialog is open
        self._apply_geometry()                # push config display-calibration into the render modules

    # ---- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="dock-loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        try:
            if self.connected:
                self.dock.clear_all()
                self.dock.flush()
        except Exception:
            pass
        self.dock.close()

    # ---- the loop ----------------------------------------------------------
    def _run(self) -> None:
        while self._running:
            if not self.connected:
                if not self._try_connect():
                    time.sleep(1.0)
                    continue
            try:
                self._service_requests()
                # Spin faster while an animation or live calibration is active.
                busy = self._anim or self._page_anim or self._calib
                ev = self.dock.read_event(timeout_ms=10 if busy else 200)
                if ev:
                    self._handle_event(ev)
            except OSError:
                # device was unplugged / I/O error -> drop and retry
                self._set_connected(False)
                self.dock.close()
                time.sleep(0.5)
            except Exception as e:
                # A render/encode bug must NEVER kill the loop — otherwise the last frame
                # (e.g. the calibration pattern) freezes on screen and input dies. Log + go on.
                _log_error("loop", e)
                time.sleep(0.05)

    def _try_connect(self) -> bool:
        try:
            if not AKP03.is_present():
                return False
            self.dock.open()
            self.dock.set_brightness(self.config.brightness)
            self.dock.clear_all()
            self.dock.flush()
            self._set_connected(True)
            self._render_requested = True
            self._service_requests()
            return True
        except Exception:
            self.dock.close()
            return False

    def _service_requests(self) -> None:
        if self._reload_requested:
            self._reload_requested = False
            with self._lock:
                self.config = Config.load()
            self._apply_geometry()
            self._folder = None
            self._pending_brightness = self.config.brightness
            self._render_requested = True
        if self._pending_brightness is not None:
            b = self._pending_brightness
            self._pending_brightness = None
            self.dock.set_brightness(b)
        if self._pending_page is not None:
            direction, idx = self._pending_page
            self._pending_page = None
            self._start_page_swipe(direction, idx)
        # Render the calibration preview FIRST, then the page — so when both fire in one pass
        # (e.g. a preview tick landing right as the dialog closes), the normal page is always
        # the LAST thing written to the keys and the pattern can never win the final write.
        if self._calib_dirty:
            self._calib_dirty = False
            try:
                self._render_calib()
            except OSError:
                raise
            except Exception as e:
                _log_error("render_calib", e)
        if self._render_requested:
            self._render_requested = False
            try:
                self._render_page()
            except OSError:
                raise
            except Exception as e:
                _log_error("render_page", e)
        if self._anim:
            self._advance_anim()
        if self._page_anim:
            self._advance_page_anim()

    # ---- display geometry / calibration ------------------------------------
    def _apply_geometry(self) -> None:
        """Push the config's display calibration (w/h tile + shift) into the render modules."""
        from . import images, device
        d = self.config.display()                 # normalises w/h (incl. old `size`) + shift
        w = max(40, min(180, int(d.get("w", 88))))
        h = max(40, min(180, int(d.get("h", 88))))
        # Clamp the nudge so a stale/large saved shift can't crop the icon off the far edge.
        dx = max(-20, min(20, int(d.get("dx", 0))))
        dy = max(-20, min(20, int(d.get("dy", 0))))
        images.KEY_SIZE = (w, h)
        device.KEY_SIZE = (w, h)
        device.CONTENT_SHIFT = (dx, dy)

    def begin_calibration(self) -> None:
        """Open a calibration session: only now will preview_calibration take effect."""
        self._calib_active = True
        _log_debug("begin")

    def _render_calib(self) -> None:
        if not self.connected or not self._calib or not self._calib_active:
            return
        from .images import calib_pattern
        from .device import encode_key_image
        w, h, dx, dy = self._calib
        try:
            jb = encode_key_image(calib_pattern((w, h)), self.dock.image_rotation,
                                  self.dock.image_mirror, size=(w, h), shift=(dx, dy))
            for i in range(len(LCD_KEYS)):
                self.dock.set_key_image(i, jb)
            self.dock.flush()
        except OSError:
            pass

    def preview_calibration(self, w: int, h: int, dx: int, dy: int) -> None:
        """Live preview (any thread): show the centring target with these values.

        Ignored unless a calibration session is open — so a late debounced preview that
        fires AFTER Save/Cancel (Qt timer/GC race) can never re-arm the stuck pattern.
        """
        if not self._calib_active:
            return
        self._calib = (int(w), int(h), int(dx), int(dy))
        self._calib_dirty = True

    def apply_calibration(self, w: int, h: int, dx: int, dy: int) -> None:
        """Persist the calibration, apply it to the render pipeline, re-render."""
        # Close the session + leave calibration mode + request the page restore FIRST, so the
        # calib pattern is always cleared from the dock even if persisting the config throws.
        self._calib_active = False
        self._calib = None
        self._calib_dirty = False
        d = self.config.data.setdefault("display", {})
        d.pop("size", None)                       # superseded by independent w/h
        d["w"], d["h"], d["dx"], d["dy"] = int(w), int(h), int(dx), int(dy)
        self._apply_geometry()
        self._render_requested = True
        _log_debug(f"apply w={w} h={h} dx={dx} dy={dy} connected={self.connected}")
        try:
            self.config.save()
        except Exception as e:
            _log_error("save_calibration", e)

    def end_calibration(self) -> None:
        """Leave calibration mode without saving — restore the normal page."""
        self._calib_active = False
        self._calib = None
        self._calib_dirty = False
        self._render_requested = True
        _log_debug(f"end connected={self.connected}")

    # ---- rendering ---------------------------------------------------------
    def _current_items(self) -> Dict[str, Any]:
        if self._folder is not None:
            folder = self.config.folders_of().get(self._folder)
            if folder is not None:
                return folder.get("items", {})
            self._folder = None                     # folder was deleted -> fall back to page
        return self.config.page(self.page_index).get("items", {})

    def _face_for_index(self, i: int):
        # The last key is the auto 'Back' key whenever a folder is open.
        if self._folder is not None and i == len(LCD_KEYS) - 1:
            return render_face(_BACK_FACE, show_label=True)
        item = self._current_items().get(LCD_KEYS[i]) or {}
        show = item.get("show_label", self.config.data.get("show_labels", True))
        return render_face(item, show_label=show)

    def _render_page(self) -> None:
        if not self.connected:
            _log_debug("render_page SKIPPED (not connected)")
            return
        for i in range(len(LCD_KEYS)):              # key1..key6 -> device key 0..5
            self.dock.set_key_pil(i, self._face_for_index(i))
        self.dock.flush()
        if self.on_status:
            self.on_status()

    def _key_face(self, index: int):
        return self._face_for_index(index)

    def _animate_key(self, index: int) -> None:
        """Kick off a squash-and-stretch bounce on a key (frames stepped in the loop)."""
        if not (0 <= index < len(LCD_KEYS)):
            return
        # If another key is still bouncing, snap it back to rest first.
        if self._anim and self._anim["index"] != index:
            self._restore_key(self._anim["index"], self._anim["page"])
        try:
            frames = press_frames(self._key_face(index),
                                  self.config.data.get("press_anim", "bounce"))
        except Exception:
            return
        self._anim = {"index": index, "page": self.page_index, "frames": frames,
                      "start": time.time(), "dur": 0.020, "last": -1}
        self._advance_anim()                  # show frame 0 immediately

    def _advance_anim(self) -> None:
        a = self._anim
        if not a:
            return
        if a["page"] != self.page_index or not self.connected:
            self._anim = None
            return
        fi = int((time.time() - a["start"]) / a["dur"])
        if fi >= len(a["frames"]):
            self._restore_key(a["index"], a["page"])
            self._anim = None
            return
        if fi != a["last"]:
            a["last"] = fi
            try:
                self.dock.set_key_pil(a["index"], a["frames"][fi], quality=_ANIM_Q, subsampling=_ANIM_SS)
                self.dock.flush()
            except OSError:
                self._anim = None

    def _restore_key(self, index: int, page: int) -> None:
        if page == self.page_index and self.connected:
            try:
                self.dock.set_key_pil(index, self._key_face(index))
                self.dock.flush()
            except OSError:
                pass

    # ---- events ------------------------------------------------------------
    def _binding_for(self, input_id: str):
        if input_id.startswith("key"):
            return self._current_items().get(input_id)            # LCD keys: per-page (or folder)
        if input_id.startswith("enc"):
            # Per-page knob: the page's override if set, else the shared global default.
            page_items = self.config.page(self.page_index).get("items", {})
            if input_id in page_items:
                return page_items[input_id]
            return self.config.globals_of().get(input_id)
        return self.config.globals_of().get(input_id)            # round buttons: profile-global

    def _handle_event(self, ev: Event) -> None:
        if (ev.kind == "key" and ev.pressed and self.connected
                and self.config.data.get("press_fx", True)):
            self._animate_key(ev.index)
        # The last key acts as 'Back' while a folder sub-page is open.
        if (ev.kind == "key" and ev.pressed and self._folder is not None
                and ev.index == len(LCD_KEYS) - 1):
            self.folder_back()
            return
        if ev.kind in ("key", "button", "encoder_push"):
            if not ev.pressed:
                return
            binding = self._binding_for(ev.input_id)
        elif ev.kind == "encoder_turn":
            binding = self._binding_for(ev.input_id)
        else:
            return
        if binding:
            self.engine.execute(binding.get("action"))

    # ---- navigation (called by ActionEngine, in loop thread) ---------------
    def _page_count(self) -> int:
        return max(1, len(self.config.pages()))

    def next_page(self) -> None:
        self._folder = None
        self._pending_page = (1, (self.page_index + 1) % self._page_count())

    def prev_page(self) -> None:
        self._folder = None
        self._pending_page = (-1, (self.page_index - 1) % self._page_count())

    def goto_page(self, index: int) -> None:
        self._folder = None
        idx = max(0, min(self._page_count() - 1, int(index)))
        direction = 0 if idx == self.page_index else (1 if idx > self.page_index else -1)
        self._pending_page = (direction, idx)

    def _start_page_swipe(self, direction: int, new_index: int) -> None:
        """Render a phone-style horizontal swipe across all 6 keys on a page change."""
        self._folder = None
        self._anim = None                                 # cancel any key bounce
        if (not self.connected or new_index == self.page_index
                or not self.config.data.get("page_fx", True)):
            self.page_index = new_index
            self._render_requested = True
            return
        old_faces = [self._face_for_index(i) for i in range(len(LCD_KEYS))]
        self.page_index = new_index
        new_faces = [self._face_for_index(i) for i in range(len(LCD_KEYS))]
        self._page_anim = {"frames": page_swipe_frames(old_faces, new_faces, direction, frames=16),
                           "start": time.time(), "dur": 0.018, "last": -1}
        self._advance_page_anim()
        if self.on_status:
            self.on_status()

    def _advance_page_anim(self) -> None:
        a = self._page_anim
        if not a:
            return
        if not self.connected:
            self._page_anim = None
            return
        fi = int((time.time() - a["start"]) / a["dur"])
        if fi >= len(a["frames"]):
            self._page_anim = None
            self._render_page()                           # settle on the final page
            return
        if fi != a["last"]:
            a["last"] = fi
            try:
                for i, face in enumerate(a["frames"][fi]):
                    self.dock.set_key_pil(i, face, quality=_ANIM_Q, subsampling=_ANIM_SS)
                self.dock.flush()
            except OSError:
                self._page_anim = None

    def enter_folder(self, fid: str) -> None:
        if fid and fid in self.config.folders_of():
            self._folder = fid
            self._render_requested = True

    def folder_back(self) -> None:
        if self._folder is not None:
            self._folder = None
            self._render_requested = True

    def set_profile(self, name: str) -> None:
        if name and self.config.set_active_profile(name):
            self._folder = None
            self.page_index = 0
            self.config.save()
            self._render_requested = True

    def set_brightness(self, value: int) -> None:
        self.config.brightness = int(value)
        self.config.save()
        self._pending_brightness = self.config.brightness

    def adjust_brightness(self, delta: int) -> None:
        self.set_brightness(self.config.brightness + int(delta))

    # ---- external (UI thread) requests -------------------------------------
    def request_reload(self) -> None:
        """Re-read config from disk and re-render (safe from any thread)."""
        self._reload_requested = True

    def request_render(self) -> None:
        self._render_requested = True

    def replace_config(self, cfg: Config) -> None:
        """Swap in an already-loaded Config (e.g. after a restore/import) and re-render."""
        with self._lock:
            self.config = cfg
        self._apply_geometry()
        self._folder = None
        self.page_index = 0
        self._pending_brightness = cfg.brightness
        self._render_requested = True

    # ---- status ------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        pages = self.config.pages()
        return {
            "connected": self.connected,
            "profile": self.config.data.get("active_profile"),
            "profiles": self.config.profile_names(),
            "page_index": self.page_index,
            "page_count": len(pages),
            "page_name": pages[self.page_index % len(pages)].get("name") if pages else "",
            "brightness": self.config.brightness,
        }

    def _set_connected(self, value: bool) -> None:
        if value != self.connected:
            self.connected = value
            if self.on_status:
                self.on_status()
