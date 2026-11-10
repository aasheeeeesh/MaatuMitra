"""Palette (single source of colours), WCAG contrast maths, and the CSS injected into the app.

Design: warm paper background, one calm teal for actions, ONE strong red reserved for
flags, green for "checker OK", blue for "answered by you". State is never colour alone:
every badge also has an icon shape and a text label (see app.py).
"""

from __future__ import annotations

from pathlib import Path

PALETTE: dict[str, str] = {
    "bg": "#FBF8F3",
    "surface": "#FFFFFF",
    "text": "#1C1B1A",
    "muted": "#4A4743",
    "primary": "#0B5D5B",
    "on_primary": "#FFFFFF",
    "flag": "#A3231A",
    "on_flag": "#FFFFFF",
    "flag_bg": "#FDECEA",
    "flag_text": "#7A1A12",
    "ok": "#1E6B34",
    "on_ok": "#FFFFFF",
    "ok_bg": "#E8F4EC",
    "ok_text": "#17532A",
    "done": "#1F4E8C",
    "on_done": "#FFFFFF",
    "done_bg": "#E7EEF8",
    "done_text": "#173B6B",
    "ev_bg": "#FFE8A3",
    "ev_flag_bg": "#F9D3CD",
    "border": "#8A847C",
}

# (foreground, background) pairs used for TEXT: must reach 4.5:1 (WCAG AA, normal text)
CONTRAST_PAIRS = [
    ("text", "bg"),
    ("text", "surface"),
    ("muted", "bg"),
    ("muted", "surface"),
    ("on_primary", "primary"),
    ("on_flag", "flag"),
    ("flag_text", "flag_bg"),
    ("text", "flag_bg"),
    ("on_ok", "ok"),
    ("ok_text", "ok_bg"),
    ("on_done", "done"),
    ("done_text", "done_bg"),
    ("text", "ev_bg"),
    ("text", "ev_flag_bg"),
    ("primary", "bg"),
]

# state colours (borders, icons) against the page: must reach 3:1 (WCAG 1.4.11 non-text)
STATE_PAIRS = [
    ("flag", "bg"),
    ("flag", "surface"),
    ("ok", "bg"),
    ("done", "bg"),
    ("border", "surface"),
]

CSS_FILE = Path(__file__).resolve().parent / "static" / "style.css"
FONT_URL = "app/static/fonts/NotoSansKannada-VF.ttf"


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg: str, bg: str) -> float:
    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def css() -> str:
    variables = ";".join(f"--mm-{k.replace('_', '-')}: {v}" for k, v in PALETTE.items())
    font_face = (
        '@font-face { font-family: "Noto Sans Kannada"; '
        f'src: url("{FONT_URL}") format("truetype"); '
        "font-weight: 100 900; font-display: swap; }"
    )
    return (
        f"<style>{font_face} :root {{ {variables} }} {CSS_FILE.read_text(encoding='utf-8')}</style>"
    )
