"""Render the full configurator window in the new Stream Deck layout (header + canvas +
bottom inspector + right actions sidebar) so we can eyeball it on the real Windows renderer."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication            # noqa: E402
from PySide6.QtGui import QFont                        # noqa: E402
from PySide6.QtCore import QTimer                      # noqa: E402
from dock.config import Config, default_config         # noqa: E402
from dock.controller import DockController             # noqa: E402
from dock.gui import ConfigWindow, QSS, APP_TITLE      # noqa: E402

SEL = sys.argv[1] if len(sys.argv) > 1 else "key1"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get("TEMP", ROOT), "layout.png")

app = QApplication([])
app.setApplicationName(APP_TITLE)
app.setFont(QFont("Segoe UI", 9))
app.setStyleSheet(QSS)

data = default_config()
items = data["profiles"][0]["pages"][0].setdefault("items", {})
items["key1"] = {"label": "Site", "icon": "", "action": {"type": "open", "target": "https://anthropic.com"}}
items["key2"] = {"label": "Mute", "action": {"type": "mic", "mode": "toggle"}}
_act = os.environ.get("SHOT_ACTION")
if _act:                                   # let a render override key1's action (e.g. discord/sound)
    a = {"type": _act}
    if os.environ.get("SHOT_MODE"):
        a["mode"] = os.environ["SHOT_MODE"]
    items["key1"] = {"label": "K1", "action": a}

win = ConfigWindow(DockController(Config(data)))
win.resize(1900, 1000)
win.show()


def shoot():
    for _ in range(8):
        app.processEvents()
    win.select(SEL)
    for _ in range(8):
        app.processEvents()
    win.repaint(); app.processEvents()
    win.grab().save(OUT)
    print("saved", OUT)
    app.quit()


QTimer.singleShot(600, shoot)
app.exec()
