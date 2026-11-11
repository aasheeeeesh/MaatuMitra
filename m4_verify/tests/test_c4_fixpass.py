"""C4 fixes from the clinical review (reviews/m4_verify/2026-11-10-clinical.md, D-91).

(e) a dose for a child is "not checkable" -> flag CR-PAEDIATRIC, never pass;
(f) blank range / unknown drug / count or liquid units get the reason code cannot_verify,
    kept apart from real violations (out_of_range, exceeds_max_daily, unit_not_allowed, span_mismatch);
(g) allowed units per drug (lexicon note where it names the form, else the m4 config table);
(h) max daily dose where the lexicon gives it.
Uses the PROJECT lexicon data/lexicon/drugs.csv (REFREEZE-1 values). Not clinical advice:
the simulated clinical review is ai_simulated_review; Kannada is not native-validated.
"""

from __future__ import annotations

import pytest

from contracts.validate import validate_doc
from m4_verify.checks import reason_code, severity_class
from m4_verify.config import DATA_LEXICON, default_config
from m4_verify.lexicon import child_cues, load_lexicon
from m4_verify.tests.helpers import med, record, transcript
from m4_verify.verifier import verify

LEX = load_lexicon(DATA_LEXICON)
CFG = default_config()


def run(turns, meds):
    v = verify(record(turns, meds=meds), transcript(turns), lexicon=LEX, config=CFG)
    assert validate_doc("verdict", v) == []
    return v


def c4(v, status=None):
    return [
        c
        for c in v["checks"]
        if c["check_id"] == "C4" and (status is None or c["status"] == status)
    ]


PARA = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಮೂರು ದಿನ"


# ------------------------------------------------------------------ (e) paediatric
def test_child_dose_inside_adult_range_is_flagged_not_passed():
    turns = ["ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ.", PARA + " ಕೊಡಿ."]
    v = run(turns, [med(turns, PARA, 1, "paracetamol", 500, "mg", 3, 3)])
    assert c4(v, "pass") == []
    f = c4(v, "flag")
    assert any(reason_code(c["reason"]) == "cannot_verify:paediatric" for c in f), f
    assert any(severity_class(c["reason"]) == "CR-PAEDIATRIC" for c in f)
    assert v["auto_acceptable"] is False


def test_adult_twin_without_child_cue_passes():
    turns = ["ಜ್ವರ ಇದೆ.", PARA + " ತೆಗೆದುಕೊಳ್ಳಿ."]
    v = run(turns, [med(turns, PARA, 1, "paracetamol", 500, "mg", 3, 3)])
    assert c4(v, "flag") == [], c4(v)
    assert c4(v, "pass")


def test_child_syrup_ml_is_paediatric_and_liquid_strength():
    span = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 5 ml ದಿನಕ್ಕೆ ಮೂರು ಸಾರಿ ಮೂರು ದಿನ"
    turns = ["ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ.", span + " ಕೊಡಿ."]
    v = run(turns, [med(turns, span, 1, "paracetamol", 5, "ml", 3, 3)])
    codes = {reason_code(c["reason"]) for c in c4(v, "flag")}
    assert {"cannot_verify:paediatric", "cannot_verify:liquid_strength"} <= codes, codes
    assert c4(v, "pass") == []


@pytest.mark.parametrize(
    "text", ["ಮಗುವಿಗೆ ಜ್ವರ", "ಮಗು ಅಳುತ್ತಿದೆ", "ಮಕ್ಕಳಿಗೆ ಕೊಡಿ", "the child has fever", "ಶಿಶುವಿಗೆ ಜ್ವರ"]
)
def test_child_cues_found(text):
    assert child_cues(text)


@pytest.mark.parametrize("text", ["ಜ್ವರ ಇದೆ", "ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಿ", "ಎಲ್ಲರಿಗೂ ಕೊಡಿ", "children's ward closed"])
def test_child_cue_twins_and_traps(text):
    # "children's" -> tokens children, s: still a cue (fail-closed is the safe side); others none
    if "children" in text:
        assert child_cues(text)
    else:
        assert child_cues(text) == []


# ------------------------------------------------------------------ (f) cannot_verify vs violations
def test_blank_range_is_cannot_verify_not_a_violation():
    span = "ಡೈಕ್ಲೋಫೆನಾಕ್ 50 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಮೂರು ದಿನ"
    turns = [span + " ತೆಗೆದುಕೊಳ್ಳಿ."]
    v = run(turns, [med(turns, span, 0, "diclofenac", 50, "mg", 2, 3)])
    codes = [reason_code(c["reason"]) for c in c4(v, "flag")]
    assert codes == ["cannot_verify:no_range"], c4(v)
    assert "no verified range" in c4(v, "flag")[0]["reason"]


def test_out_of_range_is_a_violation_code():
    span = "ಪ್ಯಾರಸಿಟಮಾಲ್ 5000 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಮೂರು ದಿನ"
    turns = [span + " ತೆಗೆದುಕೊಳ್ಳಿ."]
    v = run(turns, [med(turns, span, 0, "paracetamol", 5000, "mg", 1, 3)])
    f = c4(v, "flag")
    assert "out_of_range" in {reason_code(c["reason"]) for c in f}
    assert all(severity_class(c["reason"]) == "CR-DOSE" for c in f if "out_of_range" in c["reason"])


def test_count_unit_is_cannot_verify():
    span = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಮೂರು ದಿನ"
    turns = [span + " ತೆಗೆದುಕೊಳ್ಳಿ."]
    v = run(turns, [med(turns, span, 0, "paracetamol", 1, "tablet", 3, 3)])
    assert [reason_code(c["reason"]) for c in c4(v, "flag")] == ["cannot_verify:count_unit"]


def test_reason_code_parser():
    assert reason_code("out_of_range [CR-DOSE]: x") == "out_of_range"
    assert reason_code("cannot_verify:no_range [CR-DOSE]: x") == "cannot_verify:no_range"
    assert severity_class("cannot_verify:paediatric [CR-PAEDIATRIC]: x") == "CR-PAEDIATRIC"
    assert reason_code("check_error: ValueError: boom") == "check_error"
    assert reason_code("some free text") is None


# ------------------------------------------------------------------ (g) allowed units per drug
def test_injection_only_drug_as_tablet_is_a_route_flag():
    span = "ಸೆಫ್ಟ್ರಿಯಾಕ್ಸೋನ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ"
    turns = [span + " ತೆಗೆದುಕೊಳ್ಳಿ."]
    v = run(turns, [med(turns, span, 0, "ceftriaxone", 1, "tablet", 1, 5)])
    f = [c for c in c4(v, "flag") if reason_code(c["reason"]) == "unit_not_allowed"]
    assert f and severity_class(f[0]["reason"]) == "CR-ROUTE", c4(v)


def test_ors_in_mg_is_not_allowed():
    span = "ಓ.ಆರ್.ಎಸ್ 500 mg"
    turns = [span + " ಕುಡಿಸಿ."]
    v = run(turns, [med(turns, span, 0, "ors", 500, "mg")])
    assert "unit_not_allowed" in {reason_code(c["reason"]) for c in c4(v, "flag")}


def test_tablet_drug_in_ml_is_not_allowed_but_paracetamol_syrup_is():
    span = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 5 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ"
    turns = [span + " ತೆಗೆದುಕೊಳ್ಳಿ."]
    v = run(turns, [med(turns, span, 0, "amoxicillin", 5, "ml", 3, 5)])
    assert "unit_not_allowed" in {reason_code(c["reason"]) for c in c4(v, "flag")}
    span = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 5 ml ದಿನಕ್ಕೆ ಮೂರು ಸಾರಿ ಮೂರು ದಿನ"
    turns = [span + " ಕೊಡಿ."]
    v = run(turns, [med(turns, span, 0, "paracetamol", 5, "ml", 3, 3)])
    codes = {reason_code(c["reason"]) for c in c4(v, "flag")}
    assert "unit_not_allowed" not in codes and "cannot_verify:liquid_strength" in codes


def test_units_for_drug_and_their_source():
    assert "tablet" not in CFG.units_for("ceftriaxone", LEX)
    assert "mg" not in CFG.units_for("ors", LEX) and "sachet" in CFG.units_for("ors", LEX)
    assert {"tablet", "mcg"} <= set(CFG.units_for("iron-folic acid", LEX))
    assert "ml" in CFG.units_for("paracetamol", LEX)
    assert "ml" not in CFG.units_for("amoxicillin", LEX)
    assert CFG.units_source("ceftriaxone", LEX).startswith("lexicon")
    assert CFG.units_source("paracetamol", LEX).startswith("m4 config")


# ------------------------------------------------------------------ (h) max daily
def test_max_daily_from_lexicon():
    span = "ಪ್ಯಾರಸಿಟಮಾಲ್ 1000 mg ದಿನಕ್ಕೆ ಆರು ಬಾರಿ ಮೂರು ದಿನ"
    turns = [span + " ತೆಗೆದುಕೊಳ್ಳಿ."]
    v = run(turns, [med(turns, span, 0, "paracetamol", 1000, "mg", 6, 3)])
    f = [c for c in c4(v, "flag") if reason_code(c["reason"]) == "exceeds_max_daily"]
    assert f and "4000" in f[0]["reason"], c4(v)
    span2 = "ಪ್ಯಾರಸಿಟಮಾಲ್ 1000 mg ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಮೂರು ದಿನ"
    turns2 = [span2 + " ತೆಗೆದುಕೊಳ್ಳಿ."]
    v2 = run(turns2, [med(turns2, span2, 0, "paracetamol", 1000, "mg", 4, 3)])
    assert c4(v2, "flag") == [], c4(v2)  # exactly 4000 mg/day is not above the max
