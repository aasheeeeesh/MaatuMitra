"""Kannada text helpers (kannada-nlp skill, sections 1-2)."""

from __future__ import annotations

import unicodedata

import regex

TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
LATIN = regex.compile(r"[A-Za-z]")
KN_DIGITS = "೦೧೨೩೪೫೬೭೮೯"
_TO_ASCII = {ord(k): str(i) for i, k in enumerate(KN_DIGITS)}
NUM_WORDS = {
    1: ("ಒಂದು", "one"),
    2: ("ಎರಡು", "two"),
    3: ("ಮೂರು", "three"),
    4: ("ನಾಲ್ಕು", "four"),
    5: ("ಐದು", "five"),
    6: ("ಆರು", "six"),
    7: ("ಏಳು", "seven"),
    14: ("ಹದಿನಾಲ್ಕು", "fourteen"),
}
# syrup volumes in ml, spoken (AI-composed, not native-validated)
ML_WORDS = {2.5: "ಎರಡೂವರೆ", 5: "ಐದು", 7.5: "ಏಳೂವರೆ", 10: "ಹತ್ತು"}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s.replace("﻿", "").replace("​", ""))


def compare_copy(s: str) -> str:
    """Comparison copy: NFC, no ZWJ/ZWNJ, Kannada digits -> ASCII. Never for offsets."""
    return nfc(s).replace("‌", "").replace("‍", "").translate(_TO_ASCII)


def tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text)]


def to_kn_digits(n: int | float) -> str:
    s = str(int(n)) if float(n).is_integer() else str(n)
    return "".join(KN_DIGITS[int(c)] if c.isdigit() else c for c in s)


def fmt_num(n: int | float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def has_latin(text: str) -> bool:
    return bool(LATIN.search(text))


def has_kannada(text: str) -> bool:
    return any("ಀ" <= c <= "೿" for c in text)
