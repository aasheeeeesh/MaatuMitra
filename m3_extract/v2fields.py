"""Word lists and small rules for the record.v2 fields (route, formulation, status, as-needed,
food timing, age band, weight). Pure functions over Token lists; rules.py supplies the context.

Conventions follow gold.v2 (m1_data/goldv2.py): a field is filled only when a word says it (or a
form word implies it, as the gold derivation does); its evidence is the smallest span of those words.
Sources: Wiktionary raw entries fetched 2026-11-12: ಮಗು "child", ವರ್ಷ "year", ತಿಂಗಳು "month",
ಶಿಶು "infant", ಕುಡಿ "to drink", ತಿನ್ನು "to eat". Everything else here (verb forms, ಸಿರಪ್, ಕೆಜಿ,
ಊಟದ ನಂತರ, the question-verb classes) is UNVERIFIED and not native-validated.
"""

from __future__ import annotations

import regex

from m3_extract.numbers import parse_number
from m3_extract.textnorm import Token

FORM_WORDS = {
    "ಮಾತ್ರೆ": "tablet",
    "ಮಾತ್ರೆಗಳು": "tablet",
    "tablet": "tablet",
    "tab": "tablet",
    "ಕ್ಯಾಪ್ಸೂಲ್": "capsule",
    "capsule": "capsule",
    "ಸಿರಪ್": "syrup",
    "syrup": "syrup",
    "ಸಸ್ಪೆನ್ಷನ್": "suspension",
    "suspension": "suspension",
    "injection": "injection",
    "ಇಂಜೆಕ್ಷನ್": "injection",
    "ಪ್ಯಾಕೆಟ್": "sachet",
    "ಸ್ಯಾಚೆಟ್": "sachet",
    "sachet": "sachet",
}
ORAL_FORMS = {"tablet", "capsule", "syrup", "suspension"}
LIQUID_FORMS = {"syrup", "suspension"}
DRINK = regex.compile(r"^ಕುಡಿ")  # ಕುಡಿಸಿ, ಕುಡಿಯಿರಿ, ಕುಡಿಯಲಿಲ್ಲ ...

PRESCRIBE_VERBS = {
    "ತೆಗೆದುಕೊಳ್ಳಿ",
    "ಕೊಡಿ",
    "ಕುಡಿಸಿ",
    "ಕುಡಿಯಿರಿ",
    "ಕೊಡುತ್ತೇವೆ",
    "ತಿನ್ನಿ",
}
TAKEN_VERBS = {
    "ಕೊಟ್ಟೆ",
    "ಕೊಟ್ಟೆವು",
    "ಕುಡಿಯಿತು",
    "ಕುಡಿಯುತ್ತೆ",
    "ತಿನ್ನುತ್ತೆ",
    "ತೆಗೆದುಕೊಂಡೆವು",
    "ತೆಗೆದುಕೊಂಡಿದ್ದೇನೆ",
    "ತಿಂದೆ",
    "ಕುಡಿದೆ",
}
INTAKE_STEM = regex.compile(r"^(ಕುಡಿ|ತಿನ್ನ|ತಿಂ|ತೆಗೆದುಕೊಳ್ಳ|ತೆಗೆದುಕೊಂಡ|ಕೊಡ|ಕುಡಿಸ)")
ADVISE_CUE = regex.compile(r"(ಬೇಡ|ಬೇಡಿ|ಬಾರದು|ಕೂಡದು)$")
CLINICIAN = {"doctor", "nurse", "asha", "pharmacist"}

# question classes for a bare ಹೌದು / ಇಲ್ಲ answer: (positive status, negative status)
QUESTION_COMPLETED = regex.compile(r"^ಮುಗಿಸ")
QUESTION_MAY = regex.compile(r"ಬಹುದಾ$|ಬಹುದೇ$|ಬಹುದು$")
QUESTION_TAKEN = regex.compile(r"^(ತೆಗೆದುಕೊಂಡ|ತೆಗೆದುಕೊಳ್ಳುತ್ತಿ|ಕುಡಿಯಿತಾ|ಕುಡಿದ|ಕುಡಿಯುತ್ತಿ|ತಿಂದ|ಕೊಡುತ್ತಿ)")

FOOD = [
    (("ಊಟದ", "ನಂತರ"), "after_food"),
    (("ಊಟದ", "ಮೊದಲು"), "before_food"),
    (("ಊಟದ", "ಜೊತೆ"), "with_food"),
    (("ಖಾಲಿ", "ಹೊಟ್ಟೆ"), "empty_stomach"),
]
YEAR_WORDS = {"ವರ್ಷದ", "ವರ್ಷ"}  # ವರ್ಷದಿಂದ ("for N years") is a duration, not an age
MONTH_WORDS = {"ತಿಂಗಳ", "ತಿಂಗಳಿನ"}  # ತಿಂಗಳು alone is ambiguous (a duration): not read
CHILD_WORD = regex.compile(r"^ಮಗು")
INFANT_WORD = regex.compile(r"^ಶಿಶು")
KG_WORDS = {"kg", "ಕೆಜಿ", "ಕಿಲೋ"}
GLUED_KG = regex.compile(r"^([0-9]+(?:\.[0-9]+)?)kg$")


def span_of(tokens: list[Token]) -> tuple[int, int]:
    return tokens[0].start, tokens[-1].end


def form_in(tokens: list[Token]) -> tuple[str, Token] | None:
    """First form word; "ಮಾತ್ರೆ ಬೇರೆ" (the tablet I said is another one) names no form of this drug."""
    for k, t in enumerate(tokens):
        if k + 1 < len(tokens) and tokens[k + 1].norm == "ಬೇರೆ":
            continue
        if t.norm in FORM_WORDS:
            return FORM_WORDS[t.norm], t
    return None


def route_for(formulation: str | None, form_tok: Token | None, clause: list[Token]):
    """(route, span token) as the gold derivation does: explicit form word, else a drink verb."""
    if formulation in ORAL_FORMS and form_tok is not None:
        return "oral", form_tok
    if formulation == "injection" and form_tok is not None:
        return "injection_unspecified", form_tok
    if formulation is None:
        for t in clause:
            if DRINK.match(t.norm):
                return "oral", t
    return None, None


def statement_status(
    clause: list[Token], sentence: list[Token], negated: bool, cues: list[Token]
) -> tuple[str, tuple[int, int] | None]:
    """Status of a drug in a statement from its verb. Returns (status, evidence span or None)."""
    norms = [t.norm for t in clause]
    if negated:
        for k, n in enumerate(norms[:-1]):
            if n.startswith("ತೆಗೆದುಕೊಳ್ಳದೆ") and norms[k + 1].startswith("ಬಿಟ್ಟ"):
                return "stopped_early", span_of(clause[k : k + 2])
        for c in cues:
            if ADVISE_CUE.search(c.norm):
                return "advised_against", (c.start, c.end)
        for t in clause:
            if INTAKE_STEM.match(t.norm) and any(t.start == c.start for c in cues):
                return "not_taken", (t.start, t.end)
        return "unknown", None
    for pool in (clause, sentence):
        for t in pool:
            if t.norm in TAKEN_VERBS:
                return "already_taken", (t.start, t.end)
            if t.norm in PRESCRIBE_VERBS:
                return "prescribed", (t.start, t.end)
    return "unknown", None


def question_status(question: list[Token], answer: str) -> str:
    """Status from a question about the drug and a bare answer ('affirmative' / 'negative')."""
    pos = answer == "affirmative"
    norms = [t.norm for t in question]
    if any(QUESTION_COMPLETED.match(n) for n in norms):
        return "already_taken" if pos else "stopped_early"
    if any(QUESTION_MAY.search(n) for n in norms):
        return "prescribed" if pos else "advised_against"
    if any(QUESTION_TAKEN.match(n) for n in norms):
        return "already_taken" if pos else "not_taken"
    return "unknown"


def as_needed_spans(tokens: list[Token], symptom_tok: set[int]) -> list[tuple[int, int, int]]:
    """'<symptom> ಇದ್ದರೆ ಮಾತ್ರ' = only if. Returns (first token index, last token index, ...)."""
    out = []
    for k in range(len(tokens) - 1):
        if (
            tokens[k].norm == "ಇದ್ದರೆ"
            and tokens[k + 1].norm == "ಮಾತ್ರ"
            and tokens[k].turn == tokens[k + 1].turn
        ):
            first = k - 1 if k > 0 and (k - 1) in symptom_tok else k
            out.append((first, k + 1, k))
    return out


def food_spans(tokens: list[Token]) -> list[tuple[int, int, str]]:
    out = []
    for k in range(len(tokens) - 1):
        for words, value in FOOD:
            if (tokens[k].norm, tokens[k + 1].norm) == words:
                out.append((k, k + 1, value))
    return out


def _band_years(v: float) -> str | None:
    if v < 1 or v > 120:
        return None
    return "child" if v < 10 else "adolescent" if v < 18 else "adult" if v < 65 else "older_adult"


def find_age(tokens: list[Token]) -> tuple[str, int, int] | None:
    """(band, start, end): '<N> ವರ್ಷದ' / '<N> ತಿಂಗಳ' first, else the word for child / infant."""
    for k in range(len(tokens) - 1):
        v = parse_number(tokens[k].norm)
        nxt = tokens[k + 1]
        if v is None or nxt.turn != tokens[k].turn:
            continue
        if nxt.norm in YEAR_WORDS and (b := _band_years(v)):
            return b, tokens[k].start, nxt.end
        if nxt.norm in MONTH_WORDS and 0 < v < 216:
            return ("infant" if v < 12 else "child"), tokens[k].start, nxt.end
    for pat, band in ((CHILD_WORD, "child"), (INFANT_WORD, "infant")):
        for t in tokens:
            if pat.match(t.norm):
                return band, t.start, t.end
    return None


def find_weight(tokens: list[Token]) -> tuple[float, int, int] | None:
    for k, t in enumerate(tokens):
        g = GLUED_KG.match(t.norm)
        if g:
            v = float(g.group(1))
            if 0 < v <= 300:
                return v, t.start, t.end
        if t.norm in KG_WORDS and k > 0 and tokens[k - 1].turn == t.turn:
            v = parse_number(tokens[k - 1].norm)
            if v is not None and 0 < v <= 300:
                return v, tokens[k - 1].start, t.end
    return None
