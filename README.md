# AjazzDock

A lean, **native** controller for the **Ajazz AKP03E** "Stream Dock" (6 LCD keys + 3 buttons
+ 3 rotary encoders) — written in Python + Qt (PySide6). No browser, no web view, no account,
no cloud, no telemetry, no background updater. A real desktop window + a system-tray icon that
talk to the device directly over its vendor HID interface.

Built and verified against real hardware (USB **VID `0x0300` / PID `0x3002`**). Protocol credit:
[`4ndv/mirajazz`](https://github.com/4ndv/mirajazz) + [`4ndv/opendeck-akp03`](https://github.com/4ndv/opendeck-akp03).

## What it does

- Renders icons + labels (full-color emoji **or** your own PNG/JPG) to the 6 LCD keys.
- Binds **every** input — 6 keys, 3 round buttons, 3 encoders (turn ◀/▶ and push) — to actions.
- **Actions:** open app/file/folder/URL · hotkeys (`ctrl+shift+t`) · type text · media transport ·
  system volume · **mic mute** · switch page · switch profile · set brightness · multi-step macros.
- **Pages** (unlimited per profile) and **profiles**, switchable from a key, button, the tray menu,
  or the app.
- Native dark-themed configurator: device-shaped key grid with live previews, color/emoji/PNG
  pickers, and a Test button. Auto-reconnects if you unplug/replug.

## Install & run

```powershell
# one-time setup
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
./build.ps1       # produces dist\AjazzDock.exe (single ~47 MB file, no Python needed to run)
./install.ps1     # copies to %LOCALAPPDATA%\AjazzDock, makes Start Menu + Desktop shortcuts, enables autostart, launches it
```

After that: launch from the **Start Menu / Desktop** shortcut, or it starts automatically on login
(to the tray). Right-click the tray icon for **Open Configurator**, profile switching, the
**Start with Windows** toggle, and **Quit**. Closing the window hides it to the tray.

`./uninstall.ps1` removes the app, shortcuts, and autostart (your settings in
`%APPDATA%\AjazzDock` are kept).

### Run from source (dev)

```powershell
.\.venv\Scripts\python.exe run.py            # native window + tray
.\.venv\Scripts\python.exe -m dock.gui --tray   # start hidden to tray
```

## Config

Plain JSON at `%APPDATA%\AjazzDock\config.json`; uploaded key images in
`%APPDATA%\AjazzDock\icons\`. Binding ids match the hardware: `key1`–`key6`, `btn7`–`btn9`,
`enc0`–`enc2` (push) and `enc0+`/`enc0-` … (turn cw/ccw). Faces (label/icon/color) only render
on `key1`–`key6`.

## Architecture

| File | Role |
|------|------|
| `dock/device.py`     | Low-level AKP03 HID driver (images, brightness, input events) — hardware-verified |
| `dock/images.py`     | Renders key faces (emoji/PNG + label) to 60×60 |
| `dock/actions.py`    | Action engine (open/hotkey/text/media/volume/mic/page/profile/brightness/macro) |
| `dock/config.py`     | JSON config: profiles → pages → bindings |
| `dock/controller.py` | Event loop: device input → actions, renders pages, reconnect |
| `dock/gui.py`        | **Native PySide6 app**: window + editor + system tray + single-instance IPC |
| `dock/iconart.py`    | App-icon glyph |
| `dock/autostart.py`  | Start-with-Windows (HKCU Run key) |
| `tools/`             | `probe.py`, `sniff.py`, `selftest.py`, `make_icon.py`, `micstate.py` |
| `build.ps1` · `install.ps1` · `uninstall.ps1` | package / install / remove |

## Dependencies

`PySide6` (Qt), `hidapi`, `Pillow`, `keyboard`, `pycaw` + `comtypes` (mic mute). Windows-only.
