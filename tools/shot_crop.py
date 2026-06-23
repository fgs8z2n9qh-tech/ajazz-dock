"""Screenshot the ImageCropDialog for verification."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PIL import Image  # noqa: E402
import dock.gui as gui  # noqa: E402

app = QApplication([])
app.setStyleSheet(gui.QSS)
img = Image.open(os.path.join(ASSETS, "fs_tall.png"))  # non-square -> shows the crop rect
dlg = gui.ImageCropDialog(img)
dlg.show()
out = os.path.join(ASSETS, "crop_dialog.png")
QTimer.singleShot(600, lambda: (dlg.grab().save(out), app.quit()))
app.exec()
print("wrote", out)
