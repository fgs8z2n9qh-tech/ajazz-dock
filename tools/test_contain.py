"""Compare image cover (crop) vs contain (whole image), and per-key title off."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

from PIL import Image, ImageDraw  # noqa: E402
from dock.images import render_face  # noqa: E402

img = os.path.join(ASSETS, "fs_wide.png")  # 1280x320, red border + ellipse (crop detector)
cases = [
    ("cover (crops sides)", {"icon": img, "color": "#15243a", "fit": "cover", "label": "Wide"}),
    ("contain (whole png)", {"icon": img, "color": "#15243a", "fit": "contain", "label": "Wide"}),
    ("contain, title off", {"icon": img, "color": "#15243a", "fit": "contain", "show_label": False}),
]
cell = 160
out = Image.new("RGB", (len(cases) * cell, cell + 26), (17, 17, 19))
d = ImageDraw.Draw(out)
for i, (name, it) in enumerate(cases):
    face = render_face(it, show_label=it.get("show_label", True)).resize((cell - 12, cell - 12), Image.NEAREST)
    out.paste(face, (i * cell + 6, 6))
    d.text((i * cell + 8, cell + 6), name, fill=(170, 175, 182))
out.save(os.path.join(ASSETS, "contain_test.png"))
print("wrote assets/contain_test.png")
