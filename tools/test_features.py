"""Verify the shortcut-recorder conversions and the full-screen image slicer."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402

app = QApplication([])

from dock.gui import hotkey_to_qseq, qseq_to_hotkey  # noqa: E402
from dock.actions import _normalize_hotkey  # noqa: E402
from dock.images import slice_fullscreen, render_face, KEY_SIZE  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

print("=== shortcut recorder conversions ===")
for combo in ("Ctrl+Shift+T", "Meta+E", "Alt+F4", "Ctrl+Alt+Del", "F5"):
    spec = qseq_to_hotkey(QKeySequence(combo))
    print(f"  recorded {combo:14s} -> stored '{spec}' -> keyboard '{_normalize_hotkey(spec)}'")
print("  load 'win+e' back into editor ->", hotkey_to_qseq("win+e").toString())

print("=== full-screen slice ===")
os.makedirs(ASSETS, exist_ok=True)
src = Image.new("RGB", (640, 420), (15, 20, 30))
d = ImageDraw.Draw(src)
for i in range(0, 640, 16):
    d.line([(i, 0), (i, 420)], fill=((i * 2) % 256, 120, 255 - ((i * 2) % 256)))
d.ellipse([170, 70, 470, 350], outline=(255, 255, 255), width=10)
d.text((250, 195), "FULLSCREEN", fill=(255, 255, 0))
src_path = os.path.join(ASSETS, "fs_src.png")
src.save(src_path)

tiles = slice_fullscreen(src_path, os.path.join(ASSETS, "_icons"), tag="t")
print(f"  produced {len(tiles)} tiles")

gap, (kw, kh) = 22, KEY_SIZE
W, H = 3 * kw + 2 * gap, 2 * kh + gap
big = Image.new("RGB", (W, H), (0, 0, 0))
for i, t in enumerate(tiles):
    r, c = divmod(i, 3)
    big.paste(render_face({"icon": t, "fit": "cover"}), (c * (kw + gap), r * (kh + gap)))
big.resize((W * 4, H * 4), Image.NEAREST).save(os.path.join(ASSETS, "fs_montage.png"))
print("  wrote assets/fs_montage.png (gaps simulate the device bezels)")
