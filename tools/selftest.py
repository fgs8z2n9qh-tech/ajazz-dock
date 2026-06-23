"""End-to-end hardware self-test for the AKP03E.

1. Opens + initializes the device.
2. Pushes 6 distinct numbered images to the LCD keys (proves the OUTPUT protocol
   and lets us check image orientation).
3. Listens for input events (proves the INPUT protocol, post-init).

Run: python tools/selftest.py [listen_seconds]
"""
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from dock.device import AKP03  # noqa: E402

COLORS = [(205, 45, 45), (40, 165, 70), (45, 95, 210),
          (210, 150, 30), (150, 45, 185), (30, 175, 175)]


def _font(size):
    for p in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_img(n):
    img = Image.new("RGB", (60, 60), COLORS[n - 1])
    d = ImageDraw.Draw(img)
    # White bar along the PRE-rotation TOP edge: reveals final orientation.
    d.rectangle([0, 0, 59, 9], fill=(255, 255, 255))
    d.text((30, 34), str(n), fill=(255, 255, 255), anchor="mm", font=_font(36))
    return img


def main():
    listen = float(sys.argv[1]) if len(sys.argv) > 1 else 45.0
    dock = AKP03()
    try:
        dock.open()
        print("Opened device. Initializing + setting brightness 70%...", flush=True)
        dock.set_brightness(70)
        print("Uploading numbered images to the 6 LCD keys...", flush=True)
        for n in range(1, 7):
            dock.set_key_pil(n - 1, make_img(n))
        dock.flush()
        print(">>> LOOK AT THE DEVICE: the 6 LCD keys should now show 1-6 on "
              "colored backgrounds. <<<", flush=True)
        print(f">>> Now press keys / buttons / turn + push knobs for {listen:.0f}s. <<<",
              flush=True)

        events = 0
        start = time.time()
        while time.time() - start < listen:
            ev = dock.read_event(timeout_ms=200)
            if ev:
                events += 1
                t = time.time() - start
                print(f"  t={t:6.2f}s  {ev.kind:<13} id={ev.input_id:<6} "
                      f"idx={ev.index} pressed={ev.pressed} delta={ev.delta} "
                      f"raw=0x{ev.raw_code:02x}", flush=True)
        print(f"\n===== {events} input events captured =====", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        dock.close()


if __name__ == "__main__":
    main()
