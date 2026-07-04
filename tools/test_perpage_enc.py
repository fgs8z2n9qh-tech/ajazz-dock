"""Verify encoders are per-page (page override -> shared global fallback)."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication                # noqa: E402
from dock.config import Config, default_config            # noqa: E402
from dock.controller import DockController                # noqa: E402
from dock.gui import ConfigWindow                         # noqa: E402

fails = []


def check(name, cond):
    print(("  ok " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


data = default_config()
prof = data["profiles"][0]
ctrl = DockController(Config(data))

# default globals has enc0+ = volume up; no page override yet
ctrl.page_index = 0
b = ctrl._binding_for("enc0+")
check("page0 knob falls back to global (volume up)", b and b["action"].get("volume") == "up")

# add a page-0 override
prof["pages"][0].setdefault("items", {})["enc0+"] = {"action": {"type": "brightness", "mode": "up"}}
b = ctrl._binding_for("enc0+")
check("page0 knob uses its override (brightness)", b["action"]["type"] == "brightness")

# page 1 has no override -> still the global default
ctrl.page_index = 1
b = ctrl._binding_for("enc0+")
check("page1 knob still the global default (volume up)", b and b["action"].get("volume") == "up")

# round buttons stay global regardless of page
b = ctrl._binding_for("btn8")
check("button still global", b and b["action"].get("page") == "next")

# GUI: editing a knob on a page seeds + stores a per-page override
app = QApplication.instance() or QApplication([])
win = ConfigWindow(DockController(Config(default_config())))
win.cur_page = 1
win.select("enc0-")                                       # opens/edits the knob on page 1
seeded = "enc0-" in win.pages()[1].get("items", {})
check("editing a knob created a page-1 override", seeded)
check("page-0 was NOT touched", "enc0-" not in win.pages()[0].get("items", {}))

# GUI: copy a whole dial (all 3 sub-actions) and paste it onto another dial
win.cur_page = 0
items0 = win.pages()[0].setdefault("items", {})
items0["enc0-"] = {"action": {"type": "smartlight", "mode": "brightness_down", "step": 10}}
items0["enc0"] = {"action": {"type": "smartlight", "mode": "toggle"}}
items0["enc0+"] = {"action": {"type": "smartlight", "mode": "brightness_up", "step": 10}}
# the knob control MUST carry .win + .sid or its right-click menu never fires (regression)
knob = win.slot_btns.get("enc0")
check("knob control has .win set (so right-click menu works)", knob is not None and knob.win is win)
check("knob control has .sid set", knob is not None and knob.sid == "enc0")
# and contextMenuEvent routes a knob to _knob_context_menu (not the button path)
seen = {}
win._knob_context_menu = lambda base, gpos: seen.setdefault("knob", base)
win._slot_context_menu = lambda *a, **k: seen.setdefault("button", a)

class _Ev:
    def globalPos(self):
        from PySide6.QtCore import QPoint
        return QPoint(0, 0)
type(knob).contextMenuEvent(knob, _Ev())
check("right-clicking a knob opens the knob menu", seen.get("knob") == "enc0" and "button" not in seen)

win._copy_knob("enc0")
check("copy captured all 3 sub-actions", set(win.clipboard_encoder) == {"-", "", "+"})
win._paste_knob("enc1")                                   # paste onto a different dial
it = win.pages()[0].get("items", {})
check("paste set enc1 turn-left", it["enc1-"]["action"]["mode"] == "brightness_down")
check("paste set enc1 push", it["enc1"]["action"]["mode"] == "toggle")
check("paste set enc1 turn-right", it["enc1+"]["action"]["mode"] == "brightness_up")
check("paste is a deep copy (independent)", it["enc1-"] is not items0["enc0-"])

# the user's flow: copy on page 0, switch to ANOTHER page, paste there
win.cur_page = 1
win._paste_knob("enc0")
it1 = win.pages()[1].get("items", {})
check("cross-page paste lands on page 1", it1.get("enc0-", {}).get("action", {}).get("mode") == "brightness_down")
check("page-0 dial unchanged by the page-1 paste",
      win.pages()[0]["items"]["enc0-"]["action"]["mode"] == "brightness_down")
# default knob copy grabs the GLOBAL fallback (volume), not nothing
win2 = ConfigWindow(DockController(Config(default_config())))
win2._copy_knob("enc0")
check("copying a default dial captures its global volume mapping",
      win2.clipboard_encoder["+"]["action"].get("volume") == "up")
# clear wipes all 3 (back on page 0)
win.cur_page = 0
win._clear_knob("enc1")
it = win.pages()[0].get("items", {})
check("clear set all 3 to none",
      all(it[f"enc1{s}"]["action"]["type"] == "none" for s in ("-", "", "+")))

# ---- knobs are renamable: a custom per-page caption overrides the auto name -------------------
win.cur_page = 0
auto = win._auto_caption("enc0")
win._set_dial_caption("enc0", "Lights")
check("custom dial name overrides the auto caption", win._control_caption("enc0") == "Lights")
check("custom name stored on the page", win.pages()[0].get("captions", {}).get("enc0") == "Lights")
check("on-stage knob shows the custom name", win.slot_btns["enc0"]._caption == "Lights")
# per-page: page 1 keeps the auto name
win.cur_page = 1
check("a different page keeps the auto caption", win._control_caption("enc0") == win._auto_caption("enc0"))
# blank reverts to auto
win.cur_page = 0
win._set_dial_caption("enc0", "   ")
check("blank name reverts to the auto caption", win._control_caption("enc0") == auto)
check("blank name removed from storage", "enc0" not in win.pages()[0].get("captions", {}))

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
