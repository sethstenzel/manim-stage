"""Dark and light palettes on Qt's Fusion style (spec F01: dark/light UI).

Colours meet WCAG AA contrast for text on their backgrounds. State is never shown
by colour alone: every coloured badge also has text or an icon shape.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DARK = {
    "window": "#1e1f22",
    "base": "#16171a",
    "alt": "#24262b",
    "text": "#e6e6e6",
    "muted": "#a0a4ab",
    "button": "#2b2d31",
    "highlight": "#3d7bd9",
    "hl_text": "#ffffff",
    "link": "#7fb4ff",
    "viewport": "#0e0f11",
    "error": "#ff6b6b",
    "ok": "#5cc98a",
    "cached": "#3d7bd9",
    "uncached": "#3a3d43",
    "playhead": "#ffcc4d",
}
LIGHT = {
    "window": "#f3f3f4",
    "base": "#ffffff",
    "alt": "#ebecef",
    "text": "#1b1c1f",
    "muted": "#5b5f66",
    "button": "#e4e5e8",
    "highlight": "#2462c4",
    "hl_text": "#ffffff",
    "link": "#1d55b0",
    "viewport": "#d9dadd",
    "error": "#b3261e",
    "ok": "#1e7a46",
    "cached": "#2462c4",
    "uncached": "#c4c6cb",
    "playhead": "#b8860b",
}


def colors(dark: bool) -> dict[str, str]:
    return DARK if dark else LIGHT


def apply_theme(app: QApplication, dark: bool) -> None:
    c = colors(dark)
    app.setStyle("Fusion")
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["window"],
        QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["base"],
        QPalette.ColorRole.AlternateBase: c["alt"],
        QPalette.ColorRole.Text: c["text"],
        QPalette.ColorRole.Button: c["button"],
        QPalette.ColorRole.ButtonText: c["text"],
        QPalette.ColorRole.Highlight: c["highlight"],
        QPalette.ColorRole.HighlightedText: c["hl_text"],
        QPalette.ColorRole.Link: c["link"],
        QPalette.ColorRole.ToolTipBase: c["alt"],
        QPalette.ColorRole.ToolTipText: c["text"],
        QPalette.ColorRole.PlaceholderText: c["muted"],
    }
    for role, value in roles.items():
        pal.setColor(role, QColor(value))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c["muted"]))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c["muted"]))
    app.setPalette(pal)
    app.setProperty("manim_stage_dark", dark)


def is_dark(app: QApplication) -> bool:
    return bool(app.property("manim_stage_dark"))


# Event colours per Manim animation category (manim_stage.catalog). Bars always carry
# a text label too, so colour is never the only signal.
CATEGORY_COLORS = {
    "creation": "#4f9d69",
    "fading": "#5b8fd6",
    "transform": "#a26bd1",
    "indication": "#d6a23f",
    "movement": "#3fa7b5",
    "rotation": "#c7663e",
    "growing": "#7aa93c",
    "numbers": "#c9578c",
    "changing": "#8f7bd8",
    "composition": "#6c7a89",
    "speedmodifier": "#b0894f",
    "updaters": "#4aa58e",
    "specialized": "#b86fa8",
    "animation": "#7f8c99",
    "animate": "#4c86c6",
    "custom": "#9a8f5a",
    "wait": "#6b6f76",
    "section": "#e0b94c",
    "cue": "#ff8a5c",
    "plugin": "#b39ddb",
    "sound": "#3aa0d8",
    "caption": "#9aa3ad",
}


def category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS["animation"])
