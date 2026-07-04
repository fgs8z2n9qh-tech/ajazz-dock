"""Folder open/close zoom transition: frame generation + controller wiring (no real device)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dock.images import folder_transition_frames, render_face
from dock.config import Config, default_config
from dock.controller import DockController

def diff(a, b):
    ba, bb = a.convert("RGB").tobytes(), b.convert("RGB").tobytes()
    return sum(abs(x - y) for x, y in zip(ba, bb))

old = [render_face({"label": f"P{i}", "color": "#202020"}) for i in range(6)]
new = [render_face({"label": f"F{i}", "color": "#0050a0"}) for i in range(6)]

# 1) frame generation: 10 frames x 6 faces, progressing page -> folder on open
fo = folder_transition_frames(old, new, opening=True)
assert len(fo) == 10 and all(len(f) == 6 for f in fo), len(fo)
assert diff(fo[0][0], old[0]) < diff(fo[0][0], new[0]), "first open frame should look like the page"
assert diff(fo[-1][0], new[0]) < diff(fo[-1][0], old[0]), "last open frame should look like the folder"
print("OK open frames progress page -> folder")

fc = folder_transition_frames(old, new, opening=False)   # base=new(page revealed), mover=old(folder)
assert len(fc) == 10 and diff(fc[-1][0], new[0]) < diff(fc[-1][0], old[0]), "close should reveal the page"

# every selectable style produces valid 6-face frames (open + close), incl. iPhone 'expand'
from dock.images import FOLDER_ANIM_ORDER
for nm in FOLDER_ANIM_ORDER:
    for opening in (True, False):
        for src in (0, 5):                       # expand grows from the pressed key
            frs = folder_transition_frames(old, new, opening=opening, name=nm, frames=8, src=src)
            assert len(frs) == 8 and all(len(f) == 6 and all(im.size == old[0].size for im in f)
                                         for f in frs), (nm, opening, src)
# 'expand' from key 0 vs key 5 differ (it really uses the source key)
e0 = folder_transition_frames(old, new, True, name="expand", frames=8, src=0)[2][0].tobytes()
e5 = folder_transition_frames(old, new, True, name="expand", frames=8, src=5)[2][0].tobytes()
assert e0 != e5, "expand should depend on the source key"
print(f"OK all {len(FOLDER_ANIM_ORDER)} folder styles render: {FOLDER_ANIM_ORDER}")

# expand uses a LAZY per-frame generator (no upfront stall): (n, fn) with fn(i) -> 6 faces
from dock.images import expand_gen
n, fn = expand_gen(old, new, True, 14, src=0)
assert n == 14 and callable(fn)
f0 = fn(0)
assert len(f0) == 6 and all(im.size == old[0].size for im in f0)
assert fn(13)[0].tobytes() != f0[0].tobytes(), "expand frames should change over time"
print("OK expand_gen is a lazy per-frame generator")
print("OK close frames reveal the page")

# 2) controller wiring with a fake device
class FakeDock:
    image_rotation, image_mirror = 90, False
    def __init__(self): self.pushes = 0; self.flushes = 0
    def set_key_pil(self, *a, **k): self.pushes += 1
    def set_key_image(self, *a, **k): self.pushes += 1
    def flush(self): self.flushes += 1

data = default_config()
prof = data["profiles"][0]
prof["folders"] = {"f1": {"name": "Apps", "items": {"key1": {"label": "FF", "icon": "🦊"}}}}
prof["pages"][0]["items"]["key1"] = {"label": "Apps", "icon": "📁",
                                     "action": {"type": "folder", "folder": "f1"}}
ctrl = DockController(Config(data))
ctrl.dock = FakeDock(); ctrl.connected = True

ctrl.enter_folder("f1")
assert ctrl._folder == "f1" and ctrl._page_anim is not None, "open animation not started"
fd = ctrl.dock
ctrl._page_anim["start"] = time.time() - 0.05            # advance a couple frames
ctrl._advance_page_anim()
assert fd.pushes >= 6, f"expected frame push, got {fd.pushes}"
ctrl._page_anim["start"] = time.time() - 999             # settle
ctrl._advance_page_anim()
assert ctrl._page_anim is None, "open animation didn't settle"
print("OK enter_folder ran + settled the open animation")

ctrl.folder_back()
assert ctrl._folder is None and ctrl._page_anim is not None, "close animation not started"
ctrl._page_anim["start"] = time.time() - 999
ctrl._advance_page_anim()
assert ctrl._page_anim is None
print("OK folder_back ran + settled the close animation")

# 3) transitions off -> snaps (no animation)
data["page_fx"] = False
ctrl2 = DockController(Config(data)); ctrl2.dock = FakeDock(); ctrl2.connected = True
ctrl2.enter_folder("f1")
assert ctrl2._page_anim is None and ctrl2._render_requested, "should snap when page_fx is off"
print("OK page_fx off -> folder snaps (no animation)")

print("\nALL OK")
