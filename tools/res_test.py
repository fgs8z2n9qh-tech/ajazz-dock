"""On-device resolution probe: push a different SOURCE-resolution test card to each of the
6 LCD keys, so one photo reveals the panel's true native per-key resolution.

Each card has a 2px-pitch vertical grating (left, cyan) + horizontal grating (right, orange)
+ a green edge border + the source size label. Compare the keys: the largest size where the
fine lines still resolve into DISTINCT stripes (not a smear) ~ the native cell resolution.

Run with the AjazzDock app CLOSED (it holds the HID device). Leaves the cards on the dock so
you can photograph them; relaunch the app afterwards to restore your normal faces.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFont          # noqa: E402
from dock.device import AKP03                          # noqa: E402

SIZES = [60, 72, 84, 96, 108, 120]                     # one per key (host indices 0..5)


def card(s: int, label: str) -> Image.Image:
    img = Image.new("RGB", (s, s), (10, 10, 10))
    d = ImageDraw.Draw(img)
    half = s // 2
    for x in range(2, half):                           # left: vertical grating, 2px pitch
        if x % 2 == 0:
            d.line([(x, 2), (x, s - 3)], fill=(120, 210, 255))
    for y in range(2, s - 2):                           # right: horizontal grating, 2px pitch
        if y % 2 == 0:
            d.line([(half + 1, y), (s - 3, y)], fill=(255, 170, 90))
    d.rectangle([0, 0, s - 1, s - 1], outline=(0, 230, 120))   # edge border (full bleed)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", max(10, s // 5))
    except OSError:
        font = ImageFont.load_default()
    d.text((3, 1), label, fill=(255, 255, 255), font=font)
    return img


def to_jpeg(img: Image.Image) -> bytes:
    img = img.transpose(Image.ROTATE_270)              # device shows images rotated 90deg
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, subsampling=0)
    return buf.getvalue()


def main() -> int:
    if not AKP03.is_present():
        print("AKP03 NOT found (VID 0x0300/PID 0x3002). Is it plugged in? Is the app still holding it?")
        return 1
    dev = AKP03().open()
    try:
        dev.set_brightness(85)                          # visible for the photo (app restores from config later)
        for key, s in enumerate(SIZES):
            jpeg = to_jpeg(card(s, str(s)))
            dev.set_key_image(key, jpeg)
            print(f"  key{key + 1}: {s}x{s}  ({len(jpeg)} bytes JPEG)")
        dev.flush()
    finally:
        dev.close()
    print("\nSent. Photograph the dock now (one shot of all 6 keys), then relaunch AjazzDock to restore.")
    print("Key layout (top row L->R, bottom row L->R):  60  72  84 / 96 108 120")
    return 0


if __name__ == "__main__":
    sys.exit(main())
