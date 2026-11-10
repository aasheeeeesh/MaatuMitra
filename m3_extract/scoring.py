"""Field-level scoring of record.v1 against gold.v1 by severity class (docs/severity.md).

A FIELD is one scalar slot of a gold item: medication 6 (drug, dose_value, dose_unit,
frequency_per_day, duration_days, negated), symptom 2 (name, present), advice 2 (text, negated),
follow-up 1 per record. patient_ref / encounter_type are encounter context (supplied, not
extracted) and are NOT scored. A missed item is ONE error (its other fields stay in the
denominator); an extra item adds ONE field and ONE error. A rejected record (failed evidence
check) is scored as an empty record and counted separately.

Codes (severity.md + extensions marked *, see handoff/decisions.md):
  critical: CR-NEG CR-DRUG CR-DOSE CR-FREQ CR-DUR CR-UNSUPPORTED
  major:    MA-MISSED-SYMPTOM MA-EXTRA-SYMPTOM MA-MISSED-DRUG
            MA-WORDING-UNJUDGED* (advice/follow-up text differs; severity rule 5: unsure -> MAJOR)
            MA-MISSED-ADVICE* MA-EXTRA-ADVICE* MA-MISSED-FOLLOWUP* MA-EXTRA-FOLLOWUP*
  minor:    MI-FORMAT (unused so far)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

Z = 1.959964
MED_FIELDS = ("dose_value", "dose_unit", "frequency_per_day", "duration_days", "negated")
MED_CODE = {
    "dose_value": "CR-DOSE",
    "dose_unit": "CR-DOSE",
    "frequency_per_day": "CR-FREQ",
    "duration_days": "CR-DUR",
    "negated": "CR-NEG",
}


def severity_of(code: str | None) -> str | None:
    if code is None:
        return None
    return {"CR": "critical", "MA": "major", "MI": "minor"}[code[:2]]


def wilson(k: int, n: int, z: float = Z) -> tuple[float | None, float | None]:
    """Wilson 95% interval for k/n. centre = (p + z^2/2n)/(1 + z^2/n);
    half = z*sqrt(p(1-p)/n + z^2/(4n^2))/(1 + z^2/n)."""
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


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
    evidence_overlap: bool | None = None

    @property
    def severity(self) -> str | None:
        return severity_of(self.code)


def _overlap(ev: dict | None, gs: dict | None) -> bool:
    if not ev or not gs:
        return False
    return ev["char_start"] < gs["char_end"] and gs["char_start"] < ev["char_end"]


def _eq(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return math.isclose(float(a), float(b), abs_tol=1e-9)
    return a == b


def _norm_text(s: str) -> str:
    return " ".join(s.casefold().split())


def score_record(
    pred: dict[str, Any] | None, gold: dict[str, Any], *, offsets_comparable: bool = True
) -> list[FieldResult]:
    """Compare one predicted record (None = rejected/missing) with its gold.v1 document.
    offsets_comparable: True when the record was extracted from the GOLD transcript (same text),
    so evidence offsets can be compared with gold spans."""
    cid = gold["conversation_id"]
    gr = gold["gold_record"]
    pred = pred or {"symptoms": [], "medications": [], "advice": [], "follow_up": None}
    out: list[FieldResult] = []

    def ov(p, g):
        return _overlap(p.get("evidence"), g.get("gold_span")) if offsets_comparable else None

    # ---------------- medications
    gm, pm = list(gr["medications"]), list(pred.get("medications") or [])
    gold_drugs = {g["drug"] for g in gm}
    used: set[int] = set()
    pairs: list[tuple[dict, dict | None, bool]] = []
    for g in gm:
        j = next((j for j, p in enumerate(pm) if j not in used and p["drug"] == g["drug"]), None)
        if j is not None:
            used.add(j)
        pairs.append((g, pm[j] if j is not None else None, False))
    for k, (g, p, _) in enumerate(pairs):
        if p is None and offsets_comparable:
            j = next(
                (
                    j
                    for j, q in enumerate(pm)
                    if j not in used
                    and q["drug"] not in gold_drugs
                    and _overlap(q.get("evidence"), g["gold_span"])
                ),
                None,
            )
            if j is not None:
                used.add(j)
                pairs[k] = (g, pm[j], True)
    for g, p, wrong in pairs:
        name = g["drug"]
        if p is None:
            out.append(
                FieldResult(
                    cid,
                    "medication",
                    name,
                    "drug",
                    "MA-MISSED-DRUG",
                    name,
                    None,
                    "drug not in record",
                )
            )
            out += [
                FieldResult(
                    cid, "medication", name, f, None, g[f], None, "item missed (counted once)"
                )
                for f in MED_FIELDS
            ]
            continue
        out.append(
            FieldResult(
                cid,
                "medication",
                name,
                "drug",
                "CR-DRUG" if wrong else None,
                name,
                p["drug"],
                evidence_overlap=ov(p, g),
            )
        )
        for f in MED_FIELDS:
            ok = _eq(g[f], p.get(f))
            out.append(
                FieldResult(cid, "medication", name, f, None if ok else MED_CODE[f], g[f], p.get(f))
            )
    for j, p in enumerate(pm):
        if j in used:
            continue
        g = next((g for g in gm if g["drug"] == p["drug"]), None)
        if g is None:
            out.append(
                FieldResult(
                    cid,
                    "medication",
                    p["drug"],
                    "drug",
                    "CR-UNSUPPORTED",
                    None,
                    p["drug"],
                    "drug in record but not in gold",
                )
            )
        else:  # duplicate entry for a spoken drug: every field must still agree
            out.append(
                FieldResult(
                    cid,
                    "medication",
                    p["drug"],
                    "drug",
                    None,
                    g["drug"],
                    p["drug"],
                    "duplicate entry",
                )
            )
            for f in MED_FIELDS:
                ok = _eq(g[f], p.get(f))
                out.append(
                    FieldResult(
                        cid,
                        "medication",
                        p["drug"],
                        f,
                        None if ok else MED_CODE[f],
                        g[f],
                        p.get(f),
                        "duplicate entry",
                    )
                )

    # ---------------- symptoms
    gs, ps = list(gr["symptoms"]), list(pred.get("symptoms") or [])
    used = set()
    for g in gs:
        j = next((j for j, p in enumerate(ps) if j not in used and p["name"] == g["name"]), None)
        if j is None:
            out.append(
                FieldResult(cid, "symptom", g["name"], "name", "MA-MISSED-SYMPTOM", g["name"], None)
            )
            out.append(
                FieldResult(
                    cid,
                    "symptom",
                    g["name"],
                    "present",
                    None,
                    g["present"],
                    None,
                    "item missed (counted once)",
                )
            )
            continue
        used.add(j)
        p = ps[j]
        out.append(
            FieldResult(
                cid,
                "symptom",
                g["name"],
                "name",
                None,
                g["name"],
                p["name"],
                evidence_overlap=ov(p, g),
            )
        )
        out.append(
            FieldResult(
                cid,
                "symptom",
                g["name"],
                "present",
                None if p["present"] == g["present"] else "CR-NEG",
                g["present"],
                p["present"],
            )
        )
    for j, p in enumerate(ps):
        if j in used:
            continue
        g = next((g for g in gs if g["name"] == p["name"]), None)
        if g is None:
            out.append(
                FieldResult(cid, "symptom", p["name"], "name", "MA-EXTRA-SYMPTOM", None, p["name"])
            )
        else:
            out.append(
                FieldResult(
                    cid, "symptom", p["name"], "name", None, g["name"], p["name"], "duplicate entry"
                )
            )
            out.append(
                FieldResult(
                    cid,
                    "symptom",
                    p["name"],
                    "present",
                    None if p["present"] == g["present"] else "CR-NEG",
                    g["present"],
                    p["present"],
                    "duplicate entry",
                )
            )

    # ---------------- advice
    ga, pa = list(gr["advice"]), list(pred.get("advice") or [])
    used = set()
    apairs: list[tuple[dict, dict | None]] = []
    for g in ga:
        j = next(
            (
                j
                for j, p in enumerate(pa)
                if j not in used and _norm_text(p["text"]) == _norm_text(g["text"])
            ),
            None,
        )
        if j is not None:
            used.add(j)
        apairs.append((g, pa[j] if j is not None else None))
    for k, (g, p) in enumerate(apairs):
        if p is None and offsets_comparable:
            j = next(
                (
                    j
                    for j, q in enumerate(pa)
                    if j not in used and _overlap(q.get("evidence"), g["gold_span"])
                ),
                None,
            )
            if j is not None:
                used.add(j)
                apairs[k] = (g, pa[j])
    for g, p in apairs:
        if p is None:
            out.append(
                FieldResult(cid, "advice", g["text"], "text", "MA-MISSED-ADVICE", g["text"], None)
            )
            out.append(
                FieldResult(
                    cid,
                    "advice",
                    g["text"],
                    "negated",
                    None,
                    g["negated"],
                    None,
                    "item missed (counted once)",
                )
            )
            continue
        same = _norm_text(p["text"]) == _norm_text(g["text"])
        out.append(
            FieldResult(
                cid,
                "advice",
                g["text"],
                "text",
                None if same else "MA-WORDING-UNJUDGED",
                g["text"],
                p["text"],
                evidence_overlap=ov(p, g),
            )
        )
        out.append(
            FieldResult(
                cid,
                "advice",
                g["text"],
                "negated",
                None if p["negated"] == g["negated"] else "CR-NEG",
                g["negated"],
                p["negated"],
            )
        )
    for j, p in enumerate(pa):
        if j not in used:
            out.append(
                FieldResult(cid, "advice", p["text"], "text", "MA-EXTRA-ADVICE", None, p["text"])
            )

    # ---------------- follow-up
    gf, pf = gr.get("follow_up"), pred.get("follow_up")
    if gf is None and pf is None:
        out.append(FieldResult(cid, "follow_up", "-", "text", None))
    elif gf is None:
        out.append(
            FieldResult(cid, "follow_up", "-", "text", "MA-EXTRA-FOLLOWUP", None, pf["text"])
        )
    elif pf is None:
        out.append(
            FieldResult(
                cid, "follow_up", gf["text"], "text", "MA-MISSED-FOLLOWUP", gf["text"], None
            )
        )
    else:
        same = _norm_text(pf["text"]) == _norm_text(gf["text"])
        out.append(
            FieldResult(
                cid,
                "follow_up",
                gf["text"],
                "text",
                None if same else "MA-WORDING-UNJUDGED",
                gf["text"],
                pf["text"],
                evidence_overlap=ov(pf, gf),
            )
        )
    return out


def aggregate(results: list[FieldResult]) -> list[dict[str, Any]]:
    """Errors per 1,000 fields per severity class, with Wilson 95% CI and N."""
    n = len(results)
    n_rec = len({r.conversation_id for r in results})
    rows = []
    for sev in ("critical", "major", "minor", "any"):
        k = sum(1 for r in results if r.code and (sev == "any" or r.severity == sev))
        lo, hi = wilson(k, n)
        rows.append(
            {
                "severity": sev,
                "n_records": n_rec,
                "n_fields": n,
                "errors": k,
                "per_1000": (1000 * k / n) if n else None,
                "ci_low_per_1000": None if lo is None else 1000 * lo,
                "ci_high_per_1000": None if hi is None else 1000 * hi,
            }
        )
    return rows
