r"""Comparison normalisation for Kannada text (kannada-nlp skill section 1).

Stored text is never changed; these functions build the COMPARISON copy only:
strip BOM and zero-width space, NFC, remove ZWJ/ZWNJ, Kannada digits -> ASCII, casefold,
collapse whitespace. Tokens: regex [\p{L}\p{M}\p{N}]+ ; graphemes: regex \X.
"""

from __future__ import annotations

import unicodedata

import regex

TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
GRAPHEME = regex.compile(r"\X")
PUNCT = regex.compile(r"[\p{P}\p{S}]+")
_KN_DIGITS = {0x0CE6 + i: str(i) for i in range(10)}
_DROP = {0xFEFF: None, 0x200B: None, 0x200C: None, 0x200D: None}


def compare_norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s.translate({0xFEFF: None, 0x200B: None}))
    s = s.translate(_DROP).translate(_KN_DIGITS).casefold()
    return " ".join(s.split())


def strip_punct(s: str) -> str:
    return " ".join(PUNCT.sub(" ", s).split())


def tokens(s: str) -> list[str]:
    return TOKEN.findall(compare_norm(s))


def graphemes(s: str) -> list[str]:
    return GRAPHEME.findall(s)
