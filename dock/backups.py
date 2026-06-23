"""Backup history + export/import for the AjazzDock config.

Every operation that writes the live config (restore, import) snapshots the current
config FIRST, so a restore/import can itself always be undone. Reads tolerate a BOM.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
from typing import Any, Dict, List

from .config import backups_dir, config_path

_PREFIX = "config-"
_SUFFIX = ".json"


def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def snapshot(reason: str = "") -> str:
    """Copy the live config into the backups folder (bypasses the save throttle)."""
    src = config_path()
    tag = ("-" + "".join(c for c in reason if c.isalnum())) if reason else ""
    dst = os.path.join(backups_dir(), f"{_PREFIX}{_stamp()}{tag}{_SUFFIX}")
    if os.path.exists(src):
        shutil.copyfile(src, dst)
    _prune()
    return dst


def _prune(keep: int = 40) -> None:
    d = backups_dir()
    snaps = sorted(f for f in os.listdir(d) if f.startswith(_PREFIX) and f.endswith(_SUFFIX))
    for old in snaps[:-keep]:
        try:
            os.remove(os.path.join(d, old))
        except OSError:
            pass


def _read(path: str) -> Dict[str, Any] | None:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and "profiles" in d else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _summary(path: str) -> Dict[str, Any]:
    d = _read(path)
    if d is None:
        return {"ok": False, "pages": 0, "keys": 0}
    profs = d.get("profiles", [])
    pages = sum(len(p.get("pages", [])) for p in profs)
    keys = sum(len(pg.get("items", {})) for p in profs for pg in p.get("pages", []))
    return {"ok": True, "pages": pages, "keys": keys}


def list_backups() -> List[Dict[str, Any]]:
    """Newest-first list of backups with a quick summary."""
    d = backups_dir()
    out: List[Dict[str, Any]] = []
    for f in sorted(os.listdir(d), reverse=True):
        if not (f.startswith(_PREFIX) and f.endswith(_SUFFIX)):
            continue
        p = os.path.join(d, f)
        try:
            st = os.stat(p)
        except OSError:
            continue
        out.append({
            "name": f, "path": p,
            "when": datetime.datetime.fromtimestamp(st.st_mtime),
            "size": st.st_size, **_summary(p),
        })
    return out


def _write_live(src_path: str) -> bool:
    """Atomically copy `src_path` over the live config (validating it first)."""
    if _read(src_path) is None:
        return False
    dst = config_path()
    tmp = dst + ".tmp"
    shutil.copyfile(src_path, tmp)
    os.replace(tmp, dst)
    return True


def restore(path: str) -> bool:
    """Make `path` the live config — after backing up whatever is live now."""
    if _read(path) is None:
        return False
    snapshot("prerestore")
    return _write_live(path)


def export_to(dest: str) -> bool:
    src = config_path()
    if not os.path.exists(src):
        return False
    shutil.copyfile(src, dest)
    return True


def import_from(src: str) -> bool:
    """Replace the live config with `src` — after backing up the current one."""
    if _read(src) is None:
        return False
    snapshot("preimport")
    return _write_live(src)
