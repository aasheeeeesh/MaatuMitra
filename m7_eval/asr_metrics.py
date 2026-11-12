"""ASR metrics (docs/metrics.md section 1): CER (primary), grapheme CER, WER (secondary),
critical-term recall per class (drug / number / unit / negation).

Independent re-implementation for m7 (m7 may not import m2_asr). CER is computed on the
comparison copy (textnorm.compare_norm). `cer_nopunct` additionally removes punctuation and is
reported as a SECONDARY column only (ASR output usually has no punctuation; gold text does).
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import regex
import yaml

from m7_eval import textnorm as tn

CLASSES = ("drug", "number", "unit", "negation")


def levenshtein(a: Sequence, b: Sequence) -> int:
    """Edit distance (insert, delete, substitute all cost 1)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def utterance_metrics(ref: str, hyp: str) -> dict:
    r, h = tn.compare_norm(ref), tn.compare_norm(hyp)
    rp, hp = tn.strip_punct(r), tn.strip_punct(h)
    rg, hg = tn.graphemes(r), tn.graphemes(h)
    rw, hw = r.split(), h.split()
    ce, ge, we, cpe = (
        levenshtein(r, h),
        levenshtein(rg, hg),
        levenshtein(rw, hw),
        levenshtein(rp, hp),
    )

    def div(e: int, n: int) -> float | None:
        return e / n if n else None

    return {
        "ref_chars": len(r),
        "char_edits": ce,
        "cer": div(ce, len(r)),
        "ref_graphemes": len(rg),
        "grapheme_edits": ge,
        "gcer": div(ge, len(rg)),
        "ref_words": len(rw),
        "word_edits": we,
        "wer": div(we, len(rw)),
        "ref_chars_nopunct": len(rp),
        "cer_nopunct": div(cpe, len(rp)),
    }


@dataclass
class CriticalTerms:
    """drugs: [(drug_id, token sequence)]; units: token sequences; negation_patterns are
    applied to ONE token at a time (never raw substrings)."""

    drugs: list[tuple[str, list[str]]]
    number_words: list[str]
    units: list[list[str]]
    negation_patterns: list[str]
    _neg: list = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.drugs = [(d, [tn.compare_norm(t) for t in seq]) for d, seq in self.drugs if seq]
        self.drugs.sort(key=lambda x: -len(x[1]))  # longest match first
        self.units = sorted(([tn.compare_norm(t) for t in u] for u in self.units), key=len)[::-1]
        self.number_words = [tn.compare_norm(w) for w in self.number_words]
        self._neg = [regex.compile(p) for p in self.negation_patterns]

    def extract(self, text: str) -> dict[str, list[str]]:
        toks = tn.tokens(text)
        out: dict[str, list[str]] = {c: [] for c in CLASSES}
        i = 0
        while i < len(toks):
            hit = next(
                ((d, len(s)) for d, s in self.drugs if toks[i : i + len(s)] == s), None
            ) or next(
                ((" ".join(u), len(u)) for u in self.units if toks[i : i + len(u)] == u), None
            )
            if hit is not None:
                is_drug = any(hit[0] == d for d, _ in self.drugs)
                out["drug" if is_drug else "unit"].append(hit[0])
                i += hit[1]
                continue
            t = toks[i]
            if t.isdigit() or t in self.number_words:
                out["number"].append(t)
            elif any(p.search(t) for p in self._neg):
                out["negation"].append(t)
            i += 1
        return out

    def recall(self, ref: str, hyp: str) -> dict[str, tuple[int, int]]:
        """Per class (hits, n): a reference term is found if the hypothesis has it (count-aware)."""
        r, h = self.extract(ref), self.extract(hyp)
        res = {}
        for c in CLASSES:
            rc, hc = Counter(r[c]), Counter(h[c])
            res[c] = (sum(min(v, hc[k]) for k, v in rc.items()), sum(rc.values()))
        return res


def load_terms(root: Path, config_path: Path) -> CriticalTerms:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    drugs: list[tuple[str, list[str]]] = []
    lex = root / "data" / "lexicon" / "drugs.csv"
    if lex.exists():
        with lex.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                names = [row["generic_en"], row["kn_primary"]]
                names += row["kn_variants"].split("|") + row["roman_variants"].split("|")
                for nm in names:
                    if nm.strip() and not nm.strip().isdigit():
                        drugs.append((row["generic_en"], tn.tokens(nm)))
    neg: list[str] = []
    table = root / ".claude" / "skills" / "kannada-nlp" / "negation_table.yaml"
    if table.exists():
        t = yaml.safe_load(table.read_text(encoding="utf-8"))
        neg = [e["pattern"] for e in t["entries"] if e["type"] in ("strong_whole_token", "suffix")]
    return CriticalTerms(drugs, cfg["number_words"], cfg["units"], neg)
