"""Shared app-icon artwork — the "Hexpad" glyph (used by the GUI, the tray, and the .ico generator).

The mark is the device itself: a 2×3 grid of gradient LCD keys above three encoder dots, on a dark
rounded slab. Rendered once at 256px and scaled, so every size stays crisp.
"""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw

_P = 256
# The shared spectrum the keys are cut from (blue → violet → pink → orange).
_SPECTRUM = [(0.0, (70, 150, 255)), (0.40, (150, 90, 235)),
             (0.70, (235, 70, 150)), (1.0, (255, 150, 60))]


def _rrect_mask(w: int, h: int, rad: int) -> Image.Image:
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=rad, fill=255)
    return m


def _lin_grad(w: int, h: int, stops, angle=45) -> Image.Image:
    base = Image.new("RGB", (w, h))
    px = base.load()
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    for y in range(h):
        for x in range(w):
            t = max(0.0, min(1.0, ((x / max(1, w)) * dx + (y / max(1, h)) * dy + 1) / 2.0))
            for i in range(len(stops) - 1):
                t0, c0 = stops[i]
                t1, c1 = stops[i + 1]
                if t0 <= t <= t1:
                    f = (t - t0) / max(1e-6, t1 - t0)
                    px[x, y] = tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
                    break
            else:
                px[x, y] = stops[-1][1]
    return base


@lru_cache(maxsize=1)
def _master() -> Image.Image:
    """The full-resolution Hexpad icon (256px), built once and cached."""
    P = _P
    ic = Image.new("RGBA", (P, P), (0, 0, 0, 0))
    ic.paste(_lin_grad(P, P, [(0, (26, 28, 36)), (1, (12, 13, 18))], 90),
             (0, 0), _rrect_mask(P, P, int(P * 0.22)))
    full = _lin_grad(P, P, _SPECTRUM, 55)                 # the keys are cut from one spectrum
    kw = kh = int(P * 0.205)
    gap = P * 0.04
    top = P * 0.13
    x0 = (P - (3 * kw + 2 * gap)) / 2
    for r in range(2):
        for c in range(3):
            x, y = int(x0 + c * (kw + gap)), int(top + r * (kh + gap))
            patch = full.crop((x, y, x + kw, y + kh))
            key = Image.new("RGBA", (kw, kh), (0, 0, 0, 0))
            key.paste(patch, (0, 0), _rrect_mask(kw, kh, int(kw * 0.28)))
            ic.alpha_composite(key, (x, y))
    d = ImageDraw.Draw(ic)                                # three encoder dots below the keys
    ky = top + 2 * kh + gap + P * 0.085
    rr = P * 0.052
    for c in range(3):
        cxk = x0 + c * (kw + gap) + kw / 2
        d.ellipse([cxk - rr, ky - rr, cxk + rr, ky + rr],
                  fill=(60, 66, 78), outline=(120, 130, 150), width=max(2, int(P * 0.012)))
        d.line([(cxk, ky - rr * 0.55), (cxk, ky)], fill=(205, 214, 228), width=max(2, int(P * 0.016)))
    return ic


def icon_image(size: int = 64) -> Image.Image:
    """The Hexpad app icon at any size (RGBA), scaled from the cached 256px master."""
    m = _master()
    if size == _P:
        return m.copy()
    return m.resize((max(1, size), max(1, size)), Image.LANCZOS)
