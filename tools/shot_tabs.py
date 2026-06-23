"""Grab the redesigned page-switcher (segmented track + add/delete), 4 pages."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication                # noqa: E402
from PySide6.QtGui import QFont                           # noqa: E402
from PySide6.QtCore import QTimer, QRect                   # noqa: E402
from dock.config import Config, default_config            # noqa: E402
from dock.controller import DockController                # noqa: E402
from dock.gui import ConfigWindow, QSS, APP_TITLE         # noqa: E402

app = QApplication([])
app.setApplicationName(APP_TITLE)
app.setFont(QFont("Segoe UI", 9))
app.setStyleSheet(QSS)

data = default_config()
pages = data["profiles"][0]["pages"]
pages.append({"name": "Page 3", "items": {}})
pages.append({"name": "Page 4", "items": {}})
win = ConfigWindow(DockController(Config(data)))
win.show()


def grab():
    for _ in range(6):
        app.processEvents()
    win.grab().save(os.path.join(ROOT, "assets", "shot_tabs_full.png"))
    win.grab(QRect(216, 0, 740, 110)).save(os.path.join(ROOT, "assets", "shot_tabs.png"))
    print("saved shot_tabs.png + shot_tabs_full.png · pages =", len(win.pages()))
    app.quit()


QTimer.singleShot(600, grab)
app.exec()
