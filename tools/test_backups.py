"""Isolated functional test for dock.backups — proves restore/export/import never lose data.

Points APPDATA at a throwaway temp dir so the real config is untouched. Run with any python.
"""
import os
import sys
import json
import tempfile
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

tmp = tempfile.mkdtemp(prefix="ajtest-")
os.environ["APPDATA"] = tmp
os.environ.pop("AJAZZDOCK_CONFIG", None)

from dock.config import Config, config_path, backups_dir  # noqa: E402
from dock import backups  # noqa: E402

fails = []


def check(name, cond):
    print(("  ok " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def live():
    with open(config_path(), encoding="utf-8-sig") as f:
        return json.load(f)


# 1. initial save creates the live file + one history snapshot
cfg = Config.load()
cfg.data["profiles"][0]["pages"][0]["items"]["key1"] = {
    "label": "Mixtape", "icon": "M", "action": {"type": "open", "target": "Mixtape.exe"}}
cfg.save()
check("live config has Mixtape", live()["profiles"][0]["pages"][0]["items"]["key1"]["label"] == "Mixtape")
check("save wrote a history snapshot", len(backups.list_backups()) >= 1)

# 2. manual snapshot of the Mixtape state
snap_mix = backups.snapshot("manual")
check("manual snapshot exists", os.path.exists(snap_mix))

# 3. mutate + save, then restore the Mixtape snapshot
cfg.data["profiles"][0]["pages"][0]["items"]["key1"]["label"] = "CHANGED"
cfg.save()
check("live now CHANGED", live()["profiles"][0]["pages"][0]["items"]["key1"]["label"] == "CHANGED")

n_before = len(backups.list_backups())
ok = backups.restore(snap_mix)
check("restore returned True", ok)
check("restore brought Mixtape back", live()["profiles"][0]["pages"][0]["items"]["key1"]["label"] == "Mixtape")
check("restore first backed up CHANGED (count grew)", len(backups.list_backups()) == n_before + 1)

# 4. export then corrupt then import
exp = os.path.join(tmp, "exported.json")
check("export ok", backups.export_to(exp) and os.path.exists(exp))
with open(config_path(), "w", encoding="utf-8") as f:
    f.write("{ this is not valid json")             # simulate corruption
ok = backups.import_from(exp)
check("import returned True", ok)
check("import restored Mixtape", live()["profiles"][0]["pages"][0]["items"]["key1"]["label"] == "Mixtape")

# 5. invalid sources are rejected, not applied
bad = os.path.join(tmp, "bad.json")
with open(bad, "w") as f:
    f.write("not json")
check("restore rejects garbage", backups.restore(bad) is False)
check("import rejects garbage", backups.import_from(bad) is False)
check("live still intact after rejects", live()["profiles"][0]["pages"][0]["items"]["key1"]["label"] == "Mixtape")

shutil.rmtree(tmp, ignore_errors=True)
print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILURE(S): {fails}")
sys.exit(1 if fails else 0)
