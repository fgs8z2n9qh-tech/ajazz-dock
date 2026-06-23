"""Encode must NOT distort aspect ratio: a square content marker stays square through the
uniform inset + pure-translate + rotation pipeline, for any (w,h) and shift."""
import os, sys, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from dock import device

def square_bbox_ratio(jpeg):
    im = Image.open(io.BytesIO(jpeg)).convert("RGB")
    # find the bright square's bounding box
    xs, ys = [], []
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            if r > 150 and g > 150 and b > 150:
                xs.append(x); ys.append(y)
    if not xs:
        return None
    bw = max(xs) - min(xs) + 1
    bh = max(ys) - min(ys) + 1
    return bw / bh

def make(w, h):
    im = Image.new("RGB", (w, h), (10, 10, 10))
    s = min(w, h) // 2                 # a centred SQUARE (equal sides)
    x0, y0 = (w - s) // 2, (h - s) // 2
    im.paste(Image.new("RGB", (s, s), (240, 240, 240)), (x0, y0))
    return im

worst = 0.0
for (w, h) in [(88, 88), (88, 140), (140, 88), (100, 130)]:
    for shift in [(0, 0), (-6, 8), (10, -10)]:
        jb = device.encode_key_image(make(w, h), size=(w, h), shift=shift)
        ratio = square_bbox_ratio(jb)
        assert ratio is not None, (w, h, shift)
        err = abs(ratio - 1.0)
        worst = max(worst, err)
        assert err < 0.12, f"aspect distorted at size=({w},{h}) shift={shift}: bbox ratio={ratio:.3f}"
print(f"OK: square stays square (worst bbox aspect error {worst:.3f} < 0.12) across non-square tiles + shifts")
print("\nALL OK")
