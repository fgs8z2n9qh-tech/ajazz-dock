"""Shared app-icon artwork (used by the GUI, the tray, and the .ico generator)."""
from __future__ import annotations

from PIL import Image, ImageDraw


def icon_image(size: int = 64) -> Image.Image:
    """A dock glyph: rounded slab with a 2x3 grid of lit keys (scales to any size)."""
    f = size / 64.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6 * f, 12 * f, 58 * f, 52 * f], radius=9 * f,
                        fill=(28, 32, 40, 255), outline=(70, 80, 95, 255), width=max(1, int(2 * f)))
    cols = [(61, 139, 255), (26, 161, 121), (200, 136, 31),
            (122, 60, 196), (192, 57, 43), (60, 64, 72)]
    i = 0
    for r in range(2):
        for c in range(3):
            x = 14 * f + c * 13 * f
            y = 19 * f + r * 15 * f
            d.rounded_rectangle([x, y, x + 10 * f, y + 11 * f], radius=3 * f, fill=cols[i])
            i += 1
    return img
