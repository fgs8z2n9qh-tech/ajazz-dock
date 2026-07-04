"""Encoder brightness/colour must COALESCE: a fast burst of ticks -> few bulb writes, right value.

Uses a fake kasa device so no real bulb is touched; exercises the real tapo coalescing task on the
real background event loop.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AJAZZDOCK_CONFIG", os.path.join(os.environ.get("TEMP", "/tmp"), "_nudge_cfg.json"))

import dock.tapo as TP


class FakeLight:
    def __init__(self):
        self.brightness = 50
        self.hsv = (0, 100, 100)
        self.bri_calls = 0
        self.hsv_calls = 0

    async def set_brightness(self, v):
        self.brightness = int(v); self.bri_calls += 1

    async def set_hsv(self, h, s, v):
        self.hsv = (int(h), int(s), int(v)); self.hsv_calls += 1


class FakeDev:
    def __init__(self):
        self.is_on = True
        self._fl = FakeLight()

    async def turn_on(self):
        self.is_on = True

    async def turn_off(self):
        self.is_on = False

    async def update(self):
        pass


fake = FakeDev()


async def _fake_connect(host, user, pw):
    return fake


TP._connect = _fake_connect
TP._light = lambda dev: dev._fl

# ---- 1) a fast burst of +1 brightness ticks reaches the right value with FAR fewer writes ------
for _ in range(20):
    TP.nudge("1.2.3.4", "u", "p", "bri", 1)
time.sleep(0.6)
fl = fake._fl
assert fl.brightness == 70, ("brightness should accumulate 50+20", fl.brightness)
assert fl.bri_calls <= 5, ("ticks must coalesce into a few writes, not one-per-tick", fl.bri_calls)
print(f"OK brightness coalesced: 20 ticks -> {fl.bri_calls} write(s), value={fl.brightness}")

# ---- 2) clamping at 100 ------------------------------------------------------------------------
before = fl.bri_calls
for _ in range(60):
    TP.nudge("1.2.3.4", "u", "p", "bri", 1)
time.sleep(0.6)
assert fl.brightness == 100, ("must clamp at 100", fl.brightness)
print(f"OK brightness clamps at 100 (writes={fl.bri_calls - before})")

# ---- 3) hue wraps mod 360 and also coalesces ---------------------------------------------------
for _ in range(15):
    TP.nudge("1.2.3.4", "u", "p", "hue", 30)   # +450 -> 0 + 450 = 90 (mod 360)
time.sleep(0.6)
assert fl.hsv[0] == 90, ("hue should wrap mod 360 (0+450)%360=90", fl.hsv)
assert fl.hsv_calls <= 5, ("hue ticks must coalesce", fl.hsv_calls)
print(f"OK hue coalesced + wraps: 15 ticks -> {fl.hsv_calls} write(s), hue={fl.hsv[0]}")

print("\nRESULT: ALL PASS")
sys.stdout.flush()
os._exit(0)
