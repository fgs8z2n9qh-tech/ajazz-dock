"""Extract a Windows app/file icon (from an .exe, shortcut, or file path) as a PIL image.

Two sources, best-quality first:
  1. the shell's 256px "jumbo" image list (crisp — most modern apps ship a 256px icon), via Win32;
  2. Qt's QFileIconProvider (caps at ~128px) as a fallback.

Shortcuts (.lnk) are resolved FIRST to the real target exe / custom icon — otherwise the shell
returns the shortcut's generic icon (a blank page with the little blue overlay arrow).

The Qt path must run on the GUI thread. The configurator calls this for an 'open' action's target.
"""
from __future__ import annotations

import io
import os
import shutil
from typing import Optional, Tuple

from PIL import Image


def _resolve(target: str) -> Optional[str]:
    """A concrete local path for `target`: as-is if it exists, else resolved on PATH."""
    if not target:
        return None
    path = target.strip().strip('"')
    if os.path.exists(path):
        return path
    if not path.lower().startswith(("http://", "https://")):
        found = shutil.which(path)
        if found:
            return found
    return None


def _resolve_lnk(lnk: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (target exe, custom icon path) for a .lnk shortcut, via the Windows shell."""
    try:
        import comtypes.client
        from comtypes.client.dynamic import Dispatch
        sh = Dispatch(comtypes.client.CreateObject("WScript.Shell"))
        sc = sh.CreateShortcut(lnk)
        target = (str(sc.TargetPath or "")).strip()
        iconloc = (str(sc.IconLocation or "")).strip()        # "path,index" (often ",0" = no custom)
        icon_path = iconloc.rsplit(",", 1)[0].strip().strip('"') if "," in iconloc else iconloc.strip('"')
        return (target or None), (icon_path or None)
    except Exception:
        return None, None


def _hicon_to_pil(hicon) -> Optional[Image.Image]:
    """Convert an HICON to a PIL RGBA image (32-bit BGRA via GetDIBits)."""
    import ctypes
    from ctypes import wintypes, byref, sizeof, Structure, c_int, create_string_buffer, memset
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    class ICONINFO(Structure):
        _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]

    class BITMAP(Structure):
        _fields_ = [("bmType", wintypes.LONG), ("bmWidth", wintypes.LONG), ("bmHeight", wintypes.LONG),
                    ("bmWidthBytes", wintypes.LONG), ("bmPlanes", wintypes.WORD),
                    ("bmBitsPixel", wintypes.WORD), ("bmBits", ctypes.c_void_p)]

    class BITMAPINFOHEADER(Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", c_int), ("biHeight", c_int),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", c_int), ("biYPelsPerMeter", c_int),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    # 64-bit-safe handle argtypes (else handles overflow a default C int).
    user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
    gdi32.GetObjectW.argtypes = [wintypes.HANDLE, c_int, ctypes.c_void_p]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    user32.GetDC.argtypes = [wintypes.HWND]; user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]

    ii = ICONINFO()
    if not user32.GetIconInfo(hicon, byref(ii)):
        return None
    try:
        bm = BITMAP()
        gdi32.GetObjectW(ii.hbmColor, sizeof(bm), byref(bm))
        w, h = bm.bmWidth, bm.bmHeight
        if w <= 0 or h <= 0:
            return None
        bih = BITMAPINFOHEADER()
        memset(byref(bih), 0, sizeof(bih))
        bih.biSize = sizeof(bih); bih.biWidth = w; bih.biHeight = -h    # top-down
        bih.biPlanes = 1; bih.biBitCount = 32; bih.biCompression = 0    # 32-bit BI_RGB
        hdc = user32.GetDC(None)
        buf = create_string_buffer(w * h * 4)
        scanlines = gdi32.GetDIBits(hdc, ii.hbmColor, 0, h, buf, byref(bih), 0)
        user32.ReleaseDC(None, hdc)
        if scanlines != h:        # failed/partial blit -> let the crisper Qt provider try instead
            return None
        return Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1).copy()
    finally:
        if ii.hbmColor:
            gdi32.DeleteObject(ii.hbmColor)
        if ii.hbmMask:
            gdi32.DeleteObject(ii.hbmMask)


def _jumbo_icon(path: str) -> Optional[Image.Image]:
    """The shell's 256px 'jumbo' icon as a trimmed PIL RGBA image (crisper than Qt's 128px), or None."""
    try:
        import ctypes
        from ctypes import wintypes, byref, sizeof, Structure, c_int, POINTER
        import comtypes
        from comtypes import GUID, IUnknown, COMMETHOD, HRESULT

        SHIL_JUMBO, SHGFI_SYSICONINDEX, ILD_TRANSPARENT = 0x4, 0x4000, 0x1
        IID_IImageList = GUID("{46EB5926-582E-4017-9FDF-E8998DAA0950}")

        class IImageList(IUnknown):
            _iid_ = IID_IImageList
            _methods_ = [
                COMMETHOD([], HRESULT, "Add"), COMMETHOD([], HRESULT, "ReplaceIcon"),
                COMMETHOD([], HRESULT, "SetOverlayImage"), COMMETHOD([], HRESULT, "Replace"),
                COMMETHOD([], HRESULT, "AddMasked"), COMMETHOD([], HRESULT, "Draw"),
                COMMETHOD([], HRESULT, "Remove"),
                COMMETHOD([], HRESULT, "GetIcon", (["in"], c_int, "i"),
                          (["in"], wintypes.UINT, "flags"), (["out"], POINTER(wintypes.HICON), "picon")),
            ]

        class SHFILEINFOW(Structure):
            _fields_ = [("hIcon", wintypes.HICON), ("iIcon", c_int), ("dwAttributes", wintypes.DWORD),
                        ("szDisplayName", wintypes.WCHAR * 260), ("szTypeName", wintypes.WCHAR * 80)]

        shell32 = ctypes.windll.shell32
        shfi = SHFILEINFOW()
        if not shell32.SHGetFileInfoW(path, 0, byref(shfi), sizeof(shfi), SHGFI_SYSICONINDEX):
            return None
        shell32.SHGetImageList.argtypes = [c_int, POINTER(GUID), POINTER(POINTER(IImageList))]
        piml = POINTER(IImageList)()
        if shell32.SHGetImageList(SHIL_JUMBO, byref(IID_IImageList), byref(piml)) != 0 or not piml:
            return None
        hicon = piml.GetIcon(shfi.iIcon, ILD_TRANSPARENT)
        try:
            im = _hicon_to_pil(hicon)
        finally:
            ctypes.windll.user32.DestroyIcon.argtypes = [wintypes.HICON]
            ctypes.windll.user32.DestroyIcon(hicon)
        if im is None or im.getextrema()[3] == (0, 0):    # fully transparent -> let Qt try instead
            return None
        bb = im.getbbox()
        return im.crop(bb) if bb else im
    except Exception:
        return None


def _qt_icon(path: str, px: int) -> Optional[Image.Image]:
    """The system icon for a concrete local path via Qt (caps ~128px), trimmed PIL RGBA or None."""
    try:
        from PySide6.QtWidgets import QFileIconProvider
        from PySide6.QtCore import QFileInfo, QSize, QBuffer, QByteArray, QIODevice
        icon = QFileIconProvider().icon(QFileInfo(path))
        if icon.isNull():
            return None
        pm = icon.pixmap(QSize(px, px))
        if pm.isNull():
            return None
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        pm.save(buf, "PNG")
        buf.close()
        im = Image.open(io.BytesIO(bytes(ba))).convert("RGBA")
        bbox = im.getbbox()
        return im.crop(bbox) if bbox else im
    except Exception:
        return None


def _shell_icon(path: str, px: int) -> Optional[Image.Image]:
    """Best-quality system icon for a concrete path: 256px jumbo if available, else Qt's."""
    return _jumbo_icon(path) or _qt_icon(path, px)


def icon_image(target: str, px: int = 256) -> Optional[Image.Image]:
    """The system icon for a local file/exe/folder/shortcut as a trimmed PIL RGBA image (or None)."""
    path = _resolve(target)
    if not path:
        return None
    candidates = []
    if path.lower().endswith(".lnk"):
        tgt, ico = _resolve_lnk(path)
        for c in (ico, tgt):                   # the real icon / target exe beats the shortcut's icon
            if c and os.path.exists(c):
                candidates.append(c)
    candidates.append(path)
    for cand in candidates:
        im = _shell_icon(cand, px)
        if im is not None:
            return im
    return None


def save_icon(target: str, dest_dir: str, px: int = 256) -> Optional[str]:
    """Extract `target`'s icon, save it as a PNG under dest_dir, return the path (or None)."""
    im = icon_image(target, px)
    if im is None:
        return None
    os.makedirs(dest_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(_resolve(target) or "app"))[0] or "app"
    safe = "".join(c for c in stem if c.isalnum() or c in "-_") or "app"
    dest = os.path.join(dest_dir, f"appicon_{safe}.png")
    try:
        im.save(dest)
        return dest
    except OSError:
        return None
