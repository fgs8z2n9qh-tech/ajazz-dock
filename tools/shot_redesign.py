"""Grab the redesigned 3-column window with different controls selected, to verify
the docked inspector renders the key / knob (per-page segment row) / button editors."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication            # noqa: E402
from PySide6.QtGui import QFont                       # noqa: E402
from PySide6.QtCore import QTimer                      # noqa: E402
from dock.config import Config, default_config         # noqa: E402
from dock.controller import DockController             # noqa: E402
from dock.gui import ConfigWindow, QSS, APP_TITLE      # noqa: E402

app = QApplication([])
app.setApplicationName(APP_TITLE)
app.setFont(QFont("Segoe UI", 9))
app.setStyleSheet(QSS)

data = default_config()
# give a knob and a button real bindings so the editors show content
g = data["profiles"][0]["globals"]
g["btn7"] = {"action": {"type": "media", "media": "play_pause"}}
data["profiles"][0]["pages"][0].setdefault("items", {})["enc1"] = {
    "action": {"type": "brightness", "mode": "up", "step": 5}}

win = ConfigWindow(DockController(Config(data)))
win.show()

shots = [("enc1-", "shot_knob.png"), ("btn7", "shot_button.png")]
out_dir = os.path.join(ROOT, "assets")


def grab_next():
    if not shots:
        app.quit()
        return
    sid, name = shots.pop(0)
    win.select(sid)
    for _ in range(6):                       # flush async deleteLater() + relayout
        app.processEvents()
    win.editor_host.repaint()
    app.processEvents()
    path = os.path.join(out_dir, name)
    win.grab().save(path)
    print("saved", name, "· sel =", win.sel)
    QTimer.singleShot(400, grab_next)


QTimer.singleShot(600, grab_next)
app.exec()
