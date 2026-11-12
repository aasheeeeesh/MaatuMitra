"""gold.v2 labels (D-122, D-125..D-130), derived from the TEMPLATES - never guessed from the text.

Every template medication item may carry these metadata keys (see data/templates/README.md):
    status | status_neg + status_pos   which status; the _neg/_pos pair is picked by the item's
                                       negation slot (answer "ಇಲ್ಲ" -> not_taken, "ಹೌದು" -> already_taken)
    status_span                        marker id of the words that say it (a verb, the answer, ...)
    formulation + formulation_span     explicit (literal ಸಿರಪ್ / ಮಾತ್ರೆ / injection in the template)
    route + route_span                 explicit; otherwise derived from the formulation
    as_needed + as_needed_span, food_timing + food_span, strength {value, unit} + strength_span
Without an explicit formulation, the form word of the drug slot's dose text (ಮಾತ್ರೆ, ಕ್ಯಾಪ್ಸೂಲ್,
ಪ್ಯಾಕೆಟ್, ಇಂಜೆಕ್ಷನ್) supplies it: the renderer reports its span as "<slot>.form".
Marker "g1" in a template = the word for child (ಮಗು...) = patient_age_band child.

Nothing is inferred beyond that: no marker = no label (null), and a non-null label without an
evidence span is a template bug (ValueError), because the contract demands one.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from contracts.validate import SPEAKER_FROM_ROLE
from m1_data.render import FORMULATION_OF_WORD

STATUSES = {
    "prescribed",
    "already_taken",
    "not_taken",
    "advised_against",
    "stopped_early",
    "continue_existing",
    "unknown",
}
ITEM_KEYS = {
    "status",
    "status_neg",
    "status_pos",
    "status_span",
    "route",
    "route_span",
    "formulation",
    "formulation_span",
    "strength",
    "strength_span",
    "as_needed",
    "as_needed_span",
    "food_timing",
    "food_span",
}
ORAL_FORMULATIONS = {"tablet", "capsule", "syrup", "suspension"}
TRIM = " .,?"


def trimmed(texts: list[str], offsets: list[int], k: int, s: int, e: int) -> dict:
    """Span dict for turn-local [s, e), without surrounding spaces and . , ? (a cross-turn answer
    "ಇಲ್ಲ." is evidence "ಇಲ್ಲ")."""
    t = texts[k]
    while e > s and t[e - 1] in TRIM:
        e -= 1
    while s < e and t[s] in TRIM:
        s += 1
    if e <= s:
        raise ValueError(f"empty evidence span in turn {k}")
    return {
        "turn_index": k,
        "span_text": t[s:e],
        "char_start": offsets[k] + s,
        "char_end": offsets[k] + e,
    }


def check_item_keys(item: dict, where: str) -> None:
    """Template-load check of the v2 metadata of one medication item."""
    bad = {
        k for k in item if k.startswith(("status", "route", "formulation", "strength"))
    } - ITEM_KEYS
    if bad:
        raise ValueError(f"{where}: unknown v2 keys {sorted(bad)}")
    if "status" in item:
        if "status_neg" in item or "status_pos" in item:
            raise ValueError(f"{where}: give status OR status_neg+status_pos")
        values = [item["status"]]
    elif "status_neg" in item and "status_pos" in item:
        values = [item["status_neg"], item["status_pos"]]
        if "neg" not in item:
            raise ValueError(f"{where}: status_neg/status_pos need a neg slot on the item")
    else:
        raise ValueError(f"{where}: medication item has no status (use status: unknown if none)")
    for v in values:
        if v not in STATUSES:
            raise ValueError(f"{where}: bad status {v!r}")
    if any(v != "unknown" for v in values) and not item.get("status_span"):
        raise ValueError(f"{where}: a status other than unknown needs status_span")
    for key, span_key in (
        ("route", "route_span"),
        ("formulation", "formulation_span"),
        ("as_needed", "as_needed_span"),
        ("food_timing", "food_span"),
        ("strength", "strength_span"),
    ):
        if (key in item) != (span_key in item):
            raise ValueError(f"{where}: {key} and {span_key} go together")


def med_fields(
    item: dict[str, Any],
    *,
    negative: bool,
    span: Callable[[str], dict],
    has_span: Callable[[str], bool],
) -> dict[str, Any]:
    """The gold.v2 fields of one medication, from its template item.

    `span(marker)` returns the span dict of a marker; `has_span(marker)` says whether the marker
    was rendered. The speaker is added by the caller (it needs the turn role)."""
    spans: dict[str, dict] = {}

    def need(span_key: str) -> dict:
        mid = item.get(span_key)
        if not mid or not has_span(mid):
            raise ValueError(f"evidence marker {mid!r} ({span_key}) was not rendered")
        return span(mid)

    status = (
        item["status"] if "status" in item else item["status_neg" if negative else "status_pos"]
    )
    if status != "unknown":
        spans["status"] = need("status_span")

    formulation = None
    if "formulation" in item:
        formulation = item["formulation"]
        spans["formulation"] = need("formulation_span")
    elif item.get("slot") and has_span(f"{item['slot']}.form"):
        sp = span(f"{item['slot']}.form")
        formulation = FORMULATION_OF_WORD[sp["span_text"]]
        spans["formulation"] = sp

    route = None
    if "route" in item:
        route = item["route"]
        spans["route"] = need("route_span")
    elif formulation in ORAL_FORMULATIONS:
        route, spans["route"] = "oral", spans["formulation"]
    elif formulation == "injection":
        route, spans["route"] = "injection_unspecified", spans["formulation"]

    strength_value = strength_unit = None
    if "strength" in item:
        strength_value, strength_unit = item["strength"]["value"], item["strength"]["unit"]
        spans["strength"] = need("strength_span")

    as_needed = None
    if "as_needed" in item:
        as_needed = bool(item["as_needed"])
        spans["as_needed"] = need("as_needed_span")

    food_timing = None
    if "food_timing" in item:
        food_timing = item["food_timing"]
        spans["food_timing"] = need("food_span")

    order = ("route", "strength", "formulation", "as_needed", "food_timing", "status")
    return {
        "route": route,
        "strength_value": strength_value,
        "strength_unit": strength_unit,
        "formulation": formulation,
        "as_needed": as_needed,
        "food_timing": food_timing,
        "status": status,
        "gold_field_spans": {k: spans[k] for k in order if k in spans},
    }


def to_v2(
    gold_v1: dict,
    med_extra: list[tuple[dict, dict]],
    age_span: dict | None,
) -> dict:
    """gold.v1 doc + per-medication extras -> gold.v2 doc (v1 content is copied unchanged)."""
    turns = gold_v1["turns"]

    def speaker(item: dict) -> str:
        return SPEAKER_FROM_ROLE[turns[item["gold_span"]["turn_index"]]["speaker_role"]]

    gr = gold_v1["gold_record"]
    meds = []
    for m, extra in sorted(med_extra, key=lambda p: p[0]["gold_span"]["char_start"]):
        full = {k: m[k] for k in ("drug", "dose_value", "dose_unit", "frequency_per_day")}
        full.update({k: m[k] for k in ("duration_days", "negated", "gold_span")})
        full.update(
            {k: extra[k] for k in ("route", "strength_value", "strength_unit", "formulation")}
        )
        full.update({k: extra[k] for k in ("as_needed", "food_timing", "status")})
        full["speaker"] = speaker(m)
        full["gold_field_spans"] = extra["gold_field_spans"]
        meds.append(full)
    rec = {
        "patient_ref": gr["patient_ref"],
        "encounter_type": gr["encounter_type"],
        "patient_age_band": {"band": "child", "gold_span": age_span} if age_span else None,
        "weight_kg": None,
        "symptoms": gr["symptoms"],
        "medications": meds,
        "advice": [{**a, "speaker": speaker(a)} for a in gr["advice"]],
        "follow_up": gr["follow_up"],
    }
    return {
        "schema_version": "gold.v2",
        "conversation_id": gold_v1["conversation_id"],
        "template_family_id": gold_v1["template_family_id"],
        "turns": turns,
        "gold_record": rec,
        "tags": gold_v1["tags"],
    }


def coverage_v2(docs: dict[str, tuple[str, dict]]) -> dict:
    """Counts per split of the v2 labels. docs: conversation_id -> (split, gold.v2 doc)."""
    out: dict[str, Any] = {}
    for split in ("dev", "test", "all"):
        sel = [d for s, d in docs.values() if split in (s, "all")]
        meds = [m for d in sel for m in d["gold_record"]["medications"]]
        liquid = [m for m in meds if m["dose_unit"] == "ml"]
        out[split] = {
            "conversations": len(sel),
            "medications": len(meds),
            "status": dict(sorted(Counter(m["status"] for m in meds).items())),
            "route": dict(sorted(Counter(str(m["route"]) for m in meds).items())),
            "formulation": dict(sorted(Counter(str(m["formulation"]) for m in meds).items())),
            "as_needed": dict(sorted(Counter(str(m["as_needed"]) for m in meds).items())),
            "food_timing": dict(sorted(Counter(str(m["food_timing"]) for m in meds).items())),
            "patient_age_band": dict(
                sorted(
                    Counter(
                        (d["gold_record"]["patient_age_band"] or {}).get("band", "null")
                        for d in sel
                    ).items()
                )
            ),
            "weight_kg_set": sum(d["gold_record"]["weight_kg"] is not None for d in sel),
            "liquid_doses_ml": len(liquid),
            "liquid_doses_with_null_strength": sum(m["strength_value"] is None for m in liquid),
            "strength_set": sum(m["strength_value"] is not None for m in meds),
        }
    return out
