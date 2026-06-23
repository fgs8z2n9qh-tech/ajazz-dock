"""Push real faces rendered at the new native KEY_SIZE to the device, to calibrate by eye:
solid-colour keys show whether the fill reaches the cell edge; emoji/text keys show sharpness.

Run with the AjazzDock app CLOSED. Relaunch the app afterwards to restore.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dock.device import AKP03, KEY_SIZE              # noqa: E402
from dock.images import render_face                   # noqa: E402

FACES = [
    {"color": "#16d886"},                              # key1: solid mint  -> does the fill reach the edge?
    {"icon": "🎵", "color": "#15202c"},                # key2: emoji on dark
    {"label": "TEST", "color": "#2a3340"},             # key3: text
    {"icon": "🔥", "color": "#20101a"},                # key4: emoji
    {"icon": "🎮", "color": "#241a40"},                # key5: emoji
    {"color": "#ff5b5b"},                              # key6: solid red (opposite corner fill check)
]


def main() -> int:
    if not AKP03.is_present():
        print("AKP03 NOT found. Plugged in? App still holding it?")
        return 1
    dev = AKP03().open()
    try:
        dev.set_brightness(85)
        for key, item in enumerate(FACES):
            dev.set_key_pil(key, render_face(item))
        dev.flush()
    finally:
        dev.close()
    print(f"pushed 6 real faces rendered at KEY_SIZE={KEY_SIZE}.")
    print("Check: do the solid mint/red keys FILL the cell to the edge? are the emoji/text crisp?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
