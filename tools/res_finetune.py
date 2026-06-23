"""Final fine-tune: clear the keys, then push a full-bleed fill + white border at six
sizes (one per key). The key whose white border is COMPLETE on all four sides (no dark
strip on the left/bottom, nothing cut off) is the exact native tile size. If one axis
closes before the other, the tile is non-square.

Run with the AjazzDock app CLOSED.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw, ImageFont                    # noqa: E402
from dock.device import AKP03                                  # noqa: E402

SIZES = [84, 86, 88, 90, 92, 94]                               # one per key


def card(s: int, label: str) -> Image.Image:
    img = Image.new("RGB", (s, s), (30, 120, 200))            # solid cyan fill
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s - 1, s - 1], outline=(255, 255, 255), width=2)   # full-bleed border
    d.rectangle([1, 1, s - 2, s - 2], outline=(255, 80, 200))             # 2nd border (1px in)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", int(s * 0.42))
    except OSError:
        font = ImageFont.load_default()
    d.text((s / 2, s / 2), label, fill=(0, 0, 0), anchor="mm", font=font)
    return img


def to_jpeg(img: Image.Image) -> bytes:
    img = img.transpose(Image.ROTATE_270)
    b = io.BytesIO()
    img.save(b, format="JPEG", quality=92, subsampling=0)
    return b.getvalue()


def main() -> int:
    if not AKP03.is_present():
        print("AKP03 NOT found. Close the AjazzDock app first.")
        return 1
    dev = AKP03().open()
    try:
        dev.set_brightness(88)
        dev.clear_all()
        dev.flush()
        for key, s in enumerate(SIZES):
            dev.set_key_image(key, to_jpeg(card(s, str(s))))
            print(f"  key{key + 1}: {s}")
        dev.flush()
    finally:
        dev.close()
    print("\nLayout: 84 86 88 / 90 92 94")
    print("Which key has the full white+pink border on ALL four sides, no dark strip, nothing cut?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
