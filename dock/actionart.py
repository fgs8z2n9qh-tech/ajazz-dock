"""Custom, on-brand line-art icons for the action picker (instead of generic OS emoji).

`action_art(type, size)` returns a crisp PIL RGBA glyph drawn in the app's mint accent, in a
consistent rounded line-art style — so the configurator's action grid looks designed, not clip-art.
"""
from __future__ import annotations

import math
from typing import Optional

from PIL import Image, ImageDraw

from . import tokens as _T


def _hex_rgb(h: str):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


ACCENT = (53, 224, 138)        # mint (default; action_art uses the live theme accent below)
INK = (214, 224, 232)          # light neutral
DIM = (150, 160, 172)
RED = (236, 78, 70)
AMBER = (245, 188, 50)
BLUE = (90, 150, 255)
GREEN = (76, 200, 120)
SS = 4                          # supersample


def action_art(t: str, size: int = 64, color: Optional[str] = None) -> Optional[Image.Image]:
    S = size * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = S / 100.0
    lw = max(3, int(S * 0.072))
    # The glyph's primary stroke. Defaults to the live theme accent (mint) — used on the device
    # key faces — but the sidebar passes a neutral so the action rail stays calm and the brand
    # accent reads only where it means something (selection / active state).
    ACCENT = _hex_rgb(color) if color else _hex_rgb(_T.ACCENT)

    def P(pts):
        return [(x * u, y * u) for x, y in pts]

    def cap(x, y, r, fill):
        d.ellipse([x * u - r, y * u - r, x * u + r, y * u + r], fill=fill)

    def line(pts, w=None, fill=ACCENT, caps=True):
        w = w or lw
        d.line(P(pts), fill=fill, width=w, joint="curve")
        if caps:
            cap(pts[0][0], pts[0][1], w / 2, fill)
            cap(pts[-1][0], pts[-1][1], w / 2, fill)

    def rrect(x0, y0, x1, y1, rad, w=None, fill=None, outline=ACCENT):
        d.rounded_rectangle([x0 * u, y0 * u, x1 * u, y1 * u], radius=rad * u,
                            width=(w or lw), outline=outline, fill=fill)

    def circ(cx, cy, r, w=None, fill=None, outline=ACCENT):
        d.ellipse([(cx - r) * u, (cy - r) * u, (cx + r) * u, (cy + r) * u],
                  width=(w or lw), outline=outline, fill=fill)

    def dot(cx, cy, r, fill=ACCENT):
        d.ellipse([(cx - r) * u, (cy - r) * u, (cx + r) * u, (cy + r) * u], fill=fill)

    def poly(pts, fill=ACCENT):
        d.polygon(P(pts), fill=fill)

    def arrow(x0, y0, x1, y1, head=11, fill=ACCENT):
        line([(x0, y0), (x1, y1)], fill=fill)
        ang = math.atan2(y1 - y0, x1 - x0)
        for s in (+1, -1):
            a = ang + math.pi + s * 0.5
            line([(x1, y1), (x1 + math.cos(a) * head, y1 + math.sin(a) * head)], fill=fill)

    if t in ("open", "launch", "run"):
        rrect(18, 40, 60, 82, 9)
        arrow(48, 52, 84, 18, fill=ACCENT)
    elif t == "hotkey":                          # a little keyboard
        for x0 in (18, 42, 66):
            rrect(x0, 32, x0 + 16, 50, 4)
        rrect(26, 56, 74, 72, 4)                 # spacebar
    elif t == "text":
        line([(50, 24), (50, 74)])
        line([(34, 24), (66, 24)])              # serif top
        line([(40, 74), (60, 74)])              # serif bottom
    elif t == "media":
        circ(50, 50, 32)
        poly([(43, 38), (43, 62), (64, 50)])
    elif t == "volume":
        poly([(22, 42), (38, 42), (52, 28), (52, 72), (38, 58), (22, 58)])
        for r in (10, 18):
            d.arc([(58 - r) * u, (50 - r) * u, (58 + r) * u, (50 + r) * u], -55, 55, fill=ACCENT, width=lw)
    elif t == "sound":                           # soundboard -> a music note
        dot(38, 70, lw * 1.3)
        dot(64, 64, lw * 1.3)
        line([(45, 70), (45, 30)], caps=False)
        line([(71, 64), (71, 26)], caps=False)
        line([(45, 30), (71, 26)], w=int(lw * 1.1))
    elif t == "appvolume":                       # mixer faders
        for x, ky in ((38, 42), (62, 60)):
            line([(x, 24), (x, 78)], w=max(3, int(lw * 0.7)), fill=DIM)
            dot(x, ky, lw * 1.25, ACCENT)
    elif t == "mic":
        rrect(40, 22, 60, 58, 10)
        d.arc([30 * u, 36 * u, 70 * u, 70 * u], 20, 160, fill=ACCENT, width=lw)
        line([(50, 70), (50, 80)])
        line([(40, 82), (60, 82)])
    elif t == "discord":
        rrect(20, 26, 80, 66, 14)
        poly([(34, 64), (34, 80), (50, 66)])
        for cx in (40, 50, 60):
            dot(cx, 46, lw * 0.5, ACCENT)
    elif t == "substance":
        line([(26, 74), (50, 50)], w=int(lw * 1.4))
        poly([(48, 44), (70, 22), (78, 30), (56, 52)])
        line([(22, 78), (30, 70)], fill=AMBER)
    elif t == "quick":
        poly([(56, 16), (34, 54), (50, 54), (44, 84), (68, 44), (52, 44)], fill=AMBER)
    elif t == "system":
        circ(50, 52, 28)
        line([(50, 24), (50, 50)], fill=ACCENT)
        d.rectangle([47 * u, 20 * u, 53 * u, 30 * u], fill=(0, 0, 0, 0))
    elif t == "monitor":
        rrect(20, 26, 80, 64, 7)
        line([(40, 76), (60, 76)])
        line([(50, 64), (50, 76)])
    elif t == "smartlight":
        circ(50, 40, 22, outline=AMBER)
        line([(42, 64), (58, 64)], fill=AMBER)
        line([(44, 72), (56, 72)], fill=AMBER)
        for a in range(0, 360, 45):              # little rays
            x, y = 50 + math.cos(math.radians(a)) * 30, 40 + math.sin(math.radians(a)) * 30
            if y < 56:
                dot(x, y, lw * 0.4, AMBER)
    elif t == "rgbscene":
        dot(40, 44, 15, RED)
        dot(60, 44, 15, GREEN)
        dot(50, 60, 15, BLUE)
    elif t == "obs":                             # broadcast: record dot + signal waves
        dot(50, 50, 9, RED)
        for r in (18, 28):
            d.arc([(50 - r) * u, (50 - r) * u, (50 + r) * u, (50 + r) * u], -48, 48, fill=ACCENT, width=lw)
            d.arc([(50 - r) * u, (50 - r) * u, (50 + r) * u, (50 + r) * u], 132, 228, fill=ACCENT, width=lw)
    elif t == "page":
        poly([(28, 18), (62, 18), (74, 30), (74, 82), (28, 82)], fill=None)
        rrect(28, 18, 74, 82, 6)
        arrow(40, 50, 64, 50, head=9)
    elif t == "folder":
        poly([(18, 34), (40, 34), (48, 42), (82, 42), (82, 74), (18, 74)], fill=None)
        d.line(P([(18, 34), (40, 34), (48, 42), (82, 42), (82, 74), (18, 74), (18, 34)]),
               fill=ACCENT, width=lw, joint="curve")
    elif t == "profile":
        circ(50, 38, 16)
        d.arc([26 * u, 56 * u, 74 * u, 104 * u], 180, 360, fill=ACCENT, width=lw)
    elif t == "brightness":
        circ(50, 50, 15, fill=None, outline=AMBER)
        for a in range(0, 360, 45):
            x0 = 50 + math.cos(math.radians(a)) * 24
            y0 = 50 + math.sin(math.radians(a)) * 24
            x1 = 50 + math.cos(math.radians(a)) * 34
            y1 = 50 + math.sin(math.radians(a)) * 34
            line([(x0, y0), (x1, y1)], fill=AMBER)
    elif t == "macro":
        rrect(34, 22, 78, 50, 6, outline=DIM)
        rrect(28, 36, 72, 64, 6, outline=DIM)
        rrect(22, 50, 66, 78, 6, outline=ACCENT)
    elif t == "toggle":                          # two states swapping into each other
        arrow(24, 36, 76, 36)
        arrow(76, 64, 24, 64, fill=DIM)
    elif t == "http":                            # a globe: meridians + parallels (webhook / API)
        circ(50, 50, 30)
        d.ellipse([(50 - 13) * u, (50 - 30) * u, (50 + 13) * u, (50 + 30) * u],
                  width=lw, outline=ACCENT)      # vertical meridian
        line([(20, 50), (80, 50)])
        line([(26, 32), (74, 32)], fill=DIM)
        line([(26, 68), (74, 68)], fill=DIM)
    elif t == "none":
        circ(50, 50, 30, outline=DIM)
        line([(31, 31), (69, 69)], fill=DIM)
    else:
        return None
    return im.resize((size, size), Image.LANCZOS)
