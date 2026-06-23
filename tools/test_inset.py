"""Show the device-encoded image (with the edge inset) decoded back, upscaled."""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

from PIL import Image  # noqa: E402
from dock.images import render_face  # noqa: E402
from dock.device import encode_key_image, EDGE_INSET  # noqa: E402

faces = [
    {"label": "Mixtape", "icon": "🎵", "color": "#7ed957"},   # bright bg shows the frame
    {"label": "Files", "icon": "📁", "color": "#c8881f"},
    {"label": "", "icon": "🌐", "color": "#1aa179"},
]
out = Image.new("RGB", (len(faces) * 200, 200), (20, 20, 20))
for i, it in enumerate(faces):
    dec = Image.open(io.BytesIO(encode_key_image(render_face(it)))).resize((180, 180), Image.NEAREST)
    out.paste(dec, (i * 200 + 10, 10))
out.save(os.path.join(ASSETS, "inset_test.png"))
print(f"wrote inset_test.png (EDGE_INSET={EDGE_INSET}px; note: device-encoded => rotated 90deg)")
