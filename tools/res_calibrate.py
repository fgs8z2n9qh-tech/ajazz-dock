"""Live display calibration GUI (v3).

The device's per-key cell turned out to be LARGER than expected and anchored to a corner,
so a too-small image leaves a black gap on two edges. This version gives you full control:

  * Fill size  -> grow until the WHOLE key is coloured (no black gap on any edge)
  * X / Y      -> position the icon dead-centre
  * Icon size  -> how big the icon is

Whatever the firmware does internally, you just dial these until it looks right. Close the
window when happy — the values print to the console and get baked into the render pipeline.

Run with the AjazzDock app CLOSED.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import Qt, QTimer                          # noqa: E402
from PySide6.QtGui import QFont                                # noqa: E402
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel,  # noqa: E402
                               QSlider, QCheckBox)
from PIL import Image, ImageDraw                               # noqa: E402

from dock.device import AKP03                                  # noqa: E402
from dock.images import emoji_image                            # noqa: E402

try:
    from dock.gui import QSS
except Exception:
    QSS = ""


def pattern(fill: int, dx: int, dy: int, scale: int, real: bool) -> Image.Image:
    img = Image.new("RGB", (fill, fill), (18, 44, 62))           # bg covers the whole image
    d = ImageDraw.Draw(img)
    cx, cy = fill / 2.0 + dx, fill / 2.0 + dy
    if real:
        em = emoji_image("🎮", max(8, int(fill * scale / 100)))
        if em is not None:
            img.paste(em, (int(cx - em.width / 2), int(cy - em.height / 2)), em)
    else:
        d.line([(cx, 0), (cx, fill)], fill=(0, 255, 170), width=2)
        d.line([(0, cy), (fill, cy)], fill=(0, 255, 170), width=2)
        r = fill * scale / 200.0
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255), width=3)
    d.rectangle([0, 0, fill - 1, fill - 1], outline=(255, 200, 0))   # image-edge guide
    return img


def to_jpeg(img: Image.Image) -> bytes:
    img = img.transpose(Image.ROTATE_270)
    b = io.BytesIO()
    img.save(b, format="JPEG", quality=88, subsampling=1)
    return b.getvalue()


class Cal(QWidget):
    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.fill, self.dx, self.dy, self.scale, self.real = 150, 0, 0, 60, False
        self.setWindowTitle("AjazzDock — Display calibration")
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(8)
        self.val = QLabel(objectName="display")
        self.val.setFont(QFont("Segoe UI", 14, QFont.DemiBold))
        v.addWidget(self.val)
        self._slider("Fill size — grow until the WHOLE key is filled (no black gap)", 90, 220, self.fill, "fill", v)
        self._slider("X offset — move the icon left / right", -80, 80, 0, "dx", v)
        self._slider("Y offset — move the icon up / down", -80, 80, 0, "dy", v)
        self._slider("Icon size", 20, 100, self.scale, "scale", v)
        chk = QCheckBox("Show a real emoji instead of the crosshair")
        chk.toggled.connect(lambda b: self._set("real", b))
        v.addWidget(chk)
        hint = QLabel("1) Grow Fill size until the whole key is blue with NO black gap on any edge.\n"
                      "2) Slide X / Y so the ring (or emoji) is dead-centre.\n"
                      "3) Set the icon size you like. Then close this window.", objectName="dim")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.setInterval(40)
        self._t.timeout.connect(self._push)
        self._refresh()
        self._push()

    def _slider(self, label, lo, hi, val, attr, parent):
        parent.addWidget(QLabel(label, objectName="dim"))
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.valueChanged.connect(lambda x, a=attr: self._set(a, x))
        parent.addWidget(s)

    def _set(self, attr, x):
        setattr(self, attr, x)
        self._refresh()
        self._t.start()

    def _refresh(self):
        self.val.setText(f"Fill = {self.fill}   X = {self.dx:+d}   Y = {self.dy:+d}   size = {self.scale}%")

    def _push(self):
        try:
            jb = to_jpeg(pattern(self.fill, self.dx, self.dy, self.scale, self.real))
            for k in range(6):
                self.dev.set_key_image(k, jb)
            self.dev.flush()
        except Exception as e:
            self.val.setText(f"device error: {e}")


def main() -> int:
    if not AKP03.is_present():
        print("AKP03 NOT found. Close the AjazzDock app first (it holds the device).")
        return 1
    app = QApplication([])
    if QSS:
        app.setStyleSheet(QSS)
    dev = AKP03().open()
    dev.set_brightness(85)
    w = Cal(dev)
    w.resize(450, 330)
    w.show()
    app.exec()
    try:
        dev.close()
    except Exception:
        pass
    print(f"\nFINAL CALIBRATION:  fill={w.fill}  dx={w.dx}  dy={w.dy}  scale={w.scale}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
