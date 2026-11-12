"""record.v2 parts of checks C1..C5 (Phase C). Called from checks.py ONLY for record.v2 input, so
record.v1 verdicts (and the v1 E4 numbers) are untouched.

Where each new field is checked (verdict.v1 allows only the ids C1..C8, so no new id is added):
  C1  every new evidence span exists: field_evidence.*, patient_age_band.evidence, weight_kg.evidence
  C2  the value is re-derived from its OWN span: route, strength, formulation, age band, weight
  C3  status against the evidence (negation, advice-against, past tense, directive) and speaker
  C4  route (CR-ROUTE), paediatric (CR-PAEDIATRIC), liquid strength (CR-LIQUID-STRENGTH), dose
      range via the mg-equivalent when a strength is stated; non-prescription rows are not
      range-checked as prescriptions
  C5  as_needed and food_timing against the evidence (MA-MED-ATTRIBUTE)

Reason codes follow checks.py: "<code> [<severity class>]: message". Severity classes come from
docs/severity.md and its record.v2 mapping note. Rule of the module: never "pass" when unsure.
Exceptions are not caught here (the verifier turns them into a check_error flag: fail-closed).
"""

from __future__ import annotations

from typing import Any

from m4_verify import v2rules as R
from m4_verify.lexicon import child_cues, parse_dose_phrases, units_from_note
from m4_verify.negation import span_polarity
from m4_verify.textnorm import nfc

Result = tuple[str, str, str]
MASS = {"mg": 1.0, "g": 1000.0, "mcg": 0.001}
COUNT_UNITS = ("tablet", "capsule", "sachet")
NON_ADULT = ("infant", "child", "adolescent", "unknown")
RX_LIKE = ("prescribed", "continue_existing", "unknown")  # dose-checked as a prescription
GIVEN_NOW = ("prescribed", "continue_existing")
LAY_SPEAKERS = ("patient", "caregiver")
FE_PATH = {"strength": "strength_value"}


def _c(code: str, cls: str, msg: str) -> str:
    return f"{code} [{cls}]: {msg}"


def _fmt(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _eq(a: Any, b: Any) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return False


def is_v2(ctx) -> bool:
    return ctx.record.get("schema_version") == "record.v2"


def _slice(ctx, ev: dict[str, Any]) -> str:
    return ctx.text[int(ev["char_start"]) : int(ev["char_end"])]


def _bounds(ev: dict[str, Any]) -> tuple[int, int]:
    return int(ev["char_start"]), int(ev["char_end"])


def _clause_text(ctx, spans: list[tuple[int, int]]) -> str:
    an = ctx.analysis
    parts = [
        an.text[c.start : c.end]
        for c in an.clauses
        if any(cs < c.end and c.start < ce for cs, ce in spans)
    ]
    return "\n".join(parts)


def _meds(ctx):
    for i, m in enumerate(ctx.record["medications"]):
        yield i, f"/medications/{i}", m


def _band(ctx) -> str | None:
    ab = ctx.record.get("patient_age_band")
    return ab["band"] if ab else None


# =========================================================================== C1
def v2_spans(ctx) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for key in ("patient_age_band", "weight_kg"):
        obj = ctx.record.get(key)
        if obj is not None:
            out.append((f"/{key}/evidence", obj["evidence"]))
    for _, path, m in _meds(ctx):
        for k, ev in sorted(m.get("field_evidence", {}).items()):
            out.append((f"{path}/field_evidence/{k}", ev))
    return out


def c1_extra(ctx) -> list[Result]:
    out: list[Result] = []
    n = len(ctx.text)
    for p, ev in v2_spans(ctx):
        cs, ce = ev["char_start"], ev["char_end"]
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


# =========================================================================== C2
def _missing_span(field: str, path: str) -> Result:
    return ("flag", f"{field} is set but has no evidence span (fail-closed)", path)


def c2_extra(ctx) -> list[Result]:
    out: list[Result] = []
    ab = ctx.record.get("patient_age_band")
    if ab is not None:
        s = _slice(ctx, ab["evidence"])
        bands, why = R.age_bands(s)
        if ab["band"] == "unknown":
            out.append(
                (
                    "n/a",
                    "age band 'unknown' cannot be re-derived by rules (C4 treats it as not checkable)",
                    "/patient_age_band",
                )
            )
        elif bands is None:
            out.append(
                (
                    "flag",
                    f"age band '{ab['band']}' not derivable: no age phrase in the span '{s}'",
                    "/patient_age_band",
                )
            )
        elif ab["band"] in bands:
            out.append(
                (
                    "pass",
                    f"age band '{ab['band']}' re-derived from the span ({why})",
                    "/patient_age_band",
                )
            )
        else:
            out.append(
                (
                    "flag",
                    f"span gives {sorted(bands)} ({why}), record says '{ab['band']}'",
                    "/patient_age_band",
                )
            )
    wk = ctx.record.get("weight_kg")
    if wk is not None:
        got = R.weights(_slice(ctx, wk["evidence"]))
        if any(_eq(w, wk["value"]) for w in got):
            out.append(
                ("pass", f"weight {_fmt(wk['value'])} kg re-derived from the span", "/weight_kg")
            )
        else:
            out.append(
                (
                    "flag",
                    f"weight {_fmt(wk['value'])} kg not derivable from the span (span has: {[_fmt(w) for w in got] or 'no weight'})",
                    "/weight_kg",
                )
            )
    for _, path, m in _meds(ctx):
        fe = m.get("field_evidence", {})
        rr = m["route"]
        if rr is not None:
            p = f"{path}/route"
            if "route" not in fe:
                out.append(_missing_span("route", p))
            else:
                cues = R.route_cues(_slice(ctx, fe["route"]))
                spec = cues & set(R.SPECIFIC_PARENTERAL)
                if rr in ("other", "unknown"):
                    ok, why = False, f"route '{rr}' cannot be re-derived by rules"
                elif rr == "injection_unspecified":
                    ok = "injection" in cues and not spec
                    why = f"span route words {sorted(cues) or 'none'}"
                elif rr == "oral" and "oral" not in cues:
                    # dev-informed: m1 gold.v2 points the oral route at the formulation word
                    # (ಮಾತ್ರೆ, ಸಿರಪ್); an oral-only form supports "oral", never a parenteral route
                    forms = R.formulation_cues(_slice(ctx, fe["route"])) & set(R.ORAL_FORMS)
                    ok = bool(forms) and not (cues & {"iv", "im", "sc", "injection"})
                    why = f"span route words {sorted(cues) or 'none'}, oral form words {sorted(forms) or 'none'}"
                else:
                    ok = rr in cues
                    why = f"span route words {sorted(cues) or 'none'}"
                out.append(
                    ("pass", f"route '{rr}' re-derived from the span", p)
                    if ok
                    else ("flag", f"route '{rr}' not derivable: {why}", p)
                )
        sv, su = m["strength_value"], m["strength_unit"]
        if sv is not None:
            p = f"{path}/strength_value"
            if "strength" not in fe:
                out.append(_missing_span("strength", p))
            else:
                found = R.parse_strengths(_slice(ctx, fe["strength"]))
                if R.strength_key(sv, su) in {f.key for f in found}:
                    out.append(("pass", f"strength {_fmt(sv)} {su} re-derived from the span", p))
                else:
                    said = (
                        ", ".join(f"{_fmt(f.value)} {f.unit}" for f in found)
                        or "no strength phrase"
                    )
                    out.append(
                        (
                            "flag",
                            f"strength {_fmt(sv)} {su} not derivable from the span (span has: {said})",
                            p,
                        )
                    )
        form = m["formulation"]
        if form is not None:
            p = f"{path}/formulation"
            if "formulation" not in fe:
                out.append(_missing_span("formulation", p))
            else:
                cues = R.formulation_cues(_slice(ctx, fe["formulation"]))
                if form != "other" and form in cues:
                    out.append(("pass", f"formulation '{form}' re-derived from the span", p))
                else:
                    out.append(
                        (
                            "flag",
                            f"formulation '{form}' not derivable (span words: {sorted(cues) or 'none'})",
                            p,
                        )
                    )
    return out


# =========================================================================== C3
def _status_result(ctx, m: dict[str, Any], p: str) -> Result:
    st = m["status"]
    if st == "unknown":
        return (
            "n/a",
            "status 'unknown' (not said, or migrated from v1): status classes not measurable",
            p,
        )
    fe = m.get("field_evidence", {})
    main = _bounds(m["evidence"])
    spans = [main]
    if "status" in fe:
        spans.append(_bounds(fe["status"]))
    else:
        return _missing_span("status", p)
    sent = R.context(ctx.text, spans)
    clause = _clause_text(ctx, spans)
    pol = [span_polarity(ctx.analysis, cs, ce) for cs, ce in spans]
    neg_vals = [x.negated for x in pol]
    neg = True if any(v is True for v in neg_vals) else (None if None in neg_vals else False)
    aa = R.advise_against_cues(clause)
    past = R.past_cues(sent)
    dirc = R.directive_cues(clause)
    # dev-informed additions (handoff/decisions.md): a verbless regimen, a permission question
    # answered yes/no in the next turn, "did you finish? / no", ongoing use (ಕುಡಿಯುತ್ತೆ)
    regimen = R.has_regimen(_slice(ctx, m["evidence"]))
    perm = R.permission_cues(sent)
    answered_yes = any(x.cross_turn and x.negated is False for x in pol)
    ongoing = R.ongoing_cues(sent)
    ev = (
        f"(negated={neg}; advise-against {aa or '-'}; past {past or '-'}; directive {dirc or '-'}; "
        f"regimen {regimen}; permission question {perm or '-'}; ongoing {ongoing or '-'})"
    )
    if st in GIVEN_NOW:
        if aa or neg:
            return (
                "flag",
                _c(
                    "status_conflict",
                    "CR-NEG",
                    f"record says '{st}' but the evidence is negated or advises against {ev}",
                ),
                p,
            )
        if past and not dirc:
            return (
                "flag",
                _c(
                    "status_conflict",
                    "MA-STATUS",
                    f"record says '{st}' but the evidence is a past-tense report {ev}",
                ),
                p,
            )
        if not (dirc or regimen or (perm and answered_yes)):
            return (
                "flag",
                _c(
                    "status_unsupported",
                    "MA-STATUS",
                    f"no directive word, stated regimen or answered permission question; '{st}' cannot be re-derived {ev}",
                ),
                p,
            )
        if st == "continue_existing" and not R.continue_cues(sent):
            return (
                "flag",
                _c(
                    "status_unsupported",
                    "MA-STATUS",
                    f"no 'continue' word in the evidence sentence {ev}",
                ),
                p,
            )
        return ("pass", f"status '{st}' agrees with the evidence {ev}", p)
    if st == "already_taken":
        if aa or neg:
            return (
                "flag",
                _c(
                    "status_conflict",
                    "CR-NEG",
                    f"record says 'already_taken' but the evidence is negated or advises against {ev}",
                ),
                p,
            )
        if past or ongoing:
            return ("pass", f"status 'already_taken' agrees with the evidence {ev}", p)
        if dirc:
            return (
                "flag",
                _c(
                    "status_conflict",
                    "MA-STATUS",
                    f"record says 'already_taken' but the evidence is a directive {ev}",
                ),
                p,
            )
        return (
            "flag",
            _c(
                "status_unsupported",
                "MA-STATUS",
                f"no past-tense word in the evidence sentence {ev}",
            ),
            p,
        )
    if st == "not_taken":
        if neg is False:
            return (
                "flag",
                _c(
                    "status_conflict",
                    "CR-NEG",
                    f"record says 'not_taken' but the evidence is not negated {ev}",
                ),
                p,
            )
        if neg is None:
            return (
                "flag",
                _c(
                    "status_unsupported",
                    "MA-STATUS",
                    f"negation of the evidence cannot be determined {ev}",
                ),
                p,
            )
        if aa and not past:
            return (
                "flag",
                _c(
                    "status_conflict",
                    "MA-STATUS",
                    f"evidence advises against (not a denied past exposure) {ev}",
                ),
                p,
            )
        return ("pass", f"status 'not_taken' agrees with the evidence {ev}", p)
    if st == "advised_against":
        if aa or (neg and perm):
            return ("pass", f"status 'advised_against' agrees with the evidence {ev}", p)
        if neg:
            return (
                "flag",
                _c(
                    "status_unsupported",
                    "MA-STATUS",
                    f"evidence is negated but has no advise-against word {ev}",
                ),
                p,
            )
        return (
            "flag",
            _c(
                "status_conflict",
                "CR-NEG",
                f"record says 'advised_against' but the evidence neither negates nor advises against {ev}",
            ),
            p,
        )
    if st == "stopped_early":
        stop = R.stop_cues(sent) or (R.finish_cues(sent) if neg else [])
        if stop:
            return (
                "pass",
                f"status 'stopped_early' agrees with the evidence (stop words {stop})",
                p,
            )
        return (
            "flag",
            _c(
                "status_unsupported",
                "MA-STATUS",
                f"no stop / not-finished word in the evidence sentence {ev}",
            ),
            p,
        )
    return ("flag", _c("status_unsupported", "MA-STATUS", f"unknown status value '{st}'"), p)


def c3_extra(ctx) -> list[Result]:
    out: list[Result] = []
    for _, path, m in _meds(ctx):
        out.append(_status_result(ctx, m, f"{path}/status"))
        sp, st = m["speaker"], m["status"]
        p = f"{path}/speaker"
        if st in GIVEN_NOW and sp in LAY_SPEAKERS:
            out.append(
                (
                    "flag",
                    _c(
                        "speaker_not_prescriber",
                        "MA-STATUS",
                        f"status '{st}' but the evidence speaker is '{sp}': a patient or caregiver does not prescribe",
                    ),
                    p,
                )
            )
        else:
            out.append(
                (
                    "n/a",
                    f"speaker '{sp}' not checkable against the transcript (transcript.v1 has no speaker roles)",
                    p,
                )
            )
    for i, a in enumerate(ctx.record["advice"]):
        p = f"/advice/{i}/speaker"
        cs, ce = _bounds(a["evidence"])
        an = ctx.analysis
        turns = {c.turn for c in an.clauses if c.start < ce and cs < c.end}
        confirmed = any(  # a question in the same turn answered by a bare "yes" in the next turn
            c.turn in turns and an.cross.get(c.idx, ("",))[0] == "affirmative" for c in an.clauses
        )
        if a.get("speaker") in LAY_SPEAKERS and confirmed:
            out.append(
                (
                    "n/a",
                    f"advice said by '{a['speaker']}' as a question and confirmed by a bare yes in the next turn (answerer role not in transcript.v1)",
                    p,
                )
            )
        elif a.get("speaker") in LAY_SPEAKERS:
            out.append(
                (
                    "flag",
                    _c(
                        "speaker_not_clinician",
                        "MA-MED-ATTRIBUTE",
                        f"advice spoken by '{a['speaker']}' is not clinical advice",
                    ),
                    p,
                )
            )
        else:
            out.append(
                (
                    "n/a",
                    f"speaker '{a.get('speaker')}' not checkable against the transcript (no speaker roles)",
                    p,
                )
            )
    return out


# =========================================================================== C4
def _lexicon_routes(ctx, drug: str) -> tuple[bool, bool]:
    """(injection_only, oral_only) from the lexicon's verified_by note (no route column)."""
    d = ctx.lexicon.drugs.get(drug)
    if d is None:
        return False, False
    note = d.verified_by.casefold()
    inj_only = ctx.config.injection_only(drug, ctx.lexicon)
    oral_named = units_from_note(d.verified_by) is not None and any(
        w in note for w in ("tablet", "capsule", "syrup", "suspension", "sachet")
    )
    return inj_only, oral_named and "injection" not in note


def route_results(ctx, i: int, m: dict[str, Any]) -> list[Result]:
    p = f"/medications/{i}/route"
    rr, form, drug = m["route"], m["formulation"], m["drug"].casefold()
    fe = m.get("field_evidence", {})
    main = _bounds(m["evidence"])
    text = _clause_text(ctx, [main]) + "\n" + _slice(ctx, m["evidence"])
    for k in ("route", "formulation"):
        if k in fe:
            text += "\n" + _slice(ctx, fe[k])
    cues = R.route_cues(text)
    forms = R.formulation_cues(text)
    spoken_par = cues & {"iv", "im", "sc", "injection"}
    spec = cues & set(R.SPECIFIC_PARENTERAL)
    flags: list[Result] = []
    non_par = ("oral", "topical", "inhaled", "rectal")
    if form == "injection" and rr in non_par:
        flags.append(
            (
                "flag",
                _c(
                    "route_formulation_conflict",
                    "CR-ROUTE",
                    f"formulation 'injection' with route '{rr}'",
                ),
                p,
            )
        )
    if form in R.ORAL_FORMS and rr in R.PARENTERAL_ROUTES:
        flags.append(
            (
                "flag",
                _c(
                    "route_formulation_conflict",
                    "CR-ROUTE",
                    f"formulation '{form}' with route '{rr}'",
                ),
                p,
            )
        )
    inj_only, oral_only = _lexicon_routes(ctx, drug)
    if inj_only and (rr in non_par or form in R.ORAL_FORMS):
        flags.append(
            (
                "flag",
                _c(
                    "route_not_allowed",
                    "CR-ROUTE",
                    f"{drug} is injection-only in the lexicon note; record says route '{rr}', formulation '{form}'",
                ),
                p,
            )
        )
    if oral_only and (rr in R.PARENTERAL_ROUTES or form == "injection"):
        flags.append(
            (
                "flag",
                _c(
                    "route_not_allowed",
                    "CR-ROUTE",
                    f"the lexicon note names only oral forms for {drug}; record says route '{rr}', formulation '{form}'",
                ),
                p,
            )
        )
    said = f"evidence route words {sorted(cues) or 'none'}"
    if rr is None:
        if spoken_par:
            flags.append(
                (
                    "flag",
                    _c(
                        "route_missing",
                        "CR-ROUTE",
                        f"route is null but the evidence names one ({said})",
                    ),
                    p,
                )
            )
    elif rr in R.SPECIFIC_PARENTERAL:
        if rr not in spec or len(spec) > 1:
            flags.append(
                ("flag", _c("route_mismatch", "CR-ROUTE", f"record says '{rr}' ({said})"), p)
            )
    elif rr == "injection_unspecified":
        if spec:
            flags.append(
                (
                    "flag",
                    _c(
                        "route_mismatch",
                        "CR-ROUTE",
                        f"record says injection_unspecified but the evidence names {sorted(spec)}",
                    ),
                    p,
                )
            )
        elif "injection" not in cues:
            flags.append(
                (
                    "flag",
                    _c("route_mismatch", "CR-ROUTE", f"record says injection_unspecified ({said})"),
                    p,
                )
            )
    elif rr in non_par:
        if spoken_par:
            flags.append(
                ("flag", _c("route_mismatch", "CR-ROUTE", f"record says '{rr}' ({said})"), p)
            )
        elif rr not in cues and not (rr == "oral" and forms & set(R.ORAL_FORMS)):
            flags.append(
                (
                    "flag",
                    _c(
                        "route_unsupported",
                        "CR-ROUTE",
                        f"record says '{rr}' ({said}; formulation words {sorted(forms) or 'none'})",
                    ),
                    p,
                )
            )
    else:  # other / unknown
        flags.append(
            (
                "flag",
                _c(
                    "cannot_verify:route",
                    "CR-ROUTE",
                    f"route '{rr}' cannot be checked by rules ({said})",
                ),
                p,
            )
        )
    if flags:
        return flags
    if rr is None:
        return [("n/a", "route not said (null) and no injection/IV/IM/SC word in the evidence", p)]
    return [("pass", f"route '{rr}' agrees with the evidence ({said}) and the lexicon", p)]


def _paediatric_reason(band: str | None, kids: list[str], weight: Any) -> str:
    why = []
    if band in NON_ADULT:
        why.append(f"patient_age_band '{band}'")
    if kids:
        why.append(f"child cue in the conversation ({', '.join(kids)})")
    msg = (
        f"{' and '.join(why)}: a child's dose is weight/age-based and the adult lexicon range does "
        "not apply; not checkable by rules, a clinician must check it"
    )
    if weight is not None:
        msg += (
            f"; weight_kg {_fmt(weight['value'])} is recorded, but no paediatric dosing table has "
            "been fetched, so a weight-based dose cannot be checked by rules"
        )
    return _c("cannot_verify:paediatric", "CR-PAEDIATRIC", msg)


def _range(
    ctx, d, drug: str, mg: float, freq: Any, cls: str, how: str, path: str
) -> tuple[list[Result], str]:
    probs: list[Result] = []
    note = ""
    if d.range_mg is None:
        if ctx.config.blank_range_fails_closed:
            probs.append(
                (
                    "flag",
                    _c(
                        "cannot_verify:no_range",
                        cls,
                        f"no verified range for {drug} in the lexicon (blank); fail-closed",
                    ),
                    f"{path}/dose_value",
                )
            )
        return probs, note
    lo, hi = d.range_mg
    if not (lo <= mg <= hi):
        probs.append(
            (
                "flag",
                _c(
                    "out_of_range",
                    cls,
                    f"dose {how} = {_fmt(mg)} mg is outside the lexicon range {_fmt(lo)}-{_fmt(hi)} mg for {drug} (lexicon: {d.verified_by[:120] or 'unverified'})",
                ),
                f"{path}/dose_value",
            )
        )
    elif d.strengths_mg and mg > max(d.strengths_mg):
        note = f"; unusual: above the typical strengths {'/'.join(_fmt(x) for x in d.strengths_mg)} mg (soft note)"
    if d.max_daily_mg is not None and freq is not None and mg * float(freq) > d.max_daily_mg:
        probs.append(
            (
                "flag",
                _c(
                    "exceeds_max_daily",
                    cls,
                    f"{_fmt(mg)} mg x {_fmt(freq)}/day = {_fmt(mg * float(freq))} mg exceeds the lexicon max daily {_fmt(d.max_daily_mg)} mg for {drug}",
                ),
                f"{path}/frequency_per_day",
            )
        )
    return probs, note


def c4_med(ctx, i: int, m: dict[str, Any], kids: list[str]) -> list[Result]:
    path = f"/medications/{i}"
    out = route_results(ctx, i, m)
    dv, du, drug, st = m["dose_value"], m["dose_unit"], m["drug"].casefold(), m["status"]
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
        return out
    if du is None:
        out.append(
            (
                "flag",
                _c("span_mismatch", "CR-DOSE", f"dose {_fmt(dv)} has no unit"),
                f"{path}/dose_unit",
            )
        )
        return out
    band = _band(ctx)
    paed = band in NON_ADULT or bool(kids)
    probs: list[Result] = []
    if paed:  # any dose, any status: never passed against an adult range
        probs.append(
            (
                "flag",
                _paediatric_reason(band, kids, ctx.record.get("weight_kg")),
                f"{path}/dose_value",
            )
        )
    s = _slice(ctx, m["evidence"])
    doses = parse_dose_phrases(s)
    if not any(_eq(d.value, dv) for d in doses):
        said = ", ".join(_fmt(d.value) + " " + str(d.unit) for d in doses) or "no dose phrase"
        probs.append(
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
        probs.append(
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
    if st not in RX_LIKE:
        out += probs
        out.append(
            (
                "n/a",
                f"status '{st}': not a prescription, so adult range, strength and unit checks are not applied (C3 checks the status)",
                f"{path}/dose_value",
            )
        )
        return out
    d = ctx.lexicon.drugs.get(drug)
    if d is None:
        probs.append(
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
        return out + probs
    allowed = ctx.config.units_for(drug, ctx.lexicon)
    if du not in allowed:
        cls = (
            "CR-ROUTE"
            if ctx.config.injection_only(drug, ctx.lexicon) and du not in MASS
            else "CR-DOSE"
        )
        probs.append(
            (
                "flag",
                _c(
                    "unit_not_allowed",
                    cls,
                    f"unit '{du}' is not an allowed unit for {drug} (allowed: {', '.join(allowed)}; source: {ctx.config.units_source(drug, ctx.lexicon)})",
                ),
                f"{path}/dose_unit",
            )
        )
    # ---- strength
    sv, su, form = m["strength_value"], m["strength_unit"], m["formulation"]
    fe = m.get("field_evidence", {})
    liquid = form in R.LIQUID_FORMS or du == "ml"
    s_cls = "CR-LIQUID-STRENGTH" if liquid else "CR-DOSE"
    strength_ok = False
    if sv is not None:
        found = R.parse_strengths(_slice(ctx, fe["strength"])) if "strength" in fe else []
        strength_ok = R.strength_key(sv, su) in {f.key for f in found}
        if not strength_ok:
            probs.append(
                (
                    "flag",
                    _c(
                        "span_mismatch",
                        s_cls,
                        f"strength {_fmt(sv)} {su} is not supported by its evidence span",
                    ),
                    f"{path}/strength_value",
                )
            )
    said_str = R.parse_strengths(s)
    mg, cls, how = None, "CR-DOSE", ""
    if du in MASS:
        mg, how = float(dv) * MASS[du], f"{_fmt(dv)} {du}"
    elif du == "ml":
        cls = "CR-LIQUID-STRENGTH"
        if sv is None:
            conc = [f for f in said_str if R.mg_per_ml(f.value, f.unit) is not None]
            if conc:
                probs.append(
                    (
                        "flag",
                        _c(
                            "strength_missing",
                            cls,
                            f"dose in ml with no strength in the record, but the span states {', '.join(f'{_fmt(f.value)} {f.unit}' for f in conc)}",
                        ),
                        f"{path}/strength_value",
                    )
                )
            else:
                probs.append(
                    (
                        "flag",
                        _c(
                            "cannot_verify:liquid_strength",
                            cls,
                            f"{form or 'liquid'} dose in ml and no strength (mg per ml) in the record or the span: the mg dose is unknown; fail-closed",
                        ),
                        f"{path}/dose_value",
                    )
                )
        elif strength_ok:
            per = R.mg_per_ml(sv, su)
            if per is None:
                probs.append(
                    (
                        "flag",
                        _c(
                            "cannot_verify:liquid_strength",
                            cls,
                            f"strength unit '{su}' cannot be converted to mg per ml",
                        ),
                        f"{path}/dose_value",
                    )
                )
            else:
                mg, how = float(dv) * per, f"{_fmt(dv)} ml x {_fmt(sv)} {su}"
    elif du in COUNT_UNITS:
        if sv is None:
            mass = [f for f in said_str if R.mg_per_unit(f.value, f.unit) is not None]
            if mass:
                probs.append(
                    (
                        "flag",
                        _c(
                            "strength_missing",
                            "CR-DOSE",
                            f"dose in '{du}' with no strength in the record, but the span states {', '.join(f'{_fmt(f.value)} {f.unit}' for f in mass)}",
                        ),
                        f"{path}/strength_value",
                    )
                )
            else:
                probs.append(
                    (
                        "flag",
                        _c(
                            "cannot_verify:count_unit",
                            "CR-DOSE",
                            f"no verified range for a dose in '{du}' (lexicon ranges are in mg and the strength per unit was not stated); fail-closed",
                        ),
                        f"{path}/dose_value",
                    )
                )
        elif strength_ok:
            per = R.mg_per_unit(sv, su)
            if per is None:
                probs.append(
                    (
                        "flag",
                        _c(
                            "cannot_verify:count_unit",
                            "CR-DOSE",
                            f"strength unit '{su}' is not a mass per {du}",
                        ),
                        f"{path}/dose_value",
                    )
                )
            else:
                mg, how = float(dv) * per, f"{_fmt(dv)} {du} x {_fmt(sv)} {su}"
    else:
        probs.append(
            (
                "flag",
                _c(
                    "cannot_verify:count_unit",
                    "CR-DOSE",
                    f"no verified range for a dose in '{du}' (lexicon ranges are in mg); fail-closed",
                ),
                f"{path}/dose_value",
            )
        )
    note = ""
    if mg is not None and not paed:  # the ADULT range is never applied to a child
        rp, note = _range(ctx, d, drug, mg, m["frequency_per_day"], cls, how, path)
        probs += rp
    if probs:
        return out + probs
    if d.range_mg is None:
        return [
            *out,
            (
                "n/a",
                f"{how} matches the span; no lexicon range (blank_range_fails_closed is off)",
                f"{path}/dose_value",
            ),
        ]
    lo, hi = d.range_mg
    return [
        *out,
        (
            "pass",
            f"{how} = {_fmt(mg)} mg matches the span and lies in {_fmt(lo)}-{_fmt(hi)} mg (adult range; age band '{band}', no child cue){note}",
            f"{path}/dose_value",
        ),
    ]


def c4(ctx) -> list[Result]:
    out: list[Result] = []
    kids = sorted(set(child_cues(ctx.text)))
    band = _band(ctx)
    if band in ("adult", "older_adult") and kids:
        out.append(
            (
                "flag",
                _c(
                    "age_band_conflict",
                    "CR-PAEDIATRIC",
                    f"record says '{band}' but the conversation has child cue(s) {kids}",
                ),
                "/patient_age_band",
            )
        )
    for i, _, m in _meds(ctx):
        out += c4_med(ctx, i, m, kids)
    return out or [("n/a", "record has no medications", "/")]


# =========================================================================== C8 helper
def inside_concentration(text: str, a: int, b: int) -> bool:
    """Is [a, b) inside a stated concentration ('120 mg/5 ml') of text? Used by C8 for v2 only."""
    return any(
        s.start <= a and b <= s.end and R.mg_per_ml(s.value, s.unit) is not None
        for s in R.parse_strengths(text)
    )


# =========================================================================== C5
def c5_extra(ctx) -> list[Result]:
    out: list[Result] = []
    for _, path, m in _meds(ctx):
        fe = m.get("field_evidence", {})
        around = _clause_text(ctx, [_bounds(m["evidence"])])
        p = f"{path}/as_needed"
        an = m["as_needed"]
        if an is None:
            cues = R.prn_cues(around)
            if cues:
                out.append(
                    (
                        "flag",
                        _c(
                            "as_needed_missing",
                            "MA-MED-ATTRIBUTE",
                            f"as_needed is null but the evidence clause says {cues}",
                        ),
                        p,
                    )
                )
            else:
                out.append(
                    (
                        "pass",
                        "as_needed not in record and no 'only if / when needed' word in the evidence clause",
                        p,
                    )
                )
        elif "as_needed" not in fe:
            out.append(_missing_span("as_needed", p))
        else:
            s = _slice(ctx, fe["as_needed"])
            prn, reg = R.prn_cues(s), R.regular_cues(s)
            ok = bool(prn) if an else (bool(reg) and not prn)
            if ok:
                out.append(("pass", f"as_needed {an} re-derived from the span ({prn or reg})", p))
            else:
                out.append(
                    (
                        "flag",
                        _c(
                            "as_needed_unsupported",
                            "MA-MED-ATTRIBUTE",
                            f"as_needed {an} not derivable from the span (prn words {prn or '-'}, regular words {reg or '-'})",
                        ),
                        p,
                    )
                )
        p = f"{path}/food_timing"
        ft = m["food_timing"]
        if ft is None:
            said = R.food_timings(around)
            if said:
                out.append(
                    (
                        "flag",
                        _c(
                            "food_timing_missing",
                            "MA-MED-ATTRIBUTE",
                            f"food_timing is null but the evidence clause says {sorted(said)}",
                        ),
                        p,
                    )
                )
            else:
                out.append(
                    ("pass", "food_timing not in record and none said in the evidence clause", p)
                )
        elif "food_timing" not in fe:
            out.append(_missing_span("food_timing", p))
        else:
            said = R.food_timings(_slice(ctx, fe["food_timing"]))
            if said == {ft}:
                out.append(("pass", f"food_timing '{ft}' re-derived from the span", p))
            else:
                out.append(
                    (
                        "flag",
                        _c(
                            "food_timing_unsupported",
                            "MA-MED-ATTRIBUTE",
                            f"food_timing '{ft}' not derivable from the span (span says {sorted(said) or 'nothing'})",
                        ),
                        p,
                    )
                )
    return out
