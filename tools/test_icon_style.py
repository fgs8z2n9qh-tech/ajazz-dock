"""Icon styling: render fields + the IconStyleDialog wiring (offscreen)."""
import os, sys, tempfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication
app = QApplication([])
from PIL import Image
from dock.images import render_face, has_icon_style
from dock.config import Config, default_config
from dock.controller import DockController
from dock.gui import ConfigWindow, IconStyleDialog

tmp = tempfile.mkdtemp()
p = os.path.join(tmp, "app.png")
Image.new("RGBA", (180, 180), (240, 120, 40, 255)).save(p)

# 1) styling changes the render + is detected
base = render_face({"icon": p, "color": "#101418", "fit": "contain"}, size=(88, 88))
styled = render_face({"icon": p, "color": "#101418", "fit": "contain",
                      "icon_scale": 0.7, "icon_radius": 30, "icon_tile": True,
                      "icon_tile_color": "#1e6fd0"}, size=(88, 88))
assert base.tobytes() != styled.tobytes(), "styling didn't change the render"
assert has_icon_style({"icon_scale": 0.7}) and not has_icon_style({"icon_scale": 1.0})
print("OK styled render differs; has_icon_style detects styling")

# each new effect must change the render + be detected
for fld in ({"icon_dx": 20}, {"icon_dy": -15}, {"icon_rotate": 30}, {"icon_opacity": 40},
            {"icon_border": 3, "icon_border_color": "#35e08a"},
            {"icon_scale": 0.7, "icon_shadow": True}):     # shadow shows once the icon has padding
    r = render_face({"icon": p, "color": "#101418", "fit": "contain", **fld}, size=(88, 88))
    assert r.tobytes() != base.tobytes(), f"effect had no visible effect: {fld}"
    assert has_icon_style(fld), f"has_icon_style missed {fld}"
# background gradient changes the render even with no icon
solid = render_face({"color": "#2d6cdf", "label": "x"}, size=(88, 88))
grad = render_face({"color": "#2d6cdf", "bg2": "#7a3cc4", "bg_dir": "d", "label": "x"}, size=(88, 88))
assert solid.tobytes() != grad.tobytes(), "gradient background had no effect"
print("OK position / rotate / opacity / border / shadow / gradient all render")

# EMOJI icons must also respect the styling controls (not just image icons)
emoji_base = render_face({"icon": "🎮", "color": "#101418"}, size=(88, 88), show_label=False)
for fld in ({"icon_scale": 0.5}, {"icon_rotate": 30}, {"icon_dx": 25}, {"icon_opacity": 40},
            {"icon_tile": True, "icon_radius": 30}, {"icon_border": 4, "icon_border_color": "#35e08a"}):
    r = render_face({"icon": "🎮", "color": "#101418", **fld}, size=(88, 88), show_label=False)
    assert r.tobytes() != emoji_base.tobytes(), f"emoji styling had no effect: {fld}"
print("OK emoji icons respect the Customize controls too")

# 2) dialog wiring
data = default_config()
win = ConfigWindow(DockController(Config(data)))
win.select("key1")
item = win._store_item("key1")
item["icon"] = p
item["fit"] = "contain"
dlg = IconStyleDialog(win, item)
dlg._set("icon_scale", 0.65)
dlg._set("icon_radius", 22)
dlg._toggle_tile(True)
assert item.get("icon_scale") == 0.65 and item.get("icon_radius") == 22 and item.get("icon_tile") is True
assert item.get("icon_tile_color")
print("OK dialog applies zoom / round / tile live")

# reject restores original (no style)
dlg.reject()
assert "icon_scale" not in item and "icon_tile" not in item, "reject didn't restore"
print("OK Cancel restores the original style")

# save keeps the edits
dlg2 = IconStyleDialog(win, item)
dlg2._set("icon_scale", 0.8)
dlg2._save()
assert item.get("icon_scale") == 0.8
print("OK Save keeps the edits")

# 3) setting a new icon resets styling
item["icon_scale"] = 0.5; item["icon_tile"] = True
win._set_face(item, "icon", "🚀")
assert "icon_scale" not in item and "icon_tile" not in item, "new icon should reset style"
print("OK new icon resets style")

# 4) "Use app icon" resolves a .lnk shortcut to the real exe/icon (not the generic shortcut icon)
import dock.appicon as A
_o = (A._resolve, A._resolve_lnk, A._shell_icon, A.os.path.exists)
try:
    A._resolve = lambda t: t
    A._resolve_lnk = lambda p: ("C:/real/app.exe", "C:/real/icon.ico")
    A.os.path.exists = lambda p: True
    order = []
    A._shell_icon = lambda path, px: (order.append(path) or ("IM" if path.endswith(".ico") else None))
    got = A.icon_image("C:/x/App.lnk")
    assert got == "IM" and order[0] == "C:/real/icon.ico", (got, order)
    order.clear()
    A._shell_icon = lambda path, px: (order.append(path) or "IM")
    A.icon_image("C:/apps/foo.exe")
    assert order == ["C:/apps/foo.exe"], order      # a plain exe is used as-is
finally:
    A._resolve, A._resolve_lnk, A._shell_icon, A.os.path.exists = _o
print("OK 'Use app icon' resolves shortcuts to the real exe/icon")

print("\nALL OK")
