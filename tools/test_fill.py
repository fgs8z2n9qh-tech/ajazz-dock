"""Compare emoji fill (cover) vs default (contain) rendering."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

from PIL import Image, ImageDraw  # noqa: E402
from dock.images import render_face  # noqa: E402

cases = [
    ("default", {"icon": "🎵", "label": "Mixtape", "color": "#7ed957"}),
    ("fill+label", {"icon": "🎵", "label": "Mixtape", "color": "#7ed957", "fit": "cover"}),
    ("fill", {"icon": "🎵", "color": "#7ed957", "fit": "cover"}),
    ("gear fill", {"icon": "⚙️", "color": "#2b2f3a", "fit": "cover"}),
    ("fire fill", {"icon": "🔥", "color": "#1a1a1a", "fit": "cover"}),
    ("globe fill", {"icon": "🌐", "color": "#1aa179", "fit": "cover"}),
]
cell = 150
out = Image.new("RGB", (len(cases) * cell, cell + 26), (17, 17, 19))
d = ImageDraw.Draw(out)
for i, (name, it) in enumerate(cases):
    face = render_face(it).resize((cell - 12, cell - 12), Image.NEAREST)
    out.paste(face, (i * cell + 6, 6))
    d.text((i * cell + 8, cell + 6), name, fill=(170, 175, 182))
out.save(os.path.join(ASSETS, "fill_test.png"))
print("wrote assets/fill_test.png")
