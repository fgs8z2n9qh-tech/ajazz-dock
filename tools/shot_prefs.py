"""Render the redesigned two-pane Settings dialog (nav left, section right)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtWidgets import QApplication, QListWidget
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer
from dock.config import Config, default_config
from dock.controller import DockController
from dock.gui import ConfigWindow, QSS, APP_TITLE

ROW = int(next((a for a in sys.argv[1:] if a.isdigit()), "0"))
OUT = next((a for a in sys.argv[1:] if a.endswith(".png")), os.path.join(os.environ.get("TEMP", ROOT), "prefs.png"))

app = QApplication([])
app.setApplicationName(APP_TITLE)
app.setFont(QFont("Segoe UI", 9))
app.setStyleSheet(QSS)

data = default_config()
data["app_rules"] = [{"app": "discord.exe", "profile": None, "page": 7}]
win = ConfigWindow(DockController(Config(data)))
win.show()
dlg = win._prefs_dialog
dlg.show()


def shoot():
    for _ in range(8):
        app.processEvents()
    nav = dlg.findChild(QListWidget, "prefsnav")
    if nav is not None:
        nav.setCurrentRow(ROW)
    for _ in range(6):
        app.processEvents()
    dlg.grab().save(OUT)
    print("saved", OUT)
    app.quit()


QTimer.singleShot(500, shoot)
app.exec()
