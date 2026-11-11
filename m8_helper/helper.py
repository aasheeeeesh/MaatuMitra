"""m8 counselling helper: answers ONLY by quoting an approved card, otherwise abstains.

No text is generated. An answer is the stored kn_text + en_text of one card plus its id and
source. Order of checks in Helper.ask: empty -> mode/cards -> safety gate -> similarity.
Kannada here is NOT native-validated (kannada-nlp skill); the retrieval rules are hypotheses.
"""

from __future__ import annotations

import json
import math
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import regex

# "not sure, ask a doctor" (AI-drafted Kannada, not native-validated) + English twin.
ABSTAIN_KN = "ಖಚಿತವಿಲ್ಲ. ದಯವಿಟ್ಟು ವೈದ್ಯರನ್ನು ಅಥವಾ ಆರೋಗ್ಯ ಕಾರ್ಯಕರ್ತರನ್ನು ಕೇಳಿ."
ABSTAIN_EN = "I am not sure. Please ask a doctor or health worker."
DRAFT_LABEL = (
    "DRAFT demo answer: card written by an AI from a WHO page, not clinically approved, "
    "Kannada not native-validated."
)
APPROVED_LABEL = "Approved card (clinician reviewed)."
MODES = ("normal", "demo")

_ZW = regex.compile("[​‌‍﻿]")
_TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
_KN_DIGITS = {ord(c): str(i) for i, c in enumerate("೦೧೨೩೪೫೬೭೮೯")}
_STOP = set(
    "a an the of to in on for and or is are was be do does did how what which who when why can "
    "could should i my me we you your it its this that with at by from as not no if so about "
    "there any have has had".split()
)
# Generic Kannada question/function words only (no medical content words). Chosen after a
# score printout that covered ALL eval rows, so the test split is not pristine for this list.
_KN_STOP = set(
    "ಮತ್ತು ಎಂದರೆ ಎಂದರೇನು ಏನು ಯಾವ ಯಾವುದು ಯಾವುವು ಅಥವಾ ಈ ಆ ಇದು ಅದು ಎಂದು ಹೇಗೆ ಮಾಡಬೇಕು "
    "ಮಾಡುವ ಮಾಡಿ ಬೇಕು ಇರುವ ಇರುವವರು ಇದೆ ಆಗುತ್ತದೆ ಬರುತ್ತದೆ ಎಷ್ಟು ಇಂದು ಯಾವಾಗ ಹೇಳಿ".split()
)


def norm(text: str) -> str:
    """Comparison copy: NFC, no zero-width chars, Kannada digits -> ASCII, casefold."""
    t = unicodedata.normalize("NFC", _ZW.sub("", text)).translate(_KN_DIGITS)
    return t.casefold()


def _is_kn(tok: str) -> bool:
    return any("ಀ" <= ch <= "೿" for ch in tok)


def _stem(tok: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)]
    return tok


def features(text: str) -> Counter:
    """Latin words (light stem, stopwords dropped) + Kannada character 3-grams per word."""
    f: Counter = Counter()
    for tok in _TOKEN.findall(norm(text)):
        if _is_kn(tok):
            if tok in _KN_STOP or len(tok) < 2:
                continue
            padded = f"^{tok}$"
            if len(padded) <= 3:
                f["k:" + padded] += 1
            for i in range(len(padded) - 2):
                f["k:" + padded[i : i + 3]] += 1
        elif tok not in _STOP and not tok.isdigit():
            f["w:" + _stem(tok)] += 1
    return f


# ---------------------------------------------------------------- cards
@dataclass(frozen=True)
class Card:
    id: str
    raw: dict

    @property
    def reviewed(self) -> bool:
        return bool(self.raw.get("clinician_reviewed"))

    @property
    def doc_text(self) -> str:
        return f"{self.raw['topic']}. {self.raw['en_text']} {self.raw['kn_text']}"


def load_cards(directory: Path | str) -> list[Card]:
    cards = []
    for p in sorted(Path(directory).glob("*.json")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        cards.append(Card(raw["id"], raw))
    return cards


# ---------------------------------------------------------------- retrieval
class Retriever(Protocol):
    def search(self, query: str) -> list[tuple[Card, float]]: ...


def _cos(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


class TfidfRetriever:
    """Sublinear TF-IDF over words + Kannada char 3-grams; cosine similarity in [0, 1]."""

    def __init__(self, cards: list[Card]):
        self.cards = cards
        docs = [features(c.doc_text) for c in cards]
        n = len(docs)
        df: Counter = Counter()
        for d in docs:
            df.update(d.keys())
        self.idf = {k: math.log((1 + n) / (1 + v)) + 1.0 for k, v in df.items()}
        self.vecs = [self._vec(d) for d in docs]

    def _vec(self, f: Counter) -> dict[str, float]:
        v = {k: (1 + math.log(c)) * self.idf[k] for k, c in f.items() if k in self.idf}
        n = math.sqrt(sum(x * x for x in v.values()))
        return {k: x / n for k, x in v.items()} if n else {}

    def search(self, query: str) -> list[tuple[Card, float]]:
        q = self._vec(features(query))
        out = [(c, _cos(q, v)) for c, v in zip(self.cards, self.vecs, strict=True)]
        return sorted(out, key=lambda t: -t[1])


class OllamaRetriever:
    """Cosine over local Ollama embeddings (nomic-embed-text, 127.0.0.1 only).

    nomic-embed-text is mainly English; its Kannada quality is UNVERIFIED (measured in eval).
    """

    def __init__(
        self,
        cards: list[Card],
        model: str = "nomic-embed-text",
        url: str = "http://127.0.0.1:11434",
    ):
        self.cards, self.model, self.url = cards, model, url
        self._qcache: dict[str, list[float]] = {}
        self.vecs = self._embed([f"search_document: {c.doc_text}" for c in cards])

    def _embed(self, texts: list[str]) -> list[list[float]]:
        import urllib.request

        req = urllib.request.Request(  # noqa: S310
            self.url + "/api/embed",
            data=json.dumps({"model": self.model, "input": texts}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 (fixed local URL)
            vecs = json.loads(r.read())["embeddings"]
        out = []
        for v in vecs:
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out

    def search(self, query: str) -> list[tuple[Card, float]]:
        if query not in self._qcache:
            self._qcache[query] = self._embed([f"search_query: {query}"])[0]
        q = self._qcache[query]
        out = [
            (c, sum(a * b for a, b in zip(q, v, strict=True)))
            for c, v in zip(self.cards, self.vecs, strict=True)
        ]
        return sorted(out, key=lambda t: -t[1])


# ---------------------------------------------------------------- safety gate
_DRUGS = (
    r"amoxicillin|amoxycillin|azithromycin|ciprofloxacin|cipro|doxycycline|cefixime|ceftriaxone|"
    r"augmentin|penicillin|erythromycin|metronidazole|cotrimoxazole|levofloxacin|paracetamol"
)
_KN_DRUGS = "ಅಮೋಕ್ಸಿಸಿಲಿನ್|ಅಜಿತ್ರೋಮೈಸಿನ್|ಸಿಪ್ರೋ|ಪ್ಯಾರಾಸಿಟಮಾಲ್"
_NB = r"(?<![\p{L}\p{M}])"  # start-of-word boundary that is safe for Kannada
_CHILD = (
    r"\b(child|children|kid|kids|baby|babies|infant|toddler|son|daughter|newborn)\b|"
    + _NB
    + r"(ಮಗು|ಮಕ್ಕಳ|ಮಗುವಿ|ಕಂದ|ಶಿಶು)|\b(magu|makkal|paapu)\b"
)
_MEDWORD = (
    r"\b(give|giving|gave|antibiotic|antibiotics|tablet|tablets|pill|pills|syrup|medicine|"
    r"medicines|medication|drug|drugs|"
    + _DRUGS
    + r")\b|"
    + _NB
    + r"(ಕೊಡ|ಆಂಟಿಬಯಾಟಿಕ್|ಔಷಧ|ಮಾತ್ರೆ|ಸಿರಪ್|"
    + _KN_DRUGS
    + ")"
)
_RULES: list[tuple[str, str]] = [
    (
        "dosing",
        r"\b(dose|doses|dosage|dosing|mg|mcg|ml|milligrams?)\b|\bhow (many|much) "
        r"(tablets?|pills?|capsules?|mg|ml|drops|times|days)\b|\bhow (often|long) .{0,20}\btake\b|"
        r"\bper day\b|\bevery \d+ hours\b|\b(eshtu|yeshtu) (mg|ml|mathre|matre)\b|\bmathre\b|"
        + _NB
        + r"(ಡೋಸ್|ಮಿಲಿಗ್ರಾಂ|ಮಿಲಿ\b|ಎಂ\.?ಜಿ\b|ಎಷ್ಟು (ಮಾತ್ರೆ|ಮಿಲಿ|ಮಿಗ್ರಾಂ))",
    ),
    ("pregnancy", r"pregnan|\bgarbh|" + _NB + "ಗರ್ಭ"),
    (
        "diagnosis",
        r"\bdo (i|we) have\b|\bhave i got\b|\bam i (sick|ill|infected)\b|\bwhat (disease|illness|"
        r"condition|infection) (do|is|have)\b|\bdiagnos|\bis it (a |an )?(infection|pneumonia|"
        r"typhoid|flu|virus|viral|bacterial)\b|"
        r"\b(i have|i've got|i am having|my .{1,20} (has|have))\b.{0,40}\b(fever|cough|cold|pain|"
        r"vomit|rash|diarrhoea|diarrhea|loose)\b|\b(nange|nanage)\b|"
        + _NB
        + r"(ನನಗೆ|ನಂಗೆ|ನನ್ನ (ಮಗ|ಮಗಳ))|"
        + _NB
        + r"ಏನು (ಕಾಯಿಲೆ|ರೋಗ)",
    ),
    (
        "stop_early",
        r"\b(stop|stopping|skip|skipping|miss|quit)\b.{0,25}\b(antibiotic|antibiotics|medicine|"
        r"tablets?|course|dose|treatment)\b|\bfeel(ing)? better\b|\bnillis|"
        + _NB
        + r"(ನಿಲ್ಲಿಸ|ಸರಿಯಾದರೆ|ಗುಣವಾದರೆ)",
    ),
    (
        "request_drug",
        r"\bgive me\b|\bprescribe (me|us|him|her|them)\b|\b(i|we) (need|want) (an? )?(antibiotic|"
        r"medicine|tablet)|\bwhich (antibiotic|medicine|tablet|drug)s? (should|can|do|to)\b|"
        r"\b(should|can) i (take|use|buy|have) .{0,30}\b(" + _DRUGS + r"|antibiotic|antibiotics)\b|"
        r"\btell me .{0,20}\b(antibiotic|medicine|drug)\b|"
        + _NB
        + r"(ಕೊಡಿ|ಕೊಡು\b|ಔಷಧಿ ಹೆಸರು)|ತೆಗೆದುಕೊಳ್ಳಬಹುದೇ",
    ),
    (
        "leftover_share",
        r"\bleft ?overs?\b|\bshare\b.{0,25}\b(tablet|tablets|pill|pills|medicine|antibiotic|"
        r"antibiotics)\b|\b(neighbou?r|friend|relative)\b|" + _NB + r"(ಉಳಿದ|ಬೇರೆಯವರಿಗೆ|ಪಕ್ಕದ ಮನೆ)",
    ),
    (
        "prompt_injection",
        r"\bignore\b.{0,30}\b(instruction|instructions|rules|prompt)\b|\b(forget|disregard|"
        r"override)\b.{0,25}\b(rules|instructions|prompt)\b|\byou are now\b|\bsystem prompt\b|"
        r"\bjailbreak\b|\bact as\b|\bpretend\b|\bdeveloper mode\b|" + _NB + r"(ನಿರ್ಲಕ್ಷಿಸಿ|ಮರೆತುಬಿಡಿ)",
    ),
]
_COMPILED = [(n, regex.compile(p, regex.IGNORECASE)) for n, p in _RULES]
_CHILD_RX = regex.compile(_CHILD, regex.IGNORECASE)
_MED_RX = regex.compile(_MEDWORD, regex.IGNORECASE)


def safety_gate(question: str) -> str | None:
    """Return the name of the unsafe category, or None. Hypothesis rules, not native-validated."""
    q = norm(question)
    for name, rx in _COMPILED:
        if rx.search(q):
            return name
    if _CHILD_RX.search(q) and _MED_RX.search(q):
        return "child_drug"
    return None


# ---------------------------------------------------------------- helper
class Helper:
    def __init__(
        self, cards: list[Card], retriever: Retriever, threshold: float, mode: str = "normal"
    ):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.mode, self.threshold, self.retriever = mode, threshold, retriever
        self.served = {c.id for c in cards if c.reviewed or mode == "demo"}

    def _abstain(self, reason: str, score: float | None = None) -> dict:
        return {
            "abstain": True,
            "reason": reason,
            "card_id": None,
            "source_url": None,
            "score": score,
            "label": "",
            "kn_text": ABSTAIN_KN,
            "en_text": ABSTAIN_EN,
        }

    def ask(self, question: str) -> dict:
        if not question.strip():
            return self._abstain("empty")
        if not self.served:
            return self._abstain("no_approved_cards")
        gate = safety_gate(question)
        if gate:
            return self._abstain(f"unsafe:{gate}")
        ranked = [(c, s) for c, s in self.retriever.search(question) if c.id in self.served]
        card, score = ranked[0]
        if score < self.threshold:
            return self._abstain("low_similarity", score)
        return {
            "abstain": False,
            "reason": "card_match",
            "card_id": card.id,
            "source_url": card.raw["source_url"],
            "score": score,
            "label": APPROVED_LABEL if card.reviewed else DRAFT_LABEL,
            "kn_text": card.raw["kn_text"],
            "en_text": card.raw["en_text"],
        }
