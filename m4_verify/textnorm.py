"""The verifier's OWN text normaliser and tokeniser (PROJECT_BRIEF 6.1).

Stored text is never changed. For comparison we build a copy that:
  * is Unicode NFC,
  * drops BOM (U+FEFF), zero-width space (U+200B), ZWNJ (U+200C) and ZWJ (U+200D),
  * maps Kannada digits U+0CE6..U+0CEF to ASCII 0..9,
  * casefolds Latin text,
and keeps, for every comparison character, the index of the stored character it came from.
Tokens are found on the comparison copy with the `regex` pattern [\\p{L}\\p{M}\\p{N}]+ and their
offsets are mapped back to the stored text, so evidence offsets always refer to stored text.
A token made of a digit run glued to a letter run ("500mg") is split in two.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import regex

DROP_CHARS = {"﻿", "​", "‌", "‍"}
KN_DIGITS = {chr(0x0CE6 + i): str(i) for i in range(10)}
TOKEN_RE = regex.compile(r"[\p{L}\p{M}\p{N}]+")
SPLIT_RE = regex.compile(r"\p{N}+|[\p{L}\p{M}]+")


@dataclass(frozen=True)
class Token:
    text: str  # comparison form
    start: int  # stored-text offset (inclusive)
    end: int  # stored-text offset (exclusive)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _comparison_with_map(s: str) -> tuple[str, list[int]]:
    s = nfc(s)
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(s):
        if ch in DROP_CHARS:
            continue
        if ch in KN_DIGITS:
            ch = KN_DIGITS[ch]
        elif ch.isascii() or "LATIN" in unicodedata.name(ch, ""):
            ch = ch.casefold()
        for c in ch:
            out.append(c)
            idx.append(i)
    return "".join(out), idx


def comparison(s: str) -> str:
    """Comparison copy of s (see module docstring)."""
    return _comparison_with_map(s)[0]


@lru_cache(maxsize=4096)
def _tokens_cached(s: str) -> tuple[Token, ...]:
    comp, idx = _comparison_with_map(s)
    toks: list[Token] = []
    for m in TOKEN_RE.finditer(comp):
        # split digit runs glued to letter runs: "500mg" -> "500", "mg"
        parts = list(SPLIT_RE.finditer(m.group()))
        if len(parts) > 1 and any(p.group()[0].isdigit() for p in parts):
            for p in parts:
                a, b = m.start() + p.start(), m.start() + p.end()
                toks.append(Token(comp[a:b], idx[a], idx[b - 1] + 1))
        else:
            toks.append(Token(m.group(), idx[m.start()], idx[m.end() - 1] + 1))
    return tuple(toks)


def tokens(s: str) -> list[Token]:
    """Tokens of s in comparison form, with offsets into the (NFC) stored text."""
    return list(_tokens_cached(s))


def token_texts(s: str) -> list[str]:
    return [t.text for t in _tokens_cached(s)]


def is_kannada(s: str) -> bool:
    return any("ಀ" <= ch <= "೿" for ch in s)
