"""Live keys (dynamic icons) + full-panel wallpaper engine."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from dock import live, images
from dock.images import live_face, panel_frames, render_face

# 1) every live source returns (text, caption, frac, kind) without raising
live.prime()
for sid in live.source_ids():
    text, caption, frac, kind = live.value(sid)
    assert isinstance(text, str) and isinstance(caption, str), (sid, text, caption)
    assert frac is None or 0.0 <= frac <= 1.0, (sid, frac)
    assert kind in ("percent", "battery", "clock", "date", "net", "state", "gauge", "media", "vol"), (sid, kind)
    print(f"  live {sid:10} -> {text!r:>11} {caption!r:>10} frac={frac} kind={kind}")
print("OK all live sources return (text, caption, frac, kind)")

# 2) each kind renders at size and differs from a blank face
blank = render_face({}, size=(88, 88)).tobytes()
for t, cap, fr, k in [("47%", "CPU", 0.47, "percent"), ("88%", "GPU", 0.88, "percent"),
                      ("72%", "CHARGING", 0.72, "battery"), ("14:32", "", None, "clock"),
                      ("23", "MON JUN", None, "date"), ("512", "KB/S", None, "net")]:
    f = live_face({"color": "#101418"}, t, cap, fr, k, size=(88, 88))
    assert f.size == (88, 88) and f.tobytes() != blank, (k, "did not render")
# every selectable style renders, and the gauge is dynamic by value
from dock.images import LIVE_STYLE_ORDER
for st in LIVE_STYLE_ORDER:
    f = live_face({"color": "#101418"}, "60%", "CPU", 0.60, "percent", size=(88, 88), style=st)
    assert f.size == (88, 88) and f.tobytes() != blank, (st, "style did not render")
lo = live_face({"color": "#101418"}, "20%", "CPU", 0.20, "percent", size=(88, 88)).tobytes()
hi = live_face({"color": "#101418"}, "95%", "CPU", 0.95, "percent", size=(88, 88)).tobytes()
assert lo != hi, "gauge should look different at 20% vs 95%"
print(f"OK every live kind + all {len(LIVE_STYLE_ORDER)} styles render; dynamic by value")

# 3) panel_frames slices a 3-frame GIF into 6 tiles per frame at KEY_SIZE
tmp = tempfile.mkdtemp()
gifp = os.path.join(tmp, "anim.gif")
frames = [Image.new("RGB", (300, 200), c) for c in [(200, 30, 30), (30, 200, 30), (30, 30, 200)]]
frames[0].save(gifp, save_all=True, append_images=frames[1:], duration=100, loop=0)
pf = panel_frames(gifp, gap=22)
assert len(pf) == 3 and all(len(fr) == 6 for fr in pf)
assert all(t.size == images.KEY_SIZE for fr in pf for t in fr)
print(f"OK panel_frames: {len(pf)} frames x 6 tiles @ {images.KEY_SIZE}")
pngp = os.path.join(tmp, "wall.png"); Image.new("RGB", (300, 200), (90, 90, 90)).save(pngp)
assert len(panel_frames(pngp)) == 1
print("OK static image -> 1 frame")

# 4) controller routes a live key through live_face + sets up a panel
from dock.controller import DockController
c = DockController()
prof = c.config.active_profile()
prof["pages"][0]["items"]["key1"] = {"label": "Load", "color": "#101418", "live": {"source": "cpu"},
                                     "action": {"type": "none"}}
c.page_index = 0
assert c._face_for_index(0).size == images.KEY_SIZE
print("OK controller renders live key via live_face")
prof["pages"][0]["panel"] = {"path": gifp, "fps": 10, "gap": 22}
assert c._setup_panel(prof["pages"][0]["panel"]) is True and len(c._panel["frames"]) == 3
print("OK controller sets up animated panel")
print("\nALL OK")
