"""Checks C1..C8 and the rule REGISTRY.

Each check is a plain function `fn(ctx) -> list[(status, reason, field_path)]` with status in
pass | flag | n/a. The verifier (verifier.py) calls REGISTRY[cid].fn at run time, so a test or
an ablation can replace or disable any single check. Exceptions are NOT caught here: the
verifier turns any exception into status "flag", reason "check_error: ..." (fail-closed).

Rule of the module: never return "pass" when the value cannot be confirmed from the transcript.
"""

from __future__ import annotations

import difflib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import regex

from m4_verify.config import Config
from m4_verify.lexicon import (
    NP_FILLERS,
    SYMPTOMS,
    UNIT_TOKENS,
    Lexicon,
    child_cues,
    parse_dose_phrases,
    parse_durations,
    parse_frequencies,
    symptom_in,
    symptom_tokens,
)
from m4_verify.negation import (
    ANSWER_NEG,
    ANSWER_POS,
    Analysis,
    analyze,
    answer_of,
    classify_token,
    span_polarity,
)
from m4_verify.numbers import english_numbers, parse_numbers, word_value
from m4_verify.textnorm import nfc, tokens

Result = tuple[str, str, str]
MASS = {"mg": 1.0, "g": 1000.0, "mcg": 0.001}


@dataclass
class Ctx:
    record: dict[str, Any]
    transcript: dict[str, Any]
    lexicon: Lexicon
    config: Config
    second: dict[str, Any] | None = None
    encounter_index: dict[str, str] | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.transcript["text"]

    @cached_property
    def entity_tokens(self) -> frozenset[str]:
        return frozenset(self.lexicon.entity_tokens() | symptom_tokens() | UNIT_TOKENS | NP_FILLERS)

    @cached_property
    def analysis(self) -> Analysis:
        return analyze(self.text, self.entity_tokens)

    def items(self) -> list[tuple[str, str, dict[str, Any]]]:
        out = []
        for kind in ("symptoms", "medications", "advice"):
            for i, it in enumerate(self.record[kind]):
                out.append((f"/{kind}/{i}", kind, it))
        if self.record.get("follow_up") is not None:
            out.append(("/follow_up", "follow_up", self.record["follow_up"]))
        return out

    def span(self, item: dict[str, Any]) -> tuple[int, int, str]:
        """(start, end, transcript slice). The TRANSCRIPT slice is used, not the record's claim."""
        ev = item["evidence"]
        cs, ce = int(ev["char_start"]), int(ev["char_end"])
        return cs, ce, self.text[cs:ce]


def _fmt(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _eq(a: Any, b: Any) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- C1
def c1_span_exists(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    tid = ctx.record["source_transcript_id"]
    if tid != ctx.transcript["audio_id"]:
        out.append(
            (
                "flag",
                f"record points to transcript '{tid}' but was checked against '{ctx.transcript['audio_id']}'",
                "/source_transcript_id",
            )
        )
    else:
        out.append(
            (
                "pass",
                "source_transcript_id matches the transcript audio_id",
                "/source_transcript_id",
            )
        )
    n = len(ctx.text)
    for path, _, it in ctx.items():
        ev = it["evidence"]
        cs, ce = ev["char_start"], ev["char_end"]
        p = f"{path}/evidence"
        if not (isinstance(cs, int) and isinstance(ce, int) and 0 <= cs < ce <= n):
            out.append(
                ("flag", f"evidence offsets [{cs},{ce}) are outside the transcript (length {n})", p)
            )
        elif nfc(ctx.text[cs:ce]) != nfc(ev["span_text"]):
            out.append(
                (
                    "flag",
                    f"transcript[{cs}:{ce}] = '{ctx.text[cs:ce]}' differs from span_text '{ev['span_text']}'",
                    p,
                )
            )
        else:
            out.append(("pass", "span text found at the stated offsets (NFC)", p))
    return out


# --------------------------------------------------------------------------- C2
def c2_span_supports_value(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    for path, kind, it in ctx.items():
        _, _, s = ctx.span(it)
        if kind == "medications":
            drug = it["drug"].casefold()
            found = [d for d, _, _ in ctx.lexicon.drugs_in(s)]
            if drug not in ctx.lexicon.drugs:
                out.append(
                    (
                        "flag",
                        f"drug '{drug}' is not in the lexicon; cannot re-derive it",
                        f"{path}/drug",
                    )
                )
            elif drug in found and len(set(found)) == 1:
                out.append(
                    (
                        "pass",
                        f"drug '{drug}' re-derived from the span via the lexicon",
                        f"{path}/drug",
                    )
                )
            elif drug in found:
                out.append(
                    (
                        "flag",
                        f"span names several drugs {sorted(set(found))}; which one is meant?",
                        f"{path}/drug",
                    )
                )
            else:
                out.append(
                    (
                        "flag",
                        f"span names {sorted(set(found)) or 'no lexicon drug'}, not '{drug}'",
                        f"{path}/drug",
                    )
                )
            doses = parse_dose_phrases(s)
            dv, du = it["dose_value"], it["dose_unit"]
            if dv is None:
                if doses:
                    out.append(
                        (
                            "flag",
                            f"span states a dose ({', '.join(_fmt(d.value) + ' ' + d.unit for d in doses)}) but record has none",
                            f"{path}/dose_value",
                        )
                    )
                else:
                    out.append(
                        (
                            "pass",
                            "no dose in record and none stated in the span",
                            f"{path}/dose_value",
                        )
                    )
            else:
                match = [d for d in doses if _eq(d.value, dv)]
                if not match:
                    said = (
                        ", ".join(_fmt(d.value) + " " + str(d.unit) for d in doses)
                        or "no dose phrase"
                    )
                    out.append(
                        (
                            "flag",
                            f"dose {_fmt(dv)} not derivable from the span (span has: {said})",
                            f"{path}/dose_value",
                        )
                    )
                elif du is not None and not any(d.unit == du for d in match):
                    out.append(
                        (
                            "flag",
                            f"unit '{du}' not derivable: span says {_fmt(dv)} {match[0].unit}",
                            f"{path}/dose_unit",
                        )
                    )
                else:
                    out.append(
                        (
                            "pass",
                            f"dose {_fmt(dv)} {du} re-derived from the span",
                            f"{path}/dose_value",
                        )
                    )
        elif kind == "symptoms":
            name = it["name"].casefold()
            if name not in SYMPTOMS:
                out.append(
                    (
                        "flag",
                        f"symptom '{name}' is not in the verifier's symptom list; cannot re-derive it",
                        f"{path}/name",
                    )
                )
            elif symptom_in(name, s):
                out.append(("pass", f"symptom '{name}' re-derived from the span", f"{path}/name"))
            else:
                out.append(("flag", f"symptom '{name}' not found in the span", f"{path}/name"))
        else:
            out.append(
                (
                    "n/a",
                    "free-text value: its meaning cannot be re-derived by rules (human review; C3/C6 still apply)",
                    f"{path}/text",
                )
            )
    return out or [
        ("flag", "record has no extracted fields: nothing could be verified (fail-closed)", "/")
    ]


# --------------------------------------------------------------------------- C3
def c3_negation(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    for path, kind, it in ctx.items():
        if kind == "follow_up":
            out.append(("n/a", "follow_up has no negation field", path))
            continue
        cs, ce, _ = ctx.span(it)
        pol = span_polarity(ctx.analysis, cs, ce)
        if kind == "symptoms":
            fpath, rec_neg = f"{path}/present", not it["present"]
        else:
            fpath, rec_neg = f"{path}/negated", it["negated"]
        if not isinstance(rec_neg, bool):
            raise TypeError(f"{fpath} is not a boolean")
        if pol.negated is None:
            out.append(
                ("flag", "negation state of the span cannot be determined (no clause)", fpath)
            )
            continue
        cue_txt = ", ".join(f"{c.token}:{c.rule_id}" for c in pol.cues) or "none"
        how = f"cross-turn answer ({pol.cross_turn})" if pol.cross_turn else f"cues: {cue_txt}"
        if pol.negated != rec_neg:
            out.append(
                (
                    "flag",
                    f"transcript clause is {'NEGATED' if pol.negated else 'NOT negated'} ({how}) but record says {'negated' if rec_neg else 'not negated'}",
                    fpath,
                )
            )
        else:
            out.append(
                (
                    "pass",
                    f"negation state agrees ({'negated' if rec_neg else 'not negated'}; {how})",
                    fpath,
                )
            )
    return out or [("n/a", "record has no extracted fields", "/")]


# --------------------------------------------------------------------------- C4
# Reason codes (fix pass 2026-11-11, clinical review D-91). Every C4 flag reason starts with
# "<code> [<severity class from docs/severity.md>]: ...". cannot_verify:* means "the rules cannot
# check this dose" (it is NOT evidence of an error) and is reported apart from real violations.
C4_VIOLATIONS = ("span_mismatch", "unit_not_allowed", "out_of_range", "exceeds_max_daily")
CANNOT_VERIFY = (
    "cannot_verify:paediatric",  # child cue in the conversation: adult range does not apply
    "cannot_verify:no_range",  # lexicon range blank
    "cannot_verify:not_in_lexicon",  # drug unknown to the lexicon
    "cannot_verify:liquid_strength",  # dose in ml, no verified mg per 5 ml strength
    "cannot_verify:count_unit",  # dose in tablets/capsules/sachets: strength not stated
)
CODE_RE = regex.compile(r"^(check_error|[a-z_]+(?::[a-z_]+)?)(?: \[([A-Z]{2}-[A-Z-]+)\])?:")


def reason_code(reason: str) -> str | None:
    """'out_of_range [CR-DOSE]: ...' -> 'out_of_range'; free text -> None."""
    m = CODE_RE.match(reason)
    return m.group(1) if m else None


def severity_class(reason: str) -> str | None:
    """'cannot_verify:paediatric [CR-PAEDIATRIC]: ...' -> 'CR-PAEDIATRIC'."""
    m = CODE_RE.match(reason)
    return m.group(2) if m else None


def is_cannot_verify(reason: str) -> bool:
    return (reason_code(reason) or "").startswith("cannot_verify")


def _c(code: str, cls: str, msg: str) -> str:
    return f"{code} [{cls}]: {msg}"


def c4_dose_range(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    kids = sorted(set(child_cues(ctx.text)))
    for i, it in enumerate(ctx.record["medications"]):
        path = f"/medications/{i}"
        dv, du = it["dose_value"], it["dose_unit"]
        drug = it["drug"].casefold()
        if dv is None:
            if du is not None:
                out.append(
                    (
                        "flag",
                        _c("span_mismatch", "CR-DOSE", f"unit '{du}' given without a dose value"),
                        f"{path}/dose_unit",
                    )
                )
            else:
                out.append(("n/a", "no dose stated", path))
            continue
        if du is None:
            out.append(
                (
                    "flag",
                    _c("span_mismatch", "CR-DOSE", f"dose {_fmt(dv)} has no unit"),
                    f"{path}/dose_unit",
                )
            )
            continue
        problems: list[Result] = []
        if kids:  # (e) never pass a child's dose against an adult range
            problems.append(
                (
                    "flag",
                    _c(
                        "cannot_verify:paediatric",
                        "CR-PAEDIATRIC",
                        f"child cue in the conversation ({', '.join(kids)}): a child's dose is "
                        "weight/age-based and the adult lexicon range does not apply; not checkable "
                        "by rules, a clinician must check it",
                    ),
                    f"{path}/dose_value",
                )
            )
        _, _, s = ctx.span(it)
        doses = parse_dose_phrases(s)
        if not any(_eq(d.value, dv) for d in doses):
            said = ", ".join(_fmt(d.value) + " " + str(d.unit) for d in doses) or "no dose phrase"
            problems.append(
                (
                    "flag",
                    _c(
                        "span_mismatch",
                        "CR-DOSE",
                        f"dose {_fmt(dv)} {du} does not match the span (span: {said})",
                    ),
                    f"{path}/dose_value",
                )
            )
        elif not any(_eq(d.value, dv) and d.unit == du for d in doses):
            said = [d.unit for d in doses if _eq(d.value, dv)]
            problems.append(
                (
                    "flag",
                    _c(
                        "span_mismatch",
                        "CR-DOSE",
                        f"unit '{du}' does not match the span (span says {_fmt(dv)} {said[0]})",
                    ),
                    f"{path}/dose_unit",
                )
            )
        d = ctx.lexicon.drugs.get(drug)
        if d is None:
            problems.append(
                (
                    "flag",
                    _c(
                        "cannot_verify:not_in_lexicon",
                        "CR-DOSE",
                        f"drug '{drug}' not in the lexicon: no range to check against",
                    ),
                    f"{path}/dose_value",
                )
            )
            out += problems
            continue
        allowed = ctx.config.units_for(drug, ctx.lexicon)
        if du not in allowed:  # (g) allowed units per drug
            cls = (
                "CR-ROUTE"
                if ctx.config.injection_only(drug, ctx.lexicon) and du not in MASS
                else "CR-DOSE"
            )
            problems.append(
                (
                    "flag",
                    _c(
                        "unit_not_allowed",
                        cls,
                        f"unit '{du}' is not an allowed unit for {drug} (allowed: "
                        f"{', '.join(allowed)}; source: {ctx.config.units_source(drug, ctx.lexicon)})",
                    ),
                    f"{path}/dose_unit",
                )
            )
        note = ""
        if du in MASS:
            mg = float(dv) * MASS[du]
            if d.range_mg is None:
                if ctx.config.blank_range_fails_closed:
                    problems.append(
                        (
                            "flag",
                            _c(
                                "cannot_verify:no_range",
                                "CR-DOSE",
                                f"no verified range for {drug} in the lexicon (blank); fail-closed",
                            ),
                            f"{path}/dose_value",
                        )
                    )
            else:
                lo, hi = d.range_mg
                if not (lo <= mg <= hi):
                    problems.append(
                        (
                            "flag",
                            _c(
                                "out_of_range",
                                "CR-DOSE",
                                f"dose {_fmt(mg)} mg is outside the lexicon range {_fmt(lo)}-{_fmt(hi)} "
                                f"mg for {drug} (lexicon: {d.verified_by[:120] or 'unverified'})",
                            ),
                            f"{path}/dose_value",
                        )
                    )
                elif d.strengths_mg and mg > max(d.strengths_mg):
                    note = f"; unusual: above the typical strengths {'/'.join(_fmt(x) for x in d.strengths_mg)} mg (soft note)"
            freq = it["frequency_per_day"]
            if (
                d.max_daily_mg is not None
                and freq is not None
                and mg * float(freq) > d.max_daily_mg
            ):
                problems.append(  # (h) max daily dose where the lexicon gives it
                    (
                        "flag",
                        _c(
                            "exceeds_max_daily",
                            "CR-DOSE",
                            f"{_fmt(mg)} mg x {_fmt(freq)}/day = {_fmt(mg * float(freq))} mg exceeds "
                            f"the lexicon max daily {_fmt(d.max_daily_mg)} mg for {drug}",
                        ),
                        f"{path}/frequency_per_day",
                    )
                )
        elif du == "ml":
            problems.append(
                (
                    "flag",
                    _c(
                        "cannot_verify:liquid_strength",
                        "CR-LIQUID-STRENGTH",
                        "no verified range for a dose in ml: the lexicon has no mg-per-5 ml "
                        "strength for this liquid; fail-closed",
                    ),
                    f"{path}/dose_value",
                )
            )
        else:
            problems.append(
                (
                    "flag",
                    _c(
                        "cannot_verify:count_unit",
                        "CR-DOSE",
                        f"no verified range for a dose in '{du}' (lexicon ranges are in mg and the "
                        "strength per unit was not stated); fail-closed",
                    ),
                    f"{path}/dose_value",
                )
            )
        if problems:
            out += problems
        elif d.range_mg is None:
            out.append(
                (
                    "n/a",
                    f"{_fmt(dv)} {du} matches the span; no lexicon range (blank_range_fails_closed is off)",
                    f"{path}/dose_value",
                )
            )
        else:
            lo, hi = d.range_mg
            out.append(
                (
                    "pass",
                    f"{_fmt(dv)} {du} matches the span and lies in {_fmt(lo)}-{_fmt(hi)} mg (adult range; "
                    f"no child cue in the conversation){note}",
                    f"{path}/dose_value",
                )
            )
    return out or [("n/a", "record has no medications", "/")]


# --------------------------------------------------------------------------- C5
def _c5_field(
    path: str, name: str, rec_val: Any, found: list, unit_ok: Callable[[Any], bool]
) -> Result:
    ok = [q for q in found if unit_ok(q)]
    if rec_val is None:
        if ok:
            return (
                "flag",
                f"span states {name} {', '.join(_fmt(q.value) for q in ok)} but record has none",
                path,
            )
        return ("pass", f"no {name} in record and none stated in the span", path)
    if any(_eq(q.value, rec_val) for q in ok):
        return ("pass", f"{name} {_fmt(rec_val)} parsed from the span", path)
    if found and not ok:
        return (
            "flag",
            f"span {name} is not expressed per day/in days ({', '.join(f'{_fmt(q.value)}/{q.unit}' for q in found)})",
            path,
        )
    return (
        "flag",
        f"{name} {_fmt(rec_val)} not parsed from the span (span has: {', '.join(_fmt(q.value) for q in ok) or 'nothing parseable'})",
        path,
    )


def c5_freq_duration(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    for i, it in enumerate(ctx.record["medications"]):
        path = f"/medications/{i}"
        _, _, s = ctx.span(it)
        out.append(
            _c5_field(
                f"{path}/frequency_per_day",
                "frequency",
                it["frequency_per_day"],
                parse_frequencies(s),
                lambda q: q.unit == "day",
            )
        )
        out.append(
            _c5_field(
                f"{path}/duration_days",
                "duration",
                it["duration_days"],
                parse_durations(s),
                lambda q: q.unit in ("day", "week"),
            )
        )
    return out or [("n/a", "record has no medications", "/")]


# --------------------------------------------------------------------------- C6
def _supported_numbers(s: str) -> set[float]:
    vals = {float(n.value) for n in parse_numbers(s)}
    vals |= {float(q.value) for q in parse_frequencies(s)}
    vals |= {float(q.value) for q in parse_durations(s)}
    return vals


def c6_unsupported(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    lex = ctx.lexicon
    covered: list[tuple[int, int]] = []
    for path, kind, it in ctx.items():
        cs, ce, s = ctx.span(it)
        nums = _supported_numbers(s)
        bad: list[str] = []
        if kind == "medications":
            drug = it["drug"].casefold()
            if drug not in {d for d, _, _ in lex.drugs_in(s)}:
                out.append(
                    (
                        "flag",
                        f"drug '{drug}' is not mentioned in its span (unsupported addition)",
                        f"{path}/drug",
                    )
                )
            else:
                out.append(("pass", f"drug '{drug}' is mentioned in its span", f"{path}/drug"))
            for fld in ("dose_value", "frequency_per_day", "duration_days"):
                v = it[fld]
                if v is not None and float(v) not in nums:
                    out.append(
                        (
                            "flag",
                            f"{fld} {_fmt(v)} does not occur in the span (unsupported addition)",
                            f"{path}/{fld}",
                        )
                    )
                elif v is not None:
                    out.append(("pass", f"{fld} {_fmt(v)} occurs in the span", f"{path}/{fld}"))
        elif kind == "symptoms":
            name = it["name"].casefold()
            if name not in SYMPTOMS:
                out.append(
                    (
                        "flag",
                        f"symptom '{name}' unknown to the verifier: support cannot be confirmed",
                        f"{path}/name",
                    )
                )
            elif not symptom_in(name, s):
                out.append(
                    (
                        "flag",
                        f"symptom '{name}' does not occur in its span (unsupported addition)",
                        f"{path}/name",
                    )
                )
            else:
                out.append(("pass", f"symptom '{name}' occurs in its span", f"{path}/name"))
        else:
            covered.append((cs, ce))
            txt = it["text"]
            for v in english_numbers(txt):
                if float(v) not in nums:
                    bad.append(f"number {_fmt(v)}")
            span_drugs = {d for d, _, _ in lex.drugs_in(s)}
            for d, _, _ in lex.drugs_in(txt):
                if d not in span_drugs:
                    bad.append(f"drug '{d}'")
            if bad:
                out.append(
                    (
                        "flag",
                        f"{', '.join(bad)} in the text do(es) not occur in the span (unsupported addition)",
                        f"{path}/text",
                    )
                )
            else:
                out.append(
                    ("pass", "every number and drug in the text occurs in the span", f"{path}/text")
                )
    # possible omission: lexicon drug said in the transcript but absent from the record (MAJOR)
    in_record = {m["drug"].casefold() for m in ctx.record["medications"]}
    missing = []
    for d, a, b in lex.drugs_in(ctx.text):
        if d in in_record or any(cs <= a and b <= ce for cs, ce in covered):
            continue
        missing.append(f"{d} at [{a},{b})")
    if missing:
        out.append(
            (
                "flag",
                f"possible omission (MAJOR): drug mentioned in the transcript but not in the record: {'; '.join(dict.fromkeys(missing))}",
                "/medications",
            )
        )
    else:
        out.append(
            (
                "pass",
                "every lexicon drug mentioned in the transcript is in the record",
                "/medications",
            )
        )
    # patient link: only checkable against an encounter index (transcript.v1 has no patient field)
    if ctx.encounter_index is None:
        out.append(
            (
                "n/a",
                "patient link not verifiable: no encounter index (transcript.v1 has no patient_ref); known blind spot",
                "/patient_ref",
            )
        )
    else:
        tid = ctx.record["source_transcript_id"]
        want = ctx.encounter_index.get(tid)
        if want is None:
            out.append(
                (
                    "flag",
                    f"transcript '{tid}' is not in the encounter index; patient link unverified",
                    "/patient_ref",
                )
            )
        elif want != ctx.record["patient_ref"]:
            out.append(
                (
                    "flag",
                    f"patient_ref '{ctx.record['patient_ref']}' differs from the encounter index ('{want}') for '{tid}'",
                    "/patient_ref",
                )
            )
        else:
            out.append(("pass", "patient_ref matches the encounter index", "/patient_ref"))
    return out


# --------------------------------------------------------------------------- C7
def _critical_spans(ctx: Ctx, s: str, offset: int) -> list[tuple[int, int, str]]:
    """Critical token ranges inside s (stored offsets shifted by offset)."""
    out = []
    for d, a, b in ctx.lexicon.drugs_in(s):
        out.append((a + offset, b + offset, f"drug {d}"))
    for n in parse_numbers(s):
        out.append((n.start + offset, n.end + offset, f"number {_fmt(n.value)}"))
    for t in tokens(s):
        if t.text in UNIT_TOKENS:
            out.append((t.start + offset, t.end + offset, f"unit {t.text}"))
    return out


def _signature(ctx: Ctx, text: str) -> dict[str, Counter]:
    an = analyze(text, ctx.entity_tokens)
    return {
        "drugs": Counter(d for d, _, _ in ctx.lexicon.drugs_in(text)),
        "doses": Counter(f"{_fmt(q.value)} {q.unit}" for q in parse_dose_phrases(text)),
        "numbers": Counter(_fmt(n.value) for n in parse_numbers(text)),
        "negation cues": Counter(c.token for cl in an.clauses for c in cl.cues),
        "bare answers": Counter(
            f"{answer_of(cl)}:{cl.toks[0].text}" for cl in an.clauses if answer_of(cl)
        ),
    }


def _critical_word(ctx: Ctx, w: str) -> bool:
    return (
        w[:1].isdigit()
        or word_value(w) is not None
        or w in UNIT_TOKENS
        or bool(ctx.lexicon.drugs_in(w))
        or classify_token(w) is not None
        or w in ANSWER_NEG
        or w in ANSWER_POS
    )


def _critical_token_ids(ctx: Ctx, text: str, toks: list) -> set[int]:
    """Indices of critical tokens; a token inside a multi-token drug mention is critical too
    (amoxicillin-clavulanate vs amoxicillin differ only in "clavulanate")."""
    spans = [(a, b) for _, a, b in ctx.lexicon.drugs_in(text, toks)]
    return {
        k
        for k, t in enumerate(toks)
        if _critical_word(ctx, t.text) or any(a <= t.start and t.end <= b for a, b in spans)
    }


def _diff_ranges(ctx: Ctx, other: str) -> list[tuple[int, int, str]]:
    """Token ranges of the FIRST transcript where the second one differs on a critical word.
    A word missing in the first transcript gives a zero-width point after the previous token."""
    ta, tb = tokens(ctx.text), tokens(other)
    crit_a, crit_b = _critical_token_ids(ctx, ctx.text, ta), _critical_token_ids(ctx, other, tb)
    sm = difflib.SequenceMatcher(None, [t.text for t in ta], [t.text for t in tb], autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        wa, wb = [t.text for t in ta[i1:i2]], [t.text for t in tb[j1:j2]]
        if not (set(range(i1, i2)) & crit_a or set(range(j1, j2)) & crit_b):
            continue
        if i1 < i2:
            lo, hi = ta[i1].start, ta[i2 - 1].end
        else:
            lo = hi = ta[i1 - 1].end if i1 > 0 else 0
        out.append((lo, hi, f"'{' '.join(wa) or '-'}' vs second '{' '.join(wb) or '-'}'"))
    return out


def _item_scope(ctx: Ctx, cs: int, ce: int) -> list[tuple[int, int]]:
    """Clauses holding the span, plus the answer clause of the next turn for a question clause."""
    an = ctx.analysis
    pol = span_polarity(an, cs, ce)
    scope = []
    for k in pol.clause_ids:
        c = an.clauses[k]
        scope.append((c.start, c.end))
        if c.is_question:
            nxt = [x for x in an.clauses if x.turn == c.turn + 1]
            if nxt:
                scope.append((nxt[0].start, nxt[0].end))
    return scope or [(cs, ce)]


def c7_asr_risk(ctx: Ctx) -> list[Result]:
    words = ctx.transcript["words"]
    has_conf = any(w.get("conf") is not None for w in words)
    if not has_conf and ctx.second is None:
        return [
            (
                "n/a",
                "no word confidences and no second transcript: ASR risk not assessable (limitation; a silently dropped negation is invisible here)",
                "/",
            )
        ]
    out: list[Result] = []
    thr = ctx.config.c7_conf_threshold
    if has_conf:
        for path, _, it in ctx.items():
            cs, ce, s = ctx.span(it)
            crit = _critical_spans(ctx, s, cs)
            pol = span_polarity(ctx.analysis, cs, ce)
            crit += [(c.start, c.end, f"negation cue {c.token}") for c in pol.cues]
            low = []
            for a, b, label in crit:
                for w in words:
                    if (
                        w["char_start"] < b
                        and a < w["char_end"]
                        and w.get("conf") is not None
                        and w["conf"] < thr
                    ):
                        low.append(f"{label} ('{w['w']}' conf {w['conf']:.2f})")
            if low:
                out.append(
                    (
                        "flag",
                        f"critical token(s) below the confidence threshold {thr} [{ctx.config.c7_threshold_status}]: {'; '.join(dict.fromkeys(low))}",
                        path,
                    )
                )
            else:
                out.append(
                    (
                        "pass",
                        f"all critical tokens in the span have confidence >= {thr} or unknown [{ctx.config.c7_threshold_status}]",
                        path,
                    )
                )
    if ctx.second is not None:
        a = _signature(ctx, ctx.text)
        b = _signature(ctx, ctx.second["text"])
        diffs = []
        for k in a:
            if a[k] != b[k]:
                only1 = a[k] - b[k]
                only2 = b[k] - a[k]
                diffs.append(
                    f"{k}: first has {dict(only1) or '{}'}, second transcript has {dict(only2) or '{}'}"
                )
        if diffs:
            out.append(
                (
                    "flag",
                    "first and second transcript disagree on critical tokens: " + " | ".join(diffs),
                    "/",
                )
            )
            # attribute each difference to the item(s) whose clause holds it (integrity M4-2)
            ranges = _diff_ranges(ctx, ctx.second["text"])
            for path, _, it in ctx.items():
                cs, ce, _ = ctx.span(it)
                hit = [
                    label
                    for lo, hi, label in ranges
                    for a, b in _item_scope(ctx, cs, ce)
                    if (lo < b and a < hi) or (lo == hi and a < lo <= b)
                ]
                if hit:
                    out.append(
                        (
                            "flag",
                            "second transcript differs inside this item's clause: "
                            + "; ".join(dict.fromkeys(hit)),
                            path,
                        )
                    )
        else:
            out.append(
                (
                    "pass",
                    "second transcript agrees on drugs, doses, numbers, negation cues and bare answers",
                    "/",
                )
            )
    return out


# --------------------------------------------------------------------------- C8
def c8_ambiguity(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    an = ctx.analysis
    for msg in an.unresolved_answers:
        out.append(("flag", msg, "/"))
    for path, kind, it in ctx.items():
        cs, ce, _ = ctx.span(it)
        pol = span_polarity(an, cs, ce)
        reasons = list(pol.ambiguities)
        if kind == "medications":
            clause_text = [an.text[an.clauses[k].start : an.clauses[k].end] for k in pol.clause_ids]
            for name, fn in (
                ("dose", parse_dose_phrases),
                ("frequency", parse_frequencies),
                ("duration", parse_durations),
            ):
                vals = {f"{_fmt(q.value)} {q.unit}" for t in clause_text for q in fn(t)}
                if len(vals) > 1:
                    reasons.append(f"conflicting {name} values in one clause: {sorted(vals)}")
        if reasons:
            out.append(("flag", "; ".join(reasons), path))
        else:
            out.append(
                (
                    "pass",
                    "no ambiguity found (soft cue, double cue, unresolved answer, conflicting numbers)",
                    path,
                )
            )
    return out or [("pass", "record has no extracted fields and no unresolved bare answers", "/")]


# --------------------------------------------------------------------------- registry
@dataclass
class Check:
    check_id: str
    name: str
    fn: Callable[[Ctx], list[Result]]


REGISTRY: dict[str, Check] = {
    "C1": Check("C1", "span-exists", c1_span_exists),
    "C2": Check("C2", "span-supports-value", c2_span_supports_value),
    "C3": Check("C3", "negation-consistency", c3_negation),
    "C4": Check("C4", "dose-range", c4_dose_range),
    "C5": Check("C5", "frequency-duration-parse", c5_freq_duration),
    "C6": Check("C6", "unsupported-addition", c6_unsupported),
    "C7": Check("C7", "asr-risk", c7_asr_risk),
    "C8": Check("C8", "ambiguity", c8_ambiguity),
}
