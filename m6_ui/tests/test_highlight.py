"""XSS: all transcript text is escaped before highlight markup is added."""

from __future__ import annotations

from m6_ui import highlight
from m6_ui.tests.helpers import fixture_triplet


def test_payload_is_escaped_and_highlight_still_present():
    text = "a <script>alert(1)</script> b <img src=x onerror=alert(2)> c"
    s = text.index("<img")
    html_out = highlight.render_transcript(
        text, [highlight.Span(s, s + len("<img src=x onerror=alert(2)>"), True, "r1")]
    )
    assert "<script" not in html_out and "<img" not in html_out
    assert "&lt;script&gt;" in html_out and "&lt;img src=x onerror=alert(2)&gt;" in html_out
    assert 'class="ev ev-flag"' in html_out


def test_quotes_and_ampersands_escaped():
    out = highlight.render_transcript("\"' & <", [])
    assert "&quot;" in out and "&#x27;" in out and "&amp;" in out and "&lt;" in out


def test_overlapping_and_out_of_range_spans_do_not_crash():
    text = "abcdefghij"
    spans = [
        highlight.Span(0, 5, False, "a"),
        highlight.Span(3, 8, True, "b"),
        highlight.Span(8, 99, True, "c"),
    ]
    out = highlight.render_transcript(text, spans)
    plain = highlight.strip_tags(out)
    assert plain.replace(highlight.FLAG_MARK, "") == text


def test_newlines_become_breaks_after_escaping():
    out = highlight.render_transcript("x\n<y>", [])
    assert "<br>" in out and "&lt;y&gt;" in out


def test_xss_fixture_renders_inert():
    rec, ver, tr = fixture_triplet("rec-m6-xss")
    spans = highlight.spans_for_record(rec, ver)
    out = highlight.render_transcript(tr["text"], spans)
    for bad in ("<script", "<img", "<b ", "onerror=alert(1)>", "<i>"):
        assert bad not in out
    assert out.count("ev-flag") >= 2


def test_escape_helper():
    assert highlight.esc("<b>&") == "&lt;b&gt;&amp;"


def test_bidi_controls_are_neutralised_and_made_visible():
    # F6 (D-123): U+202A..U+202E and U+2066..U+2069 can reorder digits on screen
    for cp in [*range(0x202A, 0x202F), *range(0x2066, 0x206A)]:
        out = highlight.esc(f"dose 5\u200d00{chr(cp)}x")
        assert chr(cp) not in out
        assert f"[U+{cp:04X}]" in out
    out = highlight.render_transcript("take \u202e500\u202c mg", [])
    assert chr(0x202E) not in out and "[U+202E]" in out


def test_zwj_and_zwnj_are_kept():
    assert "‌" in highlight.esc("a‌b")
    assert "\u200d" in highlight.esc("a\u200db")
