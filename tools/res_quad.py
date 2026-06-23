"""Diagnostic: push a colour-quadrant card to every key to read EXACTLY how our image maps
to the physical cell (which part is shown, where the black gap is, per key).

Quadrants (in the sent image, before the pipeline's 90deg rotation):
  TL = red    TR = green
  BL = blue   BR = yellow
plus a white centre cross + white full-bleed border + corner dots.

From one photo we learn: which quadrants/colours are visible, where the dark gap falls, and
whether all 6 keys map the same. Run with the AjazzDock app CLOSED.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw                               # noqa: E402
from dock.device import AKP03                                  # noqa: E402

SIZE = 170                                                     # bigger than the cell on purpose


def card() -> Image.Image:
    s = SIZE
    h = s // 2
    img = Image.new("RGB", (s, s), (0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, h, h], fill=(230, 40, 40))              # TL red
    d.rectangle([h, 0, s, h], fill=(40, 200, 40))              # TR green
    d.rectangle([0, h, h, s], fill=(40, 90, 230))              # BL blue
    d.rectangle([h, h, s, s], fill=(235, 200, 40))             # BR yellow
    d.line([(s / 2, 0), (s / 2, s)], fill=(255, 255, 255), width=2)
    d.line([(0, s / 2), (s, s / 2)], fill=(255, 255, 255), width=2)
    d.rectangle([0, 0, s - 1, s - 1], outline=(255, 255, 255), width=2)
    for cx, cy in [(6, 6), (s - 7, 6), (6, s - 7), (s - 7, s - 7)]:
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(255, 255, 255))   # corner dots
    return img


def to_jpeg(img: Image.Image) -> bytes:
    img = img.transpose(Image.ROTATE_270)
    b = io.BytesIO()
    img.save(b, format="JPEG", quality=90, subsampling=0)
    return b.getvalue()


def main() -> int:
    if not AKP03.is_present():
        print("AKP03 NOT found. Close the AjazzDock app first.")
        return 1
    dev = AKP03().open()
    try:
        dev.set_brightness(90)
        jb = to_jpeg(card())
        for k in range(6):
            dev.set_key_image(k, jb)
        dev.flush()
    finally:
        dev.close()
    print(f"sent {SIZE}x{SIZE} quadrant card (R=TL G=TR B=BL Y=BR). Photograph one key clearly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
