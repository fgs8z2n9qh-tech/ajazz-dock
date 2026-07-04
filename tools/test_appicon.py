"""App-icon extraction + the configurator's 'use app icon' wiring (offscreen)."""
import os, sys, tempfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication
app = QApplication([])

from dock import appicon
from PIL import Image

# 1) extract a real system exe icon (resolve 'notepad.exe' on PATH too)
im = appicon.icon_image("notepad.exe")
assert im is not None, "could not extract notepad.exe icon"
assert isinstance(im, Image.Image) and im.width >= 8 and im.height >= 8, im
print(f"OK extracted notepad.exe icon -> {im.size} {im.mode}")

# full path works
im2 = appicon.icon_image(r"C:\Windows\explorer.exe")
assert im2 is not None and im2.width >= 8
print(f"OK extracted explorer.exe icon -> {im2.size}")

# 2) save_icon writes a PNG
tmp = tempfile.mkdtemp()
p = appicon.save_icon("notepad.exe", tmp)
assert p and os.path.exists(p) and p.endswith(".png"), p
print(f"OK saved icon PNG -> {os.path.basename(p)} ({os.path.getsize(p)} bytes)")

# bogus target -> None (no crash)
assert appicon.icon_image("this_is_not_a_real_program_xyz.exe") is None
assert appicon.save_icon("https://example.com", tmp) is None    # URLs unsupported
print("OK bogus/URL targets return None")

# 3) configurator: setting an 'open' action + applying the app icon
from dock.config import Config, default_config
from dock.controller import DockController
from dock.gui import ConfigWindow
data = default_config()
win = ConfigWindow(DockController(Config(data)))
win.select("key1")
item = win._store_item("key1")
item["action"] = {"type": "open", "target": "notepad.exe"}
win._apply_app_icon(item, silent=True)
assert item.get("icon") and os.path.exists(item["icon"]), item.get("icon")
assert item.get("icon_auto") is True and item.get("fit") == "contain"
print(f"OK _apply_app_icon set icon={os.path.basename(item['icon'])} icon_auto={item['icon_auto']}")

# a hand-picked icon clears the auto flag
win._set_face(item, "icon", "🚀")
assert "icon_auto" not in item, "manual icon should clear icon_auto"
print("OK manual icon clears icon_auto")

print("\nALL OK")
