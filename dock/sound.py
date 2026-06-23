"""Soundboard playback: play an audio clip to a chosen output device.

For a Discord soundboard, set the device to whatever Discord uses as its mic input
(a virtual cable / NGENUITY virtual device), and enable monitor to also hear it.
"""
from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd
import soundfile as sf


def list_outputs():
    """Names of playback-capable devices (deduplicated, in enumeration order)."""
    out, seen = [], set()
    for d in sd.query_devices():
        if d["max_output_channels"] > 0 and d["name"] not in seen:
            seen.add(d["name"])
            out.append(d["name"])
    return out


def _resolve(name):
    if not name:
        return None                       # system default
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0 and d["name"] == name:
            return i
    return None


def _play_to(data, sr, dev):
    try:
        with sd.OutputStream(samplerate=sr, channels=data.shape[1], device=dev,
                             dtype="float32") as s:
            s.write(data)
    except Exception as e:
        print(f"[sound] device {dev!r}: {e}")


def play(path, device=None, monitor=False, gain=1.0):
    """Play `path` to `device` (name or None=default); optionally also on default speakers."""
    def run():
        try:
            data, sr = sf.read(path, dtype="float32", always_2d=True)
        except Exception as e:
            print(f"[sound] read {path!r}: {e}")
            return
        g = float(gain or 1.0)
        if g != 1.0:
            data = np.clip(data * g, -1.0, 1.0)
        targets = [_resolve(device)]
        if monitor and device:
            targets.append(None)
        for dev in targets:
            threading.Thread(target=_play_to, args=(data, sr, dev), daemon=True).start()

    threading.Thread(target=run, daemon=True).start()


def stop():
    sd.stop()
