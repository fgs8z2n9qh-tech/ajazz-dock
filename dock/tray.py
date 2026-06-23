"""AjazzDock app: device controller + Flask backend + native WebView2 config window + tray.

The configurator is shown in a real native window (pywebview / Edge WebView2), not a
browser tab. Closing the window hides it to the tray; the app keeps running. Launching
a second copy (or the tray "Open Configurator") just raises the existing window.

Pass --tray (used by autostart) to start hidden in the tray with no window popping up.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
import urllib.request
import webbrowser

import pystray
import webview
from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

from . import autostart
from .config import Config
from .controller import DockController
from .ui import HOST, PORT, run_ui

UI_URL = f"http://{HOST}:{PORT}/"
_mutex_handle = None        # keep the single-instance mutex alive for process lifetime
_window = None              # the pywebview configurator window
_quitting = False


def icon_image(size: int = 64) -> Image.Image:
    """A dock glyph: rounded slab with a 2x3 grid of lit keys (scales to any size)."""
    f = size / 64.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6 * f, 12 * f, 58 * f, 52 * f], radius=9 * f,
                        fill=(28, 32, 40, 255), outline=(70, 80, 95, 255), width=max(1, int(2 * f)))
    cols = [(61, 139, 255), (26, 161, 121), (200, 136, 31),
            (122, 60, 196), (192, 57, 43), (60, 64, 72)]
    i = 0
    for r in range(2):
        for c in range(3):
            x = 14 * f + c * 13 * f
            y = 19 * f + r * 15 * f
            d.rounded_rectangle([x, y, x + 10 * f, y + 11 * f], radius=3 * f, fill=cols[i])
            i += 1
    return img


def _single_instance() -> bool:
    """True if we own the single-instance lock; False if AjazzDock is already running."""
    global _mutex_handle
    try:
        _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, "AjazzDock_singleton")
        return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def _wait_for_server(timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(UI_URL + "api/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.15)
    return False


def _show_window() -> None:
    if _window is not None:
        try:
            _window.show()
            _window.restore()
        except Exception:
            pass


def build_menu(controller: DockController, on_open, on_quit) -> Menu:
    def make_profile_item(name: str) -> MenuItem:
        return MenuItem(
            name,
            lambda icon, item: controller.set_profile(name),
            checked=lambda item, n=name: controller.config.data.get("active_profile") == n,
            radio=True,
        )

    def profiles_menu():
        return Menu(*[make_profile_item(n) for n in controller.config.profile_names()])

    def status_text(item):
        st = controller.status()
        conn = "● connected" if st["connected"] else "○ no device"
        return f"{conn} — {st['profile']} / {st['page_name']}"

    def toggle_autostart(icon, item):
        autostart.toggle()
        icon.update_menu()

    return Menu(
        MenuItem(status_text, None, enabled=False),
        Menu.SEPARATOR,
        MenuItem("Open Configurator", lambda icon, item: on_open(), default=True),
        MenuItem("Profile", profiles_menu()),
        MenuItem("Reload config", lambda icon, item: controller.request_reload()),
        MenuItem("Start with Windows", toggle_autostart, checked=lambda item: autostart.is_enabled()),
        Menu.SEPARATOR,
        MenuItem("Quit", lambda icon, item: on_quit()),
    )


def main() -> None:
    start_hidden = ("--tray" in sys.argv) or ("--hidden" in sys.argv)

    if not _single_instance():
        # Already running: ask the live instance to raise its window, then exit.
        try:
            urllib.request.urlopen(
                urllib.request.Request(UI_URL + "api/show_window", method="POST"), timeout=2)
        except Exception:
            pass
        return

    config = Config.load()
    controller = DockController(config)
    controller.start()
    threading.Thread(target=run_ui, args=(controller,),
                     kwargs={"on_show_window": _show_window}, name="dock-ui", daemon=True).start()
    _wait_for_server()

    # Tray icon runs in a background thread (Windows permits a non-main-thread tray);
    # the main thread is reserved for the WebView2 GUI loop.
    icon = pystray.Icon("AjazzDock", icon_image(64), "AjazzDock")

    def do_quit():
        global _quitting
        _quitting = True
        try:
            controller.stop()
        except Exception:
            pass
        try:
            if _window:
                _window.destroy()
        except Exception:
            pass
        try:
            icon.stop()
        except Exception:
            pass

    icon.menu = build_menu(controller, _show_window, do_quit)

    def on_status():
        try:
            icon.update_menu()
        except Exception:
            pass
    controller.on_status = on_status
    threading.Thread(target=icon.run, name="dock-tray", daemon=True).start()

    # Native configurator window (Edge WebView2) on the main thread.
    global _window
    try:
        _window = webview.create_window(
            "AjazzDock — Configurator", UI_URL,
            width=1040, height=740, min_size=(820, 600), hidden=start_hidden)

        def on_closing():
            if _quitting:
                return True            # allow the real close
            _window.hide()             # X minimizes to tray instead of quitting
            return False
        _window.events.closing += on_closing

        webview.start(gui="edgechromium")
    except Exception as e:
        # WebView2 unavailable -> degrade to a browser window, keep tray alive.
        print(f"[webview] native window unavailable ({e}); falling back to browser.")
        if not start_hidden:
            try:
                webbrowser.open(UI_URL)
            except Exception:
                pass
        threading.Event().wait()
        return

    # webview.start() returned => window destroyed => shut down cleanly.
    try:
        controller.stop()
    finally:
        try:
            icon.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
