"""Stress-test key-face rendering: diverse emoji, long labels, icon-only, and a PNG.

Renders a montage to assets/preview_test.png at true device pixels (NEAREST upscaled).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw  # noqa: E402
from dock.images import render_face  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")


def make_sample_png():
    """A test PNG icon (gradient disc) to exercise the image-icon path."""
    p = os.path.join(ASSETS, "sample_icon.png")
    img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([8, 8, 120, 120], fill=(255, 196, 0, 255), outline=(40, 40, 40, 255), width=6)
    d.polygon([(64, 26), (78, 58), (112, 58), (84, 80), (95, 114),
               (64, 92), (33, 114), (44, 80), (16, 58), (50, 58)], fill=(40, 40, 40, 255))
    img.save(p)
    return p


def main():
    os.makedirs(ASSETS, exist_ok=True)
    png = make_sample_png()
    items = [
        {"label": "Notepad", "icon": "📝", "color": "#2d6cdf"},
        {"label": "Play", "icon": "⏯️", "color": "#7a3cc4"},
        {"label": "Page →", "icon": "➡️", "color": "#444b55"},
        {"label": "Files", "icon": "📁", "color": "#c8881f"},
        {"label": "Mic", "icon": "🎙️", "color": "#c0392b"},
        {"label": "Volume Up", "icon": "🔊", "color": "#1aa179"},
        {"icon": "🎮", "color": "#222831"},
        {"label": "OBS Studio", "icon": "🎬", "color": "#11151c"},
        {"label": "Star", "icon": png, "color": "#1f2630"},
        {"label": "No Icon Here", "color": "#243b55"},
        {"label": "Discord", "icon": "💬", "color": "#5865f2"},
        {"label": "Lock", "icon": "🔒", "color": "#2b2f3a"},
    ]
    cols, scale, gap = 4, 150, 16
    rows = (len(items) + cols - 1) // cols
    W = cols * scale + (cols + 1) * gap
    H = rows * (scale + 22) + gap
    canvas = Image.new("RGB", (W, H), (17, 17, 19))
    d = ImageDraw.Draw(canvas)
    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        x = gap + c * (scale + gap)
        y = gap + r * (scale + 22)
        face = render_face(it).resize((scale, scale), Image.NEAREST)
        canvas.paste(face, (x, y))
        d.rectangle([x, y, x + scale - 1, y + scale - 1], outline=(60, 64, 72))
    out = os.path.join(ASSETS, "preview_test.png")
    canvas.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
