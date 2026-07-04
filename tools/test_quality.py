"""Quality features: stateful keys, encoder volume mixer + HUD, configurator drag/copy/paste."""
import copy
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AJAZZDOCK_CONFIG", os.path.join(os.environ.get("TEMP", "/tmp"), "_q_cfg.json"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
app = QApplication([])

from dock import live, actions
from dock.actions import ActionEngine
from dock.images import live_face, volume_hud_tiles
from dock.config import Config, default_config
from dock.controller import DockController
from dock.gui import ConfigWindow

# ---- 1) stateful live sources -------------------------------------------------------------
for src in ("mic", "caps", "light"):
    t, cap, frac, kind = live.value(src)
    assert kind == "state", (src, kind)
assert "mic" in live.source_ids() and "caps" in live.source_ids() and "light" in live.source_ids()
# state faces render (muted mic, caps on, bulb on/off)
for (text, capn, fr) in [("MUTED", "MIC", 1.0), ("LIVE", "MIC", 0.0),
                         ("ON", "CAPS", 1.0), ("ON", "LIGHT", 1.0), ("OFF", "LIGHT", 0.0)]:
    im = live_face({"color": "#101418"}, text, capn, fr, "state", size=(88, 88))
    assert im.size == (88, 88)
print("OK stateful sources + glyphs")

# ---- 2) appvolume action + HUD ------------------------------------------------------------
class _Ctl:
    def __init__(self): self.hud = []
    def show_volume_hud(self, vol, muted, name): self.hud.append((vol, muted, name))

ctl = _Ctl()
e = ActionEngine(ctl)
seen = []
e._appvolume = lambda a: seen.append(a)          # dispatch routing
e.execute({"type": "appvolume", "mode": "up"})
assert seen, "appvolume not dispatched"
# handler -> show_volume_hud (mock the pycaw layer)
e2 = ActionEngine(ctl)
e2._app_vol = type("V", (), {"apply": staticmethod(lambda target, mode, step: (42, False, "x.exe"))})()
e2._appvolume({"mode": "down", "step": 5, "target": "focused"})
time.sleep(0.3)
assert ctl.hud and ctl.hud[-1] == (42, False, "x.exe"), ctl.hud
tiles = volume_hud_tiles(42, False, "x.exe")
assert len(tiles) == 6
print("OK appvolume + HUD tiles")

# ---- 3) controller HUD render + revert ----------------------------------------------------
class FakeDock:
    image_rotation, image_mirror = 90, False
    def __init__(self): self.pushes = 0
    def set_key_pil(self, *a, **k): self.pushes += 1
    def set_key_image(self, *a, **k): pass
    def flush(self): pass

c = DockController(Config(default_config())); c.dock = FakeDock(); c.connected = True
c.show_volume_hud(55, False, "firefox.exe")
c._advance_volume_hud()
assert c.dock.pushes >= 6
c._volume_hud["start"] = time.time() - 2
c._advance_volume_hud()
assert c._volume_hud is None
print("OK controller HUD render + revert")

# ---- 4) configurator drag / copy / paste / clear / duplicate ------------------------------
win = ConfigWindow(DockController(Config(default_config())))
win.show()
for _ in range(3):
    app.processEvents()
items = win.items()
items["key1"] = {"label": "A", "action": {"type": "open", "target": "a.exe"}}
items["key2"] = {"label": "B", "action": {"type": "open", "target": "b.exe"}}
win._swap_or_move_binding("key1", "key2")
assert win.items()["key1"]["label"] == "B" and win.items()["key2"]["label"] == "A"
win.items().pop("key5", None)
win._swap_or_move_binding("key1", "key5")
assert win.items()["key5"]["label"] == "B" and "key1" not in win.items()
win.clipboard_binding = copy.deepcopy(win.items()["key2"])
win._store("key3")["key3"] = copy.deepcopy(win.clipboard_binding)
win.items()["key3"]["label"] = "Z"
assert win.items()["key2"]["label"] == "A", "paste not deep-copied"
win._store("key3")["key3"] = {"action": {"type": "none"}}
assert win.items()["key3"]["action"]["type"] == "none"
win.items()["key4"] = {"label": "DUP", "action": {"type": "open", "target": "d.exe"}}
win._duplicate_to_empty("key4")
labels = [(win.items().get(k) or {}).get("label") for k in ("key1", "key2", "key3", "key4", "key5", "key6")]
assert labels.count("DUP") == 2, labels
assert win.key_btns["key1"].win is win and win.key_btns["key1"].acceptDrops()
assert win.slot_btns["btn7"].win is win and win.slot_btns["btn7"].sid == "btn7"
print("OK configurator drag/copy/paste/clear/duplicate")

print("\nRESULT: ALL PASS")
sys.stdout.flush()
os._exit(0)          # skip pythonnet/.NET finalizers (avoid a harmless GIL crash on exit)
