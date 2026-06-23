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

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
