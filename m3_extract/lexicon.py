"""Drug finder over the shared lexicon (data/lexicon/drugs.csv; fixtures/lexicon/drugs_fixture.csv
in mock mode). Match types, logged for every hit:
  exact   generic_en or kn_primary
  variant kn_variants or roman_variants
  edit1   Levenshtein distance 1 on a Latin token of length >= 6 against a single-token Latin
          name, accepted only if exactly ONE drug is that close (else logged as ambiguous, no match)
Longest token-sequence match wins (iron folic acid, oral rehydration salts, ORS; ORS short-vowel ASR variants come from data/asr_variants.yaml).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import regex
import yaml

from m3_extract.textnorm import Token, comparison_form, tokenize

LATIN = regex.compile(r"^[a-z]+$")
MIN_FUZZY_LEN = 6


def levenshtein(a: str, b: str, cap: int = 2) -> int:
    if abs(len(a) - len(b)) >= cap:
        return cap
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return min(prev[-1], cap)


@dataclass(frozen=True)
class DrugMatch:
    drug: str
    start_tok: int
    end_tok: int  # exclusive
    match_type: str  # exact | variant | edit1
    form: str


@dataclass
class DrugLexicon:
    path: Path
    forms: dict[tuple[str, ...], tuple[str, str]]  # token tuple -> (generic_en, match_type)
    latin_single: dict[str, str]  # latin single-token form -> generic_en
    max_len: int
    generics: list[str]

    def find(self, tokens: list[Token]) -> list[DrugMatch]:
        out: list[DrugMatch] = []
        i = 0
        while i < len(tokens):
            hit = None
            for n in range(min(self.max_len, len(tokens) - i), 0, -1):
                # a multi-token name must stay inside one turn
                if tokens[i + n - 1].turn != tokens[i].turn:
                    continue
                key = tuple(t.norm for t in tokens[i : i + n])
                if key in self.forms:
                    drug, mt = self.forms[key]
                    hit = DrugMatch(drug, i, i + n, mt, " ".join(key))
                    break
            if hit is None:
                hit = self._fuzzy(tokens, i)
            if hit is not None:
                out.append(hit)
                i = hit.end_tok
            else:
                i += 1
        return out

    def _fuzzy(self, tokens: list[Token], i: int) -> DrugMatch | None:
        w = tokens[i].norm
        if len(w) < MIN_FUZZY_LEN or not LATIN.match(w):
            return None
        close = {
            d
            for f, d in self.latin_single.items()
            if len(f) >= MIN_FUZZY_LEN and levenshtein(w, f) <= 1
        }
        if len(close) == 1:
            return DrugMatch(close.pop(), i, i + 1, "edit1", w)
        return None


def _key(s: str) -> tuple[str, ...]:
    return tuple(t.norm for t in tokenize(s))


ASR_VARIANTS_PATH = Path(__file__).resolve().parent / "data" / "asr_variants.yaml"


def load_lexicon(
    path: str | Path, extra_variants: str | Path | None = ASR_VARIANTS_PATH
) -> DrugLexicon:
    path = Path(path)
    forms: dict[tuple[str, ...], tuple[str, str]] = {}
    latin_single: dict[str, str] = {}
    generics = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            g = row["generic_en"].strip()
            generics.append(g)
            entries = [(g, "exact"), (row["kn_primary"], "exact")]
            entries += [(v, "variant") for v in row["kn_variants"].split("|") if v.strip()]
            entries += [(v, "variant") for v in row["roman_variants"].split("|") if v.strip()]
            for form, mt in entries:
                k = _key(form)
                if not k:
                    continue
                if k in forms and forms[k][0] != g:
                    raise ValueError(f"lexicon form {form!r} maps to two drugs")
                if k not in forms or (mt == "exact" and forms[k][1] != "exact"):
                    forms[k] = (g, mt)
                if len(k) == 1 and LATIN.match(k[0]):
                    latin_single[k[0]] = g
    extra = {}
    if extra_variants is not None and Path(extra_variants).exists():
        extra = yaml.safe_load(Path(extra_variants).read_text(encoding="utf-8")).get("variants", {})
    for g, vs in extra.items():
        if g not in generics:  # fixture lexicon in mock mode may lack the drug: skip silently
            continue
        for form in vs:
            k = _key(form)
            if k and k not in forms:
                forms[k] = (g, "variant")
    return DrugLexicon(path, forms, latin_single, max(len(k) for k in forms), generics)


def comparison_key(s: str) -> str:
    return comparison_form(s)
