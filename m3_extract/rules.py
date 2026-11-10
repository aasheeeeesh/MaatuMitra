"""MAIN pipeline: deterministic rules, transcript.v1 -> record.v1 with smallest-span evidence.

See plan.md section 1 for the rules and handoff/decisions.md for why. Every decision the
extractor takes is appended to an event log (drug match type, cross-turn, polarity conflicts,
soft cues), saved next to the record by run.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import regex
import yaml

from m3_extract import __version__
from m3_extract.evidence import evidence_for
from m3_extract.lexicon import DrugLexicon, DrugMatch, load_lexicon
from m3_extract.negation import (
    Clause,
    NegationTable,
    NegResult,
    clause_negation,
    cross_turn_answer,
    load_table,
    split_clauses,
)
from m3_extract.numbers import parse_number
from m3_extract.textnorm import Token, check_stored, is_boundary_dot, tokenize
from m3_extract.units import parse_attributes

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_LEXICON = ROOT / "data" / "lexicon" / "drugs.csv"
SYMPTOMS_PATH = HERE / "data" / "symptoms.yaml"
PHRASES_PATH = HERE / "data" / "phrases.yaml"

EXIST_WORDS = {"ಇದೆ", "ಇವೆ", "ಬಂದಿದೆ", "ಆಗಿದೆ", "ಆಗುತ್ತಿದೆ", "ಇತ್ತು"}
HOW_MANY = {"ಎಷ್ಟು"}
# Conditional verb endings ("if ..."): ಇದ್ದರೆ, ಬಂದರೆ, ...ದಿದ್ದರೆ, spoken ತಗೊಂಡ್ರೆ. Words that merely
# END in these letters are listed as exceptions (ಆದರೆ "but" is a clause splitter; ತೊಂದರೆ "trouble").
CONDITIONAL_RE = regex.compile(r"(ದರೆ|ದ್ರೆ|ಡ್ರೆ)$")
NOT_CONDITIONAL = {"ಆದರೆ", "ತೊಂದರೆ"}
COORD_SPLITTERS = {"NEG-CL03", "NEG-CL04", ","}  # ಮತ್ತು, ಹಾಗೂ, comma


# ----------------------------------------------------------------------------- resources


@cache
def load_symptoms(path: str | Path = SYMPTOMS_PATH) -> dict[tuple[str, ...], str]:
    """Token-sequence form (comparison form) -> canonical symptom name."""
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    out: dict[tuple[str, ...], str] = {}
    for name, e in doc["symptoms"].items():
        for form in list(e.get("kn") or []) + list(e.get("latin") or []):
            out[tuple(t.norm for t in tokenize(form))] = name
    return out


def find_symptoms(tokens: list[Token], skip: set[int]) -> list[tuple[int, int, str]]:
    """Longest whole-token matches (start, end exclusive, name); never across turns."""
    sym = load_symptoms()
    max_len = max(len(k) for k in sym)
    out, i = [], 0
    while i < len(tokens):
        hit = None
        for n in range(min(max_len, len(tokens) - i), 0, -1):
            span = range(i, i + n)
            if any(j in skip for j in span) or tokens[i + n - 1].turn != tokens[i].turn:
                continue
            name = sym.get(tuple(tokens[j].norm for j in span))
            if name:
                hit = (i, i + n, name)
                break
        if hit:
            out.append(hit)
            i = hit[1]
        else:
            i += 1
    return out


@dataclass
class Phrase:
    id: str
    kind: str
    tokens: list[str]
    optional: set[int]
    extend: bool
    gloss_pos: str
    gloss_neg: str


@dataclass
class Phrases:
    items: list[Phrase]
    fallback_tokens: set[str]
    number_words_en: dict[float, str]


@cache
def load_phrases(path: str | Path = PHRASES_PATH) -> Phrases:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    items = []
    for kind in ("advice", "follow_up"):
        for e in doc[kind]:
            items.append(
                Phrase(
                    e["id"],
                    kind,
                    e["tokens"],
                    set(e.get("optional", [])),
                    bool(e.get("extend_to_clause_end")),
                    e["gloss_pos"],
                    e["gloss_neg"],
                )
            )
    return Phrases(
        items,
        set(doc.get("follow_up_fallback_tokens", [])),
        {float(k): v for k, v in doc.get("number_words_en", {}).items()},
    )


@cache
def _default_lexicon() -> DrugLexicon:
    return load_lexicon(DEFAULT_LEXICON)


# ----------------------------------------------------------------------------- helpers


@dataclass
class Doc:
    transcript: dict[str, Any]
    text: str
    tokens: list[Token]
    clauses: list[Clause]
    clause_of: list[int]  # token index -> clause index (-1 for splitter words)
    sentence_of: list[tuple[int, int]]  # token index -> (turn, sentence number)
    turn_tokens: dict[int, list[int]]
    neg: list[NegResult]
    events: list[dict[str, Any]] = field(default_factory=list)

    def span(self, s: int, e: int) -> dict[str, Any]:
        return evidence_for(self.transcript, s, e)


def _sentence_ids(text: str, tokens: list[Token]) -> list[tuple[int, int]]:
    out = []
    prev_end, sent, turn = 0, 0, 0
    for t in tokens:
        if t.turn != turn:
            turn, sent = t.turn, 0
            prev_end = t.start
        for k in range(prev_end, t.start):
            ch = text[k]
            if ch in "?!" or (ch == "." and is_boundary_dot(text, k)):
                sent += 1
        out.append((t.turn, sent))
        prev_end = t.end
    return out


def _build_doc(transcript: dict[str, Any], table: NegationTable) -> Doc:
    text = transcript["text"]
    check_stored(text)
    tokens = tokenize(text)
    clauses = split_clauses(text, tokens, table)
    by_start = {t.start: i for i, t in enumerate(tokens)}
    clause_of = [-1] * len(tokens)
    for ci, c in enumerate(clauses):
        for t in c.tokens:
            clause_of[by_start[t.start]] = ci
    turn_tokens: dict[int, list[int]] = {}
    for i, t in enumerate(tokens):
        turn_tokens.setdefault(t.turn, []).append(i)
    neg = [clause_negation(c, table) for c in clauses]
    return Doc(
        transcript, text, tokens, clauses, clause_of, _sentence_ids(text, tokens), turn_tokens, neg
    )


def _answer_after(doc: Doc, turn: int, table: NegationTable) -> str | None:
    nxt = doc.turn_tokens.get(turn + 1)
    if not nxt:
        return None
    return cross_turn_answer([doc.tokens[i] for i in nxt], table)


def _sentence_tokens(doc: Doc, ti: int) -> list[int]:
    key = doc.sentence_of[ti]
    return [i for i in doc.turn_tokens[doc.tokens[ti].turn] if doc.sentence_of[i] == key]


def _is_question(doc: Doc, ci: int) -> bool:
    """Rules v2: a clause is a question if its sentence ends with '?', EXCEPT a comma clause that
    ends in a statement predicate (ನನಗೆ ಜ್ವರ ಇದೆ, ... ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ?): that part is a statement and a
    bare ಇಲ್ಲ/ಹೌದು answer does not apply to it. Bare noun lists (ನೆಗಡಿ, ಚಳಿ, ... ಇದೆಯಾ?) stay questions."""
    c = doc.clauses[ci]
    if not c.is_question:
        return False
    return not (c.splitter_after == "," and c.tokens[-1].norm in EXIST_WORDS)


def _is_conditional(doc: Doc, ci: int) -> bool:
    return doc.neg[ci].conditional or any(
        CONDITIONAL_RE.search(t.norm) and t.norm not in NOT_CONDITIONAL
        for t in doc.clauses[ci].tokens
    )


# ----------------------------------------------------------------------------- medications


@dataclass
class Mention:
    kind: str  # cross_turn | statement | question
    priority: int
    n_attrs: int
    order: int
    item: dict[str, Any]
    span: tuple[int, int]


def _med_mentions(doc: Doc, matches: list[DrugMatch], table: NegationTable) -> list[Mention]:
    out = []
    for k, m in enumerate(matches):
        first = doc.tokens[m.start_tok]
        ci = doc.clause_of[m.start_tok]
        doc.events.append(
            {
                "rule": "drug_match",
                "drug": m.drug,
                "match_type": m.match_type,
                "form": m.form,
                "char_start": first.start,
            }
        )
        # attribute window: drug end -> clause end, stopping at the next drug in the clause
        cl_idx = [i for i in range(len(doc.tokens)) if doc.clause_of[i] == ci]
        nxt_start = matches[k + 1].start_tok if k + 1 < len(matches) else len(doc.tokens)
        after = [i for i in cl_idx if m.end_tok <= i < nxt_start]
        prev_end = matches[k - 1].end_tok if k > 0 else 0
        before = [i for i in cl_idx if prev_end <= i < m.start_tok]
        attrs = parse_attributes([doc.tokens[i] for i in after])
        window = after
        if attrs.count() == 0 and before:
            attrs = parse_attributes([doc.tokens[i] for i in before])
            window = before
        s, e = first.start, doc.tokens[m.end_tok - 1].end
        if attrs.last_token_index is not None:
            # every supporting token lies inside the window; span covers drug..last attribute
            idx = window[attrs.last_token_index]
            s = min(s, doc.tokens[window[0]].start) if window is before else s
            e = max(e, doc.tokens[idx].end)
        nr = doc.neg[ci]
        is_q = _is_question(doc, ci)
        answer = _answer_after(doc, first.turn, table) if is_q else None
        if answer is not None:
            kind, prio, negated = "cross_turn", 3, answer == "negative"
            s, e = first.start, doc.tokens[m.end_tok - 1].end  # entity in the QUESTION turn
            doc.events.append({"rule": "cross_turn", "item": m.drug, "polarity": answer})
        else:
            kind = "question" if is_q else "statement"
            prio = 1 if is_q else 2
            negated = nr.negated
            if negated:
                for t in nr.cue_tokens:
                    s, e = min(s, t.start), max(e, t.end)
                if nr.soft:
                    doc.events.append({"rule": "soft_negation", "item": m.drug, "cues": nr.cue_ids})
        item = {
            "drug": m.drug,
            "dose_value": attrs.dose_value,
            "dose_unit": attrs.dose_unit,
            "frequency_per_day": attrs.frequency_per_day,
            "duration_days": attrs.duration_days,
            "negated": bool(negated),
        }
        out.append(Mention(kind, prio, attrs.count(), k, item, (s, e)))
    return out


def _choose(mentions: list[Mention], key: str, doc: Doc) -> list[Mention]:
    best: dict[str, Mention] = {}
    order: list[str] = []
    for mt in mentions:
        name = mt.item[key]
        if name not in best:
            order.append(name)
            best[name] = mt
            continue
        cur = best[name]
        pol = "negated" if key == "drug" else "present"
        if mt.item[pol] != cur.item[pol]:
            doc.events.append({"rule": "polarity_conflict", "item": name})
        if (mt.priority, mt.n_attrs, mt.order) > (cur.priority, cur.n_attrs, cur.order):
            best[name] = mt
    return [best[n] for n in order]


# ----------------------------------------------------------------------------- symptoms


def _symptom_mentions(doc: Doc, lexicon_hits: set[int], table: NegationTable) -> list[Mention]:
    hits = find_symptoms(doc.tokens, lexicon_hits)
    sym_tok = {j for a, b, _ in hits for j in range(a, b)}
    by_start = {t.start: k for k, t in enumerate(doc.tokens)}
    out = []
    for a, b, name in hits:
        t, last = doc.tokens[a], doc.tokens[b - 1]
        ci = doc.clause_of[a]
        if ci < 0:
            continue
        clause = doc.clauses[ci]
        if _is_conditional(doc, ci):
            doc.events.append(
                {"rule": "symptom_skipped_conditional", "item": name, "char_start": t.start}
            )
            continue
        s, e = t.start, last.end
        if _is_question(doc, ci):
            answer = _answer_after(doc, t.turn, table)
            if answer is not None:
                doc.events.append({"rule": "cross_turn", "item": name, "polarity": answer})
                out.append(
                    Mention(
                        "cross_turn",
                        3,
                        0,
                        a,
                        {"name": name, "present": answer == "affirmative"},
                        (s, e),
                    )
                )
            elif any(doc.tokens[j].norm in HOW_MANY for j in _sentence_tokens(doc, a)):
                out.append(Mention("presupposed", 1, 0, a, {"name": name, "present": True}, (s, e)))
            continue
        # statement: polarity of its clause; a bare-noun clause before a coordinator shares the
        # next clause's predicate (ನೆಗಡಿ ಮತ್ತು ಕೆಮ್ಮು ... ಇದೆ)
        pol_ci = ci
        while (
            all(by_start[x.start] in sym_tok for x in doc.clauses[pol_ci].tokens)
            and doc.clauses[pol_ci].splitter_after in COORD_SPLITTERS
            and pol_ci + 1 < len(doc.clauses)
            and doc.clauses[pol_ci + 1].turn == clause.turn
        ):
            pol_ci += 1
        if pol_ci != ci:
            doc.events.append({"rule": "coordination", "item": name})
        nr = doc.neg[pol_ci]
        if nr.negated:
            for c in nr.cue_tokens:
                s, e = min(s, c.start), max(e, c.end)
            if nr.soft:
                doc.events.append({"rule": "soft_negation", "item": name, "cues": nr.cue_ids})
        elif b < len(doc.tokens) and doc.clause_of[b] == ci and doc.tokens[b].norm in EXIST_WORDS:
            e = doc.tokens[b].end
        out.append(Mention("statement", 2, 0, a, {"name": name, "present": not nr.negated}, (s, e)))
    return out


# ----------------------------------------------------------------------------- advice / follow-up


def _match_phrase(p: Phrase, norms: list[str], start: int) -> tuple[int, float | None] | None:
    """Match pattern p at position start; returns (end index exclusive, captured number)."""

    def rec(pi: int, ti: int, num: float | None):
        if pi == len(p.tokens):
            return ti, num
        if pi in p.optional:
            r = rec(pi + 1, ti, num)
            if r is not None:
                return r
        if ti >= len(norms):
            return None
        pat = p.tokens[pi]
        if pat == "{N}":
            v = parse_number(norms[ti])
            if v is None:
                return None
            return rec(pi + 1, ti + 1, v)
        if regex.fullmatch(pat, norms[ti]):
            return rec(pi + 1, ti + 1, num)
        return None

    return rec(0, start, None)


def _advice(doc: Doc, drug_tok: set[int]) -> tuple[list[Mention], Mention | None]:
    ph = load_phrases()
    advice: list[Mention] = []
    follow: Mention | None = None
    seen_sentences = {doc.sentence_of[i] for i in range(len(doc.tokens))}
    for key in sorted(seen_sentences):
        idx = [i for i in range(len(doc.tokens)) if doc.sentence_of[i] == key]
        if all(_is_question(doc, doc.clause_of[i]) for i in idx if doc.clause_of[i] >= 0):
            continue
        norms = [doc.tokens[i].norm for i in idx]
        used: set[int] = set()
        for p in ph.items:
            for st in range(len(idx)):
                if st in used:
                    continue
                r = _match_phrase(p, norms, st)
                if r is None:
                    continue
                en, num = r
                toks = idx[st:en]
                cis = {doc.clause_of[i] for i in toks if doc.clause_of[i] >= 0}
                if p.extend:
                    last_ci = max(cis)
                    toks = toks + [i for i in idx if doc.clause_of[i] == last_ci and i > toks[-1]]
                if any(doc.clause_of[i] == ci for ci in cis for i in drug_tok):
                    doc.events.append({"rule": "advice_skipped_drug_clause", "pattern": p.id})
                    continue
                s, e = doc.tokens[toks[0]].start, doc.tokens[toks[-1]].end
                span_cis = {doc.clause_of[i] for i in toks if doc.clause_of[i] >= 0}
                negated = any(doc.neg[ci].negated for ci in span_cis)
                if p.kind == "follow_up":  # "if not" conditions (NEG-S03) pick the negative gloss
                    use_neg = negated or any(doc.neg[ci].conditional for ci in span_cis)
                else:
                    use_neg = negated
                gloss = p.gloss_neg if use_neg else p.gloss_pos
                if num is not None:
                    gloss = gloss.replace("{N}", ph.number_words_en.get(float(num), str(num)))
                used.update(range(st, en))
                doc.events.append({"rule": "phrase", "pattern": p.id, "negated": negated})
                if p.kind == "advice":
                    advice.append(
                        Mention(
                            "statement", 2, 0, toks[0], {"text": gloss, "negated": negated}, (s, e)
                        )
                    )
                elif follow is None:
                    follow = Mention("statement", 2, 0, toks[0], {"text": gloss}, (s, e))
        if follow is None and any(n in ph.fallback_tokens for n in norms):
            s, e = doc.tokens[idx[0]].start, doc.tokens[idx[-1]].end
            follow = Mention(
                "fallback", 1, 0, idx[0], {"text": "[untranslated] " + doc.text[s:e]}, (s, e)
            )
            doc.events.append({"rule": "follow_up_fallback", "char_start": s})
    # one advice item per gloss (first occurrence)
    uniq: dict[str, Mention] = {}
    for a in advice:
        uniq.setdefault(a.item["text"], a)
    return list(uniq.values()), follow


# ----------------------------------------------------------------------------- entry point


def extractor_info(lexicon: DrugLexicon, table: NegationTable) -> dict[str, str]:
    return {
        "name": "m3-rules",
        "version": f"{__version__}+negtable-v{table.version}+{lexicon.path.name}",
    }


def extract(
    transcript: dict[str, Any],
    context: dict[str, Any],
    *,
    lexicon: DrugLexicon | None = None,
    table: NegationTable | None = None,
    record_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (record.v1, log). `context` supplies patient_ref and encounter_type (not spoken)."""
    lexicon = lexicon or _default_lexicon()
    table = table or load_table()
    doc = _build_doc(transcript, table)
    matches = lexicon.find(doc.tokens)
    drug_tok = {i for m in matches for i in range(m.start_tok, m.end_tok)}

    meds = _choose(_med_mentions(doc, matches, table), "drug", doc)
    syms = _choose(_symptom_mentions(doc, drug_tok, table), "name", doc)
    advice, follow = _advice(doc, drug_tok)

    def with_ev(m: Mention) -> dict[str, Any]:
        return {**m.item, "evidence": doc.span(*m.span)}

    rid = record_id or f"rules-{transcript['audio_id']}"
    record = {
        "schema_version": "record.v1",
        "record_id": rid,
        "patient_ref": context["patient_ref"],
        "encounter_type": context["encounter_type"],
        "source_transcript_id": transcript["audio_id"],
        "extractor": extractor_info(lexicon, table),
        "status": "draft",
        "symptoms": [with_ev(m) for m in syms],
        "medications": [with_ev(m) for m in meds],
        "advice": [with_ev(m) for m in advice],
        "follow_up": with_ev(follow) if follow else None,
    }
    log = {"record_id": rid, "source_transcript_id": transcript["audio_id"], "events": doc.events}
    return record, log
