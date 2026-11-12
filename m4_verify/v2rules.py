"""The verifier's OWN vocabulary for the record.v2 fields (Phase C).

Hand-coded here, independent of m3 and of the shared negation table (m4 never reads them).
Everything below was written by an AI agent from general knowledge of Kannada and clinical
English: UNVERIFIED and NOT native-validated. A phrase that is missing does not match, and the
checks then fail closed (flag or n/a, never pass).

Matching works on tokens of the comparison copy (textnorm: NFC, Kannada digits -> ASCII, Latin
casefolded, ZWJ/ZWNJ removed), never on raw substrings. Kannada forms marked as PREFIX match the
start of a token (case endings: ಇಂಜೆಕ್ಷನ್ -> ಇಂಜೆಕ್ಷನ್ನು); everything else is a whole token
or an explicit token-final regex.
"""

from __future__ import annotations

from dataclasses import dataclass

import regex

from m4_verify.lexicon import CHILD_PREFIXES_KN, CHILD_WORDS_EN, UNIT_SEQS, _seq_match
from m4_verify.numbers import parse_numbers_tokens
from m4_verify.textnorm import Token, tokens


# --------------------------------------------------------------------------- generic matcher
@dataclass(frozen=True)
class Vocab:
    whole: frozenset[str] = frozenset()  # whole tokens (comparison form)
    prefixes: tuple[str, ...] = ()  # Kannada token prefixes (case endings allowed)
    seqs: tuple[tuple[str, ...], ...] = ()  # multi-token sequences
    suffix_re: regex.Pattern | None = None  # token-final regex

    def hits(self, toks: list[Token]) -> list[str]:
        tt = [t.text for t in toks]
        out = []
        for i, t in enumerate(tt):
            if t in self.whole or any(t.startswith(p) for p in self.prefixes):
                out.append(t)
            elif self.suffix_re is not None and self.suffix_re.search(t):
                out.append(t)
            for seq in self.seqs:
                if tuple(tt[i : i + len(seq)]) == seq:
                    out.append(" ".join(seq))
        return out


def _v(whole=(), prefixes=(), seqs=(), suffix=None) -> Vocab:
    return Vocab(
        frozenset(whole),
        tuple(prefixes),
        tuple(tuple(s.split()) for s in seqs),
        regex.compile(suffix) if suffix else None,
    )


# --------------------------------------------------------------------------- route words
INJECTION_PREFIXES = ("ಇಂಜೆಕ್ಷನ್", "ಇಂಜೆಕ್ಶನ್", "ಇಂಜಕ್ಷನ್", "ಇಂಜೆಕ್ಷನ", "ಚುಚ್ಚುಮದ್ದ", "ಸೂಜಿ")
ROUTE_VOCAB: dict[str, Vocab] = {
    "iv": _v({"iv", "intravenous", "ಐವಿ", "drip", "ಡ್ರಿಪ್"}, seqs=["i v"]),
    "im": _v({"im", "intramuscular", "ಐಎಂ"}, seqs=["i m"]),
    "sc": _v({"sc", "subcutaneous", "ಎಸ್ಸಿ"}, seqs=["s c"]),
    "injection": _v({"injection", "injections", "inj"}, INJECTION_PREFIXES),
    # oral: drink / swallow / by mouth. ಕುಡಿ- covers ಕುಡಿಯಿರಿ, ಕುಡಿಸಿ, ಕುಡಿಯಿತಾ (UNVERIFIED)
    "oral": _v({"oral", "orally", "ಬಾಯಿಗೆ", "ಬಾಯಿಯಿಂದ", "ಬಾಯಲ್ಲಿ"}, ("ಕುಡಿ", "ನುಂಗ"), seqs=["by mouth"]),
    "topical": _v({"topical", "cream", "ointment", "gel", "apply", "ಕ್ರೀಮ್"}, ("ಹಚ್ಚ", "ಮುಲಾಮ")),
    "inhaled": _v({"inhaler", "inhale", "nebulizer", "nebuliser", "ಇನ್ಹೇಲರ್"}, ("ನೆಬ್ಯುಲೈಸ",)),
    "rectal": _v({"suppository", "rectal", "rectally"}),
}
PARENTERAL_ROUTES = ("iv", "im", "sc", "injection_unspecified")
SPECIFIC_PARENTERAL = ("iv", "im", "sc")


def route_cues(text: str) -> set[str]:
    """Route labels said in text: iv, im, sc, injection (unspecified word), oral, topical, ..."""
    toks = tokens(text)
    return {r for r, voc in ROUTE_VOCAB.items() if voc.hits(toks)}


# --------------------------------------------------------------------------- formulation words
FORM_VOCAB: dict[str, Vocab] = {
    "tablet": _v({"tablet", "tablets", "tab", "ಗುಳಿಗೆ", "ಟ್ಯಾಬ್ಲೆಟ್"}, ("ಮಾತ್ರೆ",)),  # not ಮಾತ್ರ
    "capsule": _v({"capsule", "capsules", "cap"}, ("ಕ್ಯಾಪ್ಸೂಲ್",)),
    "syrup": _v({"syrup"}, ("ಸಿರಪ್",)),
    "suspension": _v({"suspension"}, ("ಸಸ್ಪೆನ್ಷನ್",)),
    "drops": _v({"drops", "drop"}, ("ಹನಿ", "ಡ್ರಾಪ್ಸ್")),
    "injection": ROUTE_VOCAB["injection"],
    "sachet": _v({"sachet", "sachets", "packet", "ಸ್ಯಾಶೆ"}, ("ಪ್ಯಾಕೆಟ್",)),
}
LIQUID_FORMS = ("syrup", "suspension", "drops")
ORAL_FORMS = ("tablet", "capsule", "syrup", "suspension", "sachet")


def formulation_cues(text: str) -> set[str]:
    toks = tokens(text)
    return {f for f, voc in FORM_VOCAB.items() if voc.hits(toks)}


# --------------------------------------------------------------------------- strength phrases
MASS_TO_MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001}
PER_WORDS = {"per", "ಪ್ರತಿ"}


@dataclass(frozen=True)
class Strength:
    value: float
    unit: str  # record.v2 strength unit
    start: int
    end: int

    @property
    def key(self) -> tuple[str, float]:
        return strength_key(self.value, self.unit)


def strength_key(value: float, unit: str) -> tuple[str, float]:
    """Canonical form so that 120 mg/5ml == 24 mg/ml and 0.5 g == 500 mg."""
    v = float(value)
    if unit in MASS_TO_MG:
        return ("mg", round(v * MASS_TO_MG[unit], 6))
    if unit == "mg/5ml":
        return ("mg/ml", round(v / 5, 6))
    if unit == "mg/ml":
        return ("mg/ml", round(v, 6))
    if unit == "mcg/ml":
        return ("mg/ml", round(v / 1000, 6))
    if unit in ("IU", "IU/ml", "%"):
        return (unit, round(v, 6))
    return (unit, round(v, 6))


def mg_per_ml(value: float, unit: str) -> float | None:
    dim, v = strength_key(value, unit)
    return v if dim == "mg/ml" else None


def mg_per_unit(value: float, unit: str) -> float | None:
    dim, v = strength_key(value, unit)
    return v if dim == "mg" else None


def _unit_at(tt: list[str], i: int) -> tuple[str, int] | None:
    for seq, unit in UNIT_SEQS:
        if _seq_match(tt, i, seq, prefix_last=False):
            return unit, len(seq)
    return None


def parse_strengths(text: str) -> list[Strength]:
    """'120 mg/5 ml' -> 120 mg/5ml; '125 mg per 5 ml'; '24 mg/ml'; '500 mg' -> 500 mg;
    '1%' -> 1 %. A bare volume ('5 ml') is a dose, never a strength."""
    toks = tokens(text)
    tt = [t.text for t in toks]
    nums = parse_numbers_tokens(text, toks)
    by_tok = {n.first_tok: n for n in nums}
    out: list[Strength] = []
    for n in nums:
        j = n.last_tok
        end_raw = toks[j - 1].end
        if text[end_raw : end_raw + 1] == "%" or text[end_raw : end_raw + 2] == " %":
            out.append(Strength(n.value, "%", n.start, end_raw + 1))
            continue
        u = _unit_at(tt, j)
        if u is None or u[0] not in ("mg", "g", "mcg", "IU"):
            continue
        unit, ln = u
        k = j + ln  # token after the mass unit
        gap = text[toks[k - 1].end : toks[k].start] if k < len(toks) else ""
        per = "/" in gap
        if not per and k < len(toks) and tt[k] in PER_WORDS:
            per, k = True, k + 1
        if per and k < len(toks):
            vol = 1.0
            if k in by_tok:
                vol = float(by_tok[k].value)
                k = by_tok[k].last_tok
            vu = _unit_at(tt, k)
            if vu is not None and vu[0] == "ml" and vol > 0:
                end = toks[k + vu[1] - 1].end
                if unit == "IU":
                    out.append(Strength(n.value / vol, "IU/ml", n.start, end))
                elif unit == "mg" and vol == 5:
                    out.append(Strength(n.value, "mg/5ml", n.start, end))
                else:
                    out.append(Strength(n.value * MASS_TO_MG[unit] / vol, "mg/ml", n.start, end))
                continue
        out.append(Strength(n.value, unit, n.start, toks[j + ln - 1].end))
    return out


# --------------------------------------------------------------------------- age and weight
YEAR_PREFIXES = ("ವರ್ಷ", "ವರುಷ")
YEAR_EN = {"year", "years", "yr", "yrs"}
MONTH_PREFIXES = ("ತಿಂಗಳ",)
MONTH_EN = {"month", "months"}
WEEK_PREFIXES = ("ವಾರ",)
DAY_PREFIXES = ("ದಿನ", "ದಿವಸ")
INFANT_WORDS = _v({"infant", "newborn", "neonate"}, ("ಶಿಶು", "ಹಸುಗೂಸ", "ನವಜಾತ"))
OLDER_WORDS = _v({"elderly"}, ("ವೃದ್ಧ",))
AGE_CONTEXT = _v({"age", "old", "aged"}, ("ವಯಸ್ಸ", "ವಯಸ"))
BAND_CUTS = (
    (1, "infant"),
    (10, "child"),
    (18, "adolescent"),
    (65, "adult"),
)  # architect bands (contracts README): infant < 1 y, child 1-9, adolescent 10-17, adult 18-64


def band_of_years(years: float) -> str:
    for cut, band in BAND_CUTS:
        if years < cut:
            return band
    return "older_adult"


def _child_word(tok: str) -> bool:
    return tok in CHILD_WORDS_EN or any(tok.startswith(p) for p in CHILD_PREFIXES_KN)


def age_bands(text: str) -> tuple[set[str] | None, str]:
    """Bands the text supports, or None if nothing about age can be derived.

    A number + year/month word wins. Days/weeks give infant only when an age word or a child
    word is also present (a bare "ಮೂರು ದಿನ" is a duration). A child word without a number allows
    child OR infant (contracts convention: ಮಗು = child, but it may be an infant)."""
    toks = tokens(text)
    tt = [t.text for t in toks]
    has_child = any(_child_word(t) for t in tt)
    has_age_ctx = bool(AGE_CONTEXT.hits(toks))
    for n in parse_numbers_tokens(text, toks):
        j = n.last_tok
        if j >= len(tt):
            continue
        w = tt[j]
        if w.startswith(YEAR_PREFIXES) or w in YEAR_EN:
            return {band_of_years(float(n.value))}, f"{n.value} years"
        if w.startswith(MONTH_PREFIXES) or w in MONTH_EN:
            return {band_of_years(float(n.value) / 12)}, f"{n.value} months"
        if (w.startswith(WEEK_PREFIXES + DAY_PREFIXES)) and (has_child or has_age_ctx):
            return {"infant"}, f"{n.value} days/weeks old"
    if INFANT_WORDS.hits(toks):
        return {"infant"}, "infant word"
    if has_child:
        return {"child", "infant"}, "child word without an age"
    if OLDER_WORDS.hits(toks):
        return {"older_adult"}, "older-adult word"
    return None, "no age phrase"


WEIGHT_UNITS = _v(
    {"kg", "kgs", "kilo", "kilos", "kilogram", "kilograms", "ಕೆಜಿ", "ಕಿಲೋ"},
    ("ಕಿಲೋಗ್ರಾ", "ಕೆಜಿ"),
    seqs=["ಕೆ ಜಿ"],
)


def weights(text: str) -> list[float]:
    """Numbers immediately followed by a kilogram word."""
    toks = tokens(text)
    out = []
    for n in parse_numbers_tokens(text, toks):
        j = n.last_tok
        if j < len(toks) and WEIGHT_UNITS.hits(toks[j : j + 2]):
            first = WEIGHT_UNITS.hits(toks[j : j + 1]) or (
                j + 1 < len(toks) and (toks[j].text, toks[j + 1].text) == ("ಕೆ", "ಜಿ")
            )
            if first:
                out.append(n.value)
    return out


# --------------------------------------------------------------------------- as needed / regular
PRN_VOCAB = _v(
    {"ಬೇಕಾದರೆ", "ಅಗತ್ಯವಿದ್ದರೆ", "ಅವಶ್ಯವಿದ್ದರೆ", "sos", "prn"},
    seqs=["if needed", "as needed", "when needed", "if required", "if necessary"],
    # conditional verb forms: ಇದ್ದರೆ, ಆಗಿದ್ದರೆ, ಬಂದರೆ, ಹೆಚ್ಚಾದರೆ, ಆಗದಿದ್ದರೆ, colloquial ಇದ್ರೆ
    suffix=r"(ದ್ದರೆ|ಾದರೆ|ಂದರೆ|ದ್ರೆ)$",
)
NOT_PRN = {"ಅಂದರೆ", "ಎಂದರೆ", "ಆದರೆ"}  # "that is", "means", "but"
REGULAR_VOCAB = _v({"ತಪ್ಪದೆ", "ತಪ್ಪದೇ", "regularly", "ನಿಯಮಿತವಾಗಿ", "ಪ್ರತಿದಿನ", "ದಿನಾಲೂ"})


def prn_cues(text: str) -> list[str]:
    return [h for h in PRN_VOCAB.hits(tokens(text)) if h not in NOT_PRN]


def regular_cues(text: str) -> list[str]:
    return REGULAR_VOCAB.hits(tokens(text))


# --------------------------------------------------------------------------- food timing
FOOD_EN = {"food", "meal", "meals", "eating"}
FOOD_PREFIXES = ("ಊಟ", "ತಿಂಡಿ")
TIMING_WORDS = {
    "before_food": ({"ಮೊದಲು", "ಮುಂಚೆ", "ಮುನ್ನ", "ಮುಂಚಿತವಾಗಿ", "before"}, ()),
    "after_food": ({"ನಂತರ", "ಆಮೇಲೆ", "ಮೇಲೆ", "ಬಳಿಕ", "after"}, ()),
    "with_food": ({"ಜೊತೆ", "ಜೊತೆಗೆ", "ಜೊತೆಯಲ್ಲಿ", "ಒಟ್ಟಿಗೆ", "with"}, ()),
}
FUSED_FOOD = {"ಊಟದೊಂದಿಗೆ": "with_food", "ಊಟದಜೊತೆ": "with_food", "ಊಟವಾದಮೇಲೆ": "after_food"}


def food_timings(text: str) -> set[str]:
    """Food timing phrases: a food word followed (within 3 tokens) by a timing word, English
    'before/after/with food' (timing word first), or 'ಖಾಲಿ ಹೊಟ್ಟೆ' / 'empty stomach'."""
    tt = [t.text for t in tokens(text)]
    out = set()
    for i, t in enumerate(tt):
        if t in FUSED_FOOD:
            out.add(FUSED_FOOD[t])
        is_food = t in FOOD_EN or t.startswith(FOOD_PREFIXES)
        if is_food:
            for w in tt[i + 1 : i + 4]:
                for timing, (words, _) in TIMING_WORDS.items():
                    if w in words and not w.isascii():
                        out.add(timing)
            if i > 0 and tt[i - 1].isascii():
                for timing, (words, _) in TIMING_WORDS.items():
                    if tt[i - 1] in words:
                        out.add(timing)
        if t == "ಖಾಲಿ" and i + 1 < len(tt) and tt[i + 1].startswith("ಹೊಟ್ಟೆ"):
            out.add("empty_stomach")
        if t == "empty" and i + 1 < len(tt) and tt[i + 1] == "stomach":
            out.add("empty_stomach")
    return out


# --------------------------------------------------------------------------- status cues
# Past tense / "already" (already_taken). Explicit verb forms only: a generic -ಟ್ಟೆ ending would
# also match ಹೊಟ್ಟೆ (stomach), ಮೊಟ್ಟೆ (egg), ಬಟ್ಟೆ (cloth); ಆಯಿತು is the filler "ok, done".
PAST_VOCAB = _v(
    {
        "ನಿನ್ನೆ",
        "ಮೊನ್ನೆ",
        "ಈಗಾಗಲೇ",
        "ಆಗಲೇ",
        "ಮೊದಲೇ",
        "ಕುಡಿಯಿತು",
        "ಕುಡಿಯಿತಾ",
        "yesterday",
        "already",
        "ago",
        "took",
        "gave",
    },
    suffix=r"(ಕೊಟ್ಟ|ಕೊಂಡ|ಗೊಂಡ|ಕುಡಿದ|ಕುಡಿಸಿದ|ನುಂಗಿದ|ಹಾಕಿದ|ಬಳಸಿದ|ಹಚ್ಚಿದ)"
    r"(ೆ|ೆವು|ೆನು|ರು|ಳು|ನು|ಿತು|ಿದ್ದೇನೆ|ಿದ್ದೇವೆ|ಿದ್ದಾರೆ|ಿದ್ದೆ|ಿದ್ದೀನಿ|ಿದ್ದೀವಿ|ೀನಿ|ೀವಿ|ಿರಾ|ಿದ್ದೀರಾ|ಿಲ್ಲ)$",
)
# Advice against: whole ಬೇಡ/ಬೇಡಿ/ಬಾರದು/ಕೂಡದು or fused at the end of a verb (ಕೊಡಬೇಡಿ,
# ತೆಗೆದುಕೊಳ್ಳಬಾರದು). ಬೇಡಿಕೆ (demand) does not end in these forms.
AA_VOCAB = _v(
    {"ಬೇಡ", "ಬೇಡಿ", "ಬಾರದು", "ಕೂಡದು", "avoid"},
    seqs=["do not", "don t", "dont", "should not", "must not", "never give", "never take"],
    suffix=r".(ಬೇಡ|ಬೇಡಿ|ಬಾರದು|ಕೂಡದು)$",
)
# Directive (prescribing now): polite imperatives and "must take"/"I will give" forms
DIRECTIVE_VOCAB = _v(
    {"take", "give", "start", "prescribe", "prescribed", "continue", "apply", "use"},
    suffix=r"(ಕೊಳ್ಳಿ|ಕೊಳ್ಳಿರಿ|ತಗೊಳ್ಳಿ|ತಗೋಳಿ|ಕೊಡಿ|ಕೊಡಿರಿ|ಕುಡಿಯಿರಿ|ಕುಡಿಸಿ|ಹಾಕಿ|ಹಚ್ಚಿ|ನುಂಗಿ|"
    r"ಮುಂದುವರಿಸಿ|ಮುಂದುವರೆಸಿ|ಬಳಸಿ|ಉಪಯೋಗಿಸಿ|ಸೇವಿಸಿ|ಕೊಡುತ್ತೇನೆ|ಬರೆಯುತ್ತೇನೆ|ಕೊಡ್ತೀನಿ|ಬರೀತೀನಿ|"
    r"ಕೊಳ್ಳಬೇಕು|ಕೊಡಬೇಕು|ಕುಡಿಸಬೇಕು|ಹಾಕಬೇಕು|ಕುಡಿಯಬೇಕು)$",
)
STOP_VOCAB = _v({"stopped", "stop"}, ("ನಿಲ್ಲಿಸ",), suffix=r"^ಬಿಟ್ಟ(ೆ|ೆವು|ರು|ಿದ್ದೇನೆ|ಿದ್ದೇವೆ)$")
UNFINISHED_RE = regex.compile(r"^ಮುಗಿಸ(ಿಲ್ಲ|ಲಿಲ್ಲ|ದೆ|ದೇ)$")
CONTINUE_VOCAB = _v({"continue", "continuing"}, ("ಮುಂದುವರ", "ಮುಂದುವರೆ"))


# Added after the first DEV run (dev-informed, disclosed in handoff/decisions.md). General
# constructions, not template sentences; UNVERIFIED, not native-validated.
# Ongoing / habitual use of a giving or taking verb ("ಕುಡಿಯುತ್ತೆ" = drinks, "ತೆಗೆದುಕೊಳ್ಳುತ್ತೇನೆ"
# = I take): support for already_taken / continue_existing. Only giving/taking stems, so
# "ಜ್ವರ ಬರುತ್ತೆ" (fever comes) is not a cue.
ONGOING_RE = regex.compile(
    r"(ಕೊಡ|ಕುಡಿಯ|ಕೊಳ್ಳ|ತಗೊಳ್ಳ|ಹಾಕ|ನುಂಗ|ಕುಡಿಸ|ಬಳಸ|ತಿನ್ನ)ು"  # ತಿನ್ನು: "ಮಾತ್ರೆ ತಿನ್ನುತ್ತೆ" (also "eats food")
    r"(ತ್ತೆ|ತ್ತದೆ|ತ್ತೇನೆ|ತ್ತೇವೆ|ತ್ತಾರೆ|ತ್ತಾಳೆ|ತ್ತಾನೆ|ತ್ತೀನಿ|ತ್ತೀವಿ|ತ್ತಿದೆ|ತ್ತಿದ್ದೇನೆ|ತ್ತಿದ್ದೇವೆ|"
    r"ತ್ತಿದ್ದಾರೆ|ತ್ತಿದ್ದಾಳೆ|ತ್ತಿದ್ದೀನಿ|ತ್ತಿದ್ದೀರಾ|ತ್ತೀರಾ)$"
)
# Permission question "may I / shall I ...?" (ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ?, ಕೊಡಲಾ?, ತೆಗೆದುಕೊಳ್ಳಬೇಕಾ?);
# a "no" answer = advised against, a "yes" answer = allowed (given now).
PERMISSION_RE = regex.compile(r"(ಬಹುದಾ|ಬಹುದೇ|ಬೇಕಾ|ಬೇಕೇ|[ಕ-ಹ]ಲಾ)$")  # ಕಲಾ (art) would match: rare
# "finish (the course)": with a negation it supports stopped_early (ಮುಗಿಸಿದಿರಾ? / ಇಲ್ಲ)
FINISH_VOCAB = _v({"finish", "finished", "complete", "completed"}, ("ಮುಗಿಸ", "ಪೂರ್ತಿ"))


def ongoing_cues(text: str) -> list[str]:
    return [t.text for t in tokens(text) if ONGOING_RE.search(t.text)]


def permission_cues(text: str) -> list[str]:
    return [t.text for t in tokens(text) if PERMISSION_RE.search(t.text)]


def finish_cues(text: str) -> list[str]:
    return FINISH_VOCAB.hits(tokens(text))


def has_regimen(text: str) -> bool:
    """A dose, frequency or duration phrase: a stated regimen ('X 10 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ')."""
    from m4_verify.lexicon import parse_dose_phrases, parse_durations, parse_frequencies

    return bool(parse_dose_phrases(text) or parse_frequencies(text) or parse_durations(text))


def past_cues(text: str) -> list[str]:
    return PAST_VOCAB.hits(tokens(text))


def advise_against_cues(text: str) -> list[str]:
    return AA_VOCAB.hits(tokens(text))


def directive_cues(text: str) -> list[str]:
    aa = set(advise_against_cues(text))
    return [h for h in DIRECTIVE_VOCAB.hits(tokens(text)) if h not in aa]


def stop_cues(text: str) -> list[str]:
    toks = tokens(text)
    return STOP_VOCAB.hits(toks) + [t.text for t in toks if UNFINISHED_RE.search(t.text)]


def continue_cues(text: str) -> list[str]:
    return CONTINUE_VOCAB.hits(tokens(text))


# --------------------------------------------------------------------------- sentences
_TERM = set("?!।\n")
ABBREV = {"ಡಾ", "dr", "mr", "ms", "mrs", "no"}


def sentences(text: str) -> list[tuple[int, int]]:
    """Sentence spans (stored offsets, end exclusive, terminator included). Split after ? ! । and
    newline, and after '.' followed by whitespace/end unless the dot closes a dotted abbreviation
    (ಎಂ.ಜಿ.) or a listed short title (ಡಾ.)."""
    out = []
    start = 0
    n = len(text)
    for i, ch in enumerate(text):
        cut = False
        if ch in _TERM:
            cut = True
        elif ch == "." and (i + 1 == n or text[i + 1].isspace()):
            m = regex.search(r"[\p{L}\p{M}\p{N}]+$", text[:i])
            word = m.group() if m else ""
            dotted = bool(m) and m.start() > 0 and text[m.start() - 1] == "." and len(word) <= 2
            cut = not (dotted or word.casefold() in ABBREV)
        if cut:
            end = i if ch == "\n" else i + 1
            if text[start:end].strip():
                out.append((start, end))
            start = i + 1
    if text[start:].strip():
        out.append((start, n))
    # trim leading whitespace
    res = []
    for a, b in out:
        while a < b and text[a].isspace():
            a += 1
        res.append((a, b))
    return res


def context(text: str, spans: list[tuple[int, int]]) -> str:
    """Text of every sentence that overlaps one of the spans (joined with a newline)."""
    parts = []
    for a, b in sentences(text):
        if any(cs < b and a < ce for cs, ce in spans):
            parts.append(text[a:b])
    return "\n".join(parts)
