"""Number parser: ASCII digits, Kannada digits (already ASCII in the comparison form) and Kannada
number words.

Sources (fetched 2026-11-10 by nlp-engineer, raw wikitext of each en.wiktionary.org entry, Kannada
section, "cardinal numbers"): ಒಂದು 1, ಎರಡು 2, ಮೂರು 3, ನಾಲ್ಕು 4, ಐದು 5, ಆರು 6, ಏಳು 7 (also "to rise"),
ಎಂಟು 8, ಒಂಬತ್ತು 9, ಹತ್ತು 10, ಹದಿನಾಲ್ಕು 14 (its cardinal box names ಹದಿಮೂರು 13 and ಹದಿನೈದು 15),
ಅರ್ಧ "half". URL pattern: https://en.wiktionary.org/w/index.php?title=<word>&action=raw
UNVERIFIED (no page fetched by us): ಹನ್ನೊಂದು 11, ಹನ್ನೆರಡು 12, ಹದಿನಾರು 16, ಇಪ್ಪತ್ತು 20, ಮೂವತ್ತು 30,
ನೂರು 100 (m1_data's SOURCES.md KN-6 lists several of them from a fetched Wiktionary category page).
Not native-validated.
"""

from __future__ import annotations

import regex

NUMBER_WORDS: dict[str, float] = {
    "ಒಂದು": 1,
    "ಎರಡು": 2,
    "ಮೂರು": 3,
    "ನಾಲ್ಕು": 4,
    "ಐದು": 5,
    "ಆರು": 6,
    "ಏಳು": 7,
    "ಎಂಟು": 8,
    "ಒಂಬತ್ತು": 9,
    "ಹತ್ತು": 10,
    "ಹದಿಮೂರು": 13,
    "ಹದಿನಾಲ್ಕು": 14,
    "ಹದಿನೈದು": 15,
    "ಅರ್ಧ": 0.5,
    # UNVERIFIED (see module docstring)
    "ಹನ್ನೊಂದು": 11,
    "ಹನ್ನೆರಡು": 12,
    "ಹದಿನಾರು": 16,
    "ಇಪ್ಪತ್ತು": 20,
    "ಮೂವತ್ತು": 30,
    "ನೂರು": 100,
}
VERIFIED = {
    "ಒಂದು",
    "ಎರಡು",
    "ಮೂರು",
    "ನಾಲ್ಕು",
    "ಐದು",
    "ಆರು",
    "ಏಳು",
    "ಎಂಟು",
    "ಒಂಬತ್ತು",
    "ಹತ್ತು",
    "ಹದಿಮೂರು",
    "ಹದಿನಾಲ್ಕು",
    "ಹದಿನೈದು",
    "ಅರ್ಧ",
}
_DIGITS = regex.compile(r"^[0-9]+(?:\.[0-9]+)?$")


def parse_number(norm: str) -> float | int | None:
    """Parse one token in COMPARISON form (Kannada digits already mapped to ASCII)."""
    if not norm:
        return None
    if _DIGITS.match(norm):
        v = float(norm)
        return int(v) if v.is_integer() else v
    v = NUMBER_WORDS.get(norm)
    if v is None:
        return None
    return int(v) if float(v).is_integer() else v
