"""Field-level scoring of an extracted record against gold, by severity (docs/severity.md).

m7's own implementation (m7 may not import m3_extract). The FIELD unit follows the one
documented in m3_extract/scoring.py so the numbers are comparable: medication 6 fields
(drug, dose_value, dose_unit, frequency_per_day, duration_days, negated), symptom 2 (name,
present), advice 2 (text, negated), follow-up 1 per record; patient_ref and encounter_type are
supplied context and NOT scored. A missed item is ONE error (its other fields stay in the
denominator); an extra item adds ONE field and ONE error.

record.v2 + gold.v2 (both needed) add, per the severity.md v2 mapping note: medication route,
strength (value+unit as one field), formulation, as_needed, food_timing, status, speaker; and
per record patient_age_band and weight_kg. With record.v1 or gold.v1 the classes CR-ROUTE,
CR-PAEDIATRIC and CR-LIQUID-STRENGTH are NOT MEASURABLE (never reported as zero).

Codes beyond severity.md (marked * in tables; rule 5: when unsure, MAJOR):
MA-MISSED-ADVICE*, MA-EXTRA-ADVICE*, MA-MISSED-FOLLOWUP*, MA-EXTRA-FOLLOWUP*,
MA-WORDING-UNJUDGED* (advice/follow-up text differs; a human must judge MI-WORDING).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from m7_eval import stats

MED_FIELDS = ("dose_value", "dose_unit", "frequency_per_day", "duration_days", "negated")
MED_CODE = {
    "dose_value": "CR-DOSE",
    "dose_unit": "CR-DOSE",
    "frequency_per_day": "CR-FREQ",
    "duration_days": "CR-DUR",
    "negated": "CR-NEG",
}
V2_MED_FIELDS = (
    "route",
    "strength",
    "formulation",
    "as_needed",
    "food_timing",
    "status",
    "speaker",
)
V2_CLASSES = ("CR-LIQUID-STRENGTH", "CR-PAEDIATRIC", "CR-ROUTE")
GIVEN = {"prescribed", "already_taken", "continue_existing"}
NOT_GIVEN = {"not_taken", "advised_against"}
LIQUID = {"syrup", "suspension", "drops"}
NON_ADULT = {"infant", "child", "adolescent"}
SEVERITY = {"CR": "critical", "MA": "major", "MI": "minor"}


@dataclass
class FieldResult:
    conversation_id: str
    kind: str
    item: str
    field: str
    code: str | None
    gold: Any = None
    pred: Any = None
    detail: str = ""
    turn: int | None = None  # turn index of the gold span (None for extra items)

    @property
    def severity(self) -> str | None:
        return SEVERITY[self.code[:2]] if self.code else None


def _eq(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return math.isclose(float(a), float(b), abs_tol=1e-9)
    return a == b


def _norm(s: str) -> str:
    return " ".join(s.casefold().split())


def _overlap(ev: dict | None, gs: dict | None) -> bool:
    if not ev or not gs:
        return False
    return ev["char_start"] < gs["char_end"] and gs["char_start"] < ev["char_end"]


def is_v2(doc: dict | None) -> bool:
    return bool(doc) and str(doc.get("schema_version", "")).endswith(".v2")


def measurable_v2(rec: dict | None, gold: dict) -> bool:
    return is_v2(rec) and is_v2(gold)


# ------------------------------------------------------------------ v2 field rules
def _v2_med_code(f: str, g: dict, p: dict) -> str | None:
    if f == "strength":
        gs, ps = (
            (g.get("strength_value"), g.get("strength_unit")),
            (
                p.get("strength_value"),
                p.get("strength_unit"),
            ),
        )
        if _eq(gs[0], ps[0]) and gs[1] == ps[1]:
            return None
        return "CR-LIQUID-STRENGTH" if gs[0] is not None else "MA-MED-ATTRIBUTE"
    gv, pv = g.get(f), p.get(f)
    if _eq(gv, pv):
        return None
    if f == "route":
        return "CR-ROUTE"
    if f == "formulation":
        inj = {gv, pv} & {"injection"}
        return "CR-ROUTE" if inj and None not in (gv, pv) else "MA-MED-ATTRIBUTE"
    if f == "status":
        flip = (gv in GIVEN and pv in NOT_GIVEN) or (gv in NOT_GIVEN and pv in GIVEN)
        return "CR-NEG" if flip else "MA-STATUS"
    return "MA-MED-ATTRIBUTE"


def _age_code(gr: dict, pred: dict) -> str | None:
    gb = (gr.get("patient_age_band") or {}).get("band")
    pb = (pred.get("patient_age_band") or {}).get("band")
    if gb == pb:
        return None
    dosed = any(m.get("dose_value") is not None for m in gr.get("medications", []))
    if gb in NON_ADULT and pb in (None, "adult", "older_adult", "unknown") and dosed:
        return "CR-PAEDIATRIC"
    return "MA-MED-ATTRIBUTE"


# ------------------------------------------------------------------ main scorer
def score_record(
    pred: dict | None, gold: dict, *, offsets_comparable: bool = True
) -> list[FieldResult]:
    """Compare one record (None = missing/rejected) with its gold document."""
    cid = gold["conversation_id"]
    gr = gold["gold_record"]
    v2 = measurable_v2(pred, gold)
    pred = pred or {"symptoms": [], "medications": [], "advice": [], "follow_up": None}
    out: list[FieldResult] = []
    cur: dict[str, int | None] = {"t": None}

    def add(r: FieldResult) -> None:
        r.turn = cur["t"]
        out.append(r)

    def at(g: dict | None) -> None:
        cur["t"] = (g or {}).get("gold_span", {}).get("turn_index") if g else None

    # medications
    gm, pm = list(gr["medications"]), list(pred.get("medications") or [])
    gold_drugs = {g["drug"] for g in gm}
    used: set[int] = set()
    pairs: list[list[Any]] = []
    for g in gm:
        j = next((j for j, p in enumerate(pm) if j not in used and p["drug"] == g["drug"]), None)
        if j is not None:
            used.add(j)
        pairs.append([g, pm[j] if j is not None else None, False])
    if offsets_comparable:
        for pair in pairs:
            if pair[1] is None:
                j = next(
                    (
                        j
                        for j, q in enumerate(pm)
                        if j not in used
                        and q["drug"] not in gold_drugs
                        and _overlap(q.get("evidence"), pair[0].get("gold_span"))
                    ),
                    None,
                )
                if j is not None:
                    used.add(j)
                    pair[1], pair[2] = pm[j], True
    extra_fields = V2_MED_FIELDS if v2 else ()
    for g, p, wrong in pairs:
        at(g)
        name = g["drug"]
        if p is None:
            add(FieldResult(cid, "medication", name, "drug", "MA-MISSED-DRUG", name, None))
            for f in MED_FIELDS + extra_fields:
                add(FieldResult(cid, "medication", name, f, None, detail="item missed"))
            continue
        add(
            FieldResult(
                cid, "medication", name, "drug", "CR-DRUG" if wrong else None, name, p["drug"]
            )
        )
        for f in MED_FIELDS:
            code = None if _eq(g[f], p.get(f)) else MED_CODE[f]
            add(FieldResult(cid, "medication", name, f, code, g[f], p.get(f)))
        for f in extra_fields:
            add(FieldResult(cid, "medication", name, f, _v2_med_code(f, g, p), g.get(f), p.get(f)))
    for j, p in enumerate(pm):
        if j in used:
            continue
        g = next((g for g in gm if g["drug"] == p["drug"]), None)
        at(g)
        if g is None:
            add(
                FieldResult(cid, "medication", p["drug"], "drug", "CR-UNSUPPORTED", None, p["drug"])
            )
        else:  # duplicate entry for a spoken drug: every field must still agree
            add(FieldResult(cid, "medication", p["drug"], "drug", None, detail="duplicate"))
            for f in MED_FIELDS:
                code = None if _eq(g[f], p.get(f)) else MED_CODE[f]
                add(FieldResult(cid, "medication", p["drug"], f, code, g[f], p.get(f), "duplicate"))

    # symptoms
    gs, ps = list(gr["symptoms"]), list(pred.get("symptoms") or [])
    used = set()
    for g in gs:
        at(g)
        j = next((j for j, p in enumerate(ps) if j not in used and p["name"] == g["name"]), None)
        if j is None:
            add(FieldResult(cid, "symptom", g["name"], "name", "MA-MISSED-SYMPTOM", g["name"]))
            add(FieldResult(cid, "symptom", g["name"], "present", None, detail="item missed"))
            continue
        used.add(j)
        p = ps[j]
        add(FieldResult(cid, "symptom", g["name"], "name", None, g["name"], p["name"]))
        code = None if p["present"] == g["present"] else "CR-NEG"
        add(FieldResult(cid, "symptom", g["name"], "present", code, g["present"], p["present"]))
    for j, p in enumerate(ps):
        if j in used:
            continue
        g = next((g for g in gs if g["name"] == p["name"]), None)
        at(g)
        if g is None:
            add(FieldResult(cid, "symptom", p["name"], "name", "MA-EXTRA-SYMPTOM", None, p["name"]))
        else:
            add(FieldResult(cid, "symptom", p["name"], "name", None, detail="duplicate"))
            code = None if p["present"] == g["present"] else "CR-NEG"
            add(FieldResult(cid, "symptom", p["name"], "present", code, g["present"], p["present"]))

    # advice
    ga, pa = list(gr["advice"]), list(pred.get("advice") or [])
    used = set()
    apairs: list[list[Any]] = []
    for g in ga:
        j = next(
            (j for j, p in enumerate(pa) if j not in used and _norm(p["text"]) == _norm(g["text"])),
            None,
        )
        if j is not None:
            used.add(j)
        apairs.append([g, pa[j] if j is not None else None])
    if offsets_comparable:
        for pair in apairs:
            if pair[1] is None:
                j = next(
                    (
                        j
                        for j, q in enumerate(pa)
                        if j not in used and _overlap(q.get("evidence"), pair[0].get("gold_span"))
                    ),
                    None,
                )
                if j is not None:
                    used.add(j)
                    pair[1] = pa[j]
    for g, p in apairs:
        at(g)
        if p is None:
            add(FieldResult(cid, "advice", g["text"], "text", "MA-MISSED-ADVICE", g["text"]))
            add(FieldResult(cid, "advice", g["text"], "negated", None, detail="item missed"))
            continue
        same = _norm(p["text"]) == _norm(g["text"])
        add(
            FieldResult(
                cid,
                "advice",
                g["text"],
                "text",
                None if same else "MA-WORDING-UNJUDGED",
                g["text"],
                p["text"],
            )
        )
        code = None if p["negated"] == g["negated"] else "CR-NEG"
        add(FieldResult(cid, "advice", g["text"], "negated", code, g["negated"], p["negated"]))
    at(None)
    for j, p in enumerate(pa):
        if j not in used:
            add(FieldResult(cid, "advice", p["text"], "text", "MA-EXTRA-ADVICE", None, p["text"]))

    # follow-up
    gf, pf = gr.get("follow_up"), pred.get("follow_up")
    at(gf)
    if gf is None and pf is None:
        add(FieldResult(cid, "follow_up", "-", "text", None))
    elif gf is None:
        add(FieldResult(cid, "follow_up", "-", "text", "MA-EXTRA-FOLLOWUP", None, pf["text"]))
    elif pf is None:
        add(FieldResult(cid, "follow_up", gf["text"], "text", "MA-MISSED-FOLLOWUP", gf["text"]))
    else:
        same = _norm(pf["text"]) == _norm(gf["text"])
        add(
            FieldResult(
                cid,
                "follow_up",
                gf["text"],
                "text",
                None if same else "MA-WORDING-UNJUDGED",
                gf["text"],
                pf["text"],
            )
        )

    # record-level v2 fields
    if v2:
        at(gr.get("patient_age_band"))
        add(
            FieldResult(
                cid,
                "record",
                "-",
                "patient_age_band",
                _age_code(gr, pred),
                (gr.get("patient_age_band") or {}).get("band"),
                (pred.get("patient_age_band") or {}).get("band"),
            )
        )
        gw = (gr.get("weight_kg") or {}).get("value")
        pw = (pred.get("weight_kg") or {}).get("value")
        add(
            FieldResult(
                cid, "record", "-", "weight_kg", None if _eq(gw, pw) else "MA-MED-ATTRIBUTE", gw, pw
            )
        )
    return out


# ------------------------------------------------------------------ aggregation
ITEM_KINDS = ("medication", "symptom", "advice", "follow_up")
FN_CODES = {"MA-MISSED-DRUG", "MA-MISSED-SYMPTOM", "MA-MISSED-ADVICE", "MA-MISSED-FOLLOWUP"}
FP_CODES = {"CR-UNSUPPORTED", "MA-EXTRA-SYMPTOM", "MA-EXTRA-ADVICE", "MA-EXTRA-FOLLOWUP"}
ITEM_FIELD = {"medication": "drug", "symptom": "name", "advice": "text", "follow_up": "text"}


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p is not None and r is not None and (p + r) > 0 else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f1}


def item_counts(results: list[FieldResult]) -> dict[str, tuple[int, int, int]]:
    """Per item kind (tp, fp, fn). A wrong drug (CR-DRUG) counts as one FP and one FN.
    Duplicates and an empty follow-up (gold None, pred None) are neither."""
    c: dict[str, list[int]] = {k: [0, 0, 0] for k in ITEM_KINDS}
    for r in results:
        if r.field != ITEM_FIELD[r.kind] or r.kind not in c or r.detail == "duplicate":
            continue
        if r.code in FN_CODES:
            c[r.kind][2] += 1
        elif r.code in FP_CODES:
            c[r.kind][1] += 1
        elif r.code == "CR-DRUG":
            c[r.kind][1] += 1
            c[r.kind][2] += 1
        elif r.gold is not None or r.code == "MA-WORDING-UNJUDGED":
            c[r.kind][0] += 1
    return {k: tuple(v) for k, v in c.items()}


def summarise(
    per_conv: list[tuple[str, list[FieldResult]]], *, v2: bool, seed: int = 20261109
) -> dict:
    """Aggregate [(cluster_id, results)] -> severity rates with Wilson AND cluster-bootstrap
    CIs (cluster = template family, the PRIMARY CI), per-code counts and item P/R/F1."""
    sev_cluster: dict[str, dict[str, list[int]]] = {
        s: defaultdict(lambda: [0, 0]) for s in ("critical", "major", "minor", "any")
    }
    codes: dict[str, int] = defaultdict(int)
    items = {k: [0, 0, 0] for k in ITEM_KINDS}
    item_cluster: dict[str, dict[str, list[int]]] = {
        k: defaultdict(lambda: [0, 0, 0]) for k in ITEM_KINDS
    }
    for cl, res in per_conv:
        n = len(res)
        for s in sev_cluster:
            sev_cluster[s][cl][1] += n
        for r in res:
            if r.code:
                codes[r.code] += 1
                sev_cluster[r.severity][cl][0] += 1
                sev_cluster["any"][cl][0] += 1
        for k, (tp, fp, fn) in item_counts(res).items():
            for i, v in enumerate((tp, fp, fn)):
                items[k][i] += v
                item_cluster[k][cl][i] += v
    severity = {}
    for s, by in sev_cluster.items():
        k = sum(v[0] for v in by.values())
        n = sum(v[1] for v in by.values())
        row = stats.per_1000(k, n)
        lo, hi = stats.cluster_bootstrap_rate({c: tuple(v) for c, v in by.items()}, seed=seed)
        row["cluster_lo_per_1000"] = None if lo is None else 1000 * lo
        row["cluster_hi_per_1000"] = None if hi is None else 1000 * hi
        row["n_clusters"] = len(by)
        row["rule_of_three_per_1000"] = 3000 / n if (k == 0 and n) else None
        severity[s] = row
    item_rows = {}
    for kind, (tp, fp, fn) in items.items():
        row = _prf(tp, fp, fn)
        # cluster CIs for precision (tp of tp+fp) and recall (tp of tp+fn)
        cl = item_cluster[kind]
        p_lo, p_hi = stats.cluster_bootstrap_rate(
            {c: (v[0], v[0] + v[1]) for c, v in cl.items()}, seed=seed
        )
        r_lo, r_hi = stats.cluster_bootstrap_rate(
            {c: (v[0], v[0] + v[2]) for c, v in cl.items()}, seed=seed
        )
        row.update(precision_cluster_lo=p_lo, precision_cluster_hi=p_hi)
        row.update(recall_cluster_lo=r_lo, recall_cluster_hi=r_hi)
        row["precision_wilson"] = stats.wilson(tp, tp + fp)
        row["recall_wilson"] = stats.wilson(tp, tp + fn)
        item_rows[kind] = row
    return {
        "severity": severity,
        "codes": dict(sorted(codes.items())),
        "items": item_rows,
        "not_measurable": [] if v2 else list(V2_CLASSES),
        "n_records": len(per_conv),
    }
