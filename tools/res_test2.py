"""Pin down the EXACT native key resolution: each key gets a card with a 3px full-bleed
border + big size number. Read off the dock:
  * border forms a COMPLETE rectangle with a dark margin around it  -> card SMALLER than cell
  * border sits exactly at all four cell edges (no margin)          -> that size == native
  * border's bottom/right side is CUT OFF (missing)                 -> card BIGGER than cell

The largest size whose border is still fully visible ~ the native cell resolution.
Run with the AjazzDock app CLOSED. Relaunch the app afterwards to restore.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFont          # noqa: E402
from dock.device import AKP03                          # noqa: E402

SIZES = [112, 120, 128, 136, 144, 160]                 # one per key (host indices 0..5)


def card(s: int, label: str) -> Image.Image:
    img = Image.new("RGB", (s, s), (6, 6, 6))
    d = ImageDraw.Draw(img)
    for i in range(3):                                  # 3px full-bleed border at the very edge
        d.rectangle([i, i, s - 1 - i, s - 1 - i], outline=(0, 235, 255))
    # corner ticks (magenta) so a cut corner is unmistakable
    t = max(6, s // 9)
    for cx, cy, dx, dy in [(3, 3, 1, 1), (s - 4, 3, -1, 1), (3, s - 4, 1, -1), (s - 4, s - 4, -1, -1)]:
        d.line([(cx, cy), (cx + dx * t, cy)], fill=(255, 60, 200), width=3)
        d.line([(cx, cy), (cx, cy + dy * t)], fill=(255, 60, 200), width=3)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", int(s * 0.42))
    except OSError:
        font = ImageFont.load_default()
    d.text((s / 2, s / 2), label, fill=(255, 255, 255), anchor="mm", font=font)
    return img


def to_jpeg(img: Image.Image) -> bytes:
    img = img.transpose(Image.ROTATE_270)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, subsampling=0)
    return buf.getvalue()


def main() -> int:
    if not AKP03.is_present():
        print("AKP03 NOT found. Plugged in? App still holding it?")
        return 1
    dev = AKP03().open()
    try:
        dev.set_brightness(85)
        for key, s in enumerate(SIZES):
            dev.set_key_image(key, to_jpeg(card(s, str(s))))
            print(f"  key{key + 1}: {s}x{s}")
        dev.flush()
    finally:
        dev.close()
    print("\nLayout:  112 120 128 / 136 144 160")
    print("Find the largest number whose CYAN BORDER + all 4 magenta corners are fully on-screen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
