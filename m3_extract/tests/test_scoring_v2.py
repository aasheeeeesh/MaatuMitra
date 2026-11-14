"""Severity mapping of the new record.v2 fields (docs/severity.md note of 2026-11-12)."""

from m3_extract.scoring import FieldResult
from m3_extract.scoring_v2 import _code, bootstrap_ci, score_new_fields


def test_code_mapping():
    assert _code("route", "oral", "injection_unspecified") == "CR-ROUTE"
    assert _code("route", None, "oral") == "CR-ROUTE"
    assert _code("formulation", "tablet", "injection") == "CR-ROUTE"
    assert _code("formulation", "tablet", "capsule") == "MA-MED-ATTRIBUTE"
    assert _code("strength", (120, "mg/5ml"), None) == "CR-LIQUID-STRENGTH"
    assert _code("strength", (120, "mg/5ml"), (250, "mg/5ml")) == "CR-LIQUID-STRENGTH"
    assert _code("strength", None, None) is None
    assert _code("status", "prescribed", "advised_against") == "CR-NEG"
    assert _code("status", "not_taken", "already_taken") == "CR-NEG"
    assert _code("status", "stopped_early", "already_taken") == "MA-STATUS"
    assert _code("status", "unknown", "prescribed") == "MA-STATUS"
    assert _code("food_timing", "after_food", None) == "MA-MED-ATTRIBUTE"


def _gold(band, dose):
    return {
        "conversation_id": "m1-x1-000",
        "gold_record": {
            "patient_age_band": {"band": band} if band else None,
            "weight_kg": None,
            "medications": [
                {
                    "drug": "paracetamol",
                    "dose_value": dose,
                    "route": "oral",
                    "strength_value": None,
                    "strength_unit": None,
                    "formulation": "syrup",
                    "as_needed": None,
                    "food_timing": None,
                    "status": "prescribed",
                    "speaker": "asha",
                }
            ],
        },
    }


def test_paediatric_class_needs_a_dosed_medication():
    rec = {"medications": [], "patient_age_band": None, "weight_kg": None}
    age = lambda g: next(r for r in score_new_fields(rec, g) if r.field == "patient_age_band")  # noqa: E731
    assert age(_gold("child", 5)).code == "CR-PAEDIATRIC"
    assert age(_gold("child", None)).code == "MA-MED-ATTRIBUTE"
    assert age(_gold(None, 5)).code is None


def test_bootstrap_resamples_templates():
    rs = [
        FieldResult(f"m1-{t}-00{i}", "medication", "d", "f", "CR-ROUTE" if t == "a1" else None)
        for t in ("a1", "b1", "c1", "d1")
        for i in range(3)
    ]
    lo, hi = bootstrap_ci(rs, lambda r: True)
    assert lo == 0 and hi > 0 and hi <= 1000
