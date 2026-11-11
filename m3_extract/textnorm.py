"""Kannada text normaliser and tokeniser (PROJECT_BRIEF 6.1, kannada-nlp skill section 1-2).

Stored text: NFC, no BOM, no zero-width space, ZWJ/ZWNJ kept. Offsets always point into the
stored text (code points, end exclusive). Comparison form of a token: ZWJ/ZWNJ removed, Kannada
digits -> ASCII, casefold.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

import regex

BOM, ZWSP, ZWNJ, ZWJ = "﻿", "​", "‌", "‍"
_KN_DIGITS = {chr(0x0CE6 + i): str(i) for i in range(10)}
_DIGIT_TRANS = str.maketrans(_KN_DIGITS)

# A word = letters/marks/numbers; ZWJ/ZWNJ may sit INSIDE a word (removed only in the comparison
# form), so a ZWNJ does not split ಮಾತ್ರೆ‌ಗಳು. Decimal numbers (2.5, ೦.೫) are one token.
TOKEN_RE = regex.compile(
    r"[0-9೦-೯]+\.[0-9೦-೯]+"
    r"|[\p{L}\p{M}\p{N}](?:[\p{L}\p{M}\p{N}‌‍]*[\p{L}\p{M}\p{N}])?"
)
_WORDCHAR = regex.compile(r"[\p{L}\p{M}\p{N}]")


@dataclass(frozen=True)
class Token:
    text: str  # exactly as stored
    start: int
    end: int
    norm: str  # comparison form
    turn: int  # 0-based line index


def comparison_form(s: str) -> str:
    s = unicodedata.normalize("NFC", s).replace(ZWNJ, "").replace(ZWJ, "")
    return s.translate(_DIGIT_TRANS).casefold()


def normalise(s: str) -> str:
    """Input normaliser: strip BOM and zero-width spaces, then NFC. ZWJ/ZWNJ are kept."""
    return unicodedata.normalize("NFC", s.replace(BOM, "").replace(ZWSP, ""))


def check_stored(text: str) -> None:
    """Fail closed if the transcript text is not in the contract's stored form."""
    if BOM in text or ZWSP in text:
        raise ValueError("transcript text contains a BOM or zero-width space")
    if not unicodedata.is_normalized("NFC", text):
        raise ValueError("transcript text is not Unicode NFC")


def tokenize(text: str) -> list[Token]:
    out = []
    turn = 0
    last = 0
    for m in TOKEN_RE.finditer(text):
        turn += text.count("\n", last, m.start())
        last = m.start()
        out.append(Token(m.group(), m.start(), m.end(), comparison_form(m.group()), turn))
    return out


def turn_bounds(text: str) -> list[tuple[int, int]]:
    out, pos = [], 0
    for line in text.split("\n"):
        out.append((pos, pos + len(line)))
        pos += len(line) + 1
    return out


def is_boundary_dot(text: str, i: int) -> bool:
    """A '.' is NOT a boundary when a word character touches it on both sides (ಎಂ.ಜಿ, ಒ.ಆರ್.ಎಸ್,
    2.5). Deviation from a naive splitter, documented in handoff/decisions.md."""
    if text[i] != ".":
        return True
    before = i > 0 and bool(_WORDCHAR.match(text[i - 1]))
    after = i + 1 < len(text) and bool(_WORDCHAR.match(text[i + 1]))
    return not (before and after)
