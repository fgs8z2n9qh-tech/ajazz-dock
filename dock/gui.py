"""Native PySide6 desktop app for the Ajazz AKP03 — no web tech.

A real Qt window + system tray that drives the verified backend
(dock.device / dock.actions / dock.controller) directly, in-process.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading

from PySide6.QtCore import (Qt, QObject, Signal, QTimer, QSize, QRect, QRectF, QPoint, QPointF,
                            QVariantAnimation, QEasingCurve, QAbstractAnimation,
                            QPropertyAnimation, QParallelAnimationGroup)
from PySide6.QtGui import (QPixmap, QImage, QIcon, QColor, QAction, QFont, QKeySequence,
                           QPainter, QPen, QLinearGradient)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PIL import Image
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QToolButton, QLineEdit,
    QComboBox, QSpinBox, QSlider, QColorDialog, QFileDialog, QPlainTextEdit, QGridLayout,
    QHBoxLayout, QVBoxLayout, QFormLayout, QGroupBox, QScrollArea, QSystemTrayIcon, QMenu,
    QSizePolicy, QFrame, QInputDialog, QMessageBox, QButtonGroup, QCheckBox, QKeySequenceEdit,
    QDialog, QListWidget, QListWidgetItem, QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
)

from . import autostart, backups
from . import tokens as T
from .config import Config, LCD_KEYS, config_dir, backups_dir
from .controller import DockController
from .iconart import icon_image
from .images import (render_face, slice_fullscreen, effective_fit, emoji_image,
                     PRESS_ANIM_ORDER, PRESS_ANIM_LABELS)
from .emoji_data import CATEGORIES

APP_TITLE = "AjazzDock"
IPC_NAME = "AjazzDock_ipc_v1"

# Hold the singleton mutex handle for the whole process lifetime (module global so it is never GC'd).
_SINGLETON_HANDLE = None


def _acquire_singleton() -> bool:
    """Return True iff we are the FIRST/only AjazzDock instance (Windows named mutex).

    A QLocalSocket probe-then-listen guard is a TOCTOU race: if autostart (--tray) and a manual
    launch start within the same window, BOTH can become primaries, BOTH open the (non-exclusive)
    HID device, and fight over the panel — which looks exactly like the calibration pattern
    'sticking'. An OS mutex is atomic, so only one process is ever primary.
    """
    global _SINGLETON_HANDLE
    try:
        import ctypes
        ERROR_ALREADY_EXISTS = 183
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, "Local\\AjazzDock_singleton_v1")
        if not handle:
            return True                       # can't create a mutex -> don't block startup
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        _SINGLETON_HANDLE = handle            # keep it alive for the process lifetime
        return True
    except Exception:
        return True                           # never let the guard itself prevent launching

ACTION_TYPES = ["none", "open", "hotkey", "text", "media", "volume", "mic", "sound", "discord",
                "substance", "quick", "system", "monitor", "page", "folder", "profile",
                "brightness", "macro"]
# Quick actions — common Windows tasks as one-press presets (label -> op key).
_QUICK_OPS = [
    ("Empty Recycle Bin", "recycle_empty"),
    ("Open Recycle Bin", "recycle_open"),
    ("Show / hide desktop", "show_desktop"),
    ("Minimize all windows", "minimize_all"),
    ("Task Manager", "task_manager"),
    ("File Explorer", "explorer"),
    ("Windows Settings", "settings"),
    ("Run dialog", "run_dialog"),
    ("Screenshot snip", "snip"),
    ("Clipboard history", "clipboard_history"),
    ("Clear clipboard", "clipboard_clear"),
    ("Emoji panel", "emoji_panel"),
    ("Project / 2nd screen", "project"),
    ("Lock PC", "lock"),
]
_QUICK_LABEL = {op: label for label, op in _QUICK_OPS}
_QUICK_HINTS = {
    "recycle_empty": "⚠ Permanently empties the Recycle Bin — no confirmation, can't be undone.",
    "snip": "Opens the Snipping Bar to grab a region to the clipboard (Win+Shift+S).",
    "clipboard_clear": "Empties the Windows clipboard.",
    "clipboard_history": "Opens clipboard history (Win+V).",
    "project": "Opens the projection panel — duplicate / extend / second screen (Win+P).",
    "settings": "Opens the Windows Settings app.",
    "task_manager": "Opens Task Manager (Ctrl+Shift+Esc).",
}
# Substance 3D Painter operations -> the shortcut they send (verified defaults; "" = custom).
_SUBSTANCE_OPS = [
    ("Brush size  +", "]"), ("Brush size  −", "["),
    ("Paint tool", "1"), ("Eraser", "2"), ("Projection", "3"),
    ("Polygon fill", "4"), ("Smudge", "5"), ("Clone", "6"),
    ("Symmetry on / off", "l"),
    ("Undo", "ctrl+z"), ("Redo", "ctrl+y"), ("Save project", "ctrl+s"),
    ("Hide UI", "tab"), ("Perspective view", "f5"), ("Orthographic view", "f6"),
    ("Material mode", "m"), ("Center on mesh", "f"),
    ("Custom (assign in Painter)…", ""),
]
_FOLDER_BACK = {"label": "Back", "icon": "⬅️", "color": "#222a33"}

QSS = T.build_qss()


def pil_to_pixmap(img) -> QPixmap:
    img = img.convert("RGBA")
    w, h = img.size
    qimg = QImage(img.tobytes("raw", "RGBA"), w, h, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimg)


def app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(pil_to_pixmap(icon_image(s)))
    return ic


ACTION_LABELS = {
    "none": "Nothing", "open": "Open app / file / URL", "hotkey": "Keyboard shortcut",
    "text": "Type text", "media": "Media control", "volume": "System volume",
    "mic": "Microphone mute", "sound": "Play sound (soundboard)", "discord": "Discord mute / deafen",
    "system": "System (lock / sleep)", "monitor": "Monitor brightness", "page": "Switch page",
    "folder": "Open folder", "profile": "Switch profile", "brightness": "Dock screen brightness",
    "macro": "Macro (advanced)", "substance": "Substance 3D Painter",
    "quick": "Quick action",
}
_SHORT = {"open": "Open", "hotkey": "Hotkey", "text": "Text", "media": "Media", "volume": "Volume",
          "mic": "Mic", "sound": "Sound", "discord": "Discord", "system": "System",
          "monitor": "Monitors", "page": "Page", "folder": "Folder", "profile": "Profile",
          "brightness": "Brightness", "macro": "Macro", "substance": "Painter", "quick": "Quick"}
# Compact "what this control does" labels drawn INSIDE the knobs / round buttons on the stage.
_CTRL_SHORT = {"open": "Open", "hotkey": "Key", "text": "Text", "media": "Media",
               "volume": "Volume", "mic": "Mic", "sound": "Sound", "discord": "Discord",
               "system": "System", "monitor": "Screen", "page": "Page", "folder": "Folder",
               "profile": "Profile", "brightness": "Bright", "macro": "Macro",
               "substance": "Brush", "quick": "Quick"}


def _action_summary(item) -> str:
    a = (item or {}).get("action") or {}
    t = a.get("type")
    if not t or t == "none":
        return "Not set"
    if t == "folder":
        return "Folder"
    if t == "substance":
        return f"Painter: {a.get('keys', '')}"
    if t == "quick":
        return f"Quick: {_QUICK_LABEL.get(a.get('op'), a.get('op') or '')}"
    detail = {"open": a.get("target"), "hotkey": a.get("keys"), "text": a.get("text"),
              "media": a.get("media"), "volume": a.get("volume"), "mic": a.get("mic"),
              "sound": a.get("file"), "discord": a.get("discord"), "system": a.get("system"),
              "monitor": a.get("monitor"), "page": a.get("page"), "profile": a.get("name"),
              "brightness": a.get("mode") or a.get("value"), "macro": None}.get(t)
    if t in ("open", "sound") and detail:
        detail = os.path.basename(str(detail))
    label = _SHORT.get(t, t)
    return f"{label}: {str(detail)[:14]}" if detail else label


class Bridge(QObject):
    status = Signal()


class _HotkeyRecorder(QObject):
    """Capture a shortcut: a keyboard combo OR a mouse button/scroll, with modifiers.

    Low-level keyboard hook (suppress=True) so the Windows key is intercepted before
    the OS acts; a mouse hook adds buttons + scroll. Captures the first non-modifier
    trigger (key or mouse) together with any held Ctrl/Alt/Shift/Win.
    """
    captured = Signal(str)
    _MODS = ("ctrl", "alt", "shift", "windows")
    _PURE = ("ctrl", "left ctrl", "right ctrl", "alt", "left alt", "right alt", "alt gr",
             "shift", "left shift", "right shift", "windows", "left windows", "right windows")

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        hk = ""
        try:
            import time as _t
            import keyboard
            import mouse
            _t.sleep(0.3)                      # let the activating click settle
            done = threading.Event()
            result = {"hk": ""}

            def pressed(m):
                try:
                    return keyboard.is_pressed(m)
                except Exception:
                    return False

            def finish(token):
                if not done.is_set():
                    mods = [m for m in self._MODS if pressed(m)]
                    result["hk"] = "+".join(mods + [token]) if token else ""
                    done.set()

            def on_key(e):
                if e.event_type != "down":
                    return
                n = (e.name or "").lower()
                if n in self._PURE:
                    return
                finish(None if n in ("esc", "escape") else n)

            def on_mouse(ev):
                if isinstance(ev, mouse.ButtonEvent):
                    if ev.event_type == "down":
                        b = {"left": "mouse:left", "right": "mouse:right", "middle": "mouse:middle",
                             "x": "mouse:back", "x2": "mouse:forward"}.get(ev.button)
                        if b:
                            finish(b)
                elif isinstance(ev, mouse.WheelEvent):
                    finish("mouse:wheel_up" if ev.delta > 0 else "mouse:wheel_down")

            kb = keyboard.hook(on_key, suppress=True)
            ms = mouse.hook(on_mouse)
            done.wait(timeout=12)
            for unhook, h in ((keyboard.unhook, kb), (mouse.unhook, ms)):
                try:
                    unhook(h)
                except Exception:
                    pass
            hk = result["hk"]
        except Exception:
            hk = ""
        self.captured.emit(hk)


def hotkey_to_qseq(spec: str) -> QKeySequence:
    s = (spec or "").strip().replace("windows", "Meta").replace("win", "Meta")
    return QKeySequence(s)


def qseq_to_hotkey(seq: QKeySequence) -> str:
    s = seq.toString(QKeySequence.PortableText) if seq else ""
    s = s.split(",")[0].strip().lower()          # first chord only
    return s.replace("meta", "win")


def _lerp_color(a: "QColor", b: "QColor", t: float) -> "QColor":
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t),
                  int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


class KeyTile(QLabel):
    """A clickable LCD-key preview (static — no Windows-side animation)."""
    FACE = 76
    clicked = Signal()

    def __init__(self, kid: str):
        super().__init__(objectName="key")
        self.kid = kid
        self.setFixedSize(86, 86)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(f"LCD key {kid[3:]}")
        self._base_pix = None

    def set_face(self, pil):
        self._base_pix = pil_to_pixmap(pil).scaled(
            self.FACE, self.FACE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(self._base_pix)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.setFocus()
            self.clicked.emit()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(ev)


class CircleControl(QWidget):
    """A custom-painted round control (knob or button). Static — instant hover/selection,
    no animation (the user wants animations only on the device)."""
    clicked = Signal()

    def __init__(self, diameter: int, knob: bool = False):
        super().__init__()
        self.setFixedSize(diameter, diameter)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._d = diameter
        self._knob = knob
        self._selected = False
        self._hovered = False
        self._caption = ""

    def setSelected(self, on):
        if on != self._selected:
            self._selected = on
            self.update()

    def setCaption(self, text):
        text = text or ""
        if text != self._caption:
            self._caption = text
            self.update()

    def enterEvent(self, ev):
        self._hovered = True
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hovered = False
        self.update()
        super().leaveEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.setFocus()
            self.clicked.emit()
        super().mousePressEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(ev)

    def focusInEvent(self, ev):
        self.update()
        super().focusInEvent(ev)

    def focusOutEvent(self, ev):
        self.update()
        super().focusOutEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self._d / 2.0, self._d / 2.0
        r = self._d / 2.0 - 4
        focused = self.hasFocus()

        # soft accent halo so the actively-edited control "lights up" in the brand colour
        if self._selected:
            halo = QColor(T.ACCENT)
            halo.setAlpha(46)
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(cx, cy), r + 3, r + 3)

        # molded-plastic gradient fill (lighter top, darker bottom)
        grad = QLinearGradient(0, 0, 0, self._d)
        if self._knob:
            grad.setColorAt(0, QColor(T.KNOB_TOP)); grad.setColorAt(1, QColor(T.KNOB_BOT))
        else:
            grad.setColorAt(0, QColor(T.BTN_TOP)); grad.setColorAt(1, QColor(T.BTN_BOT))
        p.setBrush(grad)

        if self._selected:
            border, bw, dash = QColor(T.ACCENT), 2.2, False
        elif self._hovered:
            border, bw, dash = QColor(T.BORDER_HOVER), 1.6, False
        elif focused:
            border, bw, dash = QColor(T.ACCENT), 1.6, True
        else:
            border, bw, dash = QColor(T.BORDER), 1.5, False
        pen = QPen(border)
        pen.setWidthF(bw)
        if dash:
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # top highlight arc for a physical, molded look
        p.setBrush(Qt.NoBrush)
        hl = QPen(QColor(255, 255, 255, 26))
        hl.setWidthF(1.4)
        hl.setCapStyle(Qt.RoundCap)
        p.setPen(hl)
        ir = r - 3
        p.drawArc(QRectF(cx - ir, cy - ir, ir * 2, ir * 2), 35 * 16, 110 * 16)

        if self._knob:
            lit = self._hovered or self._selected or focused
            tp = QPen(QColor(T.ACCENT) if lit else QColor(T.TICK))
            tp.setWidthF(3)
            tp.setCapStyle(Qt.RoundCap)
            p.setPen(tp)
            top = -r + 8
            p.drawLine(QPointF(cx, cy + top), QPointF(cx, cy + top + r * 0.34))

        # what the control does — a short, muted label inside it (tick stays clear)
        if self._caption:
            fs = max(7, min(11, int(round(self._d * 0.135))))
            f = QFont("Segoe UI", fs)
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            txt = p.fontMetrics().elidedText(self._caption, Qt.ElideRight, int(self._d * 0.80))
            p.setPen(QColor(T.ACCENT) if self._selected else QColor(T.TEXT_DIM))
            cyoff = r * 0.32 if self._knob else 0.0    # knob: below the tick; button: centered
            rect = QRectF(cx - self._d / 2.0, cy + cyoff - fs, float(self._d), fs * 2.0)
            p.drawText(rect, Qt.AlignHCenter | Qt.AlignVCenter, txt)
        p.end()


class EmojiPicker(QDialog):
    """A categorized emoji picker — category tabs, keyword search and recently-used.

    Data comes from dock.emoji_data (a curated, real-colour-emoji-only set). Recents
    live in QSettings so they persist without touching the portable config file.
    """
    picked = Signal(str)
    _RECENT_KEY = "recent_emoji"
    _RECENT_MAX = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick an emoji")
        self.resize(540, 600)
        self._cat = CATEGORIES[0]["key"]
        self._index = [(ch, name, terms, c["key"])
                       for c in CATEGORIES for (ch, name, terms) in c["emoji"]]

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search emoji — e.g. fire, cat, heart, party…")
        self._search.setClearButtonEnabled(True)
        v.addWidget(self._search)

        strip = QHBoxLayout()
        strip.setSpacing(4)
        self._catgroup = QButtonGroup(self)
        self._catgroup.setExclusive(True)
        self._catbtns = {}
        catfont = QFont("Segoe UI Emoji", 15)

        def add_cat(key, icon, tip):
            b = QToolButton(objectName="emojicat")
            self._set_emoji(b, icon, 22, catfont)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(40, 34)
            b.clicked.connect(lambda _=False, k=key: self._show_cat(k))
            self._catgroup.addButton(b)
            self._catbtns[key] = b
            strip.addWidget(b)

        add_cat("recent", "🕘", "Recently used")
        for c in CATEGORIES:
            add_cat(c["key"], c["icon"], c["label"])
        strip.addStretch(1)
        v.addLayout(strip)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        v.addWidget(self._scroll, 1)
        self._count = QLabel("", objectName="dim")
        v.addWidget(self._count)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(130)
        self._timer.timeout.connect(self._apply_search)
        self._search.textChanged.connect(lambda _=None: self._timer.start())

        start = "recent" if self._recents() else CATEGORIES[0]["key"]
        self._catbtns[start].setChecked(True)
        self._show_cat(start)

    # ---- recently used (QSettings, kept out of the portable config) ----
    @staticmethod
    def _settings():
        from PySide6.QtCore import QSettings
        return QSettings("AjazzDock", "AjazzDock")

    def _recents(self):
        raw = self._settings().value(self._RECENT_KEY, "")
        return [c for c in str(raw or "").split("") if c]

    def _push_recent(self, ch):
        rec = [ch] + [c for c in self._recents() if c != ch]
        self._settings().setValue(self._RECENT_KEY, "".join(rec[:self._RECENT_MAX]))

    def _name(self, ch):
        return next((n for c, n, _t, _k in self._index if c == ch), "")

    # ---- views ----
    def _show_cat(self, key):
        self._cat = key
        if key in self._catbtns and not self._catbtns[key].isChecked():
            self._catbtns[key].setChecked(True)
        if self._search.text():
            self._search.blockSignals(True)
            self._search.clear()
            self._search.blockSignals(False)
        if key == "recent":
            items = [(ch, self._name(ch)) for ch in self._recents()]
            label, empty = "Recently used", "No recent emoji yet — pick one and it'll show here."
        else:
            cat = next(c for c in CATEGORIES if c["key"] == key)
            items = [(ch, name) for ch, name, _t in cat["emoji"]]
            label = empty = cat["label"]
        self._render(items)
        self._count.setText(f"{label} · {len(items)}" if items else empty)

    def _apply_search(self):
        q = self._search.text().strip().lower()
        if not q:
            self._show_cat(self._cat)
            return
        self._catgroup.setExclusive(False)         # allow unchecking all during search
        for b in self._catgroup.buttons():
            b.setChecked(False)
        self._catgroup.setExclusive(True)
        words = q.split()
        out = []
        for ch, name, terms, _k in self._index:
            if all(w in (name + " " + terms) for w in words):
                out.append((ch, name))
                if len(out) >= 400:
                    break
        self._render(out)
        self._count.setText((f"{len(out)} result" + ("" if len(out) == 1 else "s")) if out else "No matches")

    def _render(self, items):
        host = QWidget()
        grid = QGridLayout(host)
        grid.setSpacing(4)
        grid.setContentsMargins(2, 2, 2, 2)
        fallback = QFont("Segoe UI Emoji", 22)
        cols = 7
        for i, (ch, name) in enumerate(items):
            b = QToolButton(objectName="emoji")
            b.setFixedSize(58, 58)
            self._set_emoji(b, ch, 42, fallback)
            if name:
                b.setToolTip(name)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, e=ch: self._pick(e))
            grid.addWidget(b, i // cols, i % cols)
        grid.setRowStretch(len(items) // cols + 1, 1)
        self._scroll.setWidget(host)

    @staticmethod
    def _set_emoji(btn, glyph, px, fallback_font):
        """Show the emoji as a PIL-rendered icon (color emoji don't scale as button text)."""
        em = emoji_image(glyph, px)
        if em is not None:
            pm = pil_to_pixmap(em)
            btn.setIcon(QIcon(pm))
            btn.setIconSize(pm.size())
        else:
            btn.setText(glyph)
            btn.setFont(fallback_font)

    def _pick(self, ch):
        self._push_recent(ch)
        self.picked.emit(ch)
        self.accept()


class CropArea(QWidget):
    """Image with a movable / zoomable crop box (square-locked by default).

    Drag the box to move it; scroll wheel or zoom() to resize; center() recenters.
    """

    def __init__(self, pil_img, maxside=460, parent=None):
        super().__init__(parent)
        self.orig = pil_img.convert("RGBA")
        ow, oh = self.orig.size
        s = maxside / max(ow, oh)
        self.dw, self.dh = max(1, int(ow * s)), max(1, int(oh * s))
        self.scale = ow / self.dw                      # original px per display px
        self.pix = pil_to_pixmap(self.orig.resize((self.dw, self.dh), Image.LANCZOS))
        self.setFixedSize(self.dw, self.dh)
        self.setCursor(Qt.OpenHandCursor)
        self.square = True
        side = int(min(self.dw, self.dh) * 0.8)
        self.box = QRect(0, 0, side, side)
        self.box.moveCenter(QPoint(self.dw // 2, self.dh // 2))
        self._drag = None

    def _clamp_box(self):
        b = self.box
        w, h = min(b.width(), self.dw), min(b.height(), self.dh)
        x = max(0, min(self.dw - w, b.x()))
        y = max(0, min(self.dh - h, b.y()))
        self.box = QRect(x, y, w, h)

    def set_square(self, on):
        self.square = on
        if on:
            side = min(self.box.width(), self.box.height())
            c = self.box.center()
            self.box = QRect(0, 0, side, side)
            self.box.moveCenter(c)
        self._clamp_box()
        self.update()

    def center(self):
        self.box.moveCenter(QPoint(self.dw // 2, self.dh // 2))
        self._clamp_box()
        self.update()

    def zoom(self, factor):
        c = self.box.center()
        w = max(24, min(self.dw, int(self.box.width() * factor)))
        h = max(24, min(self.dh, int(self.box.height() * factor)))
        if self.square:
            w = h = min(w, h)
        self.box = QRect(0, 0, w, h)
        self.box.moveCenter(c)
        self._clamp_box()
        self.update()

    def wheelEvent(self, e):
        self.zoom(0.9 if e.angleDelta().y() > 0 else 1.1)   # scroll up = zoom in

    def mousePressEvent(self, e):
        if self.box.contains(e.position().toPoint()):
            self._drag = (e.position().toPoint(), QRect(self.box))
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        start, box0 = self._drag
        self.box = QRect(box0)
        self.box.translate(e.position().toPoint() - start)
        self._clamp_box()
        self.update()

    def mouseReleaseEvent(self, e):
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def paintEvent(self, e):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.pix)
        if self.box.width() > 1:
            p.fillRect(self.rect(), QColor(0, 0, 0, 120))
            p.drawPixmap(self.box, self.pix, self.box)
            pen = QPen(QColor(T.ACCENT))
            pen.setWidth(2)
            p.setPen(pen)
            p.drawRect(self.box.adjusted(0, 0, -1, -1))
        p.end()

    def cropped(self):
        if self.box.width() < 4 or self.box.height() < 4:
            return self.orig
        ow, oh = self.orig.size
        x = int(self.box.x() * self.scale)
        y = int(self.box.y() * self.scale)
        x2 = min(ow, int((self.box.x() + self.box.width()) * self.scale))
        y2 = min(oh, int((self.box.y() + self.box.height()) * self.scale))
        return self.orig.crop((x, y, x2, y2))


class ImageCropDialog(QDialog):
    def __init__(self, pil_img, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop image")
        self.result_image = None
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Drag the box to move it · scroll or use Zoom to resize.",
                           objectName="dim"))
        self.area = CropArea(pil_img)
        wrap = QHBoxLayout()
        wrap.addStretch(1)
        wrap.addWidget(self.area)
        wrap.addStretch(1)
        v.addLayout(wrap)
        ctl = QHBoxLayout()
        cbtn = QPushButton("Center")
        cbtn.clicked.connect(self.area.center)
        zin = QPushButton("Zoom +")
        zin.clicked.connect(lambda: self.area.zoom(0.85))
        zout = QPushButton("Zoom −")
        zout.clicked.connect(lambda: self.area.zoom(1.18))
        sq = QCheckBox("Square crop (matches the key shape)")
        sq.setChecked(True)
        sq.toggled.connect(self.area.set_square)
        ctl.addWidget(cbtn)
        ctl.addWidget(zin)
        ctl.addWidget(zout)
        ctl.addStretch(1)
        ctl.addWidget(sq)
        v.addLayout(ctl)
        btns = QHBoxLayout()
        full = QPushButton("Use whole image")
        full.clicked.connect(lambda: (setattr(self, "result_image", self.area.orig), self.accept()))
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Crop && use")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        btns.addWidget(full)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        v.addLayout(btns)

    def accept(self):
        if self.result_image is None:
            self.result_image = self.area.cropped()
        super().accept()


class BackupsDialog(QDialog):
    """Backup history with one-click restore (always backs up the current state first)."""

    def __init__(self, win: "ConfigWindow"):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Backups")
        self.setMinimumSize(480, 360)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Restore points, newest first. Restoring backs up your current "
                           "setup first, so nothing is ever lost.", objectName="dim"))
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self._restore())
        v.addWidget(self.list, 1)

        row = QHBoxLayout()
        self.restore_btn = QPushButton("Restore selected")
        self.restore_btn.clicked.connect(self._restore)
        now_btn = QPushButton("Back up now")
        now_btn.clicked.connect(self._backup_now)
        open_btn = QPushButton("Open folder")
        open_btn.clicked.connect(self._open_folder)
        row.addWidget(self.restore_btn)
        row.addWidget(now_btn)
        row.addWidget(open_btn)
        row.addStretch(1)
        v.addLayout(row)

        row2 = QHBoxLayout()
        exp = QPushButton("Export…")
        exp.clicked.connect(self.win._export_config)
        imp = QPushButton("Import…")
        imp.clicked.connect(self._import)
        row2.addWidget(exp)
        row2.addWidget(imp)
        row2.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row2.addWidget(close)
        v.addLayout(row2)
        self._reload()

    def _reload(self):
        self.list.clear()
        for b in backups.list_backups():
            when = b["when"].strftime("%b %d   %H:%M:%S")
            if b["ok"]:
                text = f"{when}      {b['pages']} pages · {b['keys']} keys"
            else:
                text = f"{when}      (unreadable)"
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, b["path"])
            if not b["ok"]:
                it.setForeground(QColor("#e24b4a"))
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.restore_btn.setEnabled(self.list.count() > 0)

    def _selected_path(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _restore(self):
        path = self._selected_path()
        if not path:
            return
        if QMessageBox.question(self, "Restore",
                                "Restore this backup? Your current setup is saved first.") \
                != QMessageBox.Yes:
            return
        if backups.restore(path):
            self.win._after_external_config_change()
            self._reload()
            QMessageBox.information(self, "Restored", "Backup restored to the dock.")
        else:
            QMessageBox.warning(self, "Restore failed", "That backup couldn't be read.")

    def _backup_now(self):
        backups.snapshot("manual")
        self._reload()

    def _open_folder(self):
        try:
            os.startfile(backups_dir())            # Windows
        except OSError:
            pass

    def _import(self):
        if self.win._import_config():
            self._reload()


class CalibrationDialog(QDialog):
    """Live per-key image calibration — drag Size / X / Y and watch the dock update."""

    def __init__(self, win):
        super().__init__(win)
        self.controller = win.controller
        self.setWindowTitle("Display calibration")
        self.setMinimumWidth(400)
        self._closed = False                       # guards a late debounce tick after Save/Cancel
        self.controller.begin_calibration()        # open the session (controller ignores stray previews otherwise)
        d = self.controller.config.display()
        self.w = int(d.get("w", 88))
        self.h = int(d.get("h", 88))
        self.dx = max(-20, min(20, int(d.get("dx", 0))))
        self.dy = max(-20, min(20, int(d.get("dy", 0))))

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)
        intro = QLabel("Watch the dock while you drag. The target has a CYAN band at the TOP and a "
                       "RED band at the BOTTOM. First grow Width & Height until the yellow border "
                       "reaches all four edges and the red band sits along the bottom (back off if "
                       "it bleeds into a neighbour) — that's what fills the cell. Use X / Y only for "
                       "a small centring nudge. If red ISN'T at the bottom, tell me — the axes are "
                       "rotated and I'll flip them.", objectName="dim")
        intro.setWordWrap(True)
        v.addWidget(intro)
        if not self.controller.status().get("connected"):
            warn = QLabel("⚠ The dock isn't connected — plug it in to see the live preview.",
                          objectName="dim")
            warn.setWordWrap(True)
            v.addWidget(warn)
        self.val = QLabel("", objectName="h1")
        v.addWidget(self.val)
        self.s_w = self._slider("Width  (fills left↔right)", 60, 160, self.w, "w", v)
        self.s_h = self._slider("Height  (fills top↕bottom)", 60, 160, self.h, "h", v)
        self.s_dx = self._slider("Nudge horizontal", -20, 20, self.dx, "dx", v)
        self.s_dy = self._slider("Nudge vertical", -20, 20, self.dy, "dy", v)

        row = QHBoxLayout()
        reset = QPushButton("Reset")
        reset.clicked.connect(self._reset)
        row.addWidget(reset)
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        v.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._preview)
        self._refresh()
        self._preview()

    def _slider(self, label, lo, hi, val, attr, parent):
        parent.addWidget(QLabel(label, objectName="section"))
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        s.valueChanged.connect(lambda x, a=attr: self._set(a, x))
        parent.addWidget(s)
        return s

    def _set(self, attr, x):
        setattr(self, attr, x)
        self._refresh()
        self._timer.start()

    def _refresh(self):
        self.val.setText(f"W {self.w}  ·  H {self.h}  ·  X {self.dx:+d}  ·  Y {self.dy:+d}")

    def _preview(self):
        if self._closed:
            return
        self.controller.preview_calibration(self.w, self.h, self.dx, self.dy)

    def _reset(self):
        self.s_w.setValue(88)
        self.s_h.setValue(88)
        self.s_dx.setValue(0)
        self.s_dy.setValue(0)

    def _save(self):
        self._closed = True                        # stop any pending preview from re-arming calib
        self._timer.stop()
        self.controller.apply_calibration(self.w, self.h, self.dx, self.dy)
        self.accept()

    def reject(self):
        self._closed = True
        self._timer.stop()
        self.controller.end_calibration()
        super().reject()

    def closeEvent(self, ev):
        # The title-bar X / Alt+F4 don't always route through reject(); make sure the session
        # is closed and the page restored no matter how the dialog is dismissed.
        if not self._closed:
            self._closed = True
            self._timer.stop()
            self.controller.end_calibration()
        super().closeEvent(ev)


class ConfigWindow(QMainWindow):
    def __init__(self, controller: DockController):
        super().__init__()
        self.controller = controller
        self.cfg = controller.config
        self.cur_page = 0
        self.sel = "key1"
        self.view_folder = None          # folder id being edited in-place, or None
        self._ready = False              # suppress the editor popup during startup
        self._quitting = False

        self.setWindowTitle(f"{APP_TITLE} — Configurator")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1160, 600)
        self.resize(1220, 670)

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(250)
        self._render_timer.timeout.connect(self._persist_and_render)

        self.key_btns = {}
        self.slot_btns = {}

        self._build_ui()
        self.refresh()
        self.select("key1")
        self._ready = True

    # ---- layout ------------------------------------------------------------
    def _build_ui(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        body = QHBoxLayout(root)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar(), 0)
        body.addWidget(self._build_device_panel(), 1)
        body.addWidget(self._build_inspector(), 0)

    @staticmethod
    def _hsep():
        line = QFrame(objectName="hsep")
        line.setFixedHeight(1)
        return line

    @staticmethod
    def _side_card(title):
        """A grouped sidebar section — a subtle rounded card with a small header."""
        card = QFrame(objectName="card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(12, 10, 12, 12)
        cv.setSpacing(8)
        cv.addWidget(QLabel(title.upper(), objectName="cardtitle"))
        return card, cv

    def _build_sidebar(self):
        bar = QFrame(objectName="sidebar")
        bar.setFixedWidth(216)
        v = QVBoxLayout(bar)
        v.setContentsMargins(14, 16, 14, 16)
        v.setSpacing(11)

        v.addWidget(QLabel(APP_TITLE, objectName="display"))
        self.conn_lbl = QLabel("…", objectName="dim")
        v.addWidget(self.conn_lbl)
        v.addSpacing(2)

        # Profile
        card, cv = self._side_card("Profile")
        prow = QHBoxLayout()
        prow.setSpacing(6)
        self.profile_combo = QComboBox()
        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        prow.addWidget(self.profile_combo, 1)
        add_p = QPushButton("＋")
        add_p.setFixedWidth(32)
        add_p.setToolTip("New profile")
        add_p.clicked.connect(self._add_profile)
        prow.addWidget(add_p)
        cv.addLayout(prow)
        v.addWidget(card)

        # Brightness (with a live % readout)
        card, cv = self._side_card("Brightness")
        brow = QHBoxLayout()
        brow.setSpacing(8)
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(0, 100)
        self.bright.setValue(self.cfg.brightness)
        self.bright.valueChanged.connect(self._on_brightness)
        self.bright_val = QLabel(f"{self.cfg.brightness}%", objectName="dim")
        self.bright_val.setFixedWidth(36)
        self.bright_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        brow.addWidget(self.bright, 1)
        brow.addWidget(self.bright_val)
        cv.addLayout(brow)
        v.addWidget(card)

        # Behaviour
        card, cv = self._side_card("Behaviour")
        self.titles_chk = QCheckBox("Labels under icons")
        self.titles_chk.setToolTip("Show text labels under the icons on the keys")
        self.titles_chk.setChecked(self.cfg.data.get("show_labels", True))
        self.titles_chk.toggled.connect(self._toggle_titles)
        cv.addWidget(self.titles_chk)
        self.pressfx_chk = QCheckBox("Press effects")
        self.pressfx_chk.setToolTip("Play an animation on a key when you press it on the dock")
        self.pressfx_chk.setChecked(self.cfg.data.get("press_fx", True))
        self.pressfx_chk.toggled.connect(self._toggle_pressfx)
        cv.addWidget(self.pressfx_chk)
        self.anim_combo = QComboBox()
        self.anim_combo.setFocusPolicy(Qt.StrongFocus)
        self.anim_combo.setToolTip("Press-effect style played on the dock")
        for tok in PRESS_ANIM_ORDER:
            self.anim_combo.addItem(PRESS_ANIM_LABELS.get(tok, tok), tok)
        i = self.anim_combo.findData(self.cfg.data.get("press_anim", "bounce"))
        self.anim_combo.setCurrentIndex(i if i >= 0 else 0)
        self.anim_combo.setEnabled(self.pressfx_chk.isChecked())
        self.anim_combo.currentIndexChanged.connect(
            lambda _i: self._set_press_anim(self.anim_combo.currentData()))
        cv.addWidget(self.anim_combo)
        v.addWidget(card)

        v.addStretch(1)

        # This page (page-scoped image tools)
        card, cv = self._side_card("This page")
        fs_btn = QPushButton("Full-screen image…")
        fs_btn.clicked.connect(self._set_fullscreen_image)
        cv.addWidget(fs_btn)
        fs_clear = QPushButton("Clear images")
        fs_clear.clicked.connect(self._clear_page_images)
        cv.addWidget(fs_clear)
        v.addWidget(card)

        # Setup (global — calibration / backup / export / import)
        card, cv = self._side_card("Setup")
        calib_btn = QPushButton("Display calibration…")
        calib_btn.setToolTip("Fine-tune how images sit on the dock's keys (size + position), live")
        calib_btn.clicked.connect(self._open_calibration)
        cv.addWidget(calib_btn)
        backups_btn = QPushButton("Backups && export…")
        backups_btn.setToolTip("Backup history, restore, export / import")
        backups_btn.clicked.connect(self._open_backups)
        cv.addWidget(backups_btn)
        v.addWidget(card)
        return bar

    def _build_device_panel(self):
        panel = QWidget(objectName="main")
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(12)

        # page switcher: a rounded segmented track (active page = mint segment) with the
        # add / delete buttons aligned just beside it
        self.tabs_row = QHBoxLayout()
        self.tabs_row.setContentsMargins(5, 5, 5, 5)
        self.tabs_row.setSpacing(4)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tabbar = QFrame(objectName="tabbar")
        self.tabbar.setLayout(self.tabs_row)
        self.tabs_extra = QHBoxLayout()
        self.tabs_extra.setSpacing(6)
        tabs_wrap = QHBoxLayout()
        tabs_wrap.addStretch(1)
        tabs_wrap.addWidget(self.tabbar)
        tabs_wrap.addSpacing(8)
        tabs_wrap.addLayout(self.tabs_extra)
        tabs_wrap.addStretch(1)
        v.addLayout(tabs_wrap)

        # The dock drawn to the real AKP03's proportions: 6 keys top-left, big knob
        # top-right, 3 small buttons bottom-left, 2 medium knobs bottom-right. Each control
        # is clickable and opens its settings in a popup — nothing else fills the window.
        device = QFrame(objectName="device")
        shadow = QGraphicsDropShadowEffect(device)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 175))
        device.setGraphicsEffect(shadow)
        dv = QVBoxLayout(device)
        dv.setContentsMargins(16, 12, 16, 16)
        dv.setSpacing(12)
        wm = QHBoxLayout()
        wm.addWidget(QLabel("AJAZZ", objectName="wordmark"))
        wm.addStretch(1)
        wm.addWidget(QLabel("AKP03", objectName="wordmark"))
        dv.addLayout(wm)

        cols = QHBoxLayout()
        cols.setSpacing(22)

        left = QVBoxLayout()
        left.setSpacing(14)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(12)
        for i, kid in enumerate(LCD_KEYS):
            b = KeyTile(kid)
            b.clicked.connect(lambda k=kid: self.select(k))
            self.key_btns[kid] = b
            grid.addWidget(b, i // 3, i % 3)
        # one round button centered under each key column
        for col, n in enumerate((7, 8, 9)):
            grid.addWidget(self._dev_button(f"btn{n}", f"Button {n}"), 2, col, Qt.AlignHCenter)
        left.addLayout(grid)
        left.addStretch(1)

        # Physical mapping (verified on the device): the big knob is Encoder 1, the
        # bottom-left small knob is Encoder 0, the bottom-right small knob is Encoder 2.
        right = QVBoxLayout()
        right.setSpacing(16)
        # drop the big knob so its center lines up with the vertical middle of the key grid
        right.addSpacing(26)
        right.addWidget(self._dev_knob(1, big=True), 0, Qt.AlignHCenter)
        right.addStretch(1)
        small = QHBoxLayout()
        small.setSpacing(20)
        small.addWidget(self._dev_knob(0))
        small.addWidget(self._dev_knob(2))
        right.addLayout(small)

        cols.addLayout(left)
        cols.addStretch(1)
        cols.addLayout(right)
        dv.addLayout(cols)

        # Caption above + legend below frame the hero and fill the vertical space,
        # while teaching the scope model and pointing at the inspector.
        caption = QLabel("Click any control to program it — settings open on the right  →",
                         objectName="dim")
        caption.setAlignment(Qt.AlignHCenter)
        legend = QLabel("Keys & knobs: per page    ·    buttons: shared    ·    saves automatically",
                        objectName="dim")
        legend.setAlignment(Qt.AlignHCenter)
        legend.setWordWrap(True)

        center = QHBoxLayout()
        center.addStretch(1)
        center.addWidget(device)
        center.addStretch(1)

        v.addStretch(1)
        v.addWidget(caption)
        v.addSpacing(12)
        v.addLayout(center)
        v.addSpacing(16)
        v.addWidget(legend)
        v.addStretch(1)
        return panel

    def _dev_button(self, sid, label):
        # No visible caption (cleaner) — identity lives in the tooltip + accessible name.
        b = CircleControl(42, knob=False)
        b.setToolTip(f"{label} — click to edit")
        b.setAccessibleName(label)
        b.clicked.connect(lambda s=sid: self.select(s))
        self.slot_btns[sid] = b
        return b

    def _dev_knob(self, n, big=False):
        base = f"enc{n}"
        b = CircleControl(104 if big else 62, knob=True)
        b.setToolTip(f"Encoder {n} (per page) — click to edit turn & push")
        b.setAccessibleName(f"Encoder {n}")
        b.clicked.connect(lambda s=f"{base}-": self.select(s))
        self.slot_btns[base] = b
        return b

    def _build_inspector(self):
        """The control editor, docked as a fixed right-hand column inside the window
        (replaces the old floating popup — no geometry math, no focus ping-pong)."""
        insp = QFrame(objectName="inspector")
        insp.setFixedWidth(412)
        v = QVBoxLayout(insp)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(4)
        self.ed_title = QLabel("", objectName="h1")
        v.addWidget(self.ed_title)
        self.ed_scope = QLabel("", objectName="dim")
        self.ed_scope.setWordWrap(True)
        v.addWidget(self.ed_scope)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.editor_host = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_host)
        self.editor_layout.setContentsMargins(0, 8, 0, 0)
        self.editor_layout.setSpacing(10)
        scroll.setWidget(self.editor_host)
        v.addWidget(scroll, 1)
        return insp

    def _enc_segment_row(self, sid):
        n = sid[3]
        base = f"enc{n}"
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for sub, name in (("-", "◀ Turn left"), ("", "● Push"), ("+", "▶ Turn right")):
            tid = f"{base}{sub}"
            seg = QToolButton(objectName="seg")
            seg.setText(name)
            seg.setCheckable(True)
            seg.setChecked(tid == sid)
            seg.setCursor(Qt.PointingHandCursor)
            seg.clicked.connect(lambda _=False, s=tid: self._select_sub(s))
            row.addWidget(seg)
        row.addStretch(1)
        return w

    # ---- data helpers ------------------------------------------------------
    def pages(self):
        return self.cfg.pages()

    def page(self):
        ps = self.pages()
        self.cur_page = min(self.cur_page, len(ps) - 1)
        return ps[self.cur_page]

    def items(self):
        if self.view_folder is not None:
            return self.cfg.folder(self.view_folder).setdefault("items", {})
        return self.page().setdefault("items", {})

    def _globals(self):
        return self.cfg.globals_of()

    def _store(self, sid):
        # LCD keys: per-page (or folder). Knobs: per-page. Round buttons: profile-global.
        if sid.startswith("key"):
            return self.items()
        if sid.startswith("enc"):
            return self.page().setdefault("items", {})
        return self._globals()

    def _store_item(self, sid):
        """The editable binding dict for sid. The first per-page knob edit seeds itself from
        the shared global default, so the editor opens on the knob's current behaviour."""
        if sid.startswith("enc"):
            page_items = self.page().setdefault("items", {})
            if sid not in page_items:
                import copy
                g = self._globals().get(sid)
                page_items[sid] = copy.deepcopy(g) if isinstance(g, dict) else {}
            return page_items[sid]
        return self._store(sid).setdefault(sid, {})

    def _face(self, item):
        g = self.cfg.data.get("show_labels", True)
        return render_face(item or {}, show_label=(item or {}).get("show_label", g))

    # ---- folders -----------------------------------------------------------
    def _new_folder_id(self):
        existing = self.cfg.folders_of()
        i = 1
        while f"folder{i}" in existing:
            i += 1
        return f"folder{i}"

    def _set_folder_name(self, fid, name):
        self.cfg.folder(fid)["name"] = name or "Folder"
        self.cfg.save()
        if self.view_folder == fid:
            self._refresh_tabs()

    def _enter_folder_edit(self, fid):
        self.cfg.folder(fid)                  # ensure it exists
        self.view_folder = fid
        self.sel = "key1"
        self._refresh_tabs()
        self._refresh_all_slots()
        self.select("key1")

    def _exit_folder_edit(self):
        self.view_folder = None
        self.sel = "key1"
        self._refresh_tabs()
        self._refresh_all_slots()
        self.select("key1")

    # ---- refresh -----------------------------------------------------------
    def refresh(self):
        self.cfg = self.controller.config
        self.view_folder = None
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(self.cfg.profile_names())
        self.profile_combo.setCurrentText(self.cfg.data.get("active_profile", ""))
        self.profile_combo.blockSignals(False)
        self.bright.blockSignals(True)
        self.bright.setValue(self.cfg.brightness)
        self.bright.blockSignals(False)
        self.bright_val.setText(f"{self.cfg.brightness}%")
        self.titles_chk.blockSignals(True)
        self.titles_chk.setChecked(self.cfg.data.get("show_labels", True))
        self.titles_chk.blockSignals(False)
        self.pressfx_chk.blockSignals(True)
        self.pressfx_chk.setChecked(self.cfg.data.get("press_fx", True))
        self.pressfx_chk.blockSignals(False)
        self.anim_combo.blockSignals(True)
        ai = self.anim_combo.findData(self.cfg.data.get("press_anim", "bounce"))
        self.anim_combo.setCurrentIndex(ai if ai >= 0 else 0)
        self.anim_combo.setEnabled(self.pressfx_chk.isChecked())
        self.anim_combo.blockSignals(False)
        self._refresh_tabs()
        self._refresh_all_slots()
        self._refresh_conn()

    def _refresh_conn(self):
        st = self.controller.status()
        connected = st["connected"]
        dot = "●" if connected else "○"
        self.conn_lbl.setText(f"{dot} {'Connected' if connected else 'No device'}")
        self.conn_lbl.setStyleSheet(f"color: {T.ACCENT if connected else T.DANGER};")

    def _refresh_tabs(self):
        for lay in (self.tabs_row, self.tabs_extra):
            while lay.count():
                it = lay.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
        for b in self.tab_group.buttons():
            self.tab_group.removeButton(b)

        if self.view_folder is not None:
            # inside a folder: hide the page track, show a breadcrumb beside it
            self.tabbar.hide()
            f = self.cfg.folders_of().get(self.view_folder, {})
            back = QToolButton(objectName="tab")
            back.setText("←  Back to pages")
            back.setCursor(Qt.PointingHandCursor)
            back.clicked.connect(self._exit_folder_edit)
            self.tabs_extra.addWidget(back)
            self.tabs_extra.addWidget(QLabel(f"📁  {f.get('name', 'Folder')}", objectName="section"))
            return

        self.tabbar.show()
        for i, pg in enumerate(self.pages()):
            t = QToolButton(objectName="tab")
            t.setCheckable(True)
            t.setText(pg.get("name", f"Page {i+1}"))
            t.setChecked(i == self.cur_page)
            t.setCursor(Qt.PointingHandCursor)
            t.clicked.connect(lambda _=False, idx=i: self._goto_page(idx))
            self.tab_group.addButton(t)
            self.tabs_row.addWidget(t)

        addb = QToolButton(objectName="tabicon")
        addb.setText("＋")
        addb.setFixedSize(40, 40)
        addb.setCursor(Qt.PointingHandCursor)
        addb.setToolTip("Add a page")
        addb.clicked.connect(self._add_page)
        self.tabs_extra.addWidget(addb)
        if len(self.pages()) > 1:
            rmb = QToolButton(objectName="tabicon")
            rmb.setText("🗑")
            rmb.setFixedSize(40, 40)
            rmb.setCursor(Qt.PointingHandCursor)
            rmb.setToolTip("Delete this page")
            rmb.clicked.connect(self._del_page)
            self.tabs_extra.addWidget(rmb)

    def _refresh_all_slots(self):
        items = self.items()
        in_folder = self.view_folder is not None
        last = LCD_KEYS[-1]
        for kid, b in self.key_btns.items():
            if in_folder and kid == last:
                b.set_face(render_face(_FOLDER_BACK, show_label=True))
                b.setProperty("selected", False)
            else:
                b.set_face(self._face(items.get(kid)))
                b.setProperty("selected", kid == self.sel)
            b.style().unpolish(b)
            b.style().polish(b)
        for sid, b in self.slot_btns.items():
            b.setSelected(self._ctrl_selected(sid))
        self._refresh_slot_captions()

    def _ctrl_selected(self, sid):
        # buttons match exactly; a knob (enc0) matches any of its sub-actions (enc0-/enc0/enc0+).
        return self.sel == sid or (sid.startswith("enc") and self.sel.startswith(sid))

    def _effective(self, sid):
        """Read-only effective binding (no override materialised): enc -> page item else global;
        keys -> page/folder items; buttons -> global."""
        if sid.startswith("enc"):
            return self.page().get("items", {}).get(sid) or self._globals().get(sid)
        if sid.startswith("key"):
            return self.items().get(sid)
        return self._globals().get(sid)

    def _control_caption(self, sid):
        """Short 'what it does' label for a knob/button, drawn inside it on the stage."""
        def short(b):
            t = ((b or {}).get("action") or {}).get("type")
            return _CTRL_SHORT.get(t, (t or "").title()) if t and t != "none" else ""
        if sid.startswith("enc"):
            n = sid[3]
            for sub in ("+", "", "-"):      # prefer the turn action, then push, then turn-left
                lbl = short(self._effective(f"enc{n}{sub}"))
                if lbl:
                    return lbl
            return ""
        return short(self._effective(sid))

    def _refresh_slot_captions(self):
        # only the knobs are big enough for a tidy inline label; the small round buttons
        # stay clean (their function lives in the tooltip).
        for sid, b in self.slot_btns.items():
            b.setCaption(self._control_caption(sid) if sid.startswith("enc") else "")

    def _refresh_key_preview(self, kid):
        if kid in self.key_btns:
            self.key_btns[kid].set_face(self._face(self.items().get(kid)))

    # ---- selection / editor ------------------------------------------------
    def select(self, sid):
        if self.view_folder is not None and sid == LCD_KEYS[-1]:
            self._exit_folder_edit()      # the last key is the Back tile inside a folder
            return
        self.sel = sid
        for kid, b in self.key_btns.items():
            b.setProperty("selected", kid == sid)
            b.style().unpolish(b); b.style().polish(b)
        for s, b in self.slot_btns.items():
            b.setSelected(self._ctrl_selected(s))
        self._populate_editor()

    def _select_sub(self, sid):
        """Switch the edited encoder sub-action (segment buttons) — repopulate, no re-reveal."""
        self.sel = sid
        for s, b in self.slot_btns.items():
            b.setSelected(self._ctrl_selected(s))
        self._populate_editor()

    def _clear_editor(self):
        while self.editor_layout.count():
            it = self.editor_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)                  # remove from view now, not on the next loop
                w.deleteLater()
            elif it.layout():
                self._delete_layout(it.layout())

    def _delete_layout(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            elif it.layout():
                self._delete_layout(it.layout())

    def _populate_editor(self):
        self._clear_editor()
        sid = self.sel
        item = self._store_item(sid)
        item.setdefault("action", {"type": "none"})
        is_lcd = sid.startswith("key")
        if is_lcd:
            self.ed_title.setText(f"Key {sid[3:]}")
            self.ed_scope.setText("Per page · this key's look and action.")
        elif sid.startswith("btn"):
            self.ed_title.setText(f"Button {sid[3:]}")
            self.ed_scope.setText("Shared on every page of this profile.")
        else:
            self.ed_title.setText(f"Encoder {sid[3]}")
            self.ed_scope.setText("Per page · this knob can do something different on each page.")

        if sid.startswith("enc"):
            self.editor_layout.addWidget(self._enc_segment_row(sid))

        if is_lcd:
            self.editor_layout.addWidget(self._build_face_group(item))
        self.editor_layout.addWidget(self._build_action_group(item))
        clr = QPushButton("Clear this " + ("key" if is_lcd else "control"))
        clr.setToolTip("Reset this slot — removes its action" + (" and appearance" if is_lcd else ""))
        clr.clicked.connect(self._clear_binding)
        self.editor_layout.addWidget(clr)
        self.editor_layout.addStretch(1)

    def _clear_binding(self):
        self._store(self.sel)[self.sel] = {"action": {"type": "none"}}
        self.cfg.save()
        self.controller.request_render()
        self._refresh_all_slots()
        self.select(self.sel)

    _LABEL_W = 88          # shared form-label column so every field lines up in the inspector

    def _align_labels(self, form):
        """Give every QFormLayout label the same fixed width, so the fields line up down
        the whole inspector (Appearance + Action) even across separate group boxes."""
        for r in range(form.rowCount()):
            it = form.itemAt(r, QFormLayout.LabelRole)
            if it is not None and it.widget() is not None:
                it.widget().setFixedWidth(self._LABEL_W)
                it.widget().setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def _color_field(self, initial, on_pick):
        """A colour well + its hex, as a single form field (so it aligns with the inputs)."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        hexlbl = QLabel(initial, objectName="dim")
        btn = self._color_button(initial, lambda c: (hexlbl.setText(c), on_pick(c)))
        h.addWidget(btn)
        h.addWidget(hexlbl)
        h.addStretch(1)
        return w

    def _build_face_group(self, item):
        g = QGroupBox("Appearance")
        box = QVBoxLayout(g)
        box.setSpacing(10)

        # preview, centered
        self.face_preview = QLabel()
        self.face_preview.setFixedSize(92, 92)
        self.face_preview.setAlignment(Qt.AlignCenter)
        self.face_preview.setPixmap(pil_to_pixmap(self._face(item)).scaled(92, 92))
        prow = QHBoxLayout()
        prow.addStretch(1)
        prow.addWidget(self.face_preview)
        prow.addStretch(1)
        box.addLayout(prow)

        # label + icon, aligned column
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        label_edit = QLineEdit(item.get("label", ""))
        label_edit.textChanged.connect(lambda t: self._set_face(item, "label", t))
        form.addRow("Label", label_edit)
        self.icon_edit = QLineEdit(item.get("icon", ""))
        self.icon_edit.setPlaceholderText("emoji or image path")
        self.icon_edit.textChanged.connect(lambda t: self._set_face(item, "icon", t))
        form.addRow("Icon", self.icon_edit)
        self._align_labels(form)
        box.addLayout(form)

        # icon source — three equal buttons
        btns = QHBoxLayout()
        btns.setSpacing(6)
        emo = QPushButton("😀  Emoji")
        emo.clicked.connect(lambda: self._pick_emoji(item))
        img = QPushButton("🖼  Image…")
        img.clicked.connect(lambda: self._pick_image(item))
        clr = QPushButton("Clear")
        clr.clicked.connect(lambda: self.icon_edit.setText(""))
        for b in (emo, img, clr):
            btns.addWidget(b)
        box.addLayout(btns)

        # colours, same aligned column as the fields
        cform = QFormLayout()
        cform.setHorizontalSpacing(10)
        cform.setVerticalSpacing(8)
        cform.addRow("Background", self._color_field(
            item.get("color", "#23272e"), lambda c: self._set_face(item, "color", c)))
        cform.addRow("Text", self._color_field(
            item.get("text_color", "#ffffff"), lambda c: self._set_face(item, "text_color", c)))
        self._align_labels(cform)
        box.addLayout(cform)

        # options
        fill = QCheckBox("Fill the whole key (crop to fill)")
        fill.setToolTip("On: crop the image to fill the key. Off: show the whole image, letterboxed.")
        fill.setChecked(effective_fit(item) == "cover")
        fill.toggled.connect(lambda on: self._set_flag(item, "fit", "cover" if on else "contain"))
        box.addWidget(fill)
        gl = self.cfg.data.get("show_labels", True)
        title = QCheckBox("Show label on this key")
        title.setChecked(item.get("show_label", gl))
        title.toggled.connect(lambda on: self._set_flag(item, "show_label", bool(on)))
        box.addWidget(title)
        return g

    def _color_button(self, initial, on_pick):
        b = QPushButton()
        b.setFixedSize(50, 26)

        def style(c):
            b.setStyleSheet(f"background:{c}; border:1px solid {T.BORDER}; border-radius:{T.R_SM}px;")
        style(initial)
        b._color = initial

        def choose():
            col = QColorDialog.getColor(QColor(b._color), self, "Pick color")
            if col.isValid():
                hexc = col.name()
                b._color = hexc
                style(hexc)
                on_pick(hexc)
        b.clicked.connect(choose)
        return b

    def _pick_emoji(self, item):
        dlg = EmojiPicker(self)
        dlg.picked.connect(lambda e: self.icon_edit.setText(e))
        dlg.exec()

    def _pick_image(self, item):
        path, _ = QFileDialog.getOpenFileName(self, "Choose icon image", "",
                                              "Images (*.png *.jpg *.jpeg *.bmp *.gif *.ico)")
        if not path:
            return
        try:
            pil = Image.open(path)
        except (OSError, ValueError):
            return
        dlg = ImageCropDialog(pil, self)
        if dlg.exec() != QDialog.Accepted:
            return
        result = dlg.result_image or pil
        icons = os.path.join(config_dir(), "icons")
        os.makedirs(icons, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0]
        dest = os.path.join(icons, f"{stem}.png")
        i = 1
        while os.path.exists(dest):
            dest = os.path.join(icons, f"{stem}_{i}.png")
            i += 1
        try:
            result.convert("RGBA").save(dest)
        except OSError:
            return
        self.icon_edit.setText(dest)

    def _browse_sound(self, a, edit):
        path, _ = QFileDialog.getOpenFileName(self, "Choose sound", "",
                                              "Audio (*.wav *.ogg *.flac *.mp3 *.aiff)")
        if not path:
            return
        snd = os.path.join(config_dir(), "sounds")
        os.makedirs(snd, exist_ok=True)
        dest = os.path.join(snd, os.path.basename(path))
        try:
            shutil.copyfile(path, dest)
        except OSError:
            dest = path
        edit.setText(dest)

    def _set_flag(self, item, key, value):
        """Always store value (booleans / fit), then refresh previews + device."""
        item[key] = value
        if getattr(self, "face_preview", None):
            try:
                self.face_preview.setPixmap(pil_to_pixmap(self._face(item)).scaled(96, 96))
            except RuntimeError:
                pass
        self._refresh_key_preview(self.sel)
        self._render_timer.start()

    def _set_face(self, item, key, value):
        if value:
            item[key] = value
        else:
            item.pop(key, None)
        if hasattr(self, "face_preview") and self.face_preview:
            try:
                self.face_preview.setPixmap(pil_to_pixmap(self._face(item)).scaled(96, 96))
            except RuntimeError:
                pass
        self._refresh_key_preview(self.sel)
        self._render_timer.start()

    def _set_fullscreen_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Full-screen image (spread across all 6 keys)", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path:
            return
        if QMessageBox.question(self, "Full-screen image",
                                "Replace all 6 keys on this page with image tiles?") != QMessageBox.Yes:
            return
        icons = os.path.join(config_dir(), "icons")
        tiles = slice_fullscreen(path, icons, tag=f"fs_p{self.cur_page}")
        items = self.items()
        for i, kid in enumerate(LCD_KEYS):
            it = items.setdefault(kid, {})
            it["icon"] = tiles[i]
            it["fit"] = "cover"
            it.pop("label", None)
            it.pop("color", None)
        self.cfg.save()
        self.controller.request_render()
        self._refresh_all_slots()
        self.select(self.sel)

    def _clear_page_images(self):
        if QMessageBox.question(self, "Clear images",
                                "Clear the icon, label and colour on all 6 keys of this page?") \
                != QMessageBox.Yes:
            return
        items = self.items()
        for kid in LCD_KEYS:
            it = items.get(kid)
            if it:
                for k in ("icon", "fit", "label", "color", "text_color"):
                    it.pop(k, None)
        self.cfg.save()
        self.controller.request_render()
        self._refresh_all_slots()
        self.select(self.sel)

    # ---- action editor -----------------------------------------------------
    def _build_action_group(self, item):
        g = QGroupBox("Action")
        v = QVBoxLayout(g)
        if not self.sel.startswith("key"):
            hint = QLabel("This control has no screen — set its action below.", objectName="dim")
            hint.setWordWrap(True)
            v.addWidget(hint)
        a = item["action"]
        type_row = QFormLayout()
        type_row.setHorizontalSpacing(10)
        type_combo = QComboBox()
        type_combo.setFocusPolicy(Qt.StrongFocus)          # ignore stray mouse-wheel changes
        for tok in ACTION_TYPES:
            type_combo.addItem(ACTION_LABELS.get(tok, tok), tok)
        idx = type_combo.findData(a.get("type", "none"))
        type_combo.setCurrentIndex(idx if idx >= 0 else 0)
        type_combo.currentIndexChanged.connect(
            lambda _i: self._change_action_type(item, type_combo.currentData()))
        type_row.addRow("Type", type_combo)
        self._align_labels(type_row)
        v.addLayout(type_row)

        self.action_fields_host = QWidget()
        self.action_fields_layout = QVBoxLayout(self.action_fields_host)
        self.action_fields_layout.setContentsMargins(0, 4, 0, 0)
        v.addWidget(self.action_fields_host)
        self._build_action_fields(item)
        return g

    def _change_action_type(self, item, t):
        item["action"] = {"type": t}
        self._build_action_fields(item)
        self._refresh_key_preview(self.sel)
        self._refresh_slot_captions()        # keep the knob/button's on-stage label live
        self._render_timer.start()

    def _build_action_fields(self, item):
        while self.action_fields_layout.count():
            it = self.action_fields_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._delete_layout(it.layout())
        a = item["action"]
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self.action_fields_layout.addLayout(form)
        t = a.get("type", "none")

        def line(key, ph=""):
            e = QLineEdit(str(a.get(key, "")))
            e.setPlaceholderText(ph)
            e.textChanged.connect(lambda v: self._set_action(a, key, v))
            return e

        def combo(key, opts, default):
            c = QComboBox(); c.setFocusPolicy(Qt.StrongFocus); c.addItems(opts)
            c.setCurrentText(a.get(key, default))
            if not a.get(key):
                a[key] = default
            c.currentTextChanged.connect(lambda v: self._set_action(a, key, v))
            return c

        def spin(key, lo, hi, default):
            s = QSpinBox(); s.setRange(lo, hi); s.setValue(int(a.get(key, default)))
            s.valueChanged.connect(lambda v: self._set_action(a, key, v))
            return s

        if t == "open":
            row = QHBoxLayout()
            e = line("target", "notepad.exe or https://…")
            br = QPushButton("…"); br.setFixedWidth(34)
            br.clicked.connect(lambda: self._browse_target(a, e))
            row.addWidget(e); row.addWidget(br)
            form.addRow("Target", row)
            form.addRow("Args", line("args", "optional"))
        elif t == "hotkey":
            edit = QLineEdit(a.get("keys", ""))
            edit.setPlaceholderText("e.g. ctrl+shift+t · mouse:middle  —  or click Record")
            edit.textChanged.connect(lambda v: self._set_action(a, "keys", v.strip()))
            form.addRow("Shortcut", edit)

            rec_btn = QPushButton("⏺ Record (key or mouse)")

            def do_record():
                rec_btn.setText("Press a key or mouse button…  (Esc cancels)")
                rec_btn.setEnabled(False)
                self._hk_rec = _HotkeyRecorder()

                def on_cap(hk):
                    rec_btn.setText("⏺ Record (key or mouse)")
                    rec_btn.setEnabled(True)
                    if hk and hk not in ("esc", "escape"):
                        edit.setText(hk)
                self._hk_rec.captured.connect(on_cap)
                self._hk_rec.start()
            rec_btn.clicked.connect(do_record)

            clr = QPushButton("Clear")
            clr.setFixedWidth(60)
            clr.clicked.connect(edit.clear)
            row = QHBoxLayout()
            row.addWidget(rec_btn)
            row.addWidget(clr)
            row.addStretch(1)
            form.addRow("", row)
            hint = QLabel("Click Record, then press a key combo OR a mouse button / scroll "
                          "(Ctrl/Alt/Shift/Win modifiers work too). Esc cancels.", objectName="dim")
            hint.setWordWrap(True)
            form.addRow("", hint)
        elif t == "text":
            te = QPlainTextEdit(a.get("text", "")); te.setFixedHeight(70)
            te.textChanged.connect(lambda: self._set_action(a, "text", te.toPlainText()))
            form.addRow("Text", te)
        elif t == "media":
            form.addRow("Media", combo("media", ["play_pause", "next", "prev", "stop"], "play_pause"))
        elif t == "volume":
            form.addRow("Volume", combo("volume", ["up", "down", "mute"], "up"))
            form.addRow("Step", spin("step", 1, 10, 1))
        elif t == "mic":
            form.addRow("Microphone", combo("mic", ["toggle", "mute", "unmute"], "toggle"))
        elif t == "sound":
            srow = QHBoxLayout()
            se = line("file", "path to .wav / .ogg / .flac / .mp3")
            sbr = QPushButton("…")
            sbr.setFixedWidth(34)
            sbr.clicked.connect(lambda: self._browse_sound(a, se))
            srow.addWidget(se)
            srow.addWidget(sbr)
            form.addRow("Sound file", srow)
            dev = QComboBox()
            dev.addItem("System default", "")
            try:
                from .sound import list_outputs
                for nm in list_outputs():
                    dev.addItem(nm, nm)
            except Exception:
                pass
            pos = dev.findData(a.get("device", "") or "")
            dev.setCurrentIndex(pos if pos >= 0 else 0)
            dev.currentIndexChanged.connect(lambda _i: self._set_action(a, "device", dev.currentData()))
            form.addRow("Output", dev)
            mon = QCheckBox("Also play on my speakers (monitor)")
            mon.setChecked(bool(a.get("monitor", False)))
            mon.toggled.connect(lambda on: self._set_action(a, "monitor", bool(on)))
            form.addRow("", mon)
            gsp = QSpinBox()
            gsp.setRange(0, 200)
            gsp.setValue(int(float(a.get("gain", 1.0)) * 100))
            gsp.valueChanged.connect(lambda v: self._set_action(a, "gain", v / 100.0))
            form.addRow("Volume %", gsp)
            sh = QLabel("Soundboard for Discord: set Output to the device Discord uses as its "
                        "microphone (your virtual / NGENUITY device); enable monitor to hear it too.",
                        objectName="dim")
            sh.setWordWrap(True)
            form.addRow("", sh)
        elif t == "discord":
            form.addRow("Action", combo("discord", ["mute", "deafen"], "mute"))
            if not a.get("keys"):
                a["keys"] = {"mute": "f13", "deafen": "f14"}.get(a.get("discord", "mute"), "f13")
            de = QLineEdit(a.get("keys", "f13"))
            de.textChanged.connect(lambda v: self._set_action(a, "keys", v.strip()))
            drec = QPushButton("⏺ Record")

            def _drec():
                drec.setText("Press a key…")
                drec.setEnabled(False)
                self._hk_rec = _HotkeyRecorder()

                def _dc(hk):
                    drec.setText("⏺ Record")
                    drec.setEnabled(True)
                    if hk and hk not in ("esc", "escape"):
                        de.setText(hk)
                self._hk_rec.captured.connect(_dc)
                self._hk_rec.start()
            drec.clicked.connect(_drec)
            drow = QHBoxLayout()
            drow.addWidget(de)
            drow.addWidget(drec)
            form.addRow("Send key", drow)
            dh = QLabel("In Discord → Settings → Keybinds add 'Toggle Mute' / 'Toggle Deafen' with the "
                        "SAME key (F13–F15 are unused & conflict-free). This dock key then toggles it. "
                        "(Discord has no public API for direct mute, so it goes through a keybind.)",
                        objectName="dim")
            dh.setWordWrap(True)
            form.addRow("", dh)
        elif t == "substance":
            op_combo = QComboBox()
            op_combo.setFocusPolicy(Qt.StrongFocus)
            for label, keys in _SUBSTANCE_OPS:
                op_combo.addItem(label, keys)
            cur = a.get("keys", "")
            idx = next((i for i, (l, k) in enumerate(_SUBSTANCE_OPS) if k and k == cur), -1)
            if idx < 0:
                idx = len(_SUBSTANCE_OPS) - 1 if cur else 0
            op_combo.setCurrentIndex(idx)
            if not a.get("keys") and _SUBSTANCE_OPS[idx][1]:
                a["keys"] = _SUBSTANCE_OPS[idx][1]
            form.addRow("Operation", op_combo)
            key_edit = QLineEdit(a.get("keys", ""))
            key_edit.setPlaceholderText("key, e.g. ]  or  ctrl+z")
            key_edit.textChanged.connect(lambda v: self._set_action(a, "keys", v.strip()))
            form.addRow("Sends key", key_edit)
            op_combo.currentIndexChanged.connect(
                lambda _i: key_edit.setText(op_combo.currentData()) if op_combo.currentData() else None)
            sh = QLabel("Sent by physical key, so it works on any keyboard layout. Tip: put Brush "
                        "size − / + on a knob's turn-left / turn-right for a brush dial. If a shortcut "
                        "still doesn't register (or for brush rotation, which has no default), reassign "
                        "it in Painter → Edit → Settings → Shortcuts (e.g. to F13–F24) and use Custom.",
                        objectName="dim")
            sh.setWordWrap(True)
            form.addRow("", sh)
        elif t == "quick":
            op_combo = QComboBox()
            op_combo.setFocusPolicy(Qt.StrongFocus)
            for label, op in _QUICK_OPS:
                op_combo.addItem(label, op)
            pos = op_combo.findData(a.get("op", ""))
            if pos < 0:
                pos = 0
                a["op"] = _QUICK_OPS[0][1]
            op_combo.setCurrentIndex(pos)
            form.addRow("Action", op_combo)
            qhint = QLabel("", objectName="dim")
            qhint.setWordWrap(True)
            form.addRow("", qhint)

            def _set_quick(_i=None):
                op = op_combo.currentData()
                a["op"] = op
                qhint.setText(_QUICK_HINTS.get(op, "Runs this Windows action with one press."))
                self._refresh_key_preview(self.sel)
                self._render_timer.start()
            op_combo.currentIndexChanged.connect(_set_quick)
            qhint.setText(_QUICK_HINTS.get(a.get("op"), "Runs this Windows action with one press."))
        elif t == "system":
            form.addRow("System", combo("system", ["lock", "sleep", "monitor_off", "screensaver"], "lock"))
        elif t == "monitor":
            form.addRow("Brightness", combo("monitor", ["up", "down", "set"], "up"))
            form.addRow("Step", spin("step", 1, 50, 5))
            form.addRow("Level", spin("value", 0, 100, 50))
            disp = QComboBox()
            disp.addItem("All monitors", "all")
            try:
                from .monitors import count as _moncount
                n = _moncount()
            except Exception:
                n = 0
            for mi in range(n):
                disp.addItem(f"Monitor {mi + 1}", mi)
            cur = a.get("index", "all")
            pos = disp.findData(cur if cur is not None else "all")
            disp.setCurrentIndex(pos if pos >= 0 else 0)
            a.setdefault("index", "all")
            disp.currentIndexChanged.connect(lambda _i: self._set_action(a, "index", disp.currentData()))
            form.addRow("Display", disp)
        elif t == "page":
            form.addRow("Page", combo("page", ["next", "prev", "goto"], "next"))
            form.addRow("Index", spin("target", 0, 50, 0))
        elif t == "folder":
            if not a.get("folder"):
                a["folder"] = self._new_folder_id()
            fid = a["folder"]
            folder = self.cfg.folder(fid)
            name_e = QLineEdit(folder.get("name", "Folder"))
            name_e.textChanged.connect(lambda v: self._set_folder_name(fid, v))
            form.addRow("Folder name", name_e)
            editb = QPushButton("Edit folder contents  →")
            editb.setObjectName("primary")
            editb.clicked.connect(lambda: self._enter_folder_edit(fid))
            form.addRow("", editb)
            fh = QLabel("Opens a sub-page of keys on the dock. The last key is an automatic "
                        "Back; buttons & knobs stay the same inside.", objectName="dim")
            fh.setWordWrap(True)
            form.addRow("", fh)
        elif t == "profile":
            c = QComboBox(); c.addItems(self.cfg.profile_names())
            c.setCurrentText(a.get("name", self.cfg.profile_names()[0] if self.cfg.profile_names() else ""))
            c.currentTextChanged.connect(lambda v: self._set_action(a, "name", v))
            if not a.get("name") and self.cfg.profile_names():
                a["name"] = self.cfg.profile_names()[0]
            form.addRow("Switch to", c)
        elif t == "brightness":
            form.addRow("Mode", combo("mode", ["set", "up", "down"], "set"))
            form.addRow("Step", spin("step", 1, 50, 5))
            form.addRow("Level", spin("value", 0, 100, 70))
            hint = QLabel("This is the dock's own screen brightness. "
                          "For your PC displays use the 'monitor' action.", objectName="dim")
            hint.setWordWrap(True)
            form.addRow("", hint)
        elif t == "macro":
            import json
            te = QPlainTextEdit(json.dumps(a.get("steps", []), indent=1)); te.setFixedHeight(110)

            def upd():
                import json as _j
                try:
                    a["steps"] = _j.loads(te.toPlainText())
                except ValueError:
                    pass
            te.textChanged.connect(upd)
            form.addRow("Steps", te)
        else:
            form.addRow(QLabel("No action — does nothing.", objectName="dim"))

        self._align_labels(form)
        if t != "none":
            test = QPushButton("▶ Test")
            test.clicked.connect(lambda: self.controller.engine.execute(a))
            self.action_fields_layout.addWidget(test)

    def _browse_target(self, a, edit):
        path, _ = QFileDialog.getOpenFileName(self, "Choose program or file")
        if path:
            edit.setText(path)

    def _set_action(self, a, key, value):
        a[key] = value
        self._refresh_key_preview(self.sel)
        self._render_timer.start()

    # ---- persistence / device ---------------------------------------------
    def _persist_and_render(self):
        try:
            self.cfg.save()
        except OSError:
            pass
        self.controller.request_render()

    # ---- page / profile / brightness --------------------------------------
    def _goto_page(self, idx):
        if idx == self.cur_page:
            return
        self.cur_page = idx
        self.controller.goto_page(idx)          # the device plays the swipe
        self._refresh_all_slots()               # GUI faces update instantly (no Windows animation)
        self.select(self.sel)                   # keep the inspector in sync with the new page

    def _add_page(self):
        self.pages().append({"name": f"Page {len(self.pages())+1}", "items": {}})
        self.cur_page = len(self.pages()) - 1
        self.cfg.save()
        self._refresh_tabs(); self._refresh_all_slots()
        self.controller.goto_page(self.cur_page)

    def _del_page(self):
        if len(self.pages()) < 2:
            return
        if QMessageBox.question(self, "Delete page", f"Delete '{self.page().get('name')}'?") \
                == QMessageBox.Yes:
            self.pages().pop(self.cur_page)
            self.cur_page = max(0, self.cur_page - 1)
            self.cfg.save()
            self._refresh_tabs(); self._refresh_all_slots()
            self.controller.goto_page(self.cur_page)

    def _add_profile(self):
        name, ok = QInputDialog.getText(self, "New profile", "Profile name:")
        if not ok or not name:
            return
        if name in self.cfg.profile_names():
            QMessageBox.warning(self, APP_TITLE, "A profile with that name exists.")
            return
        self.cfg.profiles.append({"name": name, "pages": [{"name": "Home", "items": {}}]})
        self.cfg.data["active_profile"] = name
        self.cur_page = 0
        self.cfg.save()
        self.controller.set_profile(name)
        self.refresh(); self.select("key1")

    def _on_profile_changed(self, name):
        if name and name != self.cfg.data.get("active_profile"):
            self.cur_page = 0
            self.controller.set_profile(name)
            self.refresh(); self.select("key1")

    def _on_brightness(self, v):
        self.bright_val.setText(f"{v}%")
        self.controller.set_brightness(v)

    def _toggle_titles(self, on):
        self.cfg.data["show_labels"] = bool(on)
        self.cfg.save()
        self.controller.request_render()
        self._refresh_all_slots()
        self._populate_editor()

    def _toggle_pressfx(self, on):
        self.cfg.data["press_fx"] = bool(on)
        self.cfg.save()
        self.anim_combo.setEnabled(bool(on))

    def _set_press_anim(self, name):
        if name:
            self.cfg.data["press_anim"] = name
            self.cfg.save()

    # ---- calibration / backups / export / import ---------------------------
    def _open_calibration(self):
        CalibrationDialog(self).exec()

    def _open_backups(self):
        BackupsDialog(self).exec()

    def _after_external_config_change(self):
        """A restore/import rewrote the config file on disk — reload & re-render."""
        self.controller.replace_config(Config.load())
        self.cur_page = 0
        self.refresh()
        self.select("key1")

    def _export_config(self) -> bool:
        default = os.path.join(os.path.expanduser("~"), "AjazzDock-profile.json")
        path, _ = QFileDialog.getSaveFileName(self, "Export configuration",
                                              default, "JSON (*.json)")
        if not path:
            return False
        if backups.export_to(path):
            QMessageBox.information(self, "Exported", "Configuration exported.")
            return True
        QMessageBox.warning(self, "Export failed", "Could not write that file.")
        return False

    def _import_config(self) -> bool:
        path, _ = QFileDialog.getOpenFileName(self, "Import configuration", "",
                                              "JSON (*.json)")
        if not path:
            return False
        if QMessageBox.question(
                self, "Import",
                "Replace your current setup with this file?\nYour current setup is backed up first."
        ) != QMessageBox.Yes:
            return False
        if backups.import_from(path):
            self._after_external_config_change()
            QMessageBox.information(self, "Imported", "Configuration imported.")
            return True
        QMessageBox.warning(self, "Import failed", "That file isn't a valid AjazzDock config.")
        return False

    # ---- external status (device thread -> GUI) ----------------------------
    def on_status(self):
        if self.controller.page_index != self.cur_page:
            self.cur_page = self.controller.page_index
            self._refresh_tabs()
            self._refresh_all_slots()
            self.select(self.sel)               # keep the docked inspector on the live page
        self._refresh_conn()

    def show_raise(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
        else:
            event.ignore()
            self.hide()


def build_tray(win: ConfigWindow, controller: DockController, do_quit) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(app_icon(), win)
    tray.setToolTip(APP_TITLE)
    menu = QMenu()

    open_act = menu.addAction("Open Configurator")
    open_act.triggered.connect(win.show_raise)
    menu.addSeparator()

    prof_menu = menu.addMenu("Profile")

    def rebuild_profiles():
        prof_menu.clear()
        active = controller.config.data.get("active_profile")
        for nm in controller.config.profile_names():
            a = prof_menu.addAction(nm)
            a.setCheckable(True)
            a.setChecked(nm == active)
            a.triggered.connect(lambda _=False, n=nm: (controller.set_profile(n), win.refresh()))
    prof_menu.aboutToShow.connect(rebuild_profiles)

    menu.addAction("Backups…").triggered.connect(lambda: (win.show_raise(), win._open_backups()))
    menu.addAction("Reload config").triggered.connect(controller.request_reload)
    auto_act = menu.addAction("Start with Windows")
    auto_act.setCheckable(True)
    auto_act.setChecked(autostart.is_enabled())
    auto_act.triggered.connect(lambda checked: (autostart.enable() if checked else autostart.disable()))
    menu.addSeparator()
    menu.addAction("Quit").triggered.connect(do_quit)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: win.show_raise()
                           if reason == QSystemTrayIcon.Trigger or reason == QSystemTrayIcon.DoubleClick
                           else None)
    tray.show()
    return tray


def main():
    start_hidden = ("--tray" in sys.argv) or ("--hidden" in sys.argv)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setWindowIcon(app_icon())
    app.setFont(QFont("Segoe UI", 9))
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS)

    if "--status" in sys.argv:
        # Query a running instance over the IPC socket (used for verification).
        sock = QLocalSocket()
        sock.connectToServer(IPC_NAME)
        if sock.waitForConnected(500):
            sock.write(b"status")
            sock.flush()
            sock.waitForBytesWritten(500)
            if sock.waitForReadyRead(900):
                print(bytes(sock.readAll()).decode())
            sock.disconnectFromServer()
        else:
            print('{"running": false}')
        return 0

    if "--screenshot" in sys.argv:
        # Build the UI without touching the device; grab a frame and exit (verification).
        controller = DockController(Config.load())
        win = ConfigWindow(controller)
        win.show()
        path = sys.argv[sys.argv.index("--screenshot") + 1]
        QTimer.singleShot(700, lambda: (win.grab().save(path), app.quit()))
        return app.exec()

    # ---- single instance: OS mutex is authoritative, IPC just forwards show/status ----
    if not _acquire_singleton():
        # Another instance already owns the device — tell it to surface its window, then exit.
        probe = QLocalSocket()
        probe.connectToServer(IPC_NAME)
        if probe.waitForConnected(800):
            probe.write(b"show")
            probe.flush()
            probe.waitForBytesWritten(300)
            probe.disconnectFromServer()
        return 0
    # We hold the mutex -> we are the sole primary, so clearing a stale socket name is safe.
    QLocalServer.removeServer(IPC_NAME)
    server = QLocalServer()
    server.listen(IPC_NAME)

    controller = DockController(Config.load())
    win = ConfigWindow(controller)

    def do_quit():
        win._quitting = True
        try:
            controller.stop()
        finally:
            app.quit()

    tray = build_tray(win, controller, do_quit)
    win._tray = tray

    bridge = Bridge()
    controller.on_status = lambda: bridge.status.emit()
    bridge.status.connect(win.on_status, Qt.QueuedConnection)

    def _on_ipc():
        sock = server.nextPendingConnection()
        if sock is None:
            return
        sock.waitForReadyRead(300)
        msg = bytes(sock.readAll()).strip()
        if msg == b"status":
            import json
            sock.write(json.dumps(controller.status()).encode())
            sock.flush()
            sock.waitForBytesWritten(300)
        else:
            win.show_raise()
        sock.disconnectFromServer()
    server.newConnection.connect(_on_ipc)
    win._server = server  # keep alive

    controller.start()
    if not start_hidden:
        win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
