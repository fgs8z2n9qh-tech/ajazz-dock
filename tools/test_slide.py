"""Crash-test the page-slide transition offscreen (no device)."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication                # noqa: E402
from dock.config import Config, default_config            # noqa: E402
from dock.controller import DockController                # noqa: E402
from dock.gui import ConfigWindow                         # noqa: E402

app = QApplication([])
win = ConfigWindow(DockController(Config(default_config())))
win.show()
app.processEvents()

win._goto_page(1)
app.processEvents()
win._goto_page(0)
app.processEvents()
win._goto_page(1)
app.processEvents()
print("OK — slide ran, cur_page =", win.cur_page)
