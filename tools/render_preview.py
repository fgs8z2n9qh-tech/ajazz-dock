"""Render the default Home page faces to a montage PNG (and optionally to the device).

Usage:
  python tools/render_preview.py            # montage only -> assets/preview_home.png
  python tools/render_preview.py push       # also push to the real device
  python tools/render_preview.py <profile> <page_index>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from dock.config import Config, LCD_KEYS  # noqa: E402
from dock.images import render_face  # noqa: E402

SCALE = 160
GAP = 16
BG = (17, 17, 19)


def montage(items):
    cols, rows = 3, 2
    W = cols * SCALE + (cols + 1) * GAP
    H = rows * SCALE + (rows + 1) * GAP + 22
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    for i, key_id in enumerate(LCD_KEYS):
        r, c = divmod(i, 3)
        x = GAP + c * (SCALE + GAP)
        y = GAP + r * (SCALE + GAP)
        face = render_face(items[key_id]) if key_id in items else render_face({})
        big = face.resize((SCALE, SCALE), Image.NEAREST)  # honest: real LCD pixels
        canvas.paste(big, (x, y))
        d.rectangle([x, y, x + SCALE - 1, y + SCALE - 1], outline=(60, 64, 72))
        d.text((x + 2, y + SCALE + 2), key_id, font=font, fill=(150, 155, 162))
    return canvas


def main():
    args = [a for a in sys.argv[1:]]
    do_push = "push" in args
    args = [a for a in args if a != "push"]
    profile_name = args[0] if len(args) > 0 else None
    page_index = int(args[1]) if len(args) > 1 else 0

    cfg = Config(Config.load().data)  # current/default config
    profile = None
    if profile_name:
        for p in cfg.profiles:
            if p.get("name") == profile_name:
                profile = p
    page = cfg.page(page_index, profile)
    items = page.get("items", {})

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "preview_home.png")
    montage(items).save(out)
    print(f"Wrote montage: {out}  (page '{page.get('name')}')")

    if do_push:
        from dock.device import AKP03
        dock = AKP03().open()
        dock.set_brightness(cfg.brightness)
        for i, key_id in enumerate(LCD_KEYS):
            face = render_face(items[key_id]) if key_id in items else render_face({})
            dock.set_key_pil(i, face)
        dock.flush()
        dock.close()
        print("Pushed page to device.")


if __name__ == "__main__":
    main()
