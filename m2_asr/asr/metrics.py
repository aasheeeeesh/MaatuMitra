r"""ASR metrics (PROJECT_BRIEF 6.3, docs/metrics.md section 1). Own implementation, no model needed.

Comparison copy (kannada-nlp skill section 1): strip BOM/ZWSP, NFC, drop ZWJ/ZWNJ, Kannada digits
-> ASCII, casefold, collapse whitespace. Stored text is never changed.
CER = Levenshtein on code points / reference code points (punctuation kept; `cer_nopunct`
is a secondary column). Grapheme CER uses regex \X. WER uses whitespace tokens (secondary:
Kannada is agglutinative). Critical-term recall is count-aware per class.
"""

from __future__ import annotations

import math
import random
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

import regex

CLASSES = ("drug", "number", "unit", "negation")
Z95 = 1.959964
BOOT_SEED = 20261109
BOOT_N = 1000

_TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
_GRAPHEME = regex.compile(r"\X")
_PUNCT = regex.compile(r"[\p{P}\p{S}]+")
_LATIN = regex.compile(r"[A-Za-z]")
_KN_DIGITS = {0x0CE6 + i: str(i) for i in range(10)}
_DROP = {0xFEFF: None, 0x200B: None, 0x200C: None, 0x200D: None}


def compare_norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s.translate({0xFEFF: None, 0x200B: None}))
    s = s.translate(_DROP).translate(_KN_DIGITS).casefold()
    return " ".join(s.split())


def strip_punct(s: str) -> str:
    return " ".join(_PUNCT.sub(" ", s).split())


def tokens(s: str) -> list[str]:
    return _TOKEN.findall(compare_norm(s))


def graphemes(s: str) -> list[str]:
    return _GRAPHEME.findall(s)


def is_code_switched(ref: str) -> bool:
    """A reference counts as code-switched when it contains any Latin letter (English drug names,
    'mg'...). Simple proxy, not native-validated."""
    return bool(_LATIN.search(ref))


def levenshtein(a: Sequence, b: Sequence) -> int:
    """Edit distance, insert/delete/substitute all cost 1."""
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
    r, h = compare_norm(ref), compare_norm(hyp)
    rp, hp = strip_punct(r), strip_punct(h)
    rg, hg = graphemes(r), graphemes(h)
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
    """drugs: [(drug_id, token sequence)]; units: token sequences; negation_patterns are regexes
    applied to ONE token at a time (never to raw substrings of the sentence)."""

    drugs: list[tuple[str, list[str]]]
    number_words: list[str]
    units: list[list[str]]
    negation_patterns: list[str]
    _neg: list = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.drugs = [(d, [compare_norm(t) for t in seq]) for d, seq in self.drugs if seq]
        self.drugs.sort(key=lambda x: -len(x[1]))  # longest match first
        self.units = sorted(([compare_norm(t) for t in u] for u in self.units), key=len)[::-1]
        self.number_words = [compare_norm(w) for w in self.number_words]
        self._neg = [regex.compile(p) for p in self.negation_patterns]

    def extract(self, text: str) -> dict[str, list[str]]:
        toks = tokens(text)
        out: dict[str, list[str]] = {c: [] for c in CLASSES}
        i = 0
        while i < len(toks):
            d = next(((n, len(s)) for n, s in self.drugs if toks[i : i + len(s)] == s), None)
            if d:
                out["drug"].append(d[0])
                i += d[1]
                continue
            u = next((u for u in self.units if toks[i : i + len(u)] == u), None)
            if u:
                out["unit"].append(" ".join(u))
                i += len(u)
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


def wilson(k: int, n: int, z: float = Z95) -> tuple[float | None, float | None]:
    """Wilson score interval: centre = (p + z^2/2n)/(1 + z^2/n),
    half = z*sqrt(p(1-p)/n + z^2/4n^2)/(1 + z^2/n)."""
    if n <= 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def percentile(xs: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (same as numpy default)."""
    s = sorted(xs)
    if not s:
        return math.nan
    pos = (len(s) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def rtf(latency_ms: float | None, duration_s: float | None) -> float | None:
    """Real-time factor = processing time / audio duration."""
    if latency_ms is None or not duration_s:
        return None
    return latency_ms / 1000 / duration_s


def bootstrap_ci(
    xs: Sequence[float], seed: int = BOOT_SEED, n_boot: int = BOOT_N
) -> tuple[float, float]:
    """Percentile bootstrap 95% CI of the mean (1000 resamples, fixed seed)."""
    if not xs:
        return math.nan, math.nan
    rng = random.Random(seed)  # noqa: S311 (statistics, not security)
    n = len(xs)
    means = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return percentile(means, 2.5), percentile(means, 97.5)
