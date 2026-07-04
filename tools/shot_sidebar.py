"""Render the right ACTIONS sidebar with Favourites / Recent / Common + a category open, in
list and grid view, to verify the redesign on the real Windows renderer."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer
from dock.config import Config, default_config
from dock.controller import DockController
from dock.gui import ConfigWindow, QSS, APP_TITLE

GRID = "--grid" in sys.argv
OUT = next((a for a in sys.argv[1:] if a.endswith(".png")), os.path.join(os.environ.get("TEMP", ROOT), "sidebar.png"))

app = QApplication([])
app.setApplicationName(APP_TITLE)
app.setFont(QFont("Segoe UI", 9))
app.setStyleSheet(QSS)

data = default_config()
data["fav_actions"] = ["smartlight", "media"]
data["recent_actions"] = ["open", "hotkey", "discord"]
data["actions_grid"] = GRID
data["actions_open_cats"] = ["Apps & files"]
win = ConfigWindow(DockController(Config(data)))
win.resize(1340, 860)
win.show()


def shoot():
    for _ in range(10):
        app.processEvents()
    full = win.grab()
    w = full.width(); h = full.height()
    crop = full.copy(w - 290, 0, 290, h)        # the right sidebar
    crop.save(OUT)
    print("saved", OUT)
    app.quit()


QTimer.singleShot(600, shoot)
app.exec()
