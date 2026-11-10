"""Negation FLAG for the rules pipeline. Reads ONLY the shared table
`.claude/skills/kannada-nlp/negation_table.yaml` (m4_verify must not; it has its own rules).

All patterns are matched against ONE token at a time (comparison form), never as raw substrings.
Every table entry is a hypothesis (status hypothesis_unverified); nothing is native-validated.

Interpretation choices (handoff/decisions.md):
- NEG-S03 (-ದಿದ್ದರೆ "if not") marks the clause as CONDITIONAL; it does not negate a record item
  in that clause (the item is hypothetical, e.g. a follow-up condition).
- NEG-SOFT01 (casual -ಲ್ಲ): if the stem (token minus ಲ್ಲ/ಲ್ಲಾ) is in `verb_stems`, it counts as a
  normal cue; otherwise it still negates but the result is marked `soft` (logged; m4's C8 flags it).
- Clause punctuation (NEG-CL01) skips abbreviation dots (ಎಂ.ಜಿ, ಒ.ಆರ್.ಎಸ್), see textnorm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import regex
import yaml

from m3_extract.textnorm import Token, comparison_form, is_boundary_dot

TABLE_PATH = (
    Path(__file__).resolve().parents[1]
    / ".claude"
    / "skills"
    / "kannada-nlp"
    / "negation_table.yaml"
)
NEGATING_TYPES = ("strong_whole_token", "suffix", "verb_lexicon_suffix")
CONDITIONAL_IDS = {"NEG-S03"}


@dataclass
class NegationTable:
    path: Path
    version: int
    verb_stems: list[str]
    cues: list[tuple[str, str, regex.Pattern]]  # (id, type, compiled)
    soft: list[tuple[str, regex.Pattern, set[str]]]
    compound: list[tuple[str, regex.Pattern, regex.Pattern]]
    punct: regex.Pattern
    splitter_words: list[tuple[str, regex.Pattern]]
    cross_turn: list[tuple[str, regex.Pattern, str]]
    must_not: dict[str, str]  # token -> id


@cache
def load_table(path: str | Path = TABLE_PATH) -> NegationTable:
    path = Path(path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    cues, soft, compound, splitters, cross, must_not = [], [], [], [], [], {}
    punct = None
    for e in doc["entries"]:
        t = e["type"]
        if t in NEGATING_TYPES:
            cues.append((e["id"], t, regex.compile(e["pattern"])))
        elif t == "soft_suffix":
            soft.append((e["id"], regex.compile(e["pattern"]), set(e.get("exclude_tokens", []))))
        elif t == "compound":
            compound.append(
                (e["id"], regex.compile(e["pattern"]), regex.compile(e["then_pattern"]))
            )
        elif t == "clause_splitter_punct":
            punct = regex.compile(e["pattern"])
        elif t == "clause_splitter_word":
            splitters.append((e["id"], regex.compile(e["pattern"])))
        elif t == "cross_turn":
            cross.append((e["id"], regex.compile(e["pattern"]), e["polarity"]))
        elif t == "must_not_trigger":
            must_not[e["token"]] = e["id"]
    if punct is None:
        raise ValueError("negation table has no clause_splitter_punct entry")
    return NegationTable(
        path,
        int(doc["version"]),
        list(doc.get("verb_stems", [])),
        cues,
        soft,
        compound,
        punct,
        splitters,
        cross,
        must_not,
    )


@dataclass
class TokenCue:
    cue_id: str
    token_index: int  # index into the clause's tokens
    soft: bool = False


def token_cues(norm: str, table: NegationTable) -> list[TokenCue]:
    """Cues fired by ONE token (comparison form). Must-not-trigger tokens never fire."""
    if norm in table.must_not:
        return []
    out = [TokenCue(cid, -1) for cid, _t, pat in table.cues if pat.search(norm)]
    if not out:
        for cid, pat, excl in table.soft:
            if norm not in excl and pat.search(norm):
                stem = regex.sub(r"ಲ್ಲಾ?$", "", norm)
                out.append(TokenCue(cid, -1, soft=stem not in table.verb_stems))
    return out


@dataclass
class Clause:
    start: int
    end: int
    tokens: list[Token]
    turn: int
    is_question: bool
    splitter_after: str | None = None  # splitter word or punctuation that ends this clause

    def text(self, full: str) -> str:
        return full[self.start : self.end]


def _is_splitter_word(norm: str, table: NegationTable) -> str | None:
    for cid, pat in table.splitter_words:
        if pat.search(norm):
            return cid
    return None


def split_clauses(text: str, tokens: list[Token], table: NegationTable) -> list[Clause]:
    """Clauses inside each turn: split at table punctuation (except abbreviation dots) and at the
    table's splitter words (the splitter word itself belongs to no clause)."""
    clauses: list[Clause] = []
    cur: list[Token] = []

    def sentence_end_char(pos: int) -> str | None:
        # first sentence-final punctuation (. ? !) after pos in the same line
        j = pos
        while j < len(text) and text[j] != "\n":
            ch = text[j]
            if ch in "?!" or (ch == "." and is_boundary_dot(text, j)):
                return ch
            j += 1
        return None

    def flush(after: str | None) -> None:
        nonlocal cur
        if cur:
            q = sentence_end_char(cur[-1].end) == "?"
            clauses.append(Clause(cur[0].start, cur[-1].end, cur, cur[0].turn, q, after))
        cur = []

    prev_end = 0
    for t in tokens:
        gap = text[prev_end : t.start] if cur else ""
        boundary = None
        for k, ch in enumerate(gap):
            if table.punct.match(ch) and (ch != "." or is_boundary_dot(text, prev_end + k)):
                boundary = ch
                break
        if cur and (boundary is not None or t.turn != cur[-1].turn):
            flush(boundary if boundary is not None else "\n")
        sw = _is_splitter_word(t.norm, table)
        if sw:
            flush(sw)
        else:
            cur.append(t)
        prev_end = t.end
    flush(None)
    return clauses


@dataclass
class NegResult:
    negated: bool
    conditional: bool
    soft: bool
    cue_ids: list[str] = field(default_factory=list)
    cue_tokens: list[Token] = field(default_factory=list)


def clause_negation(clause: Clause, table: NegationTable) -> NegResult:
    ids: list[str] = []
    toks: list[Token] = []
    soft = False
    negating = False
    conditional = False
    norms = [t.norm for t in clause.tokens]
    for t in clause.tokens:
        for c in token_cues(t.norm, table):
            ids.append(c.cue_id)
            if c.cue_id in CONDITIONAL_IDS:
                conditional = True
                continue
            toks.append(t)
            negating = True
            soft = soft or c.soft
    for cid, first, then in table.compound:
        for i, n in enumerate(norms):
            if first.search(n) and any(then.search(m) for m in norms[i + 1 :]):
                ids.append(cid)
    return NegResult(negating, conditional, soft, ids, toks)


def cross_turn_answer(turn_tokens: list[Token], table: NegationTable) -> str | None:
    """'negative' / 'affirmative' if the turn's ONLY token is a bare answer (NEG-X01 / NEG-X02)."""
    if len(turn_tokens) != 1:
        return None
    norm = comparison_form(turn_tokens[0].text)
    for _cid, pat, polarity in table.cross_turn:
        if pat.search(norm):
            return polarity
    return None
