"""Grab the Quick-action editor (Empty Recycle Bin selected) in the docked inspector."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication                # noqa: E402
from PySide6.QtGui import QFont                           # noqa: E402
from PySide6.QtCore import QTimer                          # noqa: E402
from dock.config import Config, default_config            # noqa: E402
from dock.controller import DockController                # noqa: E402
from dock.gui import ConfigWindow, QSS, APP_TITLE         # noqa: E402

app = QApplication([])
app.setApplicationName(APP_TITLE)
app.setFont(QFont("Segoe UI", 9))
app.setStyleSheet(QSS)

data = default_config()
data["profiles"][0]["globals"]["btn7"] = {"action": {"type": "quick", "op": "recycle_empty"}}
win = ConfigWindow(DockController(Config(data)))
win.show()


def grab():
    win.select("btn7")
    for _ in range(6):
        app.processEvents()
    win.grab().save(os.path.join(ROOT, "assets", "shot_quick.png"))
    print("saved shot_quick.png · btn7 op =", win.cfg.globals_of()["btn7"]["action"].get("op"))
    app.quit()


QTimer.singleShot(600, grab)
app.exec()
