"""Render the configurator's device column in several accent shades, composed into
one 2x2 comparison grid so the user can pick the mint they like."""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication            # noqa: E402
from PySide6.QtGui import QFont                       # noqa: E402
from PySide6.QtCore import QRect                       # noqa: E402
from PIL import Image, ImageDraw, ImageFont            # noqa: E402

import dock.tokens as T                                # noqa: E402
from dock.config import Config, default_config         # noqa: E402
from dock.controller import DockController             # noqa: E402

VARIANTS = [
    ("electric mint (current)", "#35e08a"),
    ("softer mint", "#46c98a"),
    ("lime green", "#6ee36a"),
    ("cyan mint", "#2fe0a8"),
]


def _shift(hexc, f):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if f >= 0:
        r, g, b = (int(c + (255 - c) * f) for c in (r, g, b))
    else:
        r, g, b = (int(c * (1 + f)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


app = QApplication([])
app.setFont(QFont("Segoe UI", 9))

data = default_config()
data["profiles"][0]["pages"][0].setdefault("items", {})["enc1"] = {
    "action": {"type": "brightness", "mode": "up"}}

tmp = []
crop = QRect(210, 0, 602, 600)
for name, hexc in VARIANTS:
    T.ACCENT = hexc
    T.ACCENT_HOVER = _shift(hexc, 0.20)
    T.ACCENT_DIM = _shift(hexc, -0.55)
    T.TOKENS.update(ACCENT=hexc, ACCENT_HOVER=T.ACCENT_HOVER, ACCENT_DIM=T.ACCENT_DIM)
    app.setStyleSheet(T.build_qss())
    from dock.gui import ConfigWindow
    win = ConfigWindow(DockController(Config(copy.deepcopy(data))))
    win.show()
    win.select("enc1-")                # show a selected knob (accent halo) + tabs
    for _ in range(8):
        app.processEvents()
    path = os.path.join(ROOT, "assets", f"_acc_{hexc.lstrip('#')}.png")
    win.grab(crop).save(path)
    tmp.append((name, hexc, path))
    win.close()
    win.deleteLater()
    app.processEvents()

# compose 2x2 with labels
tile_w = 384
imgs = [(n, h, Image.open(p).convert("RGB")) for n, h, p in tmp]
scale = tile_w / imgs[0][2].width
tile_h = int(imgs[0][2].height * scale)
bar = 30
gap = 12
W = tile_w * 2 + gap * 3
H = (tile_h + bar) * 2 + gap * 3
canvas = Image.new("RGB", (W, H), (10, 18, 14))
draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype("segoeui.ttf", 16)
except OSError:
    font = ImageFont.load_default()
for i, (name, hexc, im) in enumerate(imgs):
    col, row = i % 2, i // 2
    x = gap + col * (tile_w + gap)
    y = gap + row * (tile_h + bar + gap)
    draw.rectangle([x, y, x + tile_w, y + bar], fill=tuple(int(hexc.lstrip('#')[j:j+2], 16) for j in (0, 2, 4)))
    draw.text((x + 10, y + 6), f"{name}   {hexc}", fill=(6, 20, 13), font=font)
    canvas.paste(im.resize((tile_w, tile_h)), (x, y + bar))
out = os.path.join(ROOT, "assets", "accent_variants.png")
canvas.save(out)
print("saved", out)
for _, _, p in tmp:
    os.remove(p)
