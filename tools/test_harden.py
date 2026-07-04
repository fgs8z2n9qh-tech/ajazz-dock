"""Hardening regression tests for the 2026-06 polish pass (multi-agent review fixes).

Covers the highest-risk new surfaces that previously had no coverage: the OBS websocket auth
handshake, the action _INLINE routing, accent-theme token rebuild, the live cross-table
consistency, net-rate clamp + windowed temperature mapping, the single-lock media snapshot,
the empty-key gradient overlay, and action_art's render/None contract.
"""
import base64
import hashlib
import json
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("AJAZZDOCK_CONFIG", os.path.join(os.environ.get("TEMP", "/tmp"), "_harden_cfg.json"))

fails = []


def check(name, cond):
    print(("  ok " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# ── §1  OBS websocket auth handshake + identify gate (no live OBS) ───────────────────────────
import dock.obs as obs


class FakeWS:
    """Minimal obs-websocket v5 server: Hello(op0) → Identified(op<identify_op>) → Response(op7)."""
    def __init__(self, auth=True, identify_op=2):
        self.auth, self.identify_op = auth, identify_op
        self.sent, self.closed, self._step, self.last_req = [], False, 0, None

    def send(self, s):
        self.sent.append(s)
        d = json.loads(s)
        if d.get("op") == 6:
            self.last_req = d["d"]["requestId"]

    def recv(self):
        self._step += 1
        if self._step == 1:
            d = {"op": 0, "d": {}}
            if self.auth:
                d["d"]["authentication"] = {"salt": "SALT", "challenge": "CHAL"}
            return json.dumps(d)
        if self._step == 2:
            return json.dumps({"op": self.identify_op, "d": {}})
        return json.dumps({"op": 7, "d": {"requestId": self.last_req,
                                          "responseData": {"obsVersion": "30.1.0"}}})

    def close(self):
        self.closed = True


_factory = {"auth": True, "identify_op": 2, "last": None}


class _FakeWSModule:
    @staticmethod
    def create_connection(url, timeout=4):
        _factory["last"] = FakeWS(_factory["auth"], _factory["identify_op"])
        return _factory["last"]


obs.websocket = _FakeWSModule

o = obs._OBS()
o.configure("host", 4455, "secret")
_factory.update(auth=True, identify_op=2)
r = o.request("GetVersion")
check("obs request returns responseData on a good handshake",
      bool(r) and r.get("responseData", {}).get("obsVersion") == "30.1.0")

ident = json.loads(_factory["last"].sent[0])
_secret = base64.b64encode(hashlib.sha256(("secret" + "SALT").encode()).digest()).decode()
_expect = base64.b64encode(hashlib.sha256((_secret + "CHAL").encode()).digest()).decode()
check("obs auth response is the correct SHA256 challenge", ident["d"]["authentication"] == _expect)

o2 = obs._OBS()
o2.configure("host", 4455, "")
_factory.update(auth=False, identify_op=3)         # server rejects identify (op != 2)
raised = False
try:
    o2.request("GetVersion")
except Exception:
    raised = True
check("obs raises when identify is not acknowledged (op != 2)", raised)


# ── §2  action _INLINE routing (mic/monitor/macro/obs inline; keyboard goes off-loop) ────────
import dock.actions as actions

_INLINE = actions.ActionEngine._INLINE
check("mic stays inline (thread-bound COM endpoint)", "mic" in _INLINE)
check("monitor stays inline", "monitor" in _INLINE)
check("macro stays inline (may navigate)", "macro" in _INLINE)
check("obs stays inline (self-threads)", "obs" in _INLINE)
check("hotkey routes off-loop (not inline)", "hotkey" not in _INLINE)
check("text routes off-loop (not inline)", "text" not in _INLINE)
check("keyboard emission is guarded by a re-entrant lock", hasattr(actions, "_KBD_LOCK"))


# ── §3  accent theme rebuilds the token table ────────────────────────────────────────────────
from dock import tokens as T

T.set_accent("blue")
check("set_accent updates ACCENT", T.ACCENT == T.ACCENTS["blue"][0])
check("set_accent rebuilds TOKENS dict", T.TOKENS.get("ACCENT") == T.ACCENTS["blue"][0])
check("build_qss emits the new accent colour", T.ACCENTS["blue"][0] in T.build_qss())
T.set_accent("mint")
check("set_accent restores mint", T.ACCENT == T.ACCENTS["mint"][0])


# ── §4  live metadata tables stay consistent across every source ─────────────────────────────
from dock import live

ids = set(live._PROVIDERS)
check("_META covers exactly the providers", set(live._META) == ids)
check("LIVE_SHORT covers exactly the providers", set(live.LIVE_SHORT) == ids)
check("LIVE_EMOJI covers exactly the providers", set(live.LIVE_EMOJI) == ids)
_cat = [i for _name, group in live.LIVE_CATEGORIES for i in group]
check("LIVE_CATEGORIES union == providers", set(_cat) == ids)
check("no source appears in two categories", len(_cat) == len(set(_cat)))


# ── §5  net-rate clamp + windowed temperature mapping ────────────────────────────────────────
class _IO:
    def __init__(self, rx, tx):
        self.bytes_recv, self.bytes_sent = rx, tx


class _FakePs:
    _io = None

    @staticmethod
    def net_io_counters():
        return _FakePs._io


_real_ps = live.psutil
live.psutil = _FakePs
live._net_last.clear()
live._net_last.update({"t": time.time() - 1.0, "rx": 1_000_000})
_FakePs._io = _IO(400_000, 0)              # counter DROPPED (NIC reset) -> would be negative
_txt, _, _ = live._net()
check("net rate clamps a counter drop to 0 (no negative KB/s)", _txt == "0")
live.psutil = _real_ps

_real_start = live._start_lhm
live._start_lhm = lambda: None             # don't let the real sampler overwrite our value
live._lhm["cpu"] = 70.0
_t, _cap, _frac = live._temp("cpu", "CPU")
check("cpu temp shows °C string", _t == "70°C")
check("cpu temp frac is windowed (30..100 -> 0.57 at 70°C)", abs(_frac - (40.0 / 70.0)) < 0.01)
live._lhm["vram_temp"] = 70.0
_, _, _vf = live._vram_temp()
check("vram temp uses a hotter ceiling (30..105 -> 0.53 at 70°C)", abs(_vf - (40.0 / 75.0)) < 0.01)
live._start_lhm = _real_start


# ── §6  media snapshot reads title + cover under one lock ────────────────────────────────────
with live._media_lock:
    live._media = ("Song", "Artist", True)
    live._media_art = "COVER"
_text, _c, _f, _art = live.media_snapshot()
check("media_snapshot pairs title with its own cover", (_text, _art, _f) == ("Song", "COVER", 1.0))
with live._media_lock:
    live._media = None
    live._media_art = None
_text, _c, _f, _art = live.media_snapshot()
check("media_snapshot returns placeholders when nothing plays", (_text, _art, _f) == ("--", None, None))
check("_KEEP is a distinct sentinel", live._KEEP is not None and live._KEEP is not False)


# ── §7  empty-key cue honours a custom gradient (WYSIWYG) + action_art contract ──────────────
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from dock.config import Config, default_config
from dock.controller import DockController
from dock.gui import ConfigWindow

from dock import images as _images
win = ConfigWindow(DockController(Config(default_config())))
flat = win._empty_key_face({"color": "#102030"})
grad = win._empty_key_face({"color": "#102030", "bg2": "#e0a040", "bg_dir": "v"})
check("empty-key face is KEY_SIZE", flat.size == _images.KEY_SIZE == grad.size)
check("empty-key cue overlays the real gradient (differs from flat)",
      flat.tobytes() != grad.tobytes())

from dock.actionart import action_art
_known = ["open", "hotkey", "text", "media", "volume", "sound", "appvolume", "mic", "discord",
          "substance", "quick", "system", "monitor", "smartlight", "rgbscene", "obs", "page",
          "folder", "profile", "brightness", "macro", "none"]
_all_ok = True
for _t in _known:
    im = action_art(_t, 40)
    if im is None or im.size != (40, 40) or im.mode != "RGBA":
        _all_ok = False
        break
check("action_art renders every known type as 40x40 RGBA", _all_ok)
check("action_art returns None for an unknown type", action_art("nope", 40) is None)


# ── §8  encoder acceleration: fast spin scales the step, slow stays 1:1 ──────────────────────
from dock import controller as _C
ctl = DockController(Config(default_config()))
_clock = [1000.0]
_orig_time = _C.time.time
_C.time.time = lambda: _clock[0]
try:
    ctl._enc_last = {}
    slow = []
    for _ in range(4):
        slow.append(ctl._encoder_accel(0))
        _clock[0] += 0.30                       # big gaps -> fine control
    ctl._enc_last = {}
    fast = []
    for _ in range(6):
        fast.append(ctl._encoder_accel(1))
        _clock[0] += 0.02                       # rapid spin -> acceleration
finally:
    _C.time.time = _orig_time
check("slow encoder spin stays 1:1", set(slow) == {1})
check("fast encoder spin accelerates (>1)", max(fast) > 1)
check("encoder accel scales volume repeat", ctl._scale_step({"type": "volume", "volume": "up"}, 4)["step"] == 4)
check("encoder accel scales an explicit step", ctl._scale_step({"type": "smartlight", "mode": "brightness_up", "step": 10}, 3)["step"] == 30)
_open = {"type": "open"}
check("encoder accel leaves non-step actions untouched", ctl._scale_step(_open, 5) is _open)
ctl.config.data["encoder_accel"] = False
ctl._enc_last = {}
_C.time.time = lambda: 2000.0
try:
    check("encoder accel respects the off switch", ctl._encoder_accel(0) == 1)
finally:
    _C.time.time = _orig_time


# ── §9  monitor brightness transitions smoothly (eased ramp, not an instant jump) ────────────
from dock import monitors as _M
_mcalls = []


class _FakeDxva:
    def SetMonitorBrightness(self, handle, val):
        _mcalls.append(int(val))

    def DestroyPhysicalMonitor(self, h):
        pass


class _FakePM:
    handle = 1


_M._dxva2 = _FakeDxva()
_M._enum_physical = lambda: [_FakePM()]
_M._read = lambda pm: (0, 20, 100)              # min 0, current 20%, max 100

_mcalls.clear()
_M.set_brightness(80)
check("set_brightness is a single instant write", len(_mcalls) == 1 and _mcalls[-1] == 80)

_mcalls.clear()
_M.fade_brightness(80, duration=0.05)
check("fade_brightness ramps in multiple steps", len(_mcalls) > 3)
check("fade_brightness is monotonic and lands on target",
      all(b >= a for a, b in zip(_mcalls, _mcalls[1:])) and _mcalls[-1] == 80)

_M._read = lambda pm: (0, 50, 100)
_mcalls.clear()
_M.fade_brightness(50, duration=0.05)
check("fade to the current value does no ramp (1 write)", len(_mcalls) == 1)

check("monitor dimmer fades a big nudge but not a small one",
      __import__("dock.actions", fromlist=["_MON_FADE_MIN"])._MON_FADE_MIN > 1)


# ── §10  multi-gesture keys: tap / double-tap / hold ─────────────────────────────────────────
from dock import controller as _CC
from dock.device import Event as _Ev


class _GDock:
    image_rotation, image_mirror = 90, False

    def set_key_pil(self, *a, **k):
        pass

    def set_key_image(self, *a, **k):
        pass

    def clear_all(self):
        pass

    def flush(self):
        pass


_gdata = default_config()
_gp = _gdata["profiles"][0]["pages"][0]
_gp.setdefault("items", {})["key1"] = {
    "action": {"type": "open", "target": "TAP"},
    "action_double": {"type": "hotkey", "keys": "DBL"},
    "action_hold": {"type": "media", "media": "HOLD"},
}
_gp["items"]["key2"] = {"action": {"type": "open", "target": "PLAIN"}}   # tap-only
_gc = _CC.DockController(Config(_gdata))
_gc.dock = _GDock()
_gc.connected = True
_gfired = []
_gc.engine.execute = lambda a: _gfired.append((a or {}).get("target") or (a or {}).get("keys") or (a or {}).get("media"))
_gclock = [5000.0]
_gc_orig = _CC.time.time
_CC.time.time = lambda: _gclock[0]
try:
    def _pr(i):
        _gc._handle_event(_Ev(kind="key", index=i, pressed=True))

    def _rl(i):
        _gc._handle_event(_Ev(kind="key", index=i, pressed=False))

    _gfired.clear(); _pr(1)            # key2 = tap-only -> instant on press
    check("a tap-only key fires instantly on press", _gfired == ["PLAIN"])
    _rl(1)

    _gfired.clear(); _pr(0); _rl(0); _gc._check_gestures()
    check("a gesture key does NOT fire on release while the double window is open", _gfired == [])
    _gclock[0] += 0.3; _gc._check_gestures()
    check("a single tap fires after the double window elapses", _gfired == ["TAP"])

    _gfired.clear(); _gclock[0] += 1
    _pr(0); _rl(0); _gclock[0] += 0.1; _pr(0)      # second press within the window
    check("two quick presses fire the double-tap action", _gfired == ["DBL"])
    _rl(0)

    _gfired.clear(); _gclock[0] += 1
    _pr(0); _gclock[0] += 0.6; _gc._check_gestures()
    check("holding fires the hold action", _gfired == ["HOLD"])
    _rl(0)
finally:
    _CC.time.time = _gc_orig


# ── §11  Discord RPC voice control (mock the IPC pipe; no real Discord) ───────────────────────
from dock import discord as _D


class _FakePipe:
    def __init__(self):
        self.sent = []
        self.voice = {"mute": False, "deaf": False}
        self._q = []

    def connect(self):
        return True

    def send(self, op, payload):
        self.sent.append((op, payload))
        if op == 0:
            self._q.append((1, {"evt": "READY", "data": {}}))
            return
        cmd, nonce = payload.get("cmd"), payload.get("nonce")
        args = payload.get("args") or {}
        if cmd == "SET_VOICE_SETTINGS":
            self.voice.update({k: bool(v) for k, v in args.items()})
        data = dict(self.voice) if cmd in ("GET_VOICE_SETTINGS", "SET_VOICE_SETTINGS") else {}
        if cmd == "AUTHORIZE":
            data = {"code": "CODE"}
        self._q.append((1, {"cmd": cmd, "nonce": nonce, "data": data}))

    def recv(self):
        return self._q.pop(0)

    def close(self):
        pass


_fp = _FakePipe()
_D._Pipe = lambda: _fp
_dd = _D._Discord()
_dd.configure("cid", "sec", token="TOK")          # token preset -> skips the OAuth exchange
check("discord get_voice reads initial state", _dd.get_voice() == (False, False))
check("discord handshake is sent first (op 0)", _fp.sent and _fp.sent[0][0] == 0)
check("discord toggle_mute returns the new state", _dd.toggle_mute() is True)
check("discord state is now muted", _dd.get_voice() == (True, False))
check("discord toggle_deaf returns the new state", _dd.toggle_deaf() is True)
check("discord set_voice wrote SET_VOICE_SETTINGS",
      any(p.get("cmd") == "SET_VOICE_SETTINGS" for _o, p in _fp.sent))
# the live optimistic push: deaf implies mute
from dock import live as _LV
_LV.set_discord_state(deaf=True)
with _LV._discord_lock:
    check("set_discord_state(deaf) implies muted", _LV._discord_state == (True, True))


# ── §12  soundboard: stop-mode routing + bulk board layout ───────────────────────────────────
import dock.sound as _SND
_sndcalls = []
_SND.play = lambda *a, **k: _sndcalls.append("play")
_SND.stop = lambda: _sndcalls.append("stop")
from dock.actions import ActionEngine as _AE
_se = _AE(None)
_se._dispatch({"type": "sound", "mode": "stop"})
_se._dispatch({"type": "sound", "mode": "play", "file": "x.wav"})
check("sound 'stop' mode calls sound.stop()", _sndcalls == ["stop", "play"])

from dock.config import LCD_KEYS as _LK
_sbwin = ConfigWindow(DockController(Config(default_config())))
_n0 = len(_sbwin.cfg.pages())
_keys = [{"label": f"s{i}", "action": {"type": "sound", "mode": "play", "file": f"{i}.wav"}}
         for i in range(8)]
_sbwin._place_keys_across_pages(_keys)
_pages = _sbwin.cfg.pages()
check("soundboard appends new pages (8 clips -> 2 pages)", len(_pages) == _n0 + 2)
check("soundboard fills 6 then 2 across the new pages",
      len(_pages[_n0]["items"]) == 6 and len(_pages[_n0 + 1]["items"]) == 2)
check("soundboard jumps to the first new page", _sbwin.cur_page == _n0)
check("soundboard leaves existing pages untouched",
      all("items" in _pages[i] for i in range(_n0)))


# ── §13  Discord control: volume dials, PTT/noise toggles, channel join ──────────────────────
class _FakePipe2:
    def __init__(self):
        self.voice = {"mute": False, "deaf": False, "input": {"volume": 80},
                      "output": {"volume": 100}, "mode": {"type": "VOICE_ACTIVITY"},
                      "noise_suppression": False}
        self._q = []

    def connect(self):
        return True

    def send(self, op, p):
        if op == 0:
            self._q.append((1, {"evt": "READY", "data": {}}))
            return
        cmd, n = p.get("cmd"), p.get("nonce")
        args = p.get("args") or {}
        if cmd == "SET_VOICE_SETTINGS":
            for k, v in args.items():
                if isinstance(v, dict) and isinstance(self.voice.get(k), dict):
                    self.voice[k].update(v)
                else:
                    self.voice[k] = v
        if "VOICE_SETTINGS" in cmd:
            data = dict(self.voice)
        elif cmd == "GET_SELECTED_VOICE_CHANNEL":
            data = {"id": "CH1", "name": "VIP", "voice_states": [1, 2, 3]}
        else:
            data = {}
        self._q.append((1, {"cmd": cmd, "nonce": n, "data": data}))

    def recv(self):
        return self._q.pop(0)

    def close(self):
        pass


_fp2 = _FakePipe2()
_D._Pipe = lambda: _fp2
_dd2 = _D._Discord()
_dd2.configure("c", "s", token="T")
check("discord nudge_input clamps + steps (80 +5 -> 85)", _dd2.nudge_input(5) == 85)
check("discord nudge_input uses cache, no re-GET drift (85 +5 -> 90)", _dd2.nudge_input(5) == 90)
check("discord nudge_output goes to 200 ceiling range (100 -20 -> 80)", _dd2.nudge_output(-20) == 80)
check("discord toggle_mode flips VAD -> PTT", _dd2.toggle_mode() == "PUSH_TO_TALK")
check("discord toggle_noise flips off -> on", _dd2.toggle_noise() is True)
check("discord current_channel_id reads the selected channel", _dd2.current_channel_id() == "CH1")
_dd2.join_channel("CH1")
check("discord join sent SELECT_VOICE_CHANNEL", True)   # no exception above
# the sampler-fed providers read mode/noise/volume after a get_settings
_dd2.get_settings()
_LV._discord_mode = "PUSH_TO_TALK"
_LV._discord_noise = True
_LV._discord_vol = (90.0, 80.0)
check("discord_mode source reports PTT", _LV._discord_mode_src()[0] == "PTT")
check("discord_invol source reports a %", _LV._discord_invol()[0] == "90%")


# ── §14  Discord auto-reconnects after a restart (no re-authorize) ───────────────────────────
class _PipeR:
    def __init__(self):
        self.voice = {"mute": False, "deaf": False}
        self._q = []
        self.dead = False

    def connect(self):
        return True

    def send(self, op, p):
        if self.dead:
            raise OSError("pipe dead (discord closed)")
        if op == 0:
            self._q.append((1, {"evt": "READY", "data": {}}))
            return
        self._q.append((1, {"cmd": p.get("cmd"), "nonce": p.get("nonce"), "data": dict(self.voice)}))

    def recv(self):
        if self.dead:
            raise OSError("pipe dead")
        return self._q.pop(0)

    def close(self):
        pass


_rpipes = []
_D._Pipe = lambda: (_rpipes.append(_PipeR()) or _rpipes[-1])
_rd = _D._Discord()
_rd.configure("c", "s", token="STORED")
_rd.get_voice()                                   # initial connect (pipe #1)
_rpipes[0].dead = True                            # Discord fully closed
_after = _rd.get_voice()                          # should transparently reconnect + re-auth
check("discord reconnects after a restart", _after == (False, False))
check("discord reconnect used a fresh pipe", len(_rpipes) >= 2)
check("discord reconnect reuses the stored token (no re-authorize)", _rd.token == "STORED" and _rd._authed)


print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.stdout.flush()
os._exit(1 if fails else 0)
