"""Drug lexicon access plus the verifier's own unit / frequency / duration / symptom phrases.

The drug CSV (m1 column set) is read with the csv module; nothing from m3 is imported.
Units, frequency and duration phrases and the symptom terms are hand-coded here by an AI
agent: UNVERIFIED, not native-validated. A phrase that is missing does not parse, and the
checks then fail closed (flag) instead of guessing.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from m4_verify.numbers import Num, parse_numbers_tokens
from m4_verify.textnorm import Token, is_kannada, token_texts, tokens

# --------------------------------------------------------------------------- units
UNIT_FORMS: dict[str, list[str]] = {
    "mg": ["mg", "mgs", "ಎಂ ಜಿ", "ಎಂಜಿ", "ಮಿಲಿಗ್ರಾಂ", "ಮಿಲಿಗ್ರಾಮ್", "ಮಿ ಗ್ರಾ", "milligram", "milligrams"],
    "g": ["g", "gm", "gram", "grams", "ಗ್ರಾಂ", "ಗ್ರಾಮ್"],
    "mcg": ["mcg", "microgram", "micrograms", "ಮೈಕ್ರೋಗ್ರಾಂ"],
    "ml": ["ml", "ಎಂ ಎಲ್", "ಎಂಎಲ್", "ಮಿಲಿ", "ಮಿಲೀ", "ಮಿಲಿಲೀಟರ್", "millilitre", "milliliter", "millilitres"],
    "tablet": ["tablet", "tablets", "tab", "ಮಾತ್ರೆ", "ಮಾತ್ರೆಗಳು", "ಗುಳಿಗೆ", "ಟ್ಯಾಬ್ಲೆಟ್"],
    "capsule": ["capsule", "capsules", "cap", "ಕ್ಯಾಪ್ಸೂಲ್"],
    "sachet": ["sachet", "sachets", "packet", "ಪ್ಯಾಕೆಟ್", "ಸ್ಯಾಶೆ"],
    "drop": ["drop", "drops", "ಹನಿ"],
    "teaspoon": ["teaspoon", "teaspoons", "spoon", "ಚಮಚ"],
    "IU": ["iu"],
}  # fmt: skip
UNIT_SEQS: list[tuple[tuple[str, ...], str]] = sorted(
    ((tuple(token_texts(f)), u) for u, forms in UNIT_FORMS.items() for f in forms),
    key=lambda x: -len(x[0]),
)
UNIT_TOKENS = {t for seq, _ in UNIT_SEQS for t in seq}

# --------------------------------------------------------------------------- frequency / duration
FREQ_MARK = {"ಬಾರಿ", "ಸಲ", "ಸಾರಿ", "times", "time"}
PER_DAY = {"ದಿನಕ್ಕೆ", "ದಿವಸಕ್ಕೆ", "ದಿನಾ", "ಪ್ರತಿದಿನ", "ದಿನವೂ", "ದಿನಾಲೂ", "daily", "day", "ದಿನಕ್ಕ"}
PER_WEEK = {"ವಾರಕ್ಕೆ", "week"}
FREQ_WORDS = {"ಒಮ್ಮೆ": 1, "od": 1, "bd": 2, "bid": 2, "tds": 3, "tid": 3, "qid": 4}
EN_FREQ = {"once": 1, "twice": 2, "thrice": 3}
DAY_WORDS = {"ದಿನ", "ದಿನಗಳು", "ದಿನಗಳ", "ದಿನಗಳವರೆಗೆ", "ದಿನದವರೆಗೆ", "ದಿನಗಳ ಕಾಲ", "days", "day"}
# colloquial ದಿವಸ (fix pass 2026-11-11: missing although the Kannada review assumed it; UNVERIFIED)
DAY_WORDS |= {"ದಿವಸ", "ದಿವಸಗಳು", "ದಿವಸಗಳ", "ದಿವಸದವರೆಗೆ"}
WEEK_WORDS = {"ವಾರ", "ವಾರಗಳು", "ವಾರಗಳ", "ವಾರದವರೆಗೆ", "ವಾರಗಳವರೆಗೆ", "week", "weeks"}
MONTH_WORDS = {"ತಿಂಗಳು", "ತಿಂಗಳ", "month", "months"}
# Words after a number that make it NOT a medication duration
NOT_DURATION = {"ದಿನಕ್ಕೆ", "ದಿನದಿಂದ", "ದಿನದಲ್ಲಿ", "ದಿನಗಳಿಂದ", "ದಿನಗಳಲ್ಲಿ", "ವಾರದಿಂದ", "ವಾರದಲ್ಲಿ"}
NOT_DURATION |= {"ದಿವಸಕ್ಕೆ", "ದಿವಸದಿಂದ", "ದಿವಸದಲ್ಲಿ", "ದಿವಸಗಳಿಂದ"}

# --------------------------------------------------------------------------- symptoms
# canonical English name -> spoken forms. Kannada forms match as token PREFIXES (inflection),
# multi-word forms match as token sequences. UNVERIFIED, AI-written.
SYMPTOMS: dict[str, list[str]] = {
    "fever": ["ಜ್ವರ", "fever"],
    "cough": ["ಕೆಮ್ಮ", "ಕೆಮ್ಮು", "cough"],
    "cold": ["ನೆಗಡಿ", "ಶೀತ", "cold"],
    "headache": ["ತಲೆನೋವು", "ತಲೆ ನೋವು", "headache"],
    "vomiting": ["ವಾಂತಿ", "vomiting"],
    "diarrhoea": ["ಭೇದಿ", "ಬೇಧಿ", "ಅತಿಸಾರ", "diarrhoea", "diarrhea", "loose motion"],
    "stomach pain": ["ಹೊಟ್ಟೆನೋವು", "ಹೊಟ್ಟೆ ನೋವು", "stomach pain"],
    "sore throat": ["ಗಂಟಲು ನೋವು", "ಗಂಟಲುನೋವು", "ಗಂಟಲ ನೋವು", "sore throat"],
    "body ache": ["ಮೈಕೈ ನೋವು", "ಮೈ ನೋವು", "body ache"],
    "rash": ["ದದ್ದು", "rash"],
    "breathlessness": ["ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಸಿರು ಕಟ್ಟು", "breathlessness"],
    "ear pain": ["ಕಿವಿ ನೋವು", "ಕಿವಿನೋವು", "ear pain"],
    "burning urination": ["ಮೂತ್ರ ಉರಿ", "ಉರಿ ಮೂತ್ರ", "burning urination"],
    "weakness": ["ಸುಸ್ತು", "ನಿಶ್ಯಕ್ತಿ", "weakness"],
    "runny nose": ["ಸಿಂಬಳ", "ಮೂಗು ಸೋರು", "runny nose"],
}
SYMPTOM_SEQS: list[tuple[tuple[str, ...], str]] = sorted(
    ((tuple(token_texts(f)), name) for name, forms in SYMPTOMS.items() for f in forms),
    key=lambda x: -len(x[0]),
)
# --------------------------------------------------------------------------- child cues (C4)
# A dose for a child is weight/age-based: the adult lexicon range does not apply, so C4 flags it
# "cannot_verify:paediatric" (clinical review M4-C1, D-91). Kannada forms match as token PREFIXES
# (ಮಗು -> ಮಗುವಿಗೆ, ಮಗುವಿನ). AI-written, UNVERIFIED, not native-validated. ಮಗ / ಮಗಳು (son /
# daughter) are NOT cues: an adult son is common; this is a documented gap.
CHILD_PREFIXES_KN = ("ಮಗು", "ಮಗೂ", "ಮಕ್ಕಳ", "ಕೂಸ", "ಶಿಶು", "ಪಾಪು", "ಹಸುಗೂಸ")
CHILD_WORDS_EN = {
    "child", "children", "baby", "babies", "infant", "infants", "kid", "kids", "toddler",
    "paediatric", "pediatric", "newborn",
}  # fmt: skip


def child_cues(text: str) -> list[str]:
    """Tokens of text that say the patient is a child (see CHILD_PREFIXES_KN)."""
    out = []
    for t in token_texts(text):
        if t in CHILD_WORDS_EN or any(t.startswith(p) for p in CHILD_PREFIXES_KN):
            out.append(t)
    return out


# --------------------------------------------------------------------------- dosage forms -> units
# The drug CSV has no unit column (contract gap). Where the lexicon's verified_by note names the
# dosage form (copied by m1 from NLEM / WHO pages it fetched), we derive the allowed units from it.
# Everything else falls back to the m4 config table / default (config.py). Mass units (mg, g, mcg)
# always go together: the range check then catches an absurd value.
MASS_UNITS = ("mg", "g", "mcg")


def units_from_note(note: str) -> tuple[tuple[str, ...], bool] | None:
    """(allowed units, injection_only) derived from a lexicon note, or None if it names no form."""
    n = note.casefold()
    units: list[str] = []
    oral = False
    if "tablet" in n:
        units += [*MASS_UNITS, "tablet"]
        oral = True
    if "capsule" in n:
        units += [*MASS_UNITS, "capsule"]
        oral = True
    if "syrup" in n or "suspension" in n:
        units += [*MASS_UNITS, "ml"]
        oral = True
    if "sachet" in n:
        units += ["sachet", "ml"]
        oral = True
    injection = "injection" in n
    if injection:
        units += list(MASS_UNITS)
    if "never mg" in n:
        units = [u for u in units if u not in MASS_UNITS]
    if not units:
        return None
    return tuple(dict.fromkeys(units)), injection and not oral


# Neutral words that may stand next to an entity in a bare noun phrase ("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್")
NP_FILLERS = {"ಸಿರಪ್", "syrup", "ಔಷಧಿ", "ಔಷಧ", "ಮದ್ದು", "ಇಂಜೆಕ್ಷನ್", "injection"}


def _seq_match(
    toks: list[str], i: int, seq: tuple[str, ...], prefix_last: bool, min_prefix: int = 3
) -> bool:
    """Exact token-sequence match; the LAST token may be a prefix (Kannada case endings)
    when prefix_last is set, the form is Kannada script and at least min_prefix code points."""
    if i + len(seq) > len(toks):
        return False
    for k, s in enumerate(seq):
        t = toks[i + k]
        last = k == len(seq) - 1
        if t == s:
            continue
        if last and prefix_last and is_kannada(s) and len(s) >= min_prefix and t.startswith(s):
            continue
        return False
    return True


# --------------------------------------------------------------------------- drug lexicon
@dataclass
class Drug:
    generic: str
    kn_primary: str
    forms: list[str]
    drug_class: str
    strengths_mg: list[float]
    range_mg: tuple[float, float] | None
    max_daily_mg: float | None
    confusable: list[str]
    source_url: str
    verified_by: str


def _floats(s: str) -> list[float]:
    return [float(x) for x in s.split("|") if x.strip()]


def _range(s: str) -> tuple[float, float] | None:
    s = s.strip()
    if not s:
        return None
    lo, _, hi = s.partition("-")
    return (float(lo), float(hi or lo))


@dataclass
class Lexicon:
    path: str
    drugs: dict[str, Drug] = field(default_factory=dict)
    seqs: list[tuple[tuple[str, ...], str]] = field(default_factory=list)

    def drugs_in(self, text: str, toks: list[Token] | None = None) -> list[tuple[str, int, int]]:
        """All drug mentions in text: (generic, stored start, stored end), left to right."""
        toks = tokens(text) if toks is None else toks
        tt = [t.text for t in toks]
        out = []
        i = 0
        while i < len(tt):
            hit = None
            for seq, gen in self.seqs:
                if _seq_match(tt, i, seq, prefix_last=True, min_prefix=5):
                    hit = (seq, gen)
                    break
            if hit:
                seq, gen = hit
                out.append((gen, toks[i].start, toks[i + len(seq) - 1].end))
                i += len(seq)
            else:
                i += 1
        return out

    def entity_tokens(self) -> set[str]:
        return {t for seq, _ in self.seqs for t in seq}


def load_lexicon(path: str | Path) -> Lexicon:
    path = Path(path)
    return _load_lexicon_cached(str(path.resolve()), path.stat().st_mtime_ns)


@lru_cache(maxsize=8)
def _load_lexicon_cached(path: str, _mtime: int) -> Lexicon:
    lex = Lexicon(path=path)
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            gen = row["generic_en"].strip().casefold()
            if not gen:
                continue
            forms = [gen, row.get("kn_primary", "")]
            for col in ("kn_variants", "roman_variants"):
                forms += (row.get(col) or "").split("|")
            forms = [f.strip() for f in forms if f and f.strip()]
            lex.drugs[gen] = Drug(
                generic=gen,
                kn_primary=row.get("kn_primary", "").strip(),
                forms=forms,
                drug_class=row.get("class", "").strip(),
                strengths_mg=_floats(row.get("strengths_mg") or ""),
                range_mg=_range(row.get("adult_dose_range_mg") or ""),
                max_daily_mg=float(row["max_daily_mg"])
                if (row.get("max_daily_mg") or "").strip()
                else None,
                confusable=[
                    c.strip().casefold()
                    for c in (row.get("confusable_with") or "").split("|")
                    if c.strip()
                ],
                source_url=row.get("source_url", "").strip(),
                verified_by=row.get("verified_by", "").strip(),
            )
            for f in forms:
                seq = tuple(token_texts(f))
                if seq:
                    lex.seqs.append((seq, gen))
    # longest sequence first, then longest last token (so "amoxicillin-clavulanate" beats "amoxicillin")
    lex.seqs.sort(key=lambda x: (-len(x[0]), -len(x[0][-1])))
    return lex


# --------------------------------------------------------------------------- phrase parsers
@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str | None  # dose unit, or "day"/"week" for frequency, or None
    start: int
    end: int


def _unit_at(tt: list[str], i: int) -> tuple[str, int] | None:
    for seq, unit in UNIT_SEQS:
        if _seq_match(tt, i, seq, prefix_last=False):
            return unit, len(seq)
    return None


def parse_dose_phrases(text: str) -> list[Quantity]:
    """A number IMMEDIATELY followed by a unit: '500 mg', 'ಒಂದು ಮಾತ್ರೆ', '5 ಎಂ.ಎಲ್'."""
    toks = tokens(text)
    tt = [t.text for t in toks]
    out = []
    for n in parse_numbers_tokens(text, toks):
        u = _unit_at(tt, n.last_tok)
        if u:
            unit, ln = u
            out.append(Quantity(n.value, unit, n.start, toks[n.last_tok + ln - 1].end))
    return out


def parse_frequencies(text: str) -> list[Quantity]:
    """'ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ' -> 3/day, 'ದಿನಕ್ಕೆ ಒಮ್ಮೆ' -> 1/day, 'BD' -> 2/day, 'twice daily'."""
    toks = tokens(text)
    tt = [t.text for t in toks]
    per = (
        "day"
        if any(t in PER_DAY for t in tt)
        else ("week" if any(t in PER_WEEK for t in tt) else None)
    )
    out = []
    nums = parse_numbers_tokens(text, toks)
    for n in nums:
        if n.last_tok < len(tt) and tt[n.last_tok] in FREQ_MARK:
            out.append(Quantity(n.value, per, n.start, toks[n.last_tok].end))
    for i, t in enumerate(tt):
        if t in FREQ_WORDS:
            out.append(
                Quantity(
                    FREQ_WORDS[t],
                    per or ("day" if t != "ಒಮ್ಮೆ" else None),
                    toks[i].start,
                    toks[i].end,
                )
            )
        elif t in EN_FREQ:
            out.append(Quantity(EN_FREQ[t], per, toks[i].start, toks[i].end))
    return out


def parse_durations(text: str) -> list[Quantity]:
    """'ಐದು ದಿನ' -> 5, 'ಒಂದು ವಾರ' -> 7. Month-based durations get unit 'month' (approximate)."""
    toks = tokens(text)
    tt = [t.text for t in toks]
    out = []
    for n in parse_numbers_tokens(text, toks):
        j = n.last_tok
        if j >= len(tt) or tt[j] in NOT_DURATION:
            continue
        w = tt[j]
        if w in DAY_WORDS:
            out.append(Quantity(n.value, "day", n.start, toks[j].end))
        elif w in WEEK_WORDS:
            out.append(Quantity(n.value * 7, "week", n.start, toks[j].end))
        elif w in MONTH_WORDS:
            out.append(Quantity(n.value * 30, "month", n.start, toks[j].end))
    return out


def numbers_in(text: str) -> list[Num]:
    return parse_numbers_tokens(text)


# --------------------------------------------------------------------------- symptoms
def symptoms_in(text: str) -> list[tuple[str, int, int]]:
    toks = tokens(text)
    tt = [t.text for t in toks]
    out = []
    i = 0
    while i < len(tt):
        for seq, name in SYMPTOM_SEQS:
            if _seq_match(tt, i, seq, prefix_last=True):
                out.append((name, toks[i].start, toks[i + len(seq) - 1].end))
                i += len(seq) - 1
                break
        i += 1
    return out


def symptom_in(name: str, text: str) -> bool:
    return any(n == name for n, _, _ in symptoms_in(text))


def symptom_tokens() -> set[str]:
    return {t for seq, _ in SYMPTOM_SEQS for t in seq}
