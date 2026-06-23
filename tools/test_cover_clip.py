"""A fit:cover emoji must never clip the tile edges, for any tile aspect (the 'cutting' bug)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dock import images

BG = "#0a0a0a"
bg = images.parse_color(BG)

def edge_is_bg(face):
    w, h = face.size
    px = face.load()
    def near(p): return all(abs(p[i] - bg[i]) <= 6 for i in range(3))
    top    = all(near(px[x, 0])     for x in range(w))
    bot    = all(near(px[x, h - 1]) for x in range(w))
    left   = all(near(px[0, y])     for y in range(h))
    right  = all(near(px[w - 1, y]) for y in range(h))
    return top, bot, left, right

ok = True
for (w, h) in [(65, 65), (88, 88), (120, 60), (60, 120), (87, 86), (130, 70)]:
    for label_on in (False, True):
        item = {"icon": "📁", "color": BG, "fit": "cover",
                "label": "Files" if label_on else "", "show_label": label_on}
        face = images.render_face(item, size=(w, h), show_label=label_on)
        t, b, l, r = edge_is_bg(face)
        # With a label, the bottom strip is the (semi-opaque) label band, so skip bottom there.
        edges_clear = t and l and r and (b or label_on)
        flag = "" if edges_clear else "  <-- CLIPPED"
        if not edges_clear: ok = False
        print(f"tile {w:>3}x{h:<3} label={int(label_on)}  top={int(t)} bot={int(b)} left={int(l)} right={int(r)}{flag}")
assert ok, "a cover emoji clipped a tile edge"
print("\nOK: cover emoji never clips the tile edges")
print("ALL OK")
