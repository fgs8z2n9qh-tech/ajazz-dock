"""Verify full-screen no-crop (pad) + device encode after the edge fix."""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

from PIL import Image, ImageDraw  # noqa: E402
from dock.images import slice_fullscreen, render_face, KEY_SIZE  # noqa: E402
from dock.device import encode_key_image  # noqa: E402


def make(w, h):
    im = Image.new("RGB", (w, h), (20, 30, 50))
    d = ImageDraw.Draw(im)
    d.rectangle([3, 3, w - 4, h - 4], outline=(255, 40, 40), width=6)  # border = crop detector
    d.ellipse([w * 0.15, h * 0.15, w * 0.85, h * 0.85], outline=(255, 210, 0), width=10)
    return im


for name, (w, h) in [("tall", (360, 760)), ("wide", (1280, 320))]:
    p = os.path.join(ASSETS, f"fs_{name}.png")
    make(w, h).save(p)
    tiles = slice_fullscreen(p, os.path.join(ASSETS, "_icons"), tag=name)
    gap, (kw, kh) = 22, KEY_SIZE
    W, H = 3 * kw + 2 * gap, 2 * kh + gap
    big = Image.new("RGB", (W, H), (0, 0, 0))
    for i, t in enumerate(tiles):
        r, c = divmod(i, 3)
        big.paste(render_face({"icon": t, "fit": "cover"}), (c * (kw + gap), r * (kh + gap)))
    big.resize((W * 4, H * 4), Image.NEAREST).save(os.path.join(ASSETS, f"fs_{name}_montage.png"))
    print(f"  {name}: wrote fs_{name}_montage.png (full red border visible => no side crop)")

face = render_face({"label": "Edge", "color": "#33aa33"})
data = encode_key_image(face)
dec = Image.open(io.BytesIO(data))
print(f"  device encode: {len(data)} bytes, decoded {dec.size} {dec.format}")
