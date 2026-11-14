"""Scoring of record.v2 against gold.v2 (docs/severity.md, mapping note of 2026-11-12).

The v1 fields are scored exactly as scoring.py does (gold.v2 keeps every v1 key). The NEW fields
are scored per matched medication (matched by drug, as in v1) and per record:
  route                       mismatch -> CR-ROUTE
  formulation                 injection vs non-injection -> CR-ROUTE, any other mismatch MA-MED-ATTRIBUTE
  strength (value + unit)     mismatch (incl. missing when gold has one) -> CR-LIQUID-STRENGTH
  status                      flips given vs not given -> CR-NEG, other mismatch -> MA-STATUS
  as_needed, food_timing, speaker, weight_kg   mismatch -> MA-MED-ATTRIBUTE
  patient_age_band            gold non-adult and record null/adult, with a dosed medication
                              -> CR-PAEDIATRIC; any other mismatch MA-MED-ATTRIBUTE
A missed medication is one error in v1 (MA-MISSED-DRUG); its new fields are not counted again.
Uncertainty: Wilson 95% CI per 1,000 fields, and a per-template cluster bootstrap (templates are
the unit of resampling, because the 8 conversations of one template are near copies).
Everything on DEV is in-sample: the rules were written looking at DEV.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from m3_extract.scoring import FieldResult, _eq, score_record, wilson

GIVEN = {"prescribed", "already_taken", "continue_existing"}
NOT_GIVEN = {"not_taken", "advised_against"}
NEW_MED_FIELDS = (
    "route",
    "formulation",
    "strength",
    "status",
    "as_needed",
    "food_timing",
    "speaker",
)
NEW_RECORD_FIELDS = ("patient_age_band", "weight_kg")
NEW_FIELDS = NEW_MED_FIELDS + NEW_RECORD_FIELDS


def _val(med: dict, field: str):
    if field == "strength":
        v = med.get("strength_value")
        return None if v is None else (v, med.get("strength_unit"))
    return med.get(field)


def _status_code(g, p) -> str | None:
    if g == p:
        return None
    if (g in GIVEN and p in NOT_GIVEN) or (g in NOT_GIVEN and p in GIVEN):
        return "CR-NEG"
    return "MA-STATUS"


def _code(field: str, g, p) -> str | None:
    if field == "status":
        return _status_code(g, p)
    if field == "strength":
        same = (g is None and p is None) or (
            g is not None and p is not None and _eq(g[0], p[0]) and g[1] == p[1]
        )
        return None if same else "CR-LIQUID-STRENGTH"
    if _eq(g, p):
        return None
    if field == "route":
        return "CR-ROUTE"
    if field == "formulation" and "injection" in (g, p):
        return "CR-ROUTE"
    return "MA-MED-ATTRIBUTE"


def score_new_fields(pred: dict | None, gold: dict) -> list[FieldResult]:
    cid = gold["conversation_id"]
    gr = gold["gold_record"]
    pred = pred or {"medications": [], "patient_age_band": None, "weight_kg": None}
    out: list[FieldResult] = []
    used: set[int] = set()
    pm = list(pred.get("medications") or [])
    for g in gr["medications"]:
        j = next((j for j, p in enumerate(pm) if j not in used and p["drug"] == g["drug"]), None)
        if j is None:
            continue  # missed drug: already one MA-MISSED-DRUG error in v1
        used.add(j)
        for f in NEW_MED_FIELDS:
            gv, pv = _val(g, f), _val(pm[j], f)
            out.append(FieldResult(cid, "medication", g["drug"], f, _code(f, gv, pv), gv, pv))
    ga = (gr.get("patient_age_band") or {}).get("band")
    pa = (pred.get("patient_age_band") or {}).get("band")
    dosed = any(m["dose_value"] is not None for m in gr["medications"])
    code = None
    if ga != pa:
        code = (
            "CR-PAEDIATRIC"
            if ga in ("infant", "child", "adolescent") and pa in (None, "adult") and dosed
            else "MA-MED-ATTRIBUTE"
        )
    out.append(FieldResult(cid, "record", "-", "patient_age_band", code, ga, pa))
    gw = (gr.get("weight_kg") or {}).get("value")
    pw = (pred.get("weight_kg") or {}).get("value")
    out.append(
        FieldResult(
            cid, "record", "-", "weight_kg", None if _eq(gw, pw) else "MA-MED-ATTRIBUTE", gw, pw
        )
    )
    return out


def score_record_v2(pred, gold, *, offsets_comparable: bool = True):
    """(v1 field results, new-field results)."""
    return score_record(pred, gold, offsets_comparable=offsets_comparable), score_new_fields(
        pred, gold
    )


def _rate(k: int, n: int) -> float | None:
    return None if n == 0 else 1000 * k / n


def template_of(cid: str) -> str:
    return cid.split("-")[1]


def bootstrap_ci(
    results: list[FieldResult], select, *, reps: int = 2000, seed: int = 20261112
) -> tuple[float | None, float | None]:
    """Percentile 95% CI of errors per 1,000 fields, resampling TEMPLATES with replacement."""
    by_t: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in results:
        t = template_of(r.conversation_id)
        by_t[t][1] += 1
        by_t[t][0] += bool(r.code and select(r))
    keys = sorted(by_t)
    if not keys:
        return None, None
    rng = random.Random(seed)  # noqa: S311 (resampling, not crypto)
    rates = []
    for _ in range(reps):
        k = n = 0
        for t in (rng.choice(keys) for _ in keys):
            k += by_t[t][0]
            n += by_t[t][1]
        if n:
            rates.append(1000 * k / n)
    rates.sort()
    return rates[int(0.025 * len(rates))], rates[min(len(rates) - 1, int(0.975 * len(rates)))]


def summarise(results: list[FieldResult], label: str, scope: str) -> list[dict[str, Any]]:
    """Rows: one per field and one per severity class and per code, with N, Wilson and bootstrap."""
    rows = []

    def row(kind, name, sel_n, sel_err):
        n = sum(1 for r in results if sel_n(r))
        k = sum(1 for r in results if sel_n(r) and r.code and sel_err(r))
        lo, hi = wilson(k, n)
        blo, bhi = bootstrap_ci([r for r in results if sel_n(r)], sel_err)
        rows.append(
            {
                "pipeline": label,
                "scope": scope,
                "kind": kind,
                "name": name,
                "n_fields": n,
                "n_gold_non_null": sum(1 for r in results if sel_n(r) and r.gold is not None),
                "errors": k,
                "per_1000": _rate(k, n),
                "wilson_lo": None if lo is None else 1000 * lo,
                "wilson_hi": None if hi is None else 1000 * hi,
                "boot_template_lo": blo,
                "boot_template_hi": bhi,
            }
        )

    row("all", "all fields", lambda r: True, lambda r: True)
    for sev in ("critical", "major", "minor"):
        row("severity", sev, lambda r: True, lambda r, s=sev: r.severity == s)
    for code in sorted({r.code for r in results if r.code}):
        row("code", code, lambda r: True, lambda r, c=code: r.code == c)
    for f in sorted({(r.kind, r.field) for r in results}):
        row("field", f"{f[0]}.{f[1]}", lambda r, f=f: (r.kind, r.field) == f, lambda r: True)
    return rows
