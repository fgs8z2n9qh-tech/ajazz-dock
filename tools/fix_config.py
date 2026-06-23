"""Set dock brightness to 70 and migrate encoder/button bindings to profile globals,
on the REAL %APPDATA% config. Run with a NON-MSIX python (Programs\\Python), not the venv."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dock.config import _migrate  # noqa: E402

p = os.path.join(os.environ["APPDATA"], "AjazzDock", "config.json")
with open(p, encoding="utf-8") as fh:
    d = json.load(fh)
print("before: brightness", d.get("brightness"), "pages", len(d["profiles"][0]["pages"]))
if d.get("brightness", 0) < 15:
    d["brightness"] = 70
d = _migrate(d)
with open(p, "w", encoding="utf-8") as fh:
    json.dump(d, fh, indent=2, ensure_ascii=False)
print("after : brightness", d["brightness"], "pages", len(d["profiles"][0]["pages"]),
      "globals", list(d["profiles"][0].get("globals", {}).keys()))
