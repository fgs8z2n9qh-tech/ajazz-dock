"""Geometry / calibration regression: old `size` migration, independent w/h, non-square encode."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# isolate: never touch the real config
tmp = tempfile.mkdtemp()
cfgp = os.path.join(tmp, "config.json")
os.environ["AJAZZDOCK_CONFIG"] = cfgp

from dock import config as C
from dock import images, device

# 1) old config with only `size` migrates -> w == h == size
json.dump({"version": 1, "display": {"size": 100, "dx": -3, "dy": 5}}, open(cfgp, "w"))
cfg = C.Config.load(cfgp)
d = cfg.display()
assert d["w"] == 100 and d["h"] == 100, ("size->w/h", d)
assert d["dx"] == -3 and d["dy"] == 5, d
print("OK 1: old `size` migrates to w/h =", d["w"], d["h"])

# 2) fresh default config has independent w/h
os.remove(cfgp)
cfg2 = C.Config.load(cfgp)
d2 = cfg2.display()
assert "w" in d2 and "h" in d2, d2
print("OK 2: default display =", d2)

# 3) non-square calib pattern renders at exact (w,h)
pat = images.calib_pattern((88, 120))
assert pat.size == (88, 120), pat.size
patc = images.calib_pattern(96)  # bare int still works
assert patc.size == (96, 96), patc.size
print("OK 3: calib_pattern non-square", pat.size, "and square", patc.size)

# 4) encode a non-square tile end-to-end (no exception, returns JPEG bytes)
jb = device.encode_key_image(pat, rotation=90, size=(88, 120), shift=(-4, 8))
assert isinstance(jb, (bytes, bytearray)) and jb[:2] == b"\xff\xd8", "not a JPEG"
print("OK 4: encode_key_image non-square ->", len(jb), "bytes JPEG")

# 5) render_face honours a non-square size (taller cell)
face = images.render_face({"label": "Files", "icon": "📁", "color": "#c8881f"}, size=(88, 120))
assert face.size == (88, 120), face.size
print("OK 5: render_face non-square", face.size)

# 6) apply_calibration path: simulate controller geometry application
images.KEY_SIZE = (88, 88); device.KEY_SIZE = (88, 88)
d2["w"], d2["h"], d2["dx"], d2["dy"] = 92, 116, -5, 9
cfg2.save()
cfg3 = C.Config.load(cfgp)
dd = cfg3.display()
w = max(40, min(180, int(dd["w"]))); h = max(40, min(180, int(dd["h"])))
images.KEY_SIZE = (w, h); device.KEY_SIZE = (w, h)
device.CONTENT_SHIFT = (int(dd["dx"]), int(dd["dy"]))
assert images.KEY_SIZE == (92, 116) and device.KEY_SIZE == (92, 116), images.KEY_SIZE
assert device.CONTENT_SHIFT == (-5, 9), device.CONTENT_SHIFT
# render_face with size=None must now read the calibrated non-square value
f2 = images.render_face({"label": "x"})
assert f2.size == (92, 116), f2.size
print("OK 6: geometry application + size=None render =", f2.size)

print("\nALL OK")
