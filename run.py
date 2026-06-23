"""Launch AjazzDock (tray app + config UI) with a console for debugging.

For silent background launch use start-ajazzdock.ps1 (pythonw, no console).
"""
from dock.gui import main

if __name__ == "__main__":
    main()
