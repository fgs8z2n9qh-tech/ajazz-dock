"""Headless launcher (controller + Flask UI, no tray) — used for UI preview/testing.

Honors the PORT env var (for the preview harness); defaults to 8773.
"""
import os

from dock.config import Config
from dock.controller import DockController
from dock.ui import run_ui

if __name__ == "__main__":
    controller = DockController(Config.load())
    controller.start()
    run_ui(controller, host="127.0.0.1", port=int(os.environ.get("PORT", 8773)))
