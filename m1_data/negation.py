"""Matcher for the SHARED negation table (.claude/skills/kannada-nlp/negation_table.yaml).

m1_data uses it only to (1) self-check generated data (every cue present was declared by
the template, every declared cue really fires) and (2) count coverage. It follows the
table's own instructions: comparison copy, tokenise with [\\p{L}\\p{M}\\p{N}]+, match one
token at a time, never raw substrings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import regex
import yaml

from m1_data import kn
from m1_data.config import NEGATION_TABLE

CUE_TYPES = {"strong_whole_token", "suffix", "verb_lexicon_suffix", "soft_suffix"}
# Ids that are not negation cues by themselves (clause splitters, affirmative answer).
NON_CUE_IDS = {"NEG-CL01", "NEG-CL02", "NEG-CL03", "NEG-CL04", "NEG-CL05", "NEG-X02"}
# ಇದೆ is in the table's must-not-trigger list but occurs in most sentences; it is counted in
# coverage but not put in tags.trap_tokens (that would make the tag meaningless).
TRAP_TAG_EXCLUDE = {"ಇದೆ"}


@dataclass
class Table:
    entries: list[dict]
    version: int
    cues: list[tuple[str, str, regex.Pattern, set]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for e in self.entries:
            if e["type"] in CUE_TYPES:
                self.cues.append(
                    (
                        e["id"],
                        e["type"],
                        regex.compile(e["pattern"]),
                        set(e.get("exclude_tokens", [])),
                    )
                )
        self.punct = regex.compile(self._one("clause_splitter_punct")["pattern"])
        self.split_words = {
            e["id"]: regex.compile(e["pattern"])
            for e in self.entries
            if e["type"] == "clause_splitter_word"
        }
        comp = self._one("compound")
        self.compound = (
            comp["id"],
            regex.compile(comp["pattern"]),
            regex.compile(comp["then_pattern"]),
        )
        self.xturn = {
            e["id"]: regex.compile(e["pattern"]) for e in self.entries if e["type"] == "cross_turn"
        }
        self.traps = [e["token"] for e in self.entries if e["type"] == "must_not_trigger"]

    def _one(self, typ: str) -> dict:
        (e,) = [e for e in self.entries if e["type"] == typ]
        return e

    def token_cues(self, tok: str) -> set[str]:
        out = set()
        for pid, _typ, pat, excl in self.cues:
            if tok in excl:
                continue
            if pat.search(tok):
                out.add(pid)
        return out

    def clauses(self, turn: str) -> list[list[str]]:
        """Split at punctuation, then at clause-splitter words; return token lists."""
        out = []
        for chunk in self.punct.split(kn.compare_copy(turn)):
            cur: list[str] = []
            for t, _, _ in kn.tokens(chunk):
                if any(p.match(t) for p in self.split_words.values()):
                    if cur:
                        out.append(cur)
                    cur = []
                else:
                    cur.append(t)
            if cur:
                out.append(cur)
        return out

    def detect_turn(self, turn: str) -> set[str]:
        found: set[str] = set()
        toks = [t for t, _, _ in kn.tokens(kn.compare_copy(turn))]
        for t in toks:
            found |= self.token_cues(t)
        cid, first, then = self.compound
        for cl in self.clauses(turn):
            for i, t in enumerate(cl):
                if first.match(t) and any(then.match(u) for u in cl[i + 1 :]):
                    found.add(cid)
        if found:  # clause splitters only matter in a turn that has a cue
            if len(self.clauses_by_punct(turn)) >= 2:
                found.add("NEG-CL01")
            for pid, p in self.split_words.items():
                if any(p.match(t) for t in toks):
                    found.add(pid)
        return found

    def clauses_by_punct(self, turn: str) -> list[str]:
        return [c for c in self.punct.split(kn.compare_copy(turn)) if kn.tokens(c)]

    def detect_conversation(self, turns: list[str]) -> set[str]:
        found: set[str] = set()
        for i, turn in enumerate(turns):
            found |= self.detect_turn(turn)
            toks = [t for t, _, _ in kn.tokens(kn.compare_copy(turn))]
            if i > 0 and len(toks) == 1:
                for pid, p in self.xturn.items():
                    if p.match(toks[0]):
                        found.add(pid)
        return found


@cache
def load_table(path: Path = NEGATION_TABLE) -> Table:
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Table(entries=d["entries"], version=d["version"])


def trap_tokens_in(text: str) -> list[str]:
    """Must-not-trigger tokens present in text, in order of first appearance (no ಇದೆ)."""
    traps = set(load_table().traps) - TRAP_TAG_EXCLUDE
    out: list[str] = []
    for t, _, _ in kn.tokens(kn.compare_copy(text)):
        if t in traps and t not in out:
            out.append(t)
    return out


def all_trap_tokens_in(text: str) -> set[str]:
    traps = set(load_table().traps)
    return {t for t, _, _ in kn.tokens(kn.compare_copy(text)) if t in traps}
