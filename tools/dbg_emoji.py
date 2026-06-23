"""Diagnose emoji top-clipping: dump the intermediate render canvas + bbox tops."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw  # noqa: E402
from dock.images import _emoji_font, render_face  # noqa: E402

emojis = ["🎙️", "⚙️", "🔊", "⏯️", "📁", "🎮", "🔒", "🚀", "🎤", "🛠️"]

CANVAS = 240  # candidate fix: bigger canvas + top-left anchor
MARGIN = 24
cell = 130
dump = Image.new("RGB", (len(emojis) * cell, cell + 70), (20, 20, 20))
d0 = ImageDraw.Draw(dump)
font = _emoji_font(109)
for i, em in enumerate(emojis):
    tmp = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((MARGIN, MARGIN), em, font=font,
                             anchor="la", embedded_color=True)
    bb = tmp.getbbox()
    top = bb[1] if bb else -1
    cps = "+".join(f"U{ord(c):04X}" for c in em)
    print(f"[{i}] {cps}  bbox={bb}  top={top}  bottom={bb[3] if bb else -1}")
    face = render_face({"icon": em, "label": "Test"}).resize((120, 120), Image.NEAREST)
    dump.paste(face, (i * cell + (cell - 120) // 2, 4))
dump.save(os.path.join(ROOT, "assets", "dbg_emoji_canvas.png"))
print("wrote assets/dbg_emoji_canvas.png")
