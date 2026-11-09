"""The verifier's OWN Kannada negation rules (hand-coded; independent of m3 and of the shared
.claude/skills/kannada-nlp/negation_table.yaml, which this module never reads).

Every rule is a HYPOTHESIS written by an AI agent from PROJECT_BRIEF AGENT 5 plus general
grammar knowledge; none of it is native-validated. See m4_verify/negation_audit.md for a test
on real Kannada text and m4_verify/handoff/decisions.md for why each rule exists.

Rule ids (kept stable for reports):
  W-*   whole-token cues          ಇಲ್ಲ ಇಲ್ಲಾ ಅಲ್ಲ ಬೇಡ ಬೇಡಿ ಬಾರದು ಕೂಡದು, negative questions ಇಲ್ಲವಾ...
  EN-NOT  English cue in code-switched speech (no / not / never)
  S-*   token-final suffixes       -ಿಲ್ಲ, -ುದಿಲ್ಲ, C+ದಿದ್ದರೆ, C+ದಿದ್ರೆ, fused -ಬಾರದು -ಕೂಡದು C+ಬೇಡ(ಿ)
  V-DE  stem+ದೆ/ದೇ "without", ONLY for stems in VERB_STEMS
  V-LLA stem+ಲ್ಲ casual negative, stem in VERB_STEMS (strong)
  SOFT-LLA  C+ಲ್ಲ on an unknown stem: counted as negation but marked soft (C8 flags it)
  C-YAAVUDE ಯಾವುದೇ ... ಇಲ್ಲ "not any" (relabels the ಇಲ್ಲ cue; counts once)
Clause scope: split at ? ! ; । and at . , when followed by whitespace/end, and at the words
ಆದರೆ ಮತ್ತು ಹಾಗೂ ಆದ್ದರಿಂದ. Turns are the lines of the transcript text ("\\n").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import regex

from m4_verify.textnorm import Token, tokens

C = "[ಕ-ಹ]"  # a Kannada consonant letter (inherent vowel), no vowel sign after it

STRONG_WHOLE = {
    "ಇಲ್ಲ": "W-ILLA",
    "ಇಲ್ಲಾ": "W-ILLAA",
    "ಅಲ್ಲ": "W-ALLA",
    "ಬೇಡ": "W-BEDA",
    "ಬೇಡಿ": "W-BEDI",
    "ಬಾರದು": "W-BAARADU",
    "ಕೂಡದು": "W-KOODADU",
    # negative questions ("isn't there?"): negation, and ambiguous when answered by ಹೌದು
    # ಇಲ್ಲವೇ / ಇಲ್ಲವೆ are NOT listed: the audit on real text showed they usually mean "or".
    # _split_clauses reads them as a negative question only when "?" follows directly.
    "ಇಲ್ಲವಾ": "W-NEGQ",
    "ಇಲ್ವಾ": "W-NEGQ",
    "ಇಲ್ವ": "W-NEGQ",
    "ಇಲ್ಲವ": "W-NEGQ",
    # English inside code-switched Kannada
    "no": "EN-NOT",
    "not": "EN-NOT",
    "never": "EN-NOT",
}
NEG_QUESTION_RULES = {"W-NEGQ"}
SUFFIX_RULES: list[tuple[str, regex.Pattern]] = [
    ("S-UDILLA", regex.compile(r"ುದಿಲ್ಲಾ?$")),
    ("S-ILLA", regex.compile(r"ಿಲ್ಲಾ?$")),
    ("S-DIDDARE", regex.compile(rf"{C}ದಿದ್ದರೆ$")),
    ("S-DIDRE", regex.compile(rf"{C}ದಿದ್ರೆ$")),
    ("S-BAARADU", regex.compile(r".ಬಾರದು$")),
    ("S-KOODADU", regex.compile(r".ಕೂಡದು$")),
    ("S-BEDI", regex.compile(rf"{C}ಬೇಡಿ$")),
    ("S-BEDA", regex.compile(rf"{C}ಬೇಡ$")),
    # added after the negation audit (negation_audit.md):
    ("S-VALLA", regex.compile(r"ವಲ್ಲಾ?$")),  # noun + ಅಲ್ಲ fused: ರೋಗವಲ್ಲ, ಸಾಮಾನ್ಯವಲ್ಲ
    ("S-DIRU", regex.compile(rf"{C}ದಿರುವುದ[ುೂ]$")),  # negative verbal noun: ಬಾರದಿರುವುದು
    ("S-ILLA-FUSED", regex.compile(r"ಿಲ್ಲ[ದವ]")),  # -ಿಲ್ಲ + more suffixes: ಮಾರ್ಗವಿಲ್ಲದೆ, ...ವಿಲ್ಲವಾದ್ದರಿಂದ
    ("S-DANTE", regex.compile(rf"{C}ದಂತೆ$")),  # "so that ... not": ಬರದಂತೆ (trap: ಹೇಳಿದಂತೆ)
    ("V-AAGADE", regex.compile(r"ಾಗದ[ೆೇ]$")),  # fused ಆಗ + ದೆ: ಸಾಧ್ಯವಾಗದೆ, ಕಡಿಮೆಯಾಗದೆ
    ("V-ISADE", regex.compile(r"ಿಸದ[ೆೇ]$")),  # causative stem + ದೆ: ಸೇವಿಸದೆ, ಗಣಿಸದೆ
]
NOT_SUFFIX_CUES = {"ಮಾತ್ರವಲ್ಲ"}  # "not only" (additive), audit trap
SOFT_WHOLE = {"ಇಲ್ಲದ", "ಇಲ್ಲದೆ", "ಇಲ್ಲದೇ"}  # absence / "without": scope unclear -> soft
OR_WORDS = {"ಇಲ್ಲವೇ", "ಇಲ್ಲವೆ"}  # "or" in running text; negative question only before "?"
# Verb stems (form before -ದೆ / -ಲ್ಲ). AI-written, UNVERIFIED. ಮರೆಯ is deliberately absent:
# ಮರೆಯದೆ "without forgetting" is a positive instruction.
VERB_STEMS = {
    "ಮುಗಿಸ", "ತೆಗೆದುಕೊಳ್ಳ", "ತಗೊಳ್ಳ", "ಕುಡಿಯ", "ತಿನ್ನ", "ಕೊಡ", "ಬರ", "ಹೋಗ", "ಮಾಡ",
    "ನಿಲ್ಲಿಸ", "ಹಾಕ", "ಆಗ", "ನೋಡ", "ಹೇಳ", "ಕೇಳ", "ಬಳಸ", "ಸೇವಿಸ", "ಕುಡಿಸ",
}  # fmt: skip
SOFT_RE = regex.compile(rf"{C}ಲ್ಲಾ?$")
NOT_CUES = {"ಎಲ್ಲ", "ಎಲ್ಲಾ", "ಅಲ್ಲ"}  # ಅಲ್ಲ handled as W-ALLA before the soft rule
CLAUSE_WORDS = {"ಆದರೆ", "ಮತ್ತು", "ಹಾಗೂ", "ಆದ್ದರಿಂದ"}
COORD_WORDS = {"ಮತ್ತು", "ಹಾಗೂ", "ಇಲ್ಲವೇ", "ಇಲ್ಲವೆ"}
ALWAYS_BOUNDARY = set("?!;।॥")
SPACE_BOUNDARY = set(".,:")
ANSWER_NEG = {"ಇಲ್ಲ", "ಇಲ್ಲಾ"}
ANSWER_POS = {"ಹೌದು"}
YAAVUDE = "ಯಾವುದೇ"


@dataclass(frozen=True)
class Cue:
    rule_id: str
    token: str
    start: int
    end: int
    soft: bool = False


def classify_token(tok: str) -> Cue | None:
    """Return the negation cue for ONE comparison-form token, or None. Never substring-matches."""
    if tok in STRONG_WHOLE:
        return Cue(STRONG_WHOLE[tok], tok, 0, 0)
    if tok in SOFT_WHOLE:
        return Cue("SOFT-ILLADA", tok, 0, 0, soft=True)
    if tok in NOT_SUFFIX_CUES:
        return None
    for suf in ("ದೆ", "ದೇ"):
        if tok.endswith(suf) and tok[: -len(suf)] in VERB_STEMS:
            return Cue("V-DE", tok, 0, 0)
    for rid, rx in SUFFIX_RULES:
        if rx.search(tok):
            return Cue(rid, tok, 0, 0)
    if tok not in NOT_CUES and SOFT_RE.search(tok):
        stem = tok[:-4] if tok.endswith("ಲ್ಲಾ") else tok[:-3]
        if stem in VERB_STEMS:
            return Cue("V-LLA", tok, 0, 0)
        return Cue("SOFT-LLA", tok, 0, 0, soft=True)
    return None


@dataclass
class Clause:
    idx: int
    turn: int
    toks: list[Token]
    terminator: str = ""  # punctuation that ended the clause ("" if none)
    joiner: str | None = None  # what separates it from the NEXT clause in the same turn
    cues: list[Cue] = field(default_factory=list)
    negated: bool = False
    inherited: bool = False
    ambiguities: list[str] = field(default_factory=list)

    @property
    def start(self) -> int:
        return self.toks[0].start

    @property
    def end(self) -> int:
        return self.toks[-1].end

    @property
    def is_question(self) -> bool:
        return "?" in self.terminator

    @property
    def soft(self) -> bool:
        return any(c.soft for c in self.cues)

    @property
    def neg_question(self) -> bool:
        return any(c.rule_id in NEG_QUESTION_RULES for c in self.cues) or (
            self.is_question and self.negated
        )


@dataclass
class Analysis:
    text: str
    clauses: list[Clause]
    turn_spans: list[tuple[int, int]]
    # clause idx -> (polarity "negative"/"affirmative", negated, ambiguity list)
    cross: dict[int, tuple[str, bool, list[str]]] = field(default_factory=dict)
    unresolved_answers: list[str] = field(default_factory=list)
    unanswered_questions: set[int] = field(default_factory=set)


@dataclass
class Polarity:
    negated: bool | None
    cues: list[Cue]
    soft: bool
    ambiguities: list[str]
    cross_turn: str | None
    clause_ids: list[int]


def _split_clauses(
    text: str, entity_tokens: frozenset[str]
) -> tuple[list[Clause], list[tuple[int, int]]]:
    clauses: list[Clause] = []
    turn_spans = []
    offset = 0
    for ti, line in enumerate(text.split("\n")):
        turn_spans.append((offset, offset + len(line)))
        toks = [Token(t.text, t.start + offset, t.end + offset) for t in tokens(line)]
        cur: list[Token] = []
        prev_end = offset
        first_in_turn = len(clauses)

        def close(term: str, joiner: str | None, _ti=ti, _first=first_in_turn):
            nonlocal cur
            if cur:
                clauses.append(Clause(len(clauses), _ti, cur, term, joiner))
            elif clauses and len(clauses) > _first and term:
                clauses[-1].terminator += term
            cur = []

        for t in toks:
            gap = text[prev_end : t.start]
            punct = [ch for ch in gap if ch in ALWAYS_BOUNDARY or ch in SPACE_BOUNDARY]
            boundary = any(ch in ALWAYS_BOUNDARY for ch in gap) or (
                any(ch in SPACE_BOUNDARY for ch in gap) and any(ch.isspace() for ch in gap)
            )
            if boundary and cur:
                close("".join(punct), "punct:" + "".join(punct))
            if t.text in OR_WORDS:
                after = text[t.end : offset + len(line)].lstrip(" ")
                if after.startswith("?"):
                    cur.append(t)
                    prev_end = t.end
                    continue
                close("", "word:" + t.text)
                prev_end = t.end
                continue
            if t.text in CLAUSE_WORDS:
                close("", "word:" + t.text)
                prev_end = t.end
                continue
            cur.append(t)
            prev_end = t.end
        tail = text[prev_end : offset + len(line)]
        close("".join(ch for ch in tail if ch in ALWAYS_BOUNDARY or ch in SPACE_BOUNDARY), "turn")
        if len(clauses) > first_in_turn:
            clauses[-1].joiner = "turn"
        offset += len(line) + 1

    for c in clauses:
        found: list[Cue] = []
        toks_text = [t.text for t in c.toks]
        for k, t in enumerate(c.toks):
            cue = classify_token(t.text)
            if cue is None and t.text in OR_WORDS:  # kept in a clause only before "?"
                cue = Cue("W-NEGQ", t.text, 0, 0)
            if cue is None:
                continue
            rid = cue.rule_id
            if rid in ("W-ILLA", "W-ILLAA") and YAAVUDE in toks_text[:k]:
                rid = "C-YAAVUDE"
            found.append(Cue(rid, t.text, t.start, t.end, cue.soft))
        c.cues = found
        c.negated = bool(found)
        if len(found) >= 2:
            c.ambiguities.append(
                "two negation cues in one clause ("
                + ", ".join(f"{q.token}:{q.rule_id}" for q in found)
                + "): double negation or emphasis?"
            )
        for q in found:
            if q.soft:
                c.ambiguities.append(
                    f"soft cue '{q.token}' (casual -ಲ್ಲ on a stem not in the verb list); read as negation"
                )

    # coordination: a bare entity clause before ಮತ್ತು/ಹಾಗೂ/comma inherits the next clause's negation
    for i in range(len(clauses) - 2, -1, -1):
        c, nxt = clauses[i], clauses[i + 1]
        if c.turn != nxt.turn or c.cues or not nxt.negated:
            continue
        j = c.joiner or ""
        coord = (j.startswith("word:") and j[5:] in COORD_WORDS) or (
            j.startswith("punct:") and "," in j and "." not in j
        )
        if coord and all(t.text in entity_tokens or t.text[0].isdigit() for t in c.toks):
            c.negated = True
            c.inherited = True
            c.ambiguities.append(
                "negation may scope over coordinated items (bare item before ಮತ್ತು/ಹಾಗೂ/comma "
                "followed by a negated clause); read as negated, confirm"
            )
    return clauses, turn_spans


def _cross_turn(an: Analysis) -> None:
    by_turn: dict[int, list[Clause]] = {}
    for c in an.clauses:
        by_turn.setdefault(c.turn, []).append(c)
    n_turns = len(an.turn_spans)
    for ti in range(n_turns):
        cl = by_turn.get(ti, [])
        if not cl:
            continue
        first = cl[0]
        ans = None
        if len(first.toks) == 1:
            if first.toks[0].text in ANSWER_NEG:
                ans = "negative"
            elif first.toks[0].text in ANSWER_POS:
                ans = "affirmative"
        if ans is None:
            continue
        prev_q = [c for c in by_turn.get(ti - 1, []) if c.is_question] if ti > 0 else []
        if not prev_q:
            if ans == "negative":
                where = "it is the first turn" if ti == 0 else f"turn {ti - 1} asks no question"
                an.unresolved_answers.append(
                    f"bare '{first.toks[0].text}' in turn {ti} has no resolvable question ({where})"
                )
            continue
        for q in prev_q:
            amb: list[str] = []
            if len(prev_q) > 1:
                amb.append(
                    f"bare answer in turn {ti} follows more than one question in turn {ti - 1}"
                )
            if q.neg_question:
                amb.append(
                    f"'{first.toks[0].text}' answers a negative question in turn {ti - 1}: polarity unclear"
                )
            negated = True if ans == "negative" else q.negated
            an.cross[q.idx] = (ans, negated, amb)
    # questions with no bare answer in the next turn
    for c in an.clauses:
        if c.is_question and c.idx not in an.cross:
            an.unanswered_questions.add(c.idx)


@lru_cache(maxsize=1)
def _default_entity_tokens() -> frozenset[str]:
    from m4_verify.config import default_lexicon_path
    from m4_verify.lexicon import NP_FILLERS, UNIT_TOKENS, load_lexicon, symptom_tokens

    lex = load_lexicon(default_lexicon_path())
    return frozenset(lex.entity_tokens() | symptom_tokens() | UNIT_TOKENS | NP_FILLERS)


def analyze(text: str, entity_tokens: frozenset[str] | None = None) -> Analysis:
    ents = _default_entity_tokens() if entity_tokens is None else entity_tokens
    clauses, turn_spans = _split_clauses(text, ents)
    an = Analysis(text, clauses, turn_spans)
    _cross_turn(an)
    return an


def span_polarity(an: Analysis, cs: int, ce: int) -> Polarity:
    hit = [c for c in an.clauses if c.start < ce and cs < c.end]
    if not hit:
        return Polarity(None, [], False, ["span overlaps no clause of the transcript"], None, [])
    cues: list[Cue] = []
    amb: list[str] = []
    pols: list[bool] = []
    cross = None
    for c in hit:
        cues += c.cues
        amb += c.ambiguities
        if c.idx in an.cross:
            ans, neg, a = an.cross[c.idx]
            cross = ans
            pols.append(neg)
            amb += a
        else:
            pols.append(c.negated)
            if c.idx in an.unanswered_questions:
                amb.append(
                    "span is inside a question with no bare yes/no answer in the next turn; "
                    "polarity is not asserted"
                )
    if len(set(pols)) > 1:
        amb.append("span covers clauses with different polarity")
    return Polarity(
        negated=any(pols),
        cues=cues,
        soft=any(c.soft for c in cues),
        ambiguities=list(dict.fromkeys(amb)),
        cross_turn=cross,
        clause_ids=[c.idx for c in hit],
    )


def text_polarity(text: str) -> Polarity:
    return span_polarity(analyze(text), 0, len(text))
