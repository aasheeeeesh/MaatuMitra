"""The verifier's OWN number parser: digits (ASCII or Kannada) and Kannada number words.

Kannada number words below were written by an AI agent from general knowledge and are
UNVERIFIED / not native-validated (see m4_verify/handoff/human_todo.md). Spoken variants
that are missing simply do not parse; the checks then FAIL CLOSED (they cannot re-derive a
value, so they flag).
"""

from __future__ import annotations

from dataclasses import dataclass

from m4_verify.textnorm import Token, tokens

UNITS = {
    "ಸೊನ್ನೆ": 0, "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5, "ಆರು": 6,
    "ಏಳು": 7, "ಎಂಟು": 8, "ಒಂಬತ್ತು": 9, "ಹತ್ತು": 10, "ಹನ್ನೊಂದು": 11, "ಹನ್ನೆರಡು": 12,
    "ಹದಿಮೂರು": 13, "ಹದಿನಾಲ್ಕು": 14, "ಹದಿನೈದು": 15, "ಹದಿನಾರು": 16, "ಹದಿನೇಳು": 17,
    "ಹದಿನೆಂಟು": 18, "ಹತ್ತೊಂಬತ್ತು": 19,
}  # fmt: skip
TENS = {
    "ಇಪ್ಪತ್ತು": 20, "ಮೂವತ್ತು": 30, "ನಲವತ್ತು": 40, "ಐವತ್ತು": 50, "ಅರವತ್ತು": 60,
    "ಎಪ್ಪತ್ತು": 70, "ಎಂಬತ್ತು": 80, "ತೊಂಬತ್ತು": 90,
}  # fmt: skip
HUNDREDS = {
    "ನೂರು": 100, "ಇನ್ನೂರು": 200, "ಮುನ್ನೂರು": 300, "ನಾನೂರು": 400, "ನಾನ್ನೂರು": 400,
    "ಐನೂರು": 500, "ಆರುನೂರು": 600, "ಏಳುನೂರು": 700, "ಎಂಟುನೂರು": 800, "ಒಂಬೈನೂರು": 900,
}  # fmt: skip
# combining forms used before another number word ("ಇನ್ನೂರ ಐವತ್ತು" = 250)
HUNDREDS_COMB = {k[:-1]: v for k, v in HUNDREDS.items()}  # strip final vowel sign "ು"
THOUSAND = {"ಸಾವಿರ": 1000}
FRACTIONS = {"ಅರ್ಧ": 0.5}
HALF_SUFFIX = "ೂವರೆ"  # ಒಂದೂವರೆ = 1.5, ಎರಡೂವರೆ = 2.5

EN_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14,
    "fifteen": 15, "twenty": 20, "thirty": 30, "once": 1, "twice": 2, "thrice": 3,
    "half": 0.5,
}  # fmt: skip


@dataclass(frozen=True)
class Num:
    value: float
    start: int  # stored offsets
    end: int
    first_tok: int  # token indices (inclusive, exclusive)
    last_tok: int
    is_digit: bool


def _clean(v: float) -> float | int:
    return int(v) if float(v).is_integer() else v


def word_value(tok: str) -> float | None:
    """Value of a single Kannada number-word token, or None."""
    for table in (UNITS, TENS, HUNDREDS, THOUSAND, FRACTIONS):
        if tok in table:
            return table[tok]
    if tok.endswith(HALF_SUFFIX):
        base = tok[: -len(HALF_SUFFIX)] + "ು"
        if base in UNITS:
            return UNITS[base] + 0.5
    return None


def parse_numbers_tokens(text: str, toks: list[Token] | None = None) -> list[Num]:
    toks = tokens(text) if toks is None else toks
    out: list[Num] = []
    i = 0
    while i < len(toks):
        t = toks[i].text
        # ASCII digits (Kannada digits were already mapped), with an optional decimal part
        if t.isdigit() and t.isascii():
            val = float(t)
            j = i + 1
            if (
                j + 1 <= len(toks)
                and j < len(toks)
                and toks[j].text.isdigit()
                and text[toks[i].end : toks[j].start] == "."
            ):
                val = float(f"{t}.{toks[j].text}")
                j += 1
            out.append(Num(_clean(val), toks[i].start, toks[j - 1].end, i, j, True))
            i = j
            continue
        # Kannada words: [hundreds-combining] [tens] [units] | unit * ಸಾವಿರ
        if t in HUNDREDS_COMB and i + 1 < len(toks):
            nxt = toks[i + 1].text
            tail = TENS.get(nxt, UNITS.get(nxt))
            if tail is not None:
                j = i + 2
                val = HUNDREDS_COMB[t] + tail
                if nxt in TENS and j < len(toks) and toks[j].text in UNITS:
                    val += UNITS[toks[j].text]
                    j += 1
                out.append(Num(val, toks[i].start, toks[j - 1].end, i, j, False))
                i = j
                continue
        v = word_value(t)
        if v is not None:
            j = i + 1
            if v < 10 and j < len(toks) and toks[j].text in THOUSAND:
                v = v * 1000
                j += 1
            out.append(Num(_clean(v), toks[i].start, toks[j - 1].end, i, j, False))
            i = j
            continue
        i += 1
    return out


def parse_numbers(text: str) -> list[Num]:
    return parse_numbers_tokens(text)


def english_numbers(text: str) -> list[float]:
    """Numbers in an English free-text value (advice / follow-up), digits or words."""
    out: list[float] = []
    toks = [t.text for t in tokens(text)]
    for i, t in enumerate(toks):
        if t.isdigit():
            out.append(_clean(float(t)))
        elif t in EN_WORDS:
            v = EN_WORDS[t]
            if i + 1 < len(toks) and toks[i + 1] == "hundred":
                v *= 100
            out.append(_clean(v))
        elif t == "hundred" and (i == 0 or toks[i - 1] not in EN_WORDS):
            out.append(100)
    return out
