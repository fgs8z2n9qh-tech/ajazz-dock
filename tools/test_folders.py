"""Headless test for folder navigation in the controller + action engine (no device)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image                                   # noqa: E402
from dock.config import Config, default_config          # noqa: E402
from dock.controller import DockController              # noqa: E402

data = default_config()
prof = data["profiles"][0]
prof["folders"] = {"f1": {"name": "Apps", "items": {
    "key1": {"label": "FF", "action": {"type": "open", "target": "firefox"}}}}}
prof["pages"][0]["items"]["key1"] = {"label": "Apps", "action": {"type": "folder", "folder": "f1"}}

ctrl = DockController(Config(data))
fails = []


def check(name, cond):
    print(("  ok " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


check("page key1 is a folder action", ctrl._current_items()["key1"]["action"]["type"] == "folder")
ctrl.engine.execute({"type": "folder", "folder": "f1"})
check("folder action entered the folder", ctrl._folder == "f1")
check("current items are the folder's items", ctrl._current_items().get("key1", {}).get("label") == "FF")
check("binding for key1 = folder item", ctrl._binding_for("key1")["action"]["target"] == "firefox")
check("last key renders a Back face", isinstance(ctrl._face_for_index(5), Image.Image))
check("first key renders a face", isinstance(ctrl._face_for_index(0), Image.Image))
ctrl.folder_back()
check("folder_back exits to the page", ctrl._folder is None)
check("items are the page again", ctrl._current_items()["key1"]["action"]["type"] == "folder")
ctrl.enter_folder("f1")
ctrl.next_page()
check("changing page exits the folder", ctrl._folder is None)
ctrl.enter_folder("does-not-exist")
check("unknown folder id is ignored", ctrl._folder is None)

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
