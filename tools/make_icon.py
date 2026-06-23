"""Generate assets/ajazzdock.ico from the tray glyph (multi-size for crisp display)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dock.iconart import icon_image  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "assets", "ajazzdock.ico")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img = icon_image(256)
    img.save(OUT, format="ICO",
             sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
