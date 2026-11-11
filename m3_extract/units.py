"""Dose unit, frequency and duration parsers over a token window.

Phrase lists and their status (fetched 2026-11-10 by nlp-engineer unless said otherwise):
- ದಿನ "day", ದಿವಸ "day", ವಾರ "a week", ತಿಂಗಳು "a month", ಸಲ "time, occurrence", ಚಮಚ "spoon":
  en.wiktionary.org raw entries (Kannada section).
- ದಿನಕ್ಕೆ = dative of ದಿನ ("per day"): grammar inference, UNVERIFIED.
- ಬಾರಿ "times": NOT found on Wiktionary (404); from the brief / kannada-nlp skill. UNVERIFIED.
- ಸಾರಿ "times": attested only via m1_data SOURCES.md KN-2 ("ಎರಡು ಸಾರಿ", fetched by m1). UNVERIFIED by us.
- ಒಮ್ಮೆ "once": 404 on Wiktionary. UNVERIFIED.
- mg / ಎಂ.ಜಿ / ಮಾತ್ರೆ (tablet) / ಕ್ಯಾಪ್ಸೂಲ್ (capsule): docs/annotation_guide.md conventions (AI-written).
- ಚಮಚ -> "teaspoon": UNVERIFIED mapping (a spoon is not a measured teaspoon).
Not native-validated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from m3_extract.numbers import parse_number
from m3_extract.textnorm import Token

# Unit phrases as token sequences in COMPARISON form -> record.v1 dose_unit.
UNIT_PHRASES: list[tuple[tuple[str, ...], str]] = [
    (("ಎಂ", "ಜಿ"), "mg"),
    (("mg",), "mg"),
    (("ಮಿಲಿಗ್ರಾಂ",), "mg"),
    (("milligram",), "mg"),
    (("mcg",), "mcg"),
    (("ಮೈಕ್ರೋಗ್ರಾಂ",), "mcg"),
    (("g",), "g"),
    (("gm",), "g"),
    (("ಗ್ರಾಂ",), "g"),
    (("ಎಂ", "ಎಲ್"), "ml"),
    (("ml",), "ml"),
    (("ಮಿಲಿ",), "ml"),
    (("ಮಾತ್ರೆ",), "tablet"),
    (("ಮಾತ್ರೆಗಳು",), "tablet"),
    (("tablet",), "tablet"),
    (("tab",), "tablet"),
    (("ಕ್ಯಾಪ್ಸೂಲ್",), "capsule"),
    (("capsule",), "capsule"),
    (("ಸ್ಯಾಚೆಟ್",), "sachet"),
    (("ಪ್ಯಾಕೆಟ್",), "sachet"),  # D-93: the spoken word for an ORS sachet; UNVERIFIED mapping
    (("sachet",), "sachet"),
    (("ಹನಿ",), "drop"),
    (("drop",), "drop"),
    (("drops",), "drop"),
    (("ಚಮಚ",), "teaspoon"),
    (("iu",), "IU"),
]
PER_DAY = {"ದಿನಕ್ಕೆ"}
TIMES = {"ಬಾರಿ", "ಸಾರಿ", "ಸಲ"}
ONCE = {"ಒಮ್ಮೆ": 1}
DURATION_UNITS = {"ದಿನ": 1, "ದಿವಸ": 1, "ವಾರ": 7, "ತಿಂಗಳು": 30}


@dataclass
class Attributes:
    dose_value: float | None = None
    dose_unit: str | None = None
    frequency_per_day: float | None = None
    duration_days: float | None = None
    last_token_index: int | None = None  # index (in the given window) of the last supporting token
    notes: list[str] = field(default_factory=list)

    def count(self) -> int:
        return sum(
            v is not None
            for v in (self.dose_value, self.dose_unit, self.frequency_per_day, self.duration_days)
        )


def _unit_at(tokens: list[Token], i: int) -> tuple[str, int] | None:
    for phrase, unit in sorted(UNIT_PHRASES, key=lambda p: -len(p[0])):
        n = len(phrase)
        if tuple(t.norm for t in tokens[i : i + n]) == phrase:
            return unit, n
    return None


def parse_attributes(tokens: list[Token]) -> Attributes:
    """Read dose, frequency and duration from a window of tokens (one medication clause)."""
    a = Attributes()

    def mark(j: int) -> None:
        a.last_token_index = j if a.last_token_index is None else max(a.last_token_index, j)

    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i].norm
        # frequency: ದಿನಕ್ಕೆ N ಬಾರಿ | ದಿನಕ್ಕೆ ಒಮ್ಮೆ
        if t in PER_DAY and a.frequency_per_day is None and i + 1 < n:
            nxt = tokens[i + 1].norm
            if nxt in ONCE:
                a.frequency_per_day = ONCE[nxt]
                mark(i + 1)
                i += 2
                continue
            v = parse_number(nxt)
            if v is not None and i + 2 < n and tokens[i + 2].norm in TIMES:
                a.frequency_per_day = v
                mark(i + 2)
                i += 3
                continue
        v = parse_number(t)
        if v is not None and i + 1 < n:
            u = _unit_at(tokens, i + 1)
            if u is not None and a.dose_value is None:
                a.dose_value, a.dose_unit = v, u[0]
                mark(i + u[1])
                i += 1 + u[1]
                continue
            nxt = tokens[i + 1].norm
            if nxt in DURATION_UNITS and a.duration_days is None:
                a.duration_days = v * DURATION_UNITS[nxt]
                if a.duration_days == int(a.duration_days):
                    a.duration_days = int(a.duration_days)
                mark(i + 1)
                i += 2
                continue
            if nxt in TIMES and a.frequency_per_day is None:
                a.notes.append("times-without-per-day")  # "N ಬಾರಿ" alone: not read as per day
        i += 1
    return a
