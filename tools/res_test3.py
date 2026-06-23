"""Final native-size calibration: the device anchors the image at a CORNER, so when our
image is smaller than the cell the content drifts off-centre. Each key gets a CENTERED
crosshair + ring + full-bleed border. The size whose ring sits DEAD CENTRE of the cell
(equal margins, border fully visible) is the true native resolution.

Run with the AjazzDock app CLOSED. Relaunch afterwards.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFont          # noqa: E402
from dock.device import AKP03                          # noqa: E402

SIZES = [100, 104, 106, 108, 110, 112]                 # one per key


def card(s: int, label: str) -> Image.Image:
    img = Image.new("RGB", (s, s), (18, 42, 58))
    d = ImageDraw.Draw(img)
    c = s / 2.0
    d.line([(c, 0), (c, s)], fill=(0, 255, 170), width=2)         # centred crosshair
    d.line([(0, c), (s, c)], fill=(0, 255, 170), width=2)
    r = s * 0.24
    d.ellipse([c - r, c - r, c + r, c + r], outline=(255, 255, 255), width=3)  # centred ring
    d.rectangle([0, 0, s - 1, s - 1], outline=(255, 200, 0))      # full-bleed border
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", max(11, s // 7))
    except OSError:
        font = ImageFont.load_default()
    d.text((4, 2), label, fill=(255, 80, 200), font=font)
    return img


def to_jpeg(img: Image.Image) -> bytes:
    img = img.transpose(Image.ROTATE_270)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, subsampling=0)
    return buf.getvalue()


def main() -> int:
    if not AKP03.is_present():
        print("AKP03 NOT found. App still holding it?")
        return 1
    dev = AKP03().open()
    try:
        dev.set_brightness(85)
        for key, s in enumerate(SIZES):
            dev.set_key_image(key, to_jpeg(card(s, str(s))))
            print(f"  key{key + 1}: {s}")
        dev.flush()
    finally:
        dev.close()
    print("\nLayout: 100 104 106 / 108 110 112")
    print("Which key has the WHITE RING dead-centre (equal margins) AND its yellow border fully visible?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
