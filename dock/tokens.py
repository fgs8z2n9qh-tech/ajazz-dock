"""Central design tokens — one palette + one radius scale, referenced by BOTH the
QSS string and the custom paint code (CircleControl / KeyTile / colour wells), so
keys, knobs, buttons and tabs all light up in the same brand accent.

Design direction: a dark, near-black green-charcoal "desk" on which the Ajazz dock
sits as the hero — an elevated, shadowed slab whose selected control glows in ONE
brand accent (electric mint #35e08a), replacing the old generic blue everywhere.
"""
from string import Template

# ---- palette ---------------------------------------------------------------
# Canvas: a deep green that fades to near-black (stepped surface levels below it).
BG_TOP       = "#0c241b"
BG_MID       = "#0a1712"
BG_BOT       = "#06100c"

# Sidebar — slightly lifted off the canvas so the control rail reads as separate.
SIDEBAR_TOP  = "#102a20"
SIDEBAR_BOT  = "#0b1611"

# Three stepped surfaces for cards / inputs / raised buttons.
SURFACE_1    = "#13211b"   # cards, groupboxes, the inspector column
SURFACE_2    = "#172620"   # inputs (line edits, combos, spinboxes)
SURFACE_3    = "#1b2c25"   # buttons, segmented controls

# The device slab — a faintly lifted dark-green object that floats on its drop
# shadow, distinct from the canvas behind it (top catches a little light).
DEVICE_TOP   = "#13241c"
DEVICE_BOT   = "#0a120e"
KEY_BG       = "#000000"

BORDER       = "#26402f"
BORDER_HOVER = "#3c6149"

# Brand accent — every selection / focus / primary / slider signal uses this.
ACCENT       = "#35e08a"
ACCENT_HOVER = "#57ef9f"
ACCENT_DIM   = "#1f5c3d"   # quiet accent (slider fill, faint borders)
ACCENT_INK   = "#06140d"   # text / icon drawn on top of an accent fill

# Text contrast steps (lifted from the old greys for AA on the dark panels).
TEXT         = "#e7efe9"
TEXT_DIM     = "#acc3b6"
TEXT_FAINT   = "#7e9889"

# Round-control fills (molded-plastic gradient: lighter top, darker bottom).
KNOB_TOP     = "#243029"
KNOB_BOT     = "#161f1a"
BTN_TOP      = "#141b17"
BTN_BOT      = "#0a0f0d"
TICK         = "#7d937f"

DANGER       = "#ff6b6b"

# ---- radius scale (4 steps — collapsed from the old 11) --------------------
R_SM   = 8
R_MD   = 12
R_LG   = 16
R_PILL = 999

TOKENS = {k: v for k, v in globals().items()
          if k.isupper() and isinstance(v, (str, int))}


_QSS = Template("""
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: $TEXT; }
QMainWindow, QWidget#root { background: qlineargradient(x1:0, y1:0, x2:0.4, y2:1,
    stop:0 $BG_TOP, stop:0.55 $BG_MID, stop:1 $BG_BOT); }
QLabel#display { font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }
QLabel#h1 { font-size: 16px; font-weight: 600; }
QLabel#dim { color: $TEXT_DIM; }
QLabel#section { color: $TEXT_DIM; font-size: 12px; font-weight: 600; letter-spacing: 0.4px; }
QGroupBox { background: $SURFACE_1; border: 1px solid $BORDER; border-radius: ${R_LG}px; margin-top: 16px; padding: 12px; }
QGroupBox#panel { margin-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: $TEXT_DIM; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: $SURFACE_2; border: 1px solid $BORDER; border-radius: ${R_MD}px; padding: 6px 9px; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: $ACCENT; }
QComboBox::drop-down { border: none; width: 18px; }
QPushButton, QToolButton { background: $SURFACE_3; border: 1px solid $BORDER; border-radius: ${R_MD}px; padding: 7px 12px; }
QPushButton:hover, QToolButton:hover { border-color: $BORDER_HOVER; }
QPushButton:focus, QToolButton:focus { border-color: $ACCENT; }
QPushButton#primary { background: $ACCENT; border-color: $ACCENT; color: $ACCENT_INK; font-weight: 600; }
QPushButton#primary:hover { background: $ACCENT_HOVER; border-color: $ACCENT_HOVER; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid $BORDER; background: $SURFACE_2; }
QCheckBox::indicator:hover { border-color: $BORDER_HOVER; }
QCheckBox::indicator:checked { background: $ACCENT; border-color: $ACCENT; }
QLabel#key { background: $KEY_BG; border: 2px solid $BORDER; border-radius: ${R_LG}px; padding: 0; }
QLabel#key:hover { border-color: $BORDER_HOVER; }
QLabel#key:focus { border-color: $ACCENT; }
QLabel#key[selected="true"] { border: 2px solid $ACCENT; }
QWidget#main { background: transparent; }
QFrame#sidebar { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 $SIDEBAR_TOP, stop:1 $SIDEBAR_BOT); border-right: 1px solid $BORDER; }
QFrame#sidebar QPushButton { text-align: left; padding: 7px 10px; }
QFrame#card { background: rgba(255,255,255,0.022); border: 1px solid $BORDER; border-radius: ${R_MD}px; }
QLabel#cardtitle { color: $TEXT_DIM; font-size: 11px; font-weight: 700; letter-spacing: 0.7px; }
QFrame#inspector { background: $SURFACE_1; border-left: 1px solid $BORDER; }
QFrame#hsep { background: $BORDER; border: none; }
QFrame#device { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 $DEVICE_TOP, stop:1 $DEVICE_BOT); border: 1px solid $BORDER_HOVER; border-radius: ${R_LG}px; }
QLabel#wordmark { color: $TEXT_FAINT; font-size: 12px; font-weight: 600; letter-spacing: 3px; }
QToolButton#seg { background: $SURFACE_2; border: 1px solid $BORDER; border-radius: ${R_MD}px; padding: 6px 9px; }
QToolButton#seg:checked { background: $ACCENT; border-color: $ACCENT; color: $ACCENT_INK; }
QFrame#tabbar { background: rgba(255,255,255,0.05); border: 1px solid $BORDER; border-radius: ${R_LG}px; }
QToolButton#tab { background: transparent; border: 1px solid transparent; border-radius: ${R_MD}px; padding: 7px 18px; color: $TEXT_DIM; }
QToolButton#tab:hover { background: rgba(255,255,255,0.08); color: $TEXT; }
QToolButton#tab:checked { background: $ACCENT; color: $ACCENT_INK; font-weight: 600; }
QToolButton#tabicon { background: rgba(255,255,255,0.05); border: 1px solid $BORDER; border-radius: ${R_MD}px; padding: 0; color: $TEXT_DIM; font-size: 15px; }
QToolButton#tabicon:hover { background: rgba(255,255,255,0.09); border-color: $ACCENT; color: $TEXT; }
QSlider::groove:horizontal { height: 5px; background: $SURFACE_3; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $ACCENT_DIM; border-radius: 2px; }
QSlider::handle:horizontal { background: $ACCENT; width: 14px; margin: -6px 0; border-radius: 7px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QMenu { background: $SURFACE_2; border: 1px solid $BORDER; }
QMenu::item:selected { background: $ACCENT; color: $ACCENT_INK; }
QToolButton#emoji { background: transparent; border: none; border-radius: ${R_SM}px; padding: 0; }
QToolButton#emoji:hover { background: $SURFACE_3; }
QToolButton#emojicat { background: transparent; border: 1px solid transparent; border-radius: ${R_SM}px; padding: 0; }
QToolButton#emojicat:hover { background: rgba(255,255,255,0.07); }
QToolButton#emojicat:checked { background: rgba(255,255,255,0.10); border-color: $ACCENT; }
QDialog { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 $BG_MID, stop:1 $BG_BOT); }
""")


def build_qss() -> str:
    return _QSS.substitute(TOKENS)
