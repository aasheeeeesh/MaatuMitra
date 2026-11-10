"""Design rules that can be checked without a browser: font size, targets, contrast, binding, font."""

from __future__ import annotations

import hashlib
import tomllib

import pytest
import regex

from m6_ui import theme
from m6_ui.tests.helpers import M6

CONFIG = M6 / ".streamlit" / "config.toml"
CSS = M6 / "static" / "style.css"
FONT = M6 / "static" / "fonts" / "NotoSansKannada-VF.ttf"
FONT_SHA256 = "b062c3ec551cee95b88cbbc470036c81b69c788516fd8910ba6ae6e3c70d9bb2"


def _cfg():
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def test_server_binds_to_loopback_and_hides_chrome():
    cfg = _cfg()
    assert cfg["server"]["address"] == "127.0.0.1"
    assert cfg["server"]["enableStaticServing"] is True
    assert cfg["server"]["enableXsrfProtection"] is True
    assert cfg["browser"]["gatherUsageStats"] is False
    assert cfg["client"]["toolbarMode"] == "minimal"


def test_theme_uses_palette_and_bundled_font_and_18px_base():
    th = _cfg()["theme"]
    assert th["baseFontSize"] >= 18
    assert th["textColor"].lower() == theme.PALETTE["text"].lower()
    assert th["backgroundColor"].lower() == theme.PALETTE["bg"].lower()
    assert th["primaryColor"].lower() == theme.PALETTE["primary"].lower()
    assert "Noto Sans Kannada" in th["font"]
    faces = th["fontFaces"]
    assert any(f["url"].endswith("fonts/NotoSansKannada-VF.ttf") for f in faces)
    assert not any(f["url"].startswith("http") for f in faces), "no CDN at runtime"


@pytest.mark.parametrize("fg,bg", theme.CONTRAST_PAIRS)
def test_text_contrast_is_wcag_aa(fg, bg):
    ratio = theme.contrast(theme.PALETTE[fg], theme.PALETTE[bg])
    assert ratio >= 4.5, f"{fg} on {bg}: {ratio:.2f}"


@pytest.mark.parametrize("fg,bg", theme.STATE_PAIRS)
def test_state_colours_meet_3_to_1(fg, bg):
    assert theme.contrast(theme.PALETTE[fg], theme.PALETTE[bg]) >= 3.0


def test_contrast_formula_known_values():
    assert theme.contrast("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert theme.contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.02)


def test_css_font_sizes_and_touch_targets():
    css = theme.css()
    assert css.startswith("<style>")
    for m in regex.finditer(r"font-size:\s*([\d.]+)(px|rem|em)", css):
        val, unit = float(m.group(1)), m.group(2)
        px = val if unit == "px" else val * 18
        assert px >= 18, m.group(0)
    heights = [float(x) for x in regex.findall(r"min-height:\s*([\d.]+)px", css)]
    assert heights and min(heights) >= 48
    assert "line-height: 1.6" in css
    assert "letter-spacing" not in css and "text-transform: uppercase" not in css
    assert "max-width: 100%" in css  # 360 px: no horizontal scroll from wide elements
    assert 'url("app/static/fonts/NotoSansKannada-VF.ttf")' in css


def test_font_file_is_the_recorded_release_and_has_licence():
    assert hashlib.sha256(FONT.read_bytes()).hexdigest() == FONT_SHA256
    assert FONT.stat().st_size < 300_000
    ofl = (M6 / "static" / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in ofl
    assert "The Noto Project Authors" in ofl


def test_font_covers_every_kannada_character_used_in_ui_and_conjunct_page():
    ttlib = pytest.importorskip("fontTools.ttLib")
    cmap = ttlib.TTFont(str(FONT)).getBestCmap()
    texts = [
        (M6 / "i18n" / "kn.json").read_text(encoding="utf-8"),
        (M6 / "conjuncts.json").read_text(encoding="utf-8"),
    ]
    needed = {ord(c) for t in texts for c in t if 0x0C80 <= ord(c) <= 0x0CFF}
    assert needed
    missing = sorted(hex(c) for c in needed if c not in cmap)
    assert missing == []


def test_conjunct_page_data_has_the_required_items():
    import json

    items = json.loads((M6 / "conjuncts.json").read_text(encoding="utf-8"))["items"]
    texts = {i["text"] for i in items}
    for name in [
        "0CB8 0CCD 0CA4 0CCD 0CB0 0CC0",
        "0C95 0CCD 0CB7",
        "0C9C 0CCD 0C9E",
        "0CB6 0CCD 0CB0 0CC0",
        "0CA4 0CCD 0CB0",
        "0CB0 0CCD 0C95",
    ]:
        want = "".join(chr(int(h, 16)) for h in name.split())
        assert want in texts, name
    assert any(chr(0x200C) in t for t in texts)
