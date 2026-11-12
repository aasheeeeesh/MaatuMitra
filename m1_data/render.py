"""Template mini-language renderer.

Turn text syntax:
  {D1.name} {D1.dose} ...  typed slot attribute (see *Fill classes)
  {N1}                     negation / cross-turn slot: replaced by its negative or positive form
                           (forms may contain other placeholders)
  [[m1| ... ]]             gold-span marker; markers MAY be nested (gold.v2 evidence spans live
                           inside the main span); offsets are computed while rendering
  automatic sub-spans      a drug slot whose dose text ends in a form word (ಮಾತ್ರೆ, ಕ್ಯಾಪ್ಸೂಲ್, ...)
                           also reports the span "<slot>.form" for that word (gold.v2 formulation)

Every surface choice is drawn ONCE when a slot is filled, so re-rendering a turn for its
minimal-pair twin gives identical text except for the flipped negation form.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import regex

from m1_data import kn

PLACEHOLDER = regex.compile(r"\{([A-Z]+\d*)(?:\.([a-z_]+))?\}")
TOKEN = regex.compile(r"\[\[([a-z]+\d*)\||\]\]|\{([A-Z]+\d*)(?:\.([a-z_]+))?\}")
FORM_WORD = {"tablet": "ಮಾತ್ರೆ", "capsule": "ಕ್ಯಾಪ್ಸೂಲ್", "injection": "ಇಂಜೆಕ್ಷನ್", "sachet": "ಪ್ಯಾಕೆಟ್"}
FORMULATION_OF_WORD = {w: f for f, w in FORM_WORD.items()}

SYMPTOMS = {
    "fever": "ಜ್ವರ",
    "cough": "ಕೆಮ್ಮು",
    "cold": "ನೆಗಡಿ",
    "headache": "ತಲೆನೋವು",
    "vomiting": "ವಾಂತಿ",
    "diarrhoea": "ಅತಿಸಾರ",
    "body ache": "ಮೈಕೈನೋವು",
    "chills": "ಚಳಿ",
    "tiredness": "ಸುಸ್ತು",
    "breathing difficulty": "ಉಸಿರಾಟದ ತೊಂದರೆ",
    "pain": "ನೋವು",
}


def _pick(rng: random.Random, options: list[tuple[float, str]]) -> str:
    r = rng.random()
    acc = 0.0
    for w, v in options:
        acc += w
        if r < acc:
            return v
    return options[-1][1]


def drug_surface(drug, attr: str, rng: random.Random) -> str:
    """Spoken surface form of a drug name. name = code-switch policy; kn = Kannada script;
    en = Latin script (English generic or a roman variant)."""
    kv = drug.kn_variants or [drug.kn_primary]
    if attr == "kn":
        return drug.kn_primary if rng.random() < 0.7 else rng.choice(kv)
    if attr == "en":
        r = rng.random()
        if r < 0.5:
            return drug.generic.capitalize()
        if r < 0.8:
            return drug.generic
        return rng.choice(drug.roman)
    r = rng.random()
    if r < 0.45:
        return drug.kn_primary
    if r < 0.65:
        return rng.choice(kv)
    if r < 0.9:
        return drug.generic if rng.random() < 0.5 else drug.generic.capitalize()
    return rng.choice(drug.roman)


@dataclass
class DrugFill:
    drug: object
    dose: tuple[float, str] | None
    freq: int | None
    dur: int | None
    rng: random.Random
    surfaces: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        rng = self.rng
        s = self.surfaces
        for a in ("name", "kn", "en"):
            s[a] = drug_surface(self.drug, a, rng)
        if self.dose:
            v, unit = self.dose
            if unit == "mg":
                s["dose"] = _pick(
                    rng,
                    [
                        (0.6, f"{kn.fmt_num(v)} mg"),
                        (0.15, f"{kn.fmt_num(v)} ಎಂ.ಜಿ"),
                        (0.25, f"{kn.to_kn_digits(v)} mg"),
                    ],
                )
                s["dose_tab"] = f"{s['dose']} {FORM_WORD[self.drug.form]}"
            elif unit == "ml":
                # paediatric liquid (syrup) volume; spoken with the number word or digits
                s["dose"] = s["dose_tab"] = _pick(
                    rng,
                    [
                        (0.45, f"{kn.ML_WORDS[v]} ಎಂ.ಎಲ್"),
                        (0.35, f"{kn.fmt_num(v)} ml"),
                        (0.2, f"{kn.fmt_num(v)} ಎಂ.ಎಲ್"),
                    ],
                )
            else:
                s["dose"] = s["dose_tab"] = f"{kn.NUM_WORDS[int(v)][0]} {FORM_WORD[unit]}"
        if self.freq:
            w = kn.NUM_WORDS[self.freq][0]
            s["freq"] = _pick(rng, [(0.8, f"ದಿನಕ್ಕೆ {w} ಬಾರಿ"), (0.2, f"ದಿನಕ್ಕೆ {w} ಸಾರಿ")])
        if self.dur:
            w = kn.NUM_WORDS[self.dur][0]
            if self.dur == 7 and rng.random() < 0.5:
                s["dur"] = "ಒಂದು ವಾರ"
            else:
                s["dur"] = _pick(rng, [(0.7, f"{w} ದಿನ"), (0.3, f"{w} ದಿವಸ")])

    def attr(self, a: str | None) -> str:
        if a is None or a not in self.surfaces:
            raise KeyError(f"drug slot has no attribute {a!r} (dose/freq/dur not chosen?)")
        return self.surfaces[a]

    def parts(self, a: str | None) -> list[tuple[str, int, int]]:
        """Named sub-spans (offsets inside the surface text). Only the form word at the end of a
        dose text ("500 mg ಮಾತ್ರೆ", "ಒಂದು ಮಾತ್ರೆ") is reported, as "form"."""
        if a not in ("dose", "dose_tab") or a not in self.surfaces:
            return []
        text = self.surfaces[a]
        for word in FORM_WORD.values():
            if text.endswith(word):
                return [("form", len(text) - len(word), len(text))]
        return []


@dataclass
class SymptomFill:
    name: str
    kn: str

    def attr(self, a: str | None) -> str:
        if a == "kn":
            return self.kn
        raise KeyError(a)


@dataclass
class CountFill:
    n: int

    def attr(self, a: str | None) -> str:
        if a in ("kn", None):
            return kn.NUM_WORDS[self.n][0]
        if a == "en":
            return kn.NUM_WORDS[self.n][1]
        raise KeyError(a)


@dataclass
class WordFill:
    text: str

    def attr(self, a: str | None) -> str:
        if a is not None:
            raise KeyError(a)
        return self.text


@dataclass
class NegFill:
    neg: str
    pos: str
    patterns: list[str]
    negative: bool
    cross_turn: bool = False

    def form(self, flipped: bool = False) -> str:
        return self.neg if self.negative != flipped else self.pos


def expand_neg(text: str, slots: dict, flip: set[str] = frozenset()) -> str:
    def rep(m: regex.Match) -> str:
        sid = m.group(1)
        f = slots.get(sid)
        if isinstance(f, NegFill) and m.group(2) is None:
            return f.form(sid in flip)
        return m.group(0)

    return PLACEHOLDER.sub(rep, text)


def render_text(
    template: str, slots: dict, flip: set[str] = frozenset()
) -> tuple[str, dict[str, tuple[int, int]]]:
    """Render one turn. Returns (text, {marker_id: (start, end)}) in turn-local offsets."""
    src = expand_neg(template, slots, flip)
    out: list[str] = []
    pos = 0
    length = 0
    stack: list[tuple[str, int]] = []
    spans: dict[str, tuple[int, int]] = {}
    for m in TOKEN.finditer(src):
        lit = src[pos : m.start()]
        out.append(lit)
        length += len(lit)
        pos = m.end()
        if m.group(1):
            stack.append((m.group(1), length))
        elif m.group(0) == "]]":
            if not stack:
                raise ValueError(f"unbalanced ]] in {template!r}")
            open_id, open_at = stack.pop()
            spans[open_id] = (open_at, length)
        else:
            sid, attr = m.group(2), m.group(3)
            if sid not in slots:
                raise KeyError(f"unknown slot {sid} in {template!r}")
            val = slots[sid].attr(attr)
            parts = getattr(slots[sid], "parts", None)
            if parts is not None:
                for name, ps, pe in parts(attr):
                    spans.setdefault(f"{sid}.{name}", (length + ps, length + pe))
            out.append(val)
            length += len(val)
    out.append(src[pos:])
    if stack:
        raise ValueError(f"unclosed marker in {template!r}")
    text = "".join(out)
    if "  " in text or " ," in text or " ." in text or "{" in text or "[[" in text:
        raise ValueError(f"bad rendering {text!r} from {template!r}")
    for mid, (s, e) in spans.items():
        if not text[s:e] or text[s:e] != text[s:e].strip():
            raise ValueError(f"span {mid} has outer spaces in {text!r}")
    return kn.nfc(text), spans
