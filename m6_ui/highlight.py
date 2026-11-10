"""Transcript highlighting with XSS safety.

Order matters: the transcript is cut into plain-text segments at span boundaries, EVERY
segment is escaped with html.escape(quote=True), and only then is our own fixed markup
(<mark>, <span>, <br>) added around the escaped text. Data never becomes markup.
Offsets are code-point offsets into the stored NFC text (end exclusive), as in record.v1.
"""

from __future__ import annotations

import html
import itertools
import re
from dataclasses import dataclass

FLAG_MARK = "!"  # the icon placed after flagged evidence (paired with colour + underline)


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    flagged: bool
    label: str  # row path, used only as a data attribute after escaping


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def render_transcript(text: str, spans: list[Span]) -> str:
    n = len(text)
    good = [s for s in spans if 0 <= s.start < s.end <= n]
    cuts = sorted({0, n, *[s.start for s in good], *[s.end for s in good]})
    out: list[str] = []
    for a, b in itertools.pairwise(cuts):
        seg = esc(text[a:b]).replace("\n", "<br>")
        active = [s for s in good if s.start <= a and b <= s.end]
        if not active:
            out.append(seg)
            continue
        flagged = any(s.flagged for s in active)
        cls = "ev ev-flag" if flagged else "ev"
        rows = esc(" ".join(sorted({s.label for s in active})))
        piece = f'<mark class="{cls}" data-rows="{rows}">{seg}</mark>'
        # put the "!" icon once, at the end of each flagged span
        if flagged and any(s.flagged and s.end == b for s in active):
            piece += f'<span class="ev-marker" aria-hidden="true">{FLAG_MARK}</span>'
        out.append(piece)
    return '<div class="transcript" lang="kn">' + "".join(out) + "</div>"


def spans_for_record(record: dict, verdict: dict | None) -> list[Span]:
    """One span per row evidence; flagged if the row carries any flag."""
    from m6_ui import review  # local import keeps this module dependency-light

    spans: list[Span] = []
    seen: set[tuple[int, int, bool]] = set()
    for row in review.build_rows(record, verdict):
        ev = row.evidence
        if not ev:
            continue
        key = (ev["char_start"], ev["char_end"], bool(row.flags))
        if key in seen:
            continue
        seen.add(key)
        spans.append(Span(ev["char_start"], ev["char_end"], bool(row.flags), row.path))
    return spans


_TAG = re.compile(r"<[^>]+>")


def strip_tags(markup: str) -> str:
    """Test helper: remove our tags and unescape, to compare with the original text."""
    return html.unescape(_TAG.sub("", markup.replace("<br>", "\n")))
