"""Render key faces (color + icon/emoji + label) to PIL images for the LCD keys."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

import colorsys
import math

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

KEY_SIZE = (88, 88)        # native per-key tile (~88; bigger spills into neighbour keys)
DEFAULT_BG = "#23272e"
DEFAULT_FG = "#ffffff"

_TEXT_FONTS = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
_BOLD_FONTS = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
_EMOJI_FONT = "C:/Windows/Fonts/seguiemj.ttf"


@lru_cache(maxsize=64)
def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for p in (_BOLD_FONTS if bold else _TEXT_FONTS):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


@lru_cache(maxsize=16)
def _emoji_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    if os.path.exists(_EMOJI_FONT):
        try:
            # Segoe UI Emoji ships fixed bitmap strikes; 109 is a valid PPEM.
            return ImageFont.truetype(_EMOJI_FONT, size)
        except OSError:
            return None
    return None


def parse_color(c: Optional[str], fallback: str = DEFAULT_BG) -> Tuple[int, int, int]:
    c = (c or fallback).strip()
    if c.startswith("#"):
        c = c[1:]
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except (ValueError, IndexError):
        return (35, 39, 46)


def _looks_like_path(s: str) -> bool:
    return ("/" in s or "\\" in s or s.lower().endswith(
        (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".ico"))) and os.path.exists(s)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:2]


@lru_cache(maxsize=4096)
def emoji_image(glyph: str, target: int = 44) -> Optional[Image.Image]:
    """A single color emoji cropped to its ink box and scaled so its long side ≈ target px
    (transparent RGBA). None if the emoji font is unavailable or the glyph is empty.

    Color emoji are bitmap glyphs that DON'T scale with a Qt font's point size, so the picker
    renders them through this (PIL, embedded_color) and shows them as icons instead of text.
    """
    font = _emoji_font(109)                  # Segoe UI Emoji is bitmap; native strike is 109px
    if font is None:
        return None
    try:
        # Big canvas + top-left anchor: variation-selector emoji (…+FE0F like 🎙️/⚙️)
        # mis-center with anchor="mm" and get clipped off the edge. "la" + the crop below
        # recenter by the actual ink box, so nothing is lost.
        tmp = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        d.text((24, 24), glyph, font=font, anchor="la", embedded_color=True)
        bbox = tmp.getbbox()
        if not bbox:
            return None
        tmp = tmp.crop(bbox)
        scale = target / max(tmp.width, tmp.height)
        return tmp.resize((max(1, int(tmp.width * scale)), max(1, int(tmp.height * scale))),
                          Image.LANCZOS)
    except (OSError, ValueError):
        return None


def _draw_emoji(img: Image.Image, glyph: str, cx: int, cy: int, target: int,
                max_box: Optional[Tuple[int, int]] = None) -> bool:
    """Draw a color emoji centered at (cx, cy). Returns False if unavailable.

    `max_box` (max_w, max_h) clamps the glyph so it can NEVER overflow/clip the tile — the
    glyph is scaled down to fit the box (aspect preserved) before being pasted.
    """
    em = emoji_image(glyph, target)
    if em is None:
        return False
    if max_box is not None:
        mw, mh = max_box
        if em.width > mw or em.height > mh:
            s = min(mw / em.width, mh / em.height)
            em = em.resize((max(1, int(em.width * s)), max(1, int(em.height * s))), Image.LANCZOS)
    img.paste(em, (cx - em.width // 2, cy - em.height // 2), em)
    return True


def effective_fit(item: Dict[str, Any]) -> str:
    """'cover' (fill the key) or 'contain' (small, centered). Default: images fill, emoji don't."""
    f = item.get("fit")
    if f in ("cover", "contain"):
        return f
    icon = (item.get("icon") or "").strip()
    return "cover" if _looks_like_path(icon) else "contain"


def render_face(item: Dict[str, Any], size: Optional[Tuple[int, int]] = None,
                show_label: bool = True) -> Image.Image:
    """Render a binding's visual face. `item` may have label / icon / color / text_color."""
    if size is None:
        size = KEY_SIZE                          # read the CURRENT (calibrated) module value
    bg = parse_color(item.get("color"), DEFAULT_BG)
    if item.get("text_color"):
        fg = parse_color(item.get("text_color"), DEFAULT_FG)
    else:
        # auto-contrast: dark text on light keys, white on dark — so labels never vanish.
        lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        fg = (24, 26, 30) if lum > 140 else parse_color(DEFAULT_FG)
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    w, h = size

    icon = (item.get("icon") or "").strip()
    label = (item.get("label") or "").strip() if show_label else ""
    has_icon = bool(icon)
    has_label = bool(label)

    fit = effective_fit(item)

    def _label_overlay():
        nonlocal img, draw
        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle([0, h - 18, w, h], fill=(0, 0, 0, 150))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        font = _font(12)
        lines = _wrap(draw, label, font, w - 4)
        draw.text((w // 2, h - 9), lines[-1] if lines else label, font=font, fill=fg, anchor="mm")

    # Custom image icon -> fill the key bounds. cover = crop to fill; contain = the WHOLE
    # image letterboxed (never crops a non-square PNG), padded with the background colour.
    if has_icon and _looks_like_path(icon):
        try:
            src = Image.open(icon).convert("RGB")
            if fit == "contain":
                src = ImageOps.pad(src, size, color=bg, centering=(0.5, 0.5))
            else:
                src = ImageOps.fit(src, size, Image.LANCZOS)
            img.paste(src, (0, 0))
            if has_label:
                _label_overlay()
            return img
        except (OSError, ValueError):
            pass

    # Emoji icon -> fill the key with a big glyph (cover), unless fit=="contain".
    if has_icon and not _looks_like_path(icon) and fit == "cover":
        band = 18 if has_label else 0                     # reserve the bottom label strip
        avail_h = h - band
        # Size off the SMALLER of width / available-height so a wide or tall glyph (or a
        # non-square calibrated tile) is never clipped; max_box is a hard clamp.
        target = int(min(w, avail_h) * 0.98)
        cy = avail_h // 2
        if _draw_emoji(img, icon, w // 2, cy, target, max_box=(w - 2, avail_h - 2)):
            if has_label:
                _label_overlay()
            return img

    icon_drawn = False
    if has_icon:
        icon_cy = int(h * 0.29) if has_label else h // 2
        target = int((h * 0.44) if has_label else (h * 0.62))
        if _looks_like_path(icon):
            try:
                src = Image.open(icon).convert("RGBA")
                src.thumbnail((target, target), Image.LANCZOS)
                img.paste(src, (w // 2 - src.width // 2, icon_cy - src.height // 2), src)
                icon_drawn = True
            except (OSError, ValueError):
                icon_drawn = False
        else:
            avail_h = (h - 18) if has_label else h
            icon_drawn = _draw_emoji(img, icon, w // 2, icon_cy, target,
                                     max_box=(w - 2, avail_h - 2))
        # If an emoji/icon failed, treat its text as a label fallback.
        if not icon_drawn and not has_label:
            label, has_label = icon, True

    if has_label:
        if icon_drawn:
            font = _font(12)
            lines = _wrap(draw, label, font, w - 4)
            # Center the label within the bottom band so nothing clips at the edge.
            band_top = int(h * 0.58)
            total = len(lines) * font.size + (len(lines) - 1)
            y = band_top + (h - band_top - total) // 2 + font.size // 2
            for ln in lines:
                draw.text((w // 2, y), ln, font=font, fill=fg, anchor="mm")
                y += font.size + 1
        else:
            # Center, larger; shrink font to fit up to 2 lines.
            for fs in (22, 19, 16, 14, 12):
                font = _font(fs)
                lines = _wrap(draw, label, font, w - 6)
                if all(draw.textlength(ln, font=font) <= w - 6 for ln in lines):
                    break
            total_h = len(lines) * (font.size + 2)
            y = (h - total_h) // 2 + font.size // 2
            for ln in lines:
                draw.text((w // 2, y), ln, font=font, fill=fg, anchor="mm")
                y += font.size + 2

    return img


def blank_face(color: str = DEFAULT_BG, size: Optional[Tuple[int, int]] = None) -> Image.Image:
    return Image.new("RGB", size or KEY_SIZE, parse_color(color))


def calib_pattern(size) -> Image.Image:
    """A centring + orientation target for the display calibrator.

    `size` is (w, h) — or a bare int for a square tile. The pattern is deliberately NOT
    symmetric so the axis mapping is self-evident on the device:
      * a CYAN band marks the TOP, a RED band marks the BOTTOM (is "down" really down?),
      * a yellow border shows the tile's coverage (grow W/H until it reaches every edge),
      * a green crosshair + white ring shows the centre.
    """
    w, h = (size, size) if isinstance(size, int) else size
    img = Image.new("RGB", (w, h), (24, 52, 70))
    d = ImageDraw.Draw(img)
    band = max(4, h // 7)
    d.rectangle([0, 0, w - 1, band], fill=(0, 190, 210))            # TOP = cyan
    d.rectangle([0, h - 1 - band, w - 1, h - 1], fill=(220, 40, 40))  # BOTTOM = red
    cx, cy = w / 2.0, h / 2.0
    d.line([(cx, 0), (cx, h)], fill=(0, 255, 170), width=2)
    d.line([(0, cy), (w, cy)], fill=(0, 255, 170), width=2)
    r = min(w, h) * 0.28
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255), width=3)
    d.rectangle([0, 0, w - 1, h - 1], outline=(255, 210, 0))
    return img


def press_effect(img: Image.Image) -> Image.Image:
    """A 'pressed' variant of a face: a soft brighten + accent border (key-press feedback)."""
    base = img.convert("RGB")
    # blend toward white (won't clip already-light faces like a multiply would), + 2px border.
    out = Image.blend(base, Image.new("RGB", base.size, (255, 255, 255)), 0.22)
    d = ImageDraw.Draw(out)
    w, h = out.size
    d.rectangle([0, 0, w - 1, h - 1], outline=(61, 139, 255), width=2)
    return out


def _bg_sample(face: Image.Image) -> Tuple[int, int, int]:
    """Pick a fill colour for exposed borders by sampling the face's four corners."""
    w, h = face.size
    pts = [(1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)]
    cols = []
    for p in pts:
        c = face.getpixel(p)
        cols.append(c[:3] if isinstance(c, tuple) else (c, c, c))
    return tuple(int(sorted(c[i] for c in cols)[2]) for i in range(3))  # type: ignore[return-value]


def _scaled_face(face: Image.Image, s: float, bg: Tuple[int, int, int]) -> Image.Image:
    """Scale `face` about its centre by `s`; shrink letterboxes with `bg`, grow crops to size."""
    w, h = face.size
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    scaled = face.resize((nw, nh), Image.LANCZOS)
    if s <= 1.0:
        out = Image.new("RGB", (w, h), bg)
        out.paste(scaled, ((w - nw) // 2, (h - nh) // 2))
        return out
    left, top = (nw - w) // 2, (nh - h) // 2
    return scaled.crop((left, top, left + w, top + h))


def _translate_face(face: Image.Image, dx: float, dy: float,
                    bg: Tuple[int, int, int]) -> Image.Image:
    if not dx and not dy:
        return face.copy()
    out = Image.new("RGB", face.size, bg)
    out.paste(face, (int(round(dx)), int(round(dy))))
    return out


def _vsquash(face: Image.Image, sy: float, bg: Tuple[int, int, int]) -> Image.Image:
    """Squash vertically (keep width), anchored to the bottom — an 'impact' on landing."""
    w, h = face.size
    nh = max(1, round(h * sy))
    out = Image.new("RGB", (w, h), bg)
    out.paste(face.resize((w, nh), Image.LANCZOS), (0, h - nh))
    return out


def _rotate_face(face: Image.Image, deg: float, bg: Tuple[int, int, int]) -> Image.Image:
    return face.rotate(deg, resample=Image.BICUBIC, fillcolor=bg)


def _glow(face: Image.Image, g: float) -> Image.Image:
    if g <= 0:
        return face
    return Image.blend(face, Image.new("RGB", face.size, (255, 255, 255)), g)


# --- press-animation styles: each maps a face -> a list of 60x60 frames ---------
PRESS_BOUNCE = (0.84, 0.74, 0.88, 1.10, 1.03, 0.98, 1.0)
PRESS_GLOW = (0.12, 0.18, 0.11, 0.05, 0.0, 0.0, 0.0)


def _anim_bounce(face, bg):
    """Squash-and-stretch: press in, springy overshoot, settle."""
    return [_glow(_scaled_face(face, s, bg), g) for s, g in zip(PRESS_BOUNCE, PRESS_GLOW)]


def _anim_jump(face, bg):
    """macOS-Dock style: a smooth, slow hop that lifts toward the top of the key.

    The icon NEVER clips: the upward travel is bounded by the headroom that opens up as
    the icon shrinks, so the top edge always stays on-screen while a gap grows below it
    (which is what reads as 'jumping up'). Gravity easing + many frames keeps it fluid.
    """
    h = face.size[1]

    def hop(n, s_min):
        out = []
        for i in range(n):
            t = i / (n - 1)
            a = 4.0 * t * (1.0 - t)           # 0 -> 1 (apex) -> 0, slow near the top
            s = 1.0 - (1.0 - s_min) * a
            f = _scaled_face(face, s, bg) if s < 0.999 else face
            top_margin = (h - h * s) / 2.0    # empty space above the centred, shrunk icon
            dy = -top_margin * a              # rise into exactly that headroom: top stays >= 0
            out.append(_translate_face(f, 0, dy, bg))
        return out

    return hop(20, 0.64) + hop(14, 0.82)[1:]  # a tall hop, then a smaller settle hop


def _anim_pop(face, bg):
    """Quick scale-up flash and back."""
    seq = ((1.0, 0.10), (1.18, 0.16), (1.12, 0.07), (1.04, 0.0), (1.0, 0.0))
    return [_glow(_scaled_face(face, s, bg), g) for s, g in seq]


def _anim_pulse(face, bg):
    """A brightness pulse — no movement, subtle."""
    return [_glow(face, g) for g in (0.0, 0.12, 0.22, 0.30, 0.22, 0.12, 0.04, 0.0)]


def _anim_shake(face, bg):
    """A quick horizontal wiggle."""
    return [_translate_face(face, dx, 0, bg) for dx in (0, 5, -5, 4, -4, 2, -2, 1, 0)]


def _anim_spin(face, bg):
    """A full 360 spin of the icon."""
    return [_rotate_face(face, d, bg) for d in (0, 45, 90, 135, 180, 225, 270, 315, 360)]


def _anim_sink(face, bg):
    """A physical key-press feel: sink in and ease back, no overshoot."""
    seq = ((0.93, 0.10), (0.87, 0.15), (0.84, 0.10), (0.88, 0.04), (0.94, 0.0), (1.0, 0.0))
    return [_glow(_scaled_face(face, s, bg), g) for s, g in seq]


def _anim_flash(face, bg):
    """The classic brighten + accent-border blink."""
    return [press_effect(face), _glow(face, 0.12), face]


# ---- extra dynamic helpers -----------------------------------------------------
def _scale_xy(face, sx, sy, bg):
    """Non-uniform scale about the centre (used for flips/squash)."""
    w, h = face.size
    nw, nh = max(1, round(w * sx)), max(1, round(h * sy))
    out = Image.new("RGB", (w, h), bg)
    out.paste(face.resize((nw, nh), Image.LANCZOS), ((w - nw) // 2, (h - nh) // 2))
    return out


def _tint(face, rgb, alpha):
    if alpha <= 0:
        return face.convert("RGB")
    return Image.blend(face.convert("RGB"), Image.new("RGB", face.size, rgb), min(1.0, alpha))


def _rgb_split(face, off):
    r, g, b = face.convert("RGB").split()
    return Image.merge("RGB", (ImageChops.offset(r, off, 0), g, ImageChops.offset(b, -off, 0)))


def _ring(face, radius, alpha, color=(255, 255, 255), width=3):
    w, h = face.size
    base = face.convert("RGBA")
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cx, cy = w / 2, h / 2
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
              outline=color + (int(alpha),), width=width)
    return Image.alpha_composite(base, ov).convert("RGB")


# ---- extra dynamic press animations -------------------------------------------
def _anim_flip(face, bg):
    """A horizontal card-flip (squash the width to a sliver and back), twice."""
    out = []
    n = 16
    for i in range(n):
        sx = abs(math.cos(i / (n - 1) * 2 * math.pi))
        f = _scale_xy(face, max(0.05, sx), 1.0, bg)
        if sx < 0.25:
            f = _glow(f, 0.25)                       # highlight as it passes edge-on
        out.append(f)
    return out


def _anim_flipv(face, bg):
    """A vertical flip."""
    out = []
    n = 14
    for i in range(n):
        sy = abs(math.cos(i / (n - 1) * math.pi))
        out.append(_scale_xy(face, 1.0, max(0.05, sy), bg))
    return out


def _anim_swing(face, bg):
    """A pendulum swing that settles."""
    return [_rotate_face(face, a, bg)
            for a in (0, -15, -22, -16, -4, 9, 16, 11, 2, -6, -2, 0)]


def _anim_wobble(face, bg):
    """Jelly wobble: rotation and scale combined."""
    seq = [(0, 1.0), (-13, 1.09), (10, 0.94), (-7, 1.05), (4, 0.98), (-2, 1.01), (0, 1.0)]
    return [_scaled_face(_rotate_face(face, a, bg), s, bg) for a, s in seq]


def _anim_zoom(face, bg):
    """Zoom-blast: lunges toward you with a flash, then snaps back."""
    seq = [(1.0, 0.0), (1.3, 0.12), (1.7, 0.22), (2.2, 0.34), (1.5, 0.16), (1.0, 0.0)]
    return [_glow(_scaled_face(face, s, bg), g) for s, g in seq]


def _anim_drop(face, bg):
    """Drops in from above and bounces to rest."""
    dys = (-46, -34, -22, -10, 0, -7, -2, -5, 0, -2, 0)
    return [_translate_face(face, 0, dy, bg) for dy in dys]


def _anim_heartbeat(face, bg):
    """A double-thump pulse."""
    seq = [(1.0, 0.06), (1.17, 0.18), (1.02, 0.04), (1.15, 0.16), (1.0, 0.02), (1.0, 0.0)]
    return [_glow(_scaled_face(face, s, bg), g) for s, g in seq]


def _anim_ripple(face, bg):
    """A water-ripple ring expands from the centre."""
    out = []
    n = 11
    for i in range(n):
        t = i / (n - 1)
        out.append(_ring(face, int(t * 42), 200 * (1 - t), width=3))
    out.append(face)
    return out


def _anim_colorflash(face, bg):
    """Flashes a cool accent colour over the face."""
    return [_tint(face, (61, 139, 255), a) for a in (0.0, 0.4, 0.28, 0.16, 0.06, 0.0)]


def _anim_glitch(face, bg):
    """A digital RGB-split glitch jitter."""
    out = []
    for off in (0, 4, -3, 5, -2, 3, -1, 0):
        out.append(face if off == 0 else _rgb_split(face, off))
    return out


def _anim_sparkle(face, bg):
    """Little twinkles pop across the face."""
    pts = [(13, 15), (47, 17), (19, 45), (42, 43), (31, 9), (30, 50)]
    out = []
    n = 9
    for i in range(n):
        t = i / (n - 1)
        f = face.convert("RGBA")
        ov = Image.new("RGBA", f.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for j, (x, y) in enumerate(pts):
            ph = t - j * 0.11
            a = math.sin(ph * math.pi) if 0 <= ph <= 1 else 0
            if a > 0:
                v = int(255 * a)
                d.line([(x - 4, y), (x + 4, y)], fill=(255, 255, 255, v), width=1)
                d.line([(x, y - 4), (x, y + 4)], fill=(255, 255, 255, v), width=1)
        out.append(Image.alpha_composite(f, ov).convert("RGB"))
    return out


def _anim_neon(face, bg):
    """A rainbow neon border races around the key."""
    out = []
    n = 12
    for i in range(n):
        hue = (i / n) % 1.0
        r, g, b = (int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.9, 1.0))
        f = face.convert("RGB").copy()
        d = ImageDraw.Draw(f)
        for wdt in range(3):
            d.rectangle([wdt, wdt, 59 - wdt, 59 - wdt], outline=(r, g, b))
        out.append(f)
    out.append(face)
    return out


def _anim_squash(face, bg):
    """Anticipation squash & stretch (wide-short then tall-thin then settle)."""
    seq = [(1.0, 1.0), (1.18, 0.84), (0.86, 1.16), (1.08, 0.95), (0.97, 1.02), (1.0, 1.0)]
    return [_scale_xy(face, sx, sy, bg) for sx, sy in seq]


def _anim_spin3d(face, bg):
    """A faster full spin with a mid-spin brightness kick."""
    out = []
    n = 12
    for i in range(n):
        deg = 360 * i / (n - 1)
        f = _rotate_face(face, deg, bg)
        out.append(_glow(f, 0.18) if 120 < deg < 240 else f)
    return out


PRESS_ANIMS = {
    "bounce": _anim_bounce, "jump": _anim_jump, "pop": _anim_pop, "pulse": _anim_pulse,
    "shake": _anim_shake, "spin": _anim_spin, "sink": _anim_sink, "flash": _anim_flash,
    "flip": _anim_flip, "flipv": _anim_flipv, "swing": _anim_swing, "wobble": _anim_wobble,
    "zoom": _anim_zoom, "drop": _anim_drop, "heartbeat": _anim_heartbeat, "ripple": _anim_ripple,
    "colorflash": _anim_colorflash, "glitch": _anim_glitch, "sparkle": _anim_sparkle,
    "neon": _anim_neon, "squash": _anim_squash, "spin3d": _anim_spin3d,
}
PRESS_ANIM_ORDER = [
    "bounce", "jump", "pop", "drop", "squash", "wobble", "swing", "pulse", "heartbeat",
    "shake", "glitch", "flip", "flipv", "spin", "spin3d", "zoom", "ripple", "sparkle",
    "neon", "colorflash", "sink", "flash",
]
PRESS_ANIM_LABELS = {
    "bounce": "Bounce", "jump": "Jump (macOS)", "pop": "Pop", "drop": "Drop in",
    "squash": "Squash & stretch", "wobble": "Wobble", "swing": "Swing", "pulse": "Pulse",
    "heartbeat": "Heartbeat", "shake": "Shake", "glitch": "Glitch", "flip": "Flip",
    "flipv": "Flip vertical", "spin": "Spin", "spin3d": "Spin+", "zoom": "Zoom blast",
    "ripple": "Ripple", "sparkle": "Sparkle", "neon": "Neon border", "colorflash": "Colour flash",
    "sink": "Press-in", "flash": "Flash",
}


def press_frames(face: Image.Image, name: str = "bounce") -> list[Image.Image]:
    """Frames for a key-press animation; `name` selects the style (see PRESS_ANIMS)."""
    face = face.convert("RGB")
    bg = _bg_sample(face)
    return PRESS_ANIMS.get(name, _anim_bounce)(face, bg)


def _ease_io(t):
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2     # easeInOutCubic


def page_swipe_frames(old_faces, new_faces, direction, frames=9):
    """A smartphone-style horizontal page swipe across the 2x3 key grid.

    old_faces / new_faces: 6 RGB 60x60 key images each (row-major: 0-2 top, 3-5 bottom).
    direction: +1 = next (new slides in from the right), -1 = prev (from the left).
    Returns `frames` steps; each step is a list of 6 faces (row-major) to push to the keys.
    """
    w, h = KEY_SIZE
    rev = direction < 0
    old = [f.convert("RGB") for f in old_faces]
    new = [f.convert("RGB") for f in new_faces]

    def strip(row_old, row_new):
        seq = (row_new + row_old) if rev else (row_old + row_new)       # 6 images wide
        s = Image.new("RGB", (w * 6, h), (0, 0, 0))
        for i, img in enumerate(seq):
            s.paste(img, (i * w, 0))
        return s

    rows = (strip(old[0:3], new[0:3]), strip(old[3:6], new[3:6]))
    span = 3 * w                                                        # one page width
    out = []
    for fr in range(frames):
        t = _ease_io(fr / (frames - 1))
        p = int((1 - t) * span) if rev else int(t * span)
        faces = []
        for row_strip in rows:
            for c in range(3):
                x = p + c * w
                faces.append(row_strip.crop((x, 0, x + w, h)))
        out.append(faces)
    return out


def slice_fullscreen(path: str, dest_dir: str, tag: str = "fs", gap: int = 22):
    """Slice one image across the 2x3 LCD grid -> 6 tile paths (key1..key6, row-major).

    `gap` approximates the physical bezel gap so the picture looks continuous across keys.
    """
    os.makedirs(dest_dir, exist_ok=True)
    kw, kh = KEY_SIZE
    total = (3 * kw + 2 * gap, 2 * kh + gap)
    # pad (contain), not fit (cover): show the whole image; never crop a non-square one.
    src = ImageOps.pad(Image.open(path).convert("RGB"), total, color=(0, 0, 0),
                       centering=(0.5, 0.5))
    paths = []
    for r in range(2):
        for c in range(3):
            x, y = c * (kw + gap), r * (kh + gap)
            tile = src.crop((x, y, x + kw, y + kh))
            p = os.path.join(dest_dir, f"_{tag}_{r}{c}.png")
            tile.save(p)
            paths.append(p)
    return paths
