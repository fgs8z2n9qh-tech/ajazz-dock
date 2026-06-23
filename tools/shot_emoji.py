"""Render the new categorized emoji picker — a category view and a search view."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication                # noqa: E402
from PySide6.QtGui import QFont                           # noqa: E402
from PySide6.QtCore import QTimer                          # noqa: E402
from dock.gui import EmojiPicker, QSS, APP_TITLE          # noqa: E402

app = QApplication([])
app.setApplicationName(APP_TITLE)
app.setFont(QFont("Segoe UI", 9))
app.setStyleSheet(QSS)

dlg = EmojiPicker()
dlg.show()


def shots():
    for _ in range(4):
        app.processEvents()
    dlg.grab().save(os.path.join(ROOT, "assets", "emoji_cat.png"))
    dlg._show_cat("animals")
    for _ in range(4):
        app.processEvents()
    dlg.grab().save(os.path.join(ROOT, "assets", "emoji_animals.png"))
    dlg._search.setText("heart")
    dlg._apply_search()
    for _ in range(4):
        app.processEvents()
    dlg.grab().save(os.path.join(ROOT, "assets", "emoji_search.png"))
    print("ok · index =", len(dlg._index), "· recents =", len(dlg._recents()))
    app.quit()


QTimer.singleShot(500, shots)
app.exec()
