"""A small, non-blocking toast for the Qt configurator — slides up + fades in near the bottom of
its parent window and auto-dismisses. Replaces transient modal pop-ups (saved / tested / undone) so
the user keeps working; blocking QMessageBox is kept only for destructive confirmations."""
from PySide6.QtCore import (Qt, QTimer, QPoint, QPropertyAnimation, QParallelAnimationGroup,
                            QEasingCurve)
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect

from . import tokens as T

_KIND_ACCENT = {"ok": "#35e08a", "warn": "#e0b341", "err": "#e0533a"}   # "info" -> live accent


class Toast(QLabel):
    def __init__(self, parent, text, kind="info", msec=2200):
        super().__init__(text, parent)
        accent = _KIND_ACCENT.get(kind) or T.ACCENT
        self.setObjectName("toast")
        self.setStyleSheet(
            f"#toast {{ background: {T.SURFACE_3}; color: {T.TEXT}; border: 1px solid {accent};"
            f" border-radius: {T.R_MD}px; padding: 9px 16px; font-weight: 600; }}")
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)   # never blocks the UI underneath
        self.adjustSize()
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self.reposition()
        end = self.pos()
        self.move(end + QPoint(0, 14))            # start a touch lower, glide up into place
        self.show()
        self.raise_()
        self._anim = self._slide_fade(end, 0.0, 1.0, 220, QEasingCurve.OutCubic)
        self._anim.start()
        QTimer.singleShot(max(700, msec), self._dismiss)

    def _slide_fade(self, to_pos, o_from, o_to, dur, curve):
        fade = QPropertyAnimation(self._eff, b"opacity", self)
        fade.setDuration(dur)
        fade.setStartValue(o_from)
        fade.setEndValue(o_to)
        slide = QPropertyAnimation(self, b"pos", self)
        slide.setDuration(dur)
        slide.setStartValue(self.pos())
        slide.setEndValue(to_pos)
        slide.setEasingCurve(curve)
        grp = QParallelAnimationGroup(self)
        grp.addAnimation(fade)
        grp.addAnimation(slide)
        return grp

    def reposition(self):
        p = self.parentWidget()
        if not p:
            return
        x = (p.width() - self.width()) // 2
        y = p.height() - self.height() - 30
        self.move(max(8, x), max(8, y))

    def _dismiss(self):
        try:
            self._anim = self._slide_fade(self.pos() + QPoint(0, 10), 1.0, 0.0, 240,
                                          QEasingCurve.InCubic)
            self._anim.finished.connect(self.deleteLater)
            self._anim.start()
        except RuntimeError:
            self.deleteLater()
