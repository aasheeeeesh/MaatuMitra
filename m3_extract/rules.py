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

from contracts.validate import SPEAKER_FROM_ROLE
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
from m3_extract.v2fields import (
    ADVISE_CUE,
    CLINICIAN,
    INTAKE_STEM,
    LIQUID_FORMS,
    as_needed_spans,
    find_age,
    find_weight,
    food_spans,
    form_in,
    question_status,
    route_for,
    statement_status,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_LEXICON = ROOT / "data" / "lexicon" / "drugs.csv"
SYMPTOMS_PATH = HERE / "data" / "symptoms.yaml"
PHRASES_PATH = HERE / "data" / "phrases.yaml"

EXIST_WORDS = {"ಇದೆ", "ಇವೆ", "ಬಂದಿದೆ", "ಆಗಿದೆ", "ಆಗುತ್ತಿದೆ", "ಇತ್ತು"}
HOW_MANY = {"ಎಷ್ಟು"}
# Conditional verb endings ("if ..."): ಇದ್ದರೆ, ಬಂದರೆ, ...ದಿದ್ದರೆ, spoken ...ದ್ರೆ. Words that merely
# END in these letters are listed as exceptions (ಆದರೆ "but" is a clause splitter; ತೊಂದರೆ "trouble").
CONDITIONAL_RE = regex.compile(r"(ದರೆ|ದ್ರೆ)$")
NOT_CONDITIONAL = {"ಆದರೆ", "ತೊಂದರೆ"}
COMBINATION_DRUGS = {"iron-folic acid"}  # one spoken mg cannot be assigned to a component
COORD_SPLITTERS = {"NEG-CL03", "NEG-CL04", ","}  # ಮತ್ತು, ಹಾಗೂ, comma


# ----------------------------------------------------------------------------- resources


def fused_forms(noun: str) -> list[str]:
    """Kannada noun + ಇಲ್ಲ / ಇದೆ written as ONE word (ಜ್ವರ+ಇಲ್ಲ = ಜ್ವರವಿಲ್ಲ, ವಾಂತಿ+ಇಲ್ಲ = ವಾಂತಿಯಿಲ್ಲ,
    ಕೆಮ್ಮು+ಇಲ್ಲ = ಕೆಮ್ಮಿಲ್ಲ). Sandhi rule (grammar inference, UNVERIFIED, not native-validated):
    final ು -> ಿ; final ಿ/ೀ/ೆ -> glide ಯ + ಇ-sign; final consonant -> glide ವ + ಇ-sign."""
    if regex.fullmatch(r"[\p{Kannada}]+", noun) is None:
        return []
    if noun.endswith("ು"):
        base = noun[:-1] + "ಿ"
    elif noun[-1] in "ಿೀೆ":
        base = noun + "ಯಿ"
    elif noun[-1] in "ೇೈೊೋೌಾೂ":
        return []
    else:
        base = noun + "ವಿ"
    return [base + "ಲ್ಲ", base + "ಲ್ಲಾ", base + "ದೆ"]


@cache
def load_symptoms(path: str | Path = SYMPTOMS_PATH) -> dict[tuple[str, ...], str]:
    """Token-sequence form (comparison form) -> canonical symptom name (incl. fused ಜ್ವರವಿಲ್ಲ)."""
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    out: dict[tuple[str, ...], str] = {}
    for name, e in doc["symptoms"].items():
        for form in list(e.get("kn") or []) + list(e.get("latin") or []):
            out[tuple(t.norm for t in tokenize(form))] = name
        for form in e.get("kn") or []:
            for fused in fused_forms(form):
                out.setdefault(tuple(t.norm for t in tokenize(fused)), name)
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
    allow_drug_clause: bool
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
                    bool(e.get("allow_drug_clause")),
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


@dataclass
class V2Ctx:
    """Everything the v2 fields need besides the document."""

    on: bool = False
    roles: list[str] | None = None  # speaker per turn, already mapped to the record enum
    symptom_starts: frozenset[int] = frozenset()

    def speaker(self, turn: int) -> str:
        if self.roles is not None and 0 <= turn < len(self.roles):
            return self.roles[turn]
        return "unknown"


def _continuation(doc: Doc, ci: int, drug_tok: set[int]) -> list[int]:
    """record.v2: 'paracetamol 500 mg, ಎರಡು ಮಾತ್ರೆ' - the clause after a comma (same turn, no drug,
    not a question) still belongs to the instruction."""
    c = doc.clauses[ci]
    if c.splitter_after != "," or ci + 1 >= len(doc.clauses):
        return []
    nxt = doc.clauses[ci + 1]
    if nxt.turn != c.turn or nxt.is_question:
        return []
    idx = [i for i in range(len(doc.tokens)) if doc.clause_of[i] == ci + 1]
    return [] if any(i in drug_tok for i in idx) else idx


def _med_mentions(
    doc: Doc, matches: list[DrugMatch], table: NegationTable, v2: V2Ctx | None = None
) -> list[Mention]:
    v2 = v2 or V2Ctx()
    drug_tok = {i for m in matches for i in range(m.start_tok, m.end_tok)}
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
        if v2.on and (k + 1 >= len(matches) or doc.clause_of[matches[k + 1].start_tok] != ci):
            after += _continuation(doc, ci, drug_tok)
        prev_end = matches[k - 1].end_tok if k > 0 else 0
        before = [i for i in cl_idx if prev_end <= i < m.start_tok]
        form = None
        if v2.on:
            form = form_in([doc.tokens[i] for i in after]) or form_in(
                [doc.tokens[i] for i in reversed(before)]
            )
        kw = {
            "legacy": not v2.on,
            "text": doc.text,
            "symptom_starts": v2.symptom_starts,
            "liquid": bool(form and form[0] in LIQUID_FORMS),
            "ors": m.drug == "ors",
            "combination": m.drug in COMBINATION_DRUGS,
        }
        attrs = parse_attributes([doc.tokens[i] for i in after], **kw)
        window = after
        if attrs.count() == 0 and before:
            attrs = parse_attributes([doc.tokens[i] for i in before], **kw)
            window = before
        for ev in attrs.events:
            doc.events.append({**ev, "item": m.drug})
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
        if v2.on:
            item["_v2"] = _med_v2(
                doc, v2, m, first, window, attrs, form, before, kind, answer, nr, negated, cl_idx
            )
        out.append(Mention(kind, prio, attrs.count(), k, item, (s, e)))
    return out


def _med_v2(doc, v2, m, first, window, attrs, form, before, kind, answer, nr, negated, cl_idx):
    """record.v2 fields of one mention. Spans are (char_start, char_end) pairs."""
    f: dict[str, Any] = {"spans": {}}
    clause = [doc.tokens[i] for i in cl_idx]
    formulation, ftok = form if form else (None, None)
    if (
        kind == "statement"
        and negated
        and not any(ADVISE_CUE.search(c.norm) or INTAKE_STEM.match(c.norm) for c in nr.cue_tokens)
        and not any(INTAKE_STEM.match(t.norm) for t in clause)
    ):
        # "this is not X, the tablet I said is another": the form word names the OTHER drug
        formulation, ftok = None, None
    if formulation:
        f["formulation"] = formulation
        f["spans"]["formulation"] = (ftok.start, ftok.end)
    route, rtok = route_for(formulation, ftok, clause)
    if route:
        f["route"] = route
        f["spans"]["route"] = (rtok.start, rtok.end)
    if attrs.strength_value is not None:
        a, b = attrs.strength_idx
        f["strength"] = (attrs.strength_value, attrs.strength_unit)
        f["spans"]["strength"] = (doc.tokens[window[a]].start, doc.tokens[window[b]].end)
    speaker = v2.speaker(first.turn)
    f["speaker"] = speaker
    sent = [doc.tokens[i] for i in _sentence_tokens(doc, m.start_tok)]
    status, sp = "unknown", None
    if kind == "cross_turn":
        ans = doc.tokens[doc.turn_tokens[first.turn + 1][0]]
        status = question_status(sent, answer)
        sp = (ans.start, ans.end) if status != "unknown" else None
    elif kind == "statement":
        status, sp = statement_status(clause, sent, negated, nr.cue_tokens)
        if status == "unknown" and not negated and attrs.count() > 0 and speaker in CLINICIAN:
            status, sp = "prescribed", None  # span = the main evidence, set by the caller
            f["status_is_main_span"] = True
    f["status"] = status
    if sp is not None:
        f["spans"]["status"] = sp
    return f


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
            not doc.neg[pol_ci].negated  # a fused ಕೆಮ್ಮಿಲ್ಲ carries its own predicate
            and all(by_start[x.start] in sym_tok for x in doc.clauses[pol_ci].tokens)
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
                if not p.allow_drug_clause and any(
                    doc.clause_of[i] == ci for ci in cis for i in drug_tok
                ):
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


def _roles(context: dict[str, Any], text: str) -> list[str] | None:
    """Speaker per turn from context['turn_roles'] (gold role names), mapped to the record enum.
    Only used when there is exactly one role per transcript line; otherwise speaker stays unknown
    (never guessed). On ASR output this needs diarisation, which m2 does not provide (UNVERIFIED)."""
    roles = context.get("turn_roles")
    if not roles or len(roles) != text.count("\n") + 1:
        return None
    return [SPEAKER_FROM_ROLE.get(r, "unknown") for r in roles]


def _nearest_drug(doc: Doc, tok_idx: int, drug_pos: list[tuple[int, str]]) -> str | None:
    """Drug mention in the same sentence nearest to token tok_idx (ties: the earlier one)."""
    key = doc.sentence_of[tok_idx]
    cands = [(abs(p - tok_idx), p > tok_idx, d) for p, d in drug_pos if doc.sentence_of[p] == key]
    return min(cands)[2] if cands else None


def _sentence_fields(
    doc: Doc, items: dict[str, dict], matches: list[DrugMatch], sym_tok: set[int], table
) -> None:
    """as_needed and food_timing: phrases that belong to the nearest drug of their sentence."""
    drug_pos = [(m.start_tok, m.drug) for m in matches]
    for a, b, k in as_needed_spans(doc.tokens, sym_tok):
        d = _nearest_drug(doc, k, drug_pos)
        v2 = items[d]["_v2"] if d in items else None
        if v2 is not None and "as_needed" not in v2:
            v2["as_needed"] = True
            v2["spans"]["as_needed"] = (doc.tokens[a].start, doc.tokens[b].end)
    for a, b, value in food_spans(doc.tokens):
        ci = doc.clause_of[a]
        if ci >= 0 and doc.neg[ci].negated:
            continue
        d = _nearest_drug(doc, a, drug_pos)
        if d is None:  # a question / reminder in its own sentence about the drug just dictated
            prior = [(p, dn) for p, dn in drug_pos if p < a]
            if prior and doc.tokens[a].turn - doc.tokens[prior[-1][0]].turn <= 1:
                if _answer_after(doc, doc.tokens[a].turn, table) == "negative":
                    continue
                d = prior[-1][1]
        v2 = items[d]["_v2"] if d in items else None
        if v2 is not None and "food_timing" not in v2:
            v2["food_timing"] = value
            v2["spans"]["food_timing"] = (doc.tokens[a].start, doc.tokens[b].end)


def extract(
    transcript: dict[str, Any],
    context: dict[str, Any],
    *,
    lexicon: DrugLexicon | None = None,
    table: NegationTable | None = None,
    record_id: str | None = None,
    schema: str = "record.v2",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (record, log). `context` supplies patient_ref and encounter_type (not spoken) and,
    optionally, `turn_roles` (one gold role per transcript line, for the speaker fields).
    schema "record.v2" (default) or "record.v1" (the old output, kept for back-compatibility)."""
    if schema not in ("record.v1", "record.v2"):
        raise ValueError(f"unknown schema {schema!r}")
    v2on = schema == "record.v2"
    lexicon = lexicon or _default_lexicon()
    table = table or load_table()
    doc = _build_doc(transcript, table)
    matches = lexicon.find(doc.tokens)
    drug_tok = {i for m in matches for i in range(m.start_tok, m.end_tok)}
    hits = find_symptoms(doc.tokens, drug_tok)
    sym_tok = {j for a, b, _ in hits for j in range(a, b)}
    v2 = V2Ctx(
        v2on,
        _roles(context, doc.text) if v2on else None,
        frozenset(doc.tokens[j].start for j in sym_tok),
    )

    meds = _choose(_med_mentions(doc, matches, table, v2), "drug", doc)
    syms = _choose(_symptom_mentions(doc, drug_tok, table), "name", doc)
    advice, follow = _advice(doc, drug_tok)
    if v2on:
        _sentence_fields(doc, {m.item["drug"]: m.item for m in meds}, matches, sym_tok, table)

    def with_ev(m: Mention) -> dict[str, Any]:
        return {**{k: v for k, v in m.item.items() if k != "_v2"}, "evidence": doc.span(*m.span)}

    def med_v2(m: Mention) -> dict[str, Any]:
        f = m.item["_v2"]
        sp = f["spans"]
        if f.get("status_is_main_span"):
            sp["status"] = m.span
        out = with_ev(m)
        strength = f.get("strength", (None, None))
        out.update(
            {
                "route": f.get("route"),
                "strength_value": strength[0],
                "strength_unit": strength[1],
                "formulation": f.get("formulation"),
                "as_needed": f.get("as_needed"),
                "food_timing": f.get("food_timing"),
                "status": f["status"],
                "speaker": f["speaker"],
                "field_evidence": {
                    key: doc.span(*sp[key])
                    for key in (
                        "route",
                        "strength",
                        "formulation",
                        "as_needed",
                        "food_timing",
                        "status",
                    )
                    if key in sp
                },
            }
        )
        return out

    rid = record_id or f"rules-{transcript['audio_id']}"
    record = {
        "schema_version": schema,
        "record_id": rid,
        "patient_ref": context["patient_ref"],
        "encounter_type": context["encounter_type"],
        "source_transcript_id": transcript["audio_id"],
        "extractor": extractor_info(lexicon, table),
        "status": "draft",
        "symptoms": [with_ev(m) for m in syms],
        "medications": [med_v2(m) if v2on else with_ev(m) for m in meds],
        "advice": [with_ev(m) for m in advice],
        "follow_up": with_ev(follow) if follow else None,
    }
    if v2on:
        for a in record["advice"]:
            a["speaker"] = v2.speaker(doc.tokens[_tok_at(doc, a["evidence"]["char_start"])].turn)
        age = find_age(doc.tokens)
        w = find_weight(doc.tokens)
        record["patient_age_band"] = (
            {"band": age[0], "evidence": doc.span(age[1], age[2])} if age else None
        )
        record["weight_kg"] = {"value": w[0], "evidence": doc.span(w[1], w[2])} if w else None
    log = {"record_id": rid, "source_transcript_id": transcript["audio_id"], "events": doc.events}
    return record, log


def _tok_at(doc: Doc, char_start: int) -> int:
    return next((i for i, t in enumerate(doc.tokens) if t.end > char_start), len(doc.tokens) - 1)
