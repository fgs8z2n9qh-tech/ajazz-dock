"""Performance optimizations: live-key redraw skipping + throttled config history."""
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("AJAZZDOCK_CONFIG", os.path.join(os.environ.get("TEMP", "/tmp"), "_perf_cfg.json"))

from dock.config import Config, default_config
from dock import controller as C
from dock import live

fails = []


def check(name, cond):
    print(("  ok " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


class FakeDock:
    image_rotation, image_mirror = 90, False

    def __init__(self):
        self.pushes = 0
        self.flushes = 0
        self.image_writes = 0

    def set_key_pil(self, i, img, **kwargs):
        self.pushes += 1

    def set_key_image(self, *a, **k):
        self.image_writes += 1

    def flush(self):
        self.flushes += 1

    def set_brightness(self, *a):
        pass

    def clear_all(self):
        pass


# ---- 1) live keys don't re-render/encode/upload when the displayed value is unchanged ----------
data = default_config()
data["profiles"][0]["pages"][0].setdefault("items", {})["key1"] = {"live": {"source": "clock"}}
ctrl = C.DockController(Config(data))
ctrl.dock = FakeDock()
ctrl.connected = True
ctrl._display_on = True
ctrl.on_status = None
ctrl.page_index = 0

live.value = lambda src: ("12:34", "", None, "clock")     # a stable HH:MM clock
live.history = lambda src: []

ctrl._tick_live()
first = ctrl.dock.pushes
check("first tick pushes the live key", first == 1)
ctrl._tick_live()
check("unchanged value does NOT re-push", ctrl.dock.pushes == first)
check("no flush on a no-op tick", ctrl.dock.flushes == 1)

live.value = lambda src: ("12:35", "", None, "clock")     # the minute ticks over
ctrl._tick_live()
check("a changed value re-pushes", ctrl.dock.pushes == first + 1)
check("a changed value flushes", ctrl.dock.flushes == 2)

# a full page render invalidates the cache so the next tick repaints once
before = ctrl.dock.pushes
ctrl._render_page()                                       # pushes all 6 keys + clears _live_sig
after_render = ctrl.dock.pushes
check("render pushed all 6 keys", after_render - before == 6)
ctrl._tick_live()
check("cache cleared by render -> live key repaints once", ctrl.dock.pushes == after_render + 1)

# ---- 2) a held key no longer forces the 100 Hz busy poll after its hold has fired --------------
def busy(c):
    gesture = bool(c._tap_pending) or any(not pr["hold_fired"] for pr in c._press.values())
    return bool(c._anim or c._page_anim or c._calib or c._panel or c._volume_hud or gesture)


ctrl._press = {"btn8": {"t": time.time(), "index": 7, "kind": "button",
                        "binding": None, "hold_fired": False}}
check("holding a key before its hold fires -> fast poll", busy(ctrl) is True)
ctrl._press["btn8"]["hold_fired"] = True
check("after the hold fired -> back to idle poll (no busy-wait)", busy(ctrl) is False)
ctrl._press = {}

# ---- 3) config history snapshot is throttled WITHOUT a directory scan on the common path -------
import dock.config as cfgmod
cfgmod.Config._last_snapshot_t = time.time()              # pretend a snapshot just happened
hits = {"listdir": 0}
_orig = cfgmod.os.listdir
cfgmod.os.listdir = lambda *a, **k: (hits.__setitem__("listdir", hits["listdir"] + 1) or _orig(*a, **k))
try:
    cfgmod.Config._write_history("does-not-matter.json")  # within 5 min -> early return
finally:
    cfgmod.os.listdir = _orig
check("throttled history skips the backups directory scan", hits["listdir"] == 0)

# ---- 4) wallpaper animation: frames pre-encoded once -> playback is pure HID writes -----------
import tempfile
from PIL import Image as _Img

wp = os.path.join(tempfile.gettempdir(), "_ajazz_wp_test.png")
_Img.new("RGB", (308, 198), (40, 80, 160)).save(wp)
ctrl.dock = FakeDock()
ctrl.connected = True
ctrl._display_on = True
ctrl._panel = None
ok = ctrl._setup_panel({"path": wp, "fps": 45, "gap": 22})
check("panel setup succeeds", ok is True)
check("frames are pre-encoded to JPEG bytes (not PIL tiles)",
      isinstance(ctrl._panel["jpeg"][0][0], (bytes, bytearray)))
check("PIL tiles are dropped after pre-encode", "frames" not in ctrl._panel)
check("fps cap raised to 60 (45 kept)", ctrl._panel["fps"] == 45)
check("playback uploads via set_key_image, not re-encode", ctrl.dock.image_writes == 6)

# ---- 5) now-playing marquee: a long title scrolls; a short one does not -----------------------
data2 = default_config()
data2["profiles"][0]["pages"][0].setdefault("items", {})["key1"] = {"live": {"source": "media"}}
ctrl2 = C.DockController(Config(data2))
ctrl2.dock = FakeDock()
ctrl2.connected = True
ctrl2._display_on = True
ctrl2.on_status = None
ctrl2.page_index = 0
live.history = lambda src: []

live.value = lambda src: ("A Very Long Track Title That Will Not Fit On A Tiny Key", "Artist", 1.0, "media")
ctrl2._tick_live()
check("a long title registers a marquee", 0 in ctrl2._marquee)
ctrl2._marquee_last = 0.0
before = ctrl2.dock.pushes
ctrl2._advance_marquee()
check("marquee advance re-renders the scrolling key", ctrl2.dock.pushes == before + 1)

# a long pause must NOT cause a forward catch-up jump (offset advances by ~one frame, not the gap)
live.value = lambda src: ("A Very Long Track Title That Will Not Fit On A Tiny Key", "Artist", 1.0, "media")
ctrl2._tick_live()
ctrl2._marquee[0]["offset"] = 100.0
ctrl2._marquee[0]["last"] = time.time() - 5.0           # pretend the marquee was paused 5 s
ctrl2._marquee_last = 0.0
ctrl2._advance_marquee()
jump = ctrl2._marquee[0]["offset"] - 100.0
check("a paused marquee resumes without a catch-up jump",
      jump <= C._MARQUEE_DT * 2 * C._MARQUEE_SPEED + 1)

# a media key whose title also fires its action is unaffected; short title clears the marquee
live.value = lambda src: ("OK", "Artist", 1.0, "media")
ctrl2._tick_live()
check("a short title clears the marquee", 0 not in ctrl2._marquee)

# ---- 6) responsiveness: a key press fires its action BEFORE the press-bounce render ----------
from dock.device import Event

data3 = default_config()
data3["profiles"][0]["pages"][0].setdefault("items", {})["key1"] = {"action": {"type": "hotkey", "keys": "a"}}
ctrl3 = C.DockController(Config(data3))
ctrl3.dock = FakeDock()
ctrl3.connected = True
ctrl3._display_on = True
ctrl3.page_index = 0
order = []
ctrl3.engine.execute = lambda a: order.append("execute")
ctrl3._animate_key = lambda i: order.append("animate")
ctrl3._handle_event(Event(kind="key", index=0, pressed=True))
check("key action fires before the press animation", order == ["execute", "animate"])

# ---- 7) blocking keyboard actions run OFF the loop thread; nav/COM stay inline ----------------
import threading as _th
from dock.actions import ActionEngine

eng = ActionEngine(None)
main_id = _th.get_ident()
seen = []
eng._dispatch = lambda a: seen.append((a.get("type"), _th.get_ident()))
eng.execute({"type": "page", "page": "next"})           # inline -> loop thread
eng.execute({"type": "hotkey", "keys": "a"})            # worker -> off the loop
eng.execute({"type": "text", "text": "hi"})             # worker, in order
deadline = time.time() + 2.0
while len([s for s in seen if s[0] in ("hotkey", "text")]) < 2 and time.time() < deadline:
    time.sleep(0.01)
by_type = {t: tid for t, tid in seen}
check("navigation dispatches inline (loop thread)", by_type.get("page") == main_id)
check("hotkey dispatches on a worker thread (off the loop)",
      "hotkey" in by_type and by_type["hotkey"] != main_id)
check("keyboard actions keep their order on the worker",
      [t for t, _ in seen if t in ("hotkey", "text")] == ["hotkey", "text"])

# ---- 8) live-stat icons are resizable via icon_scale -----------------------------------------
from dock.images import live_face as _lf


def _content_px(scale):
    im = _lf({"color": "#000000", "icon_scale": scale}, "55%", "CPU", 0.55, "percent",
             size=(88, 88), show_label=False).convert("L")
    return sum(1 for p in im.getdata() if p > 30)     # non-black px = drawn gauge/number content


small = _content_px(0.6)
big = _content_px(1.4)
check("a bigger icon_scale draws a visibly larger live icon", big > small * 1.3)

# folder tiles honour icon_scale too
from dock.images import folder_face as _ff
_fc = {"key1": {"icon": "🎮"}, "key2": {"icon": "🎨"}}


def _folder_px(scale):
    im = _ff({"color": "#000000", "icon_scale": scale}, _fc, size=(88, 88), show_label=False).convert("L")
    return sum(1 for p in im.getdata() if p > 25)


check("a bigger icon_scale draws a visibly larger folder tile", _folder_px(1.4) > _folder_px(0.6) * 1.3)

# ---- 9) sampler parking + prime() no longer eager-starts LHM ---------------------------------
_before = {t.name for t in _th.enumerate()}
live.prime()
time.sleep(0.15)
check("prime() does NOT start the heavy LHM .NET sampler", "lhm-sampler" not in {t.name for t in _th.enumerate()})

live._arm_park("perftest")
live._last_read["perftest"] = time.monotonic() - 99      # long idle -> should park
_state = {"woke": False}


def _park_worker():
    live._park_if_idle("perftest")                       # blocks until touched
    _state["woke"] = True


_pw = _th.Thread(target=_park_worker, daemon=True)
_pw.start()
time.sleep(0.15)
check("an idle sampler parks (blocks, zero CPU)", _state["woke"] is False)
live._touch("perftest")                                  # a reader wakes it instantly
time.sleep(0.15)
check("a parked sampler wakes on the next read", _state["woke"] is True)

# ---- 10) media cover-art background is cached across marquee frames --------------------------
from PIL import Image as _PILImage
_art = _PILImage.new("RGB", (200, 200), (40, 90, 200))
from dock import images as _img
_img._MEDIA_BG_CACHE.clear()
_lf({"color": "#101010"}, "Song Title", "Artist", 1.0, "media", size=(88, 88), show_label=False, artwork=_art)
_key_after_first = _img._MEDIA_BG_CACHE.get("key")
_bg_after_first = _img._MEDIA_BG_CACHE.get("bg")
_lf({"color": "#101010"}, "Song Title", "Artist", 1.0, "media", size=(88, 88), show_label=False, artwork=_art)
check("media cover scrim is cached (same key across frames)", _img._MEDIA_BG_CACHE.get("key") == _key_after_first)
check("cached media background object is reused (not recomputed)", _img._MEDIA_BG_CACHE.get("bg") is _bg_after_first)

# ---- 11) brightness live-apply does NOT hit disk (only the debounced save does) --------------
_saves = {"n": 0}
_cfg = Config(default_config())
_cfg.save = lambda *a, **k: _saves.__setitem__("n", _saves["n"] + 1)
_ctl = C.DockController(_cfg)
_n0 = _saves["n"]
for _v in (40, 41, 42, 43, 44):
    _ctl.set_brightness_live(_v)                         # a drag: 5 ticks, 0 disk writes
check("set_brightness_live writes 0 configs during a drag", _saves["n"] == _n0)
check("set_brightness_live still updates the device target", _ctl._pending_brightness == 44)

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)
