"""Dose unit, strength, frequency and duration parsers over a token window.

Phrase lists and their status (fetched 2026-11-10 by nlp-engineer unless said otherwise):
- ದಿನ "day", ದಿವಸ "day", ವಾರ "a week", ತಿಂಗಳು "a month", ಸಲ "time, occurrence", ಚಮಚ "spoon":
  en.wiktionary.org raw entries (Kannada section).
- ದಿನಕ್ಕೆ = dative of ದಿನ ("per day"): grammar inference, UNVERIFIED.
- ಬಾರಿ "times": NOT found on Wiktionary (404); from the brief / kannada-nlp skill. UNVERIFIED.
- ಸಾರಿ "times": attested only via m1_data SOURCES.md KN-2 ("ಎರಡು ಸಾರಿ", fetched by m1). UNVERIFIED by us.
- ಒಮ್ಮೆ "once": 404 on Wiktionary. UNVERIFIED.
- mg / ಎಂ.ಜಿ / ಮಾತ್ರೆ (tablet) / ಕ್ಯಾಪ್ಸೂಲ್ (capsule): docs/annotation_guide.md conventions (AI-written).
- ಚಮಚ -> "teaspoon": UNVERIFIED mapping (a spoon is not a measured teaspoon). record.v2: only read
  next to a liquid form word (ಸಿರಪ್ ...), otherwise the dose stays null (clinical review M3-M6).
- ಪ್ಯಾಕೆಟ್ -> "sachet": UNVERIFIED (Wiktionary 404, 2026-11-12). record.v2: only for ORS (M3-M6).
- "mg/5 ml" (liquid strength): '/' or 'per' or ಪ್ರತಿ between a mass and a volume; only 1 ml and 5 ml
  are read (the units in contracts/schemas/record.v2). A convention, not a Kannada phrase.
Not native-validated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import regex

from m3_extract.numbers import parse_number
from m3_extract.textnorm import Token

# Unit phrases as token sequences in COMPARISON form -> record dose_unit.
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
MASS_UNITS = {"mg", "g", "mcg", "IU"}
COUNT_UNITS = {"tablet", "capsule", "sachet"}
LIQUID_UNITS = {"ml", "drop", "teaspoon"}
PER_WORDS = {"per", "ಪ್ರತಿ"}
SACHET_WORD = "ಪ್ಯಾಕೆಟ್"
SPOON_WORD = "ಚಮಚ"
GLUED = regex.compile(r"^([0-9]+(?:\.[0-9]+)?)([a-z]+)$")
LIQUID_STRENGTH_UNIT = {
    ("mg", 5): "mg/5ml",
    ("mg", 1): "mg/ml",
    ("mcg", 1): "mcg/ml",
    ("IU", 1): "IU/ml",
}


@dataclass
class Attributes:
    dose_value: float | None = None
    dose_unit: str | None = None
    frequency_per_day: float | None = None
    duration_days: float | None = None
    last_token_index: int | None = None  # index (in the given window) of the last supporting token
    notes: list[str] = field(default_factory=list)
    strength_value: float | None = None
    strength_unit: str | None = None
    dose_idx: tuple[int, int] | None = None  # (first, last) window index of the dose words
    strength_idx: tuple[int, int] | None = None
    events: list[dict] = field(default_factory=list)  # decisions worth logging (v2)

    def count(self) -> int:
        return sum(
            v is not None
            for v in (self.dose_value, self.dose_unit, self.frequency_per_day, self.duration_days)
        )


@dataclass
class _Word:
    norm: str


def _unit_at(tokens: list, i: int) -> tuple[str, int] | None:
    for phrase, unit in sorted(UNIT_PHRASES, key=lambda p: -len(p[0])):
        n = len(phrase)
        if tuple(t.norm for t in tokens[i : i + n]) == phrase:
            return unit, n
    return None


def _num_unit(tokens: list[Token], i: int) -> tuple[float, str, int, str] | None:
    """number + unit at i: (value, unit, tokens used, unit word). Also a glued token (5ml)."""
    t = tokens[i].norm
    g = GLUED.match(t)
    if g:
        u = _unit_at([_Word(g.group(2))], 0)
        v = parse_number(g.group(1))
        if u and v is not None:
            return v, u[0], 1, g.group(2)
        return None
    v = parse_number(t)
    if v is None or i + 1 >= len(tokens):
        return None
    u = _unit_at(tokens, i + 1)
    if u is None:
        return None
    return v, u[0], 1 + u[1], tokens[i + 1].norm


def _liquid_strength(tokens: list[Token], i: int, text: str | None):
    """A mass followed by '/', 'per' or ಪ್ರತಿ and a volume: 120 mg/5 ml.
    Returns (value, unit, tokens used); (None, None, used) when the volume is not 1 or 5 ml
    (consumed, not trusted); None when this is not a liquid strength."""
    nu = _num_unit(tokens, i)
    if nu is None or nu[1] not in MASS_UNITS:
        return None
    value, unit, used, _ = nu
    j = i + used
    if j >= len(tokens):
        return None
    gap = text[tokens[j - 1].end : tokens[j].start] if text is not None else ""
    if tokens[j].norm in PER_WORDS:
        j += 1
    elif "/" not in gap:
        return None
    if j >= len(tokens):
        return None
    vol = _num_unit(tokens, j)
    if vol is None:
        u = _unit_at(tokens, j)  # "mg per ml" = per one ml
        if u is None or u[0] != "ml":
            return None
        volume, vused = 1, u[1]
    else:
        if vol[1] != "ml":
            return None
        volume, vused = vol[0], vol[2]
    total = j + vused - i
    key = (unit, int(volume) if float(volume).is_integer() else -1)
    su = LIQUID_STRENGTH_UNIT.get(key)
    return (value, su, total) if su else (None, None, total)


def parse_attributes(
    tokens: list[Token],
    *,
    legacy: bool = False,
    text: str | None = None,
    symptom_starts: frozenset[int] | set[int] = frozenset(),
    liquid: bool = False,
    ors: bool = False,
    combination: bool = False,
) -> Attributes:
    """Read dose, strength, frequency and duration from a window of tokens (one medication clause).

    legacy=True: the record.v1 behaviour (the first number+unit pair is the dose; no strength).
    Otherwise (record.v2): a mass pair together with a count/volume pair gives strength + dose;
    spoons need a liquid context, packets an ORS; a duration next to a symptom word is not a
    course length. In both modes "N ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ" (once every N days) is not read as per day."""
    a = Attributes()

    def mark(j: int) -> None:
        a.last_token_index = j if a.last_token_index is None else max(a.last_token_index, j)

    pairs: list[tuple[float, str, int, int, str]] = []  # value, unit, first, last, unit word
    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i].norm
        # frequency: ದಿನಕ್ಕೆ N ಬಾರಿ | ದಿನಕ್ಕೆ ಒಮ್ಮೆ
        if t in PER_DAY and a.frequency_per_day is None and i + 1 < n:
            if i > 0 and parse_number(tokens[i - 1].norm) is not None:
                a.events.append({"rule": "frequency_not_per_day", "char_start": tokens[i].start})
                a.notes.append("every-N-days")
                i += 1
                continue
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
        if not legacy:
            ls = _liquid_strength(tokens, i, text)
            if ls is not None:
                value, unit, used = ls
                if value is not None and a.strength_value is None:
                    a.strength_value, a.strength_unit = value, unit
                    a.strength_idx = (i, i + used - 1)
                    mark(i + used - 1)
                else:
                    a.events.append(
                        {"rule": "liquid_strength_not_read", "char_start": tokens[i].start}
                    )
                i += used
                continue
        nu = _num_unit(tokens, i)
        if nu is not None:
            v, unit, used, word = nu
            if legacy:
                if a.dose_value is None:
                    a.dose_value, a.dose_unit = v, unit
                    mark(i + used - 1)
                    i += used
                    continue
            else:
                pairs.append((v, unit, i, i + used - 1, word))
                i += used
                continue
        v = parse_number(t)
        if v is not None and i + 1 < n:
            nxt = tokens[i + 1].norm
            if nxt in DURATION_UNITS and a.duration_days is None:
                near = not legacy and (
                    (i > 0 and tokens[i - 1].start in symptom_starts)
                    or (i + 2 < n and tokens[i + 2].start in symptom_starts)
                )
                if near:  # "fever for 3 days" is how long the symptom lasted, not the course
                    a.events.append(
                        {"rule": "duration_next_to_symptom", "char_start": tokens[i].start}
                    )
                    i += 2
                    continue
                a.duration_days = v * DURATION_UNITS[nxt]
                if a.duration_days == int(a.duration_days):
                    a.duration_days = int(a.duration_days)
                mark(i + 1)
                i += 2
                continue
            if nxt in TIMES and a.frequency_per_day is None:
                a.notes.append("times-without-per-day")  # "N ಬಾರಿ" alone: not read as per day
        i += 1
    if not legacy:
        _decide_dose(a, pairs, mark, liquid=liquid, ors=ors, combination=combination)
    return a


def _decide_dose(a: Attributes, pairs, mark, *, liquid: bool, ors: bool, combination: bool) -> None:
    usable = []
    for v, unit, s, e, word in pairs:
        if word == SPOON_WORD and not liquid:
            a.events.append({"rule": "unit_needs_context", "unit": word, "need": "liquid form"})
            continue
        if word == SACHET_WORD and not ors:
            a.events.append({"rule": "unit_needs_context", "unit": word, "need": "ORS"})
            continue
        if combination and unit in MASS_UNITS:
            a.events.append({"rule": "combination_mass_unit", "unit": unit})
            continue
        usable.append((v, unit, s, e))
    mass = [p for p in usable if p[1] in MASS_UNITS]
    other = [p for p in usable if p[1] not in MASS_UNITS]
    if mass and other:
        if all(p[1] in LIQUID_UNITS for p in other):
            # 250 mg 5 ml: a strength, a dose in mg, or a mistake? not guessed (review M3-M5)
            a.events.append({"rule": "ambiguous_mass_and_volume"})
            return
        d, st = other[0], mass[0]
        a.dose_value, a.dose_unit, a.dose_idx = d[0], d[1], (d[2], d[3])
        mark(d[3])
        if a.strength_value is None:
            a.strength_value, a.strength_unit, a.strength_idx = st[0], st[1], (st[2], st[3])
            mark(st[3])
        return
    if usable:
        d = usable[0]
        a.dose_value, a.dose_unit, a.dose_idx = d[0], d[1], (d[2], d[3])
        mark(d[3])
