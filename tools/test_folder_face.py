"""folder_face renders a contents grid; controller/gui pick it for folder-action keys."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dock import images
from dock.images import folder_face, render_face

contents = {
    "key1": {"icon": "📝", "color": "#2d6cdf"},
    "key2": {"icon": "🌐", "color": "#1aa179"},
    "key3": {"icon": "🎵", "color": "#7a3cc4"},
    "key4": {"icon": "⚙",  "color": "#c0392b"},
    "key5": {"icon": "🔒", "color": "#444b55"},
}
folder_item = {"label": "Tools", "color": "#101418", "action": {"type": "folder", "folder": "folder1"}}

# 1) renders at the requested size, non-empty, differs from a plain face
f = folder_face(folder_item, contents, size=(88, 88), show_label=True)
assert f.size == (88, 88), f.size
plain = render_face(folder_item, size=(88, 88), show_label=True)
assert list(f.getdata()) != list(plain.getdata()), "folder face identical to plain face"
print("OK folder_face renders + differs from plain")

# 2) empty folder still renders (folder glyph), no crash
fe = folder_face({"label": "Empty", "color": "#101418"}, {}, size=(88, 88))
assert fe.size == (88, 88)
print("OK empty folder renders")

# 3) controller routes a folder-action key through folder_face
from dock.controller import DockController
c = DockController()
prof = c.config.active_profile()
prof.setdefault("folders", {})["folder1"] = {"name": "Tools", "items": contents}
prof["pages"][0]["items"]["key1"] = folder_item
c.page_index = 0
face = c._face_for_index(0)              # key1 is the folder
ref  = folder_face(folder_item, contents, show_label=folder_item.get("show_label", True))
assert list(face.getdata()) == list(ref.getdata()), "controller didn't use folder_face for folder key"
print("OK controller renders folder key as folder_face")

# visual preview
f.resize((176, 176), images.Image.NEAREST).save("tools/_folder_preview.png")
print("\nALL OK")
