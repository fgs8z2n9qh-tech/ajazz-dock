"""Verify send_scancode_combo builds the right physical key sequence (no real input)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import dock.actions as A                                  # noqa: E402

fails = []


def check(name, cond):
    print(("  ok " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


rec = []
A._scan_event = lambda code, down: rec.append((hex(code), "down" if down else "up"))

rec.clear()
ok = A.send_scancode_combo("[")
check("'[' maps to physical OEM_4 0x1a", ok and rec == [("0x1a", "down"), ("0x1a", "up")])

rec.clear()
ok = A.send_scancode_combo("]")
check("']' maps to physical OEM_6 0x1b", ok and rec == [("0x1b", "down"), ("0x1b", "up")])

rec.clear()
ok = A.send_scancode_combo("ctrl+z")
check("ctrl+z presses ctrl then z, releases reversed",
      ok and rec == [("0x1d", "down"), ("0x2c", "down"), ("0x2c", "up"), ("0x1d", "up")])

rec.clear()
ok = A.send_scancode_combo("1")
check("digit '1' maps to scancode 0x02 (not layout char)", ok and rec == [("0x2", "down"), ("0x2", "up")])

ok = A.send_scancode_combo("brush-rotate-unmapped")
check("unmapped token returns False (falls back to keyboard.send)", ok is False)

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
