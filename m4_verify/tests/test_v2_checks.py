"""record.v2 checks (Phase C): evidence of every new field, route (CR-ROUTE), paediatric
(CR-PAEDIATRIC), liquid strength (CR-LIQUID-STRENGTH), status (CR-NEG / MA-STATUS), speaker,
as_needed and food_timing (MA-MED-ATTRIBUTE). Kannada written by an AI agent, NOT native-validated.

Lexicon: data/lexicon/drugs.csv (ceftriaxone is injection-only there; paracetamol 500-1000 mg).
"""

from __future__ import annotations

import copy
import json

import pytest

from contracts.validate import validate_doc
from m4_verify import checks as checks_mod
from m4_verify.checks import reason_code, severity_class
from m4_verify.config import DATA_LEXICON, default_config
from m4_verify.lexicon import load_lexicon
from m4_verify.tests.helpers import FIX
from m4_verify.tests.helpers_v2 import adv2, at, med2, record2, transcript
from m4_verify.verifier import verify

pytestmark = pytest.mark.skipif(not DATA_LEXICON.exists(), reason="data/lexicon/drugs.csv missing")
LEX = load_lexicon(DATA_LEXICON) if DATA_LEXICON.exists() else None
CFG = default_config()


def run(turns, rec, **kw):
    tr = transcript(turns)
    assert validate_doc("record.v2", rec) == [], validate_doc("record.v2", rec)
    v = verify(rec, tr, lexicon=LEX, config=CFG, **kw)
    assert validate_doc("verdict", v) == []
    return v


def codes(v, cid, path):
    return [(reason_code(c["reason"]), severity_class(c["reason"])) for c in at(v, cid, path)]


# =============================================================== C1: every v2 span exists
T_IV = ["Ceftriaxone 1000 mg IV ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ ಕೊಡಿ."]
S_IV = "Ceftriaxone 1000 mg IV ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ"


def iv_med(route="iv", **kw):
    fe = {"status": ("ಕೊಡಿ", 0)}
    if route is not None:
        fe["route"] = ("IV", 0)
    fe.update(kw.pop("fe", {}))
    return med2(T_IV, S_IV, 0, "ceftriaxone", 1000, "mg", 1, 5, route=route, fe=fe, **kw)


def test_c1_field_evidence_span_checked():
    rec = record2(T_IV, meds=[iv_med()])
    v = run(T_IV, rec)
    assert at(v, "C1", "/medications/0/field_evidence/route", "pass")
    bad = copy.deepcopy(rec)
    fe = bad["medications"][0]["field_evidence"]["route"]
    fe["char_start"] += 1
    fe["char_end"] += 1
    v = verify(bad, transcript(T_IV), lexicon=LEX, config=CFG)
    assert at(v, "C1", "/medications/0/field_evidence/route")


def test_c1_age_and_weight_evidence_checked():
    t = ["ಮಗುವಿಗೆ ಒಂದು ವರ್ಷ, ತೂಕ 10 kg."]
    rec = record2(t, age=("child", "ಮಗುವಿಗೆ ಒಂದು ವರ್ಷ", 0), weight=(10, "ತೂಕ 10 kg", 0))
    v = run(t, rec)
    assert at(v, "C1", "/patient_age_band/evidence", "pass")
    assert at(v, "C1", "/weight_kg/evidence", "pass")
    rec["patient_age_band"]["evidence"]["span_text"] = "ಮಗುವಿಗೆ ಎರಡು ವರ್ಷ"
    rec["patient_age_band"]["evidence"]["char_end"] = len("ಮಗುವಿಗೆ ಎರಡು ವರ್ಷ")
    v = verify(rec, transcript(t), lexicon=LEX, config=CFG)
    assert at(v, "C1", "/patient_age_band/evidence")


# =============================================================== C2: value from its own span
def test_c2_route_rederived_from_span():
    v = run(T_IV, record2(T_IV, meds=[iv_med("iv")]))
    assert at(v, "C2", "/medications/0/route", "pass")
    v = run(T_IV, record2(T_IV, meds=[iv_med("im")]))  # IV said, IM recorded
    assert at(v, "C2", "/medications/0/route")


def test_c2_formulation_rederived_and_trap():
    t = ["ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಮಾತ್ರ ತೆಗೆದುಕೊಳ್ಳಿ."]
    s = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ"
    fe = {"status": ("ತೆಗೆದುಕೊಳ್ಳಿ", 0), "formulation": ("ಮಾತ್ರೆ", 0)}
    m = med2(t, s, 0, "paracetamol", 500, "mg", 2, formulation="tablet", fe=fe)
    assert at(run(t, record2(t, meds=[m])), "C2", "/medications/0/formulation", "pass")
    m2 = med2(t, s, 0, "paracetamol", 500, "mg", 2, formulation="syrup", fe=fe)
    assert at(run(t, record2(t, meds=[m2])), "C2", "/medications/0/formulation")
    # trap: span pointing at ಮಾತ್ರ (only) cannot support "tablet"
    fe3 = {"status": ("ತೆಗೆದುಕೊಳ್ಳಿ", 0), "formulation": ("ಮಾತ್ರ", 0)}
    m3 = med2(t, s, 0, "paracetamol", 500, "mg", 2, formulation="tablet", fe=fe3)
    assert at(run(t, record2(t, meds=[m3])), "C2", "/medications/0/formulation")


T_SYR = ["ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 120 mg/5 ml, 25 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಕುಡಿಯಿರಿ."]
S_SYR = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 120 mg/5 ml, 25 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ"


def syr_med(dose=25, strength=(120, "mg/5ml"), with_span=True, **kw):
    fe = {"status": ("ಕುಡಿಯಿರಿ", 0), "formulation": ("ಸಿರಪ್", 0)}
    if strength and with_span:
        fe["strength"] = ("120 mg/5 ml", 0)
    t = kw.pop("turns", T_SYR)
    s = kw.pop("span", S_SYR)
    return med2(
        t, s, 0, "paracetamol", dose, "ml", 3, formulation="syrup", strength=strength, fe=fe, **kw
    )


def test_c2_strength_rederived_with_unit_equivalence():
    assert at(
        run(T_SYR, record2(T_SYR, meds=[syr_med()])), "C2", "/medications/0/strength_value", "pass"
    )
    m = syr_med(strength=(24, "mg/ml"))  # same concentration
    assert at(run(T_SYR, record2(T_SYR, meds=[m])), "C2", "/medications/0/strength_value", "pass")
    m = syr_med(strength=(250, "mg/5ml"))  # wrong strength
    assert at(run(T_SYR, record2(T_SYR, meds=[m])), "C2", "/medications/0/strength_value")


@pytest.mark.parametrize(
    "turn,span,band,ok",
    [
        ("ಮಗುವಿಗೆ ಒಂದು ವರ್ಷ.", "ಮಗುವಿಗೆ ಒಂದು ವರ್ಷ", "child", True),
        ("ಮಗುವಿಗೆ ಒಂದು ವರ್ಷ.", "ಮಗುವಿಗೆ ಒಂದು ವರ್ಷ", "adult", False),
        ("ಮಗುವಿಗೆ ಆರು ತಿಂಗಳು.", "ಆರು ತಿಂಗಳು", "infant", True),
        ("ರೋಗಿಗೆ 30 ವರ್ಷ.", "30 ವರ್ಷ", "adult", True),
        ("ರೋಗಿಗೆ 30 ವರ್ಷ.", "30 ವರ್ಷ", "child", False),
    ],
)
def test_c2_age_band(turn, span, band, ok):
    v = run([turn], record2([turn], age=(band, span, 0)))
    assert bool(at(v, "C2", "/patient_age_band", "pass")) is ok
    assert bool(at(v, "C2", "/patient_age_band")) is (not ok)


def test_c2_weight():
    t = ["ತೂಕ 10 kg."]
    assert at(run(t, record2(t, weight=(10, "ತೂಕ 10 kg", 0))), "C2", "/weight_kg", "pass")
    assert at(run(t, record2(t, weight=(12, "ತೂಕ 10 kg", 0))), "C2", "/weight_kg")


# =============================================================== C3: status and speaker
T_RX = ["ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."]
S_RX = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ"


def rx(
    status="prescribed", speaker="doctor", turns=T_RX, span=S_RX, st=("ತೆಗೆದುಕೊಳ್ಳಿ", 0), negated=False
):
    return med2(
        turns,
        span,
        0,
        "paracetamol",
        500,
        "mg",
        2,
        negated=negated,
        status=status,
        speaker=speaker,
        fe={"status": st} if status != "unknown" else {},
    )


def status_codes(v):
    return codes(v, "C3", "/medications/0/status")


def test_c3_prescribed_imperative_passes_and_flips_are_flagged():
    assert at(run(T_RX, record2(T_RX, meds=[rx()])), "C3", "/medications/0/status", "pass")
    for wrong in ("advised_against", "not_taken"):
        v = run(T_RX, record2(T_RX, meds=[rx(wrong)]))
        assert ("status_conflict", "CR-NEG") in status_codes(v), wrong


T_AA = ["Ibuprofen ಕೊಡಬೇಡಿ."]


def aa(status):
    return med2(
        T_AA,
        "Ibuprofen ಕೊಡಬೇಡಿ",
        0,
        "ibuprofen",
        negated=True,
        status=status,
        speaker="doctor",
        fe={"status": ("ಕೊಡಬೇಡಿ", 0)},
    )


def test_c3_advice_against_recorded_as_prescribed_is_cr_neg():
    v = run(T_AA, record2(T_AA, meds=[aa("prescribed")]))
    assert ("status_conflict", "CR-NEG") in status_codes(v)
    v = run(T_AA, record2(T_AA, meds=[aa("advised_against")]))
    assert at(v, "C3", "/medications/0/status", "pass") and not at(v, "C3", "/medications/0/status")


T_PAST = ["ನಿನ್ನೆ ರಾತ್ರಿ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕೊಟ್ಟೆ."]


def past(status, st="ನಿನ್ನೆ ರಾತ್ರಿ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕೊಟ್ಟೆ", turns=T_PAST, negated=False):
    return med2(
        turns,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್",
        0,
        "paracetamol",
        negated=negated,
        status=status,
        speaker="caregiver",
        fe={"status": (st, 0)},
    )


def test_c3_past_report_recorded_as_prescribed_is_flagged():
    v = run(T_PAST, record2(T_PAST, meds=[past("prescribed")]))
    assert ("status_conflict", "MA-STATUS") in status_codes(v)
    v = run(T_PAST, record2(T_PAST, meds=[past("already_taken")]))
    assert at(v, "C3", "/medications/0/status", "pass") and not at(v, "C3", "/medications/0/status")


def test_c3_not_given_recorded_as_already_taken_is_cr_neg():
    t = ["ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕೊಟ್ಟಿಲ್ಲ."]
    v = run(t, record2(t, meds=[past("already_taken", "ಕೊಟ್ಟಿಲ್ಲ", t, negated=True)]))
    assert ("status_conflict", "CR-NEG") in status_codes(v)
    v = run(t, record2(t, meds=[past("not_taken", "ಕೊಟ್ಟಿಲ್ಲ", t, negated=True)]))
    assert not at(v, "C3", "/medications/0/status")


@pytest.mark.parametrize(
    "answer,status,ok",
    [("ಇಲ್ಲ.", "not_taken", True), ("ಹೌದು.", "not_taken", False), ("ಹೌದು.", "already_taken", True)],
)
def test_c3_cross_turn_answer(answer, status, ok):
    t = ["ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?", answer]
    m = med2(
        t,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್",
        0,
        "paracetamol",
        negated=answer == "ಇಲ್ಲ.",
        status=status,
        speaker="asha",
        fe={"status": (answer[:-1], 1)},
    )
    v = run(t, record2(t, meds=[m]))
    assert bool(at(v, "C3", "/medications/0/status")) is (not ok), v["checks"]


@pytest.mark.parametrize(
    "turn",
    [
        "ಹೊಟ್ಟೆ ನೋವು ಇದೆ, ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ.",  # ಹೊಟ್ಟೆ trap
        "ಸರಿ ಆಯಿತು, ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ.",  # ಆಯಿತು trap
    ],
)
def test_c3_status_traps_do_not_flag_a_real_prescription(turn):
    t = [turn]
    v = run(t, record2(t, meds=[rx(turns=t)]))
    assert not at(v, "C3", "/medications/0/status"), at(v, "C3", "/medications/0/status")


def test_c3_unknown_status_is_not_applicable_never_pass():
    v = run(T_RX, record2(T_RX, meds=[rx("unknown")]))
    assert at(v, "C3", "/medications/0/status", "n/a")
    assert not at(v, "C3", "/medications/0/status", "pass")


def test_c3_prescription_spoken_by_patient_is_flagged():
    v = run(T_RX, record2(T_RX, meds=[rx(speaker="patient")]))
    assert codes(v, "C3", "/medications/0/speaker")
    v = run(T_RX, record2(T_RX, meds=[rx(speaker="caregiver")]))
    assert codes(v, "C3", "/medications/0/speaker")
    v = run(T_RX, record2(T_RX, meds=[rx(speaker="doctor")]))
    assert not at(v, "C3", "/medications/0/speaker")
    assert at(v, "C3", "/medications/0/speaker", "n/a")  # roles not in transcript.v1


def test_c3_advice_from_caregiver_is_flagged():
    t = ["ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಬೇಕು."]
    a = adv2(t, "ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಬೇಕು", 0, "take after food", False, speaker="caregiver")
    assert at(run(t, record2(t, advice=[a])), "C3", "/advice/0/speaker")


# =============================================================== C4: route (CR-ROUTE)
def route_codes(v):
    return codes(v, "C4", "/medications/0/route")


def test_c4_route_matches_evidence():
    v = run(T_IV, record2(T_IV, meds=[iv_med("iv")]))
    assert at(v, "C4", "/medications/0/route", "pass") and not route_codes(v)


def test_c4_route_missing_when_transcript_names_one():
    v = run(T_IV, record2(T_IV, meds=[iv_med(None)]))
    assert ("route_missing", "CR-ROUTE") in route_codes(v)


def test_c4_route_mismatch():
    v = run(T_IV, record2(T_IV, meds=[iv_med("im")]))
    assert ("route_mismatch", "CR-ROUTE") in route_codes(v)


def test_c4_route_formulation_conflict():
    t = ["ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ಮಾತ್ರೆ IV ಕೊಡಿ."]
    m = med2(
        t,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ಮಾತ್ರೆ IV",
        0,
        "paracetamol",
        500,
        "mg",
        route="iv",
        formulation="tablet",
        fe={"route": ("IV", 0), "formulation": ("ಮಾತ್ರೆ", 0), "status": ("ಕೊಡಿ", 0)},
    )
    rc = route_codes(run(t, record2(t, meds=[m])))
    assert ("route_formulation_conflict", "CR-ROUTE") in rc
    assert ("route_not_allowed", "CR-ROUTE") in rc  # paracetamol: oral forms only in lexicon


def test_c4_injection_only_drug_given_orally_is_flagged():
    t = ["Ceftriaxone 1000 mg ಬಾಯಿಗೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಕೊಡಿ."]
    m = med2(
        t,
        "Ceftriaxone 1000 mg ಬಾಯಿಗೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ",
        0,
        "ceftriaxone",
        1000,
        "mg",
        1,
        route="oral",
        fe={"route": ("ಬಾಯಿಗೆ", 0), "status": ("ಕೊಡಿ", 0)},
    )
    assert ("route_not_allowed", "CR-ROUTE") in route_codes(run(t, record2(t, meds=[m])))


def test_c4_route_null_and_not_said_is_not_applicable():
    v = run(T_RX, record2(T_RX, meds=[rx()]))
    assert at(v, "C4", "/medications/0/route", "n/a") and not route_codes(v)


# =============================================================== C4: paediatric (CR-PAEDIATRIC)
T_AGE7 = ["ರೋಗಿಗೆ ಏಳು ವರ್ಷ, ತೂಕ 20 kg.", "ಪ್ಯಾರಸಿಟಮಾಲ್ 250 mg ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಕೊಡಿ."]


def age7_record(band="child", weight=True):
    m = med2(
        T_AGE7,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ 250 mg ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ",
        1,
        "paracetamol",
        250,
        "mg",
        3,
        fe={"status": ("ಕೊಡಿ", 1)},
    )
    return record2(
        T_AGE7,
        meds=[m],
        age=(band, "ಏಳು ವರ್ಷ", 0),
        weight=(20, "ತೂಕ 20 kg", 0) if weight else None,
    )


@pytest.mark.parametrize("weight", [False, True])
def test_c4_child_band_without_child_word_is_not_checkable_never_pass(weight):
    v = run(T_AGE7, age7_record("child", weight))
    c = codes(v, "C4", "/medications/0/dose_value")
    assert ("cannot_verify:paediatric", "CR-PAEDIATRIC") in c
    assert not at(v, "C4", "/medications/0/dose_value", "pass")
    assert ("out_of_range", "CR-DOSE") not in c  # the ADULT range is not applied to a child
    if weight:
        txt = " ".join(x["reason"] for x in at(v, "C4", "/medications/0/dose_value"))
        assert "weight" in txt and "paediatric dosing table" in txt
    assert v["auto_acceptable"] is False


@pytest.mark.parametrize("band", ["infant", "adolescent", "unknown"])
def test_c4_every_non_adult_band_is_not_checkable(band):
    rec = age7_record("child")
    rec["patient_age_band"]["band"] = band
    v = verify(rec, transcript(T_AGE7), lexicon=LEX, config=CFG)
    c = codes(v, "C4", "/medications/0/dose_value")
    assert ("cannot_verify:paediatric", "CR-PAEDIATRIC") in c


def test_c4_adult_band_but_child_word_in_transcript_is_a_conflict():
    t = ["ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ. ರೋಗಿಗೆ 30 ವರ್ಷ.", "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಕೊಡಿ."]
    m = med2(
        t,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ",
        1,
        "paracetamol",
        500,
        "mg",
        2,
        fe={"status": ("ಕೊಡಿ", 1)},
    )
    v = run(t, record2(t, meds=[m], age=("adult", "30 ವರ್ಷ", 0)))
    assert ("age_band_conflict", "CR-PAEDIATRIC") in codes(v, "C4", "/patient_age_band")


# =============================================================== C4: liquid strength
def strength_codes(v):
    return codes(v, "C4", "/medications/0/strength_value")


def test_c4_liquid_ml_without_strength_but_strength_said_is_strength_missing():
    m = syr_med(strength=None)
    v = run(T_SYR, record2(T_SYR, meds=[m]))
    assert ("strength_missing", "CR-LIQUID-STRENGTH") in strength_codes(v)


def test_c4_liquid_ml_without_strength_and_none_said_cannot_verify():
    t = ["ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 10 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಕುಡಿಯಿರಿ."]
    m = syr_med(dose=10, strength=None, turns=t, span="ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 10 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ")
    v = run(t, record2(t, meds=[m]))
    c = codes(v, "C4", "/medications/0/dose_value") + strength_codes(v)
    assert ("cannot_verify:liquid_strength", "CR-LIQUID-STRENGTH") in c
    assert not at(v, "C4", "/medications/0/dose_value", "pass")


def test_c4_liquid_with_strength_in_range_passes_with_mg_equivalent():
    v = run(T_SYR, record2(T_SYR, meds=[syr_med()]))  # 25 ml x 24 mg/ml = 600 mg
    p = at(v, "C4", "/medications/0/dose_value", "pass")
    assert p and "600" in p[0]["reason"], v["checks"]
    assert not at(v, "C4", "/medications/0/dose_value")
    assert not strength_codes(v)


def test_c4_liquid_with_strength_out_of_range():
    t = ["ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 120 mg/5 ml, 50 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಕುಡಿಯಿರಿ."]
    m = syr_med(dose=50, turns=t, span="ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 120 mg/5 ml, 50 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ")
    v = run(t, record2(t, meds=[m]))  # 50 ml x 24 mg/ml = 1200 mg > 1000 mg
    assert ("out_of_range", "CR-LIQUID-STRENGTH") in codes(v, "C4", "/medications/0/dose_value")


def test_c4_liquid_strength_not_in_span_is_a_mismatch():
    m = syr_med(strength=(250, "mg/5ml"))
    v = run(T_SYR, record2(T_SYR, meds=[m]))
    assert ("span_mismatch", "CR-LIQUID-STRENGTH") in strength_codes(v)


T_TAB = ["ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg, ಎರಡು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."]
S_TAB = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg, ಎರಡು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ"


def test_c4_tablet_count_with_strength_uses_mg_equivalent():
    fe = {"status": ("ತೆಗೆದುಕೊಳ್ಳಿ", 0), "strength": ("500 mg", 0)}
    m = med2(T_TAB, S_TAB, 0, "paracetamol", 2, "tablet", 3, strength=(500, "mg"), fe=fe)
    v = run(T_TAB, record2(T_TAB, meds=[m]))  # 2 x 500 mg = 1000 mg: in 500-1000
    assert at(v, "C4", "/medications/0/dose_value", "pass")
    assert ("cannot_verify:count_unit", "CR-DOSE") not in codes(
        v, "C4", "/medications/0/dose_value"
    )
    m = med2(T_TAB, S_TAB, 0, "paracetamol", 2, "tablet", 3, fe={"status": ("ತೆಗೆದುಕೊಳ್ಳಿ", 0)})
    v = run(T_TAB, record2(T_TAB, meds=[m]))  # strength said but dropped from the record
    assert ("strength_missing", "CR-DOSE") in strength_codes(v)


# =============================================================== C4: status gating
def test_c4_already_taken_row_is_not_range_checked_but_span_still_is():
    t = ["ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ 2000 mg ಕೊಟ್ಟೆ."]
    m = med2(
        t,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ 2000 mg",
        0,
        "paracetamol",
        2000,
        "mg",
        status="already_taken",
        speaker="caregiver",
        fe={"status": ("ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ 2000 mg ಕೊಟ್ಟೆ", 0)},
    )
    v = run(t, record2(t, meds=[m]))
    assert ("out_of_range", "CR-DOSE") not in codes(v, "C4", "/medications/0/dose_value")
    assert at(v, "C4", "/medications/0/dose_value", "n/a")
    m["dose_value"] = 200  # wrong value: still a span mismatch
    v = run(t, record2(t, meds=[m]))
    assert ("span_mismatch", "CR-DOSE") in codes(v, "C4", "/medications/0/dose_value")


# =============================================================== C5: as_needed, food_timing
T_PRN = ["ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ಜ್ವರ ಇದ್ದರೆ ಮಾತ್ರ ತೆಗೆದುಕೊಳ್ಳಿ."]


def prn(as_needed, with_span=True):
    fe = {"status": ("ತೆಗೆದುಕೊಳ್ಳಿ", 0)}
    if as_needed is not None and with_span:
        fe["as_needed"] = ("ಜ್ವರ ಇದ್ದರೆ ಮಾತ್ರ", 0)
    return med2(T_PRN, "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg", 0, "paracetamol", 500, "mg", as_needed=as_needed, fe=fe)


def test_c5_as_needed():
    assert at(
        run(T_PRN, record2(T_PRN, meds=[prn(True)])), "C5", "/medications/0/as_needed", "pass"
    )
    v = run(T_PRN, record2(T_PRN, meds=[prn(None)]))
    assert ("as_needed_missing", "MA-MED-ATTRIBUTE") in codes(v, "C5", "/medications/0/as_needed")
    v = run(T_PRN, record2(T_PRN, meds=[prn(False)]))
    assert codes(v, "C5", "/medications/0/as_needed")


def test_c5_as_needed_trap_but():
    t = ["ಜ್ವರ ಕಡಿಮೆ ಆಗಿದೆ, ಆದರೆ ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."]
    v = run(t, record2(t, meds=[rx(turns=t)]))
    assert not at(v, "C5", "/medications/0/as_needed")


T_FOOD = ["ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಊಟದ ನಂತರ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."]


def food(timing):
    fe = {"status": ("ತೆಗೆದುಕೊಳ್ಳಿ", 0)}
    if timing:
        fe["food_timing"] = ("ಊಟದ ನಂತರ", 0)
    return med2(T_FOOD, "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg", 0, "amoxicillin", 500, "mg", food_timing=timing, fe=fe)


def test_c5_food_timing():
    v = run(T_FOOD, record2(T_FOOD, meds=[food("after_food")]))
    assert at(v, "C5", "/medications/0/food_timing", "pass")
    v = run(T_FOOD, record2(T_FOOD, meds=[food("before_food")]))
    assert codes(v, "C5", "/medications/0/food_timing")
    v = run(T_FOOD, record2(T_FOOD, meds=[food(None)]))
    assert ("food_timing_missing", "MA-MED-ATTRIBUTE") in codes(
        v, "C5", "/medications/0/food_timing"
    )


# =============================================================== verifier: contract + fail-closed
def test_v2_input_is_validated_as_record_v2():
    rec = record2(T_IV, meds=[iv_med()])
    rec["medications"][0]["field_evidence"].pop("route")  # route set without its evidence
    v = verify(rec, transcript(T_IV), lexicon=LEX, config=CFG)
    errs = [c for c in v["checks"] if c["reason"].startswith("check_error: input fails")]
    assert errs and "route" in errs[0]["reason"]
    assert v["auto_acceptable"] is False


def test_v2_check_crash_is_a_flag(monkeypatch):
    from m4_verify import v2checks

    def boom(*a, **k):
        raise RuntimeError("forced")

    monkeypatch.setattr(v2checks, "c4_med", boom)
    v = verify(record2(T_IV, meds=[iv_med()]), transcript(T_IV), lexicon=LEX, config=CFG)
    c4 = [c for c in v["checks"] if c["check_id"] == "C4"]
    assert c4 and all(c["status"] == "flag" for c in c4)
    assert c4[0]["reason"].startswith("check_error: RuntimeError: forced")
    assert v["auto_acceptable"] is False


def test_v1_records_never_reach_v2_code(monkeypatch):
    from m4_verify import v2checks
    from m4_verify.tests.helpers import med, record
    from m4_verify.tests.helpers import transcript as tr1

    for name in ("c1_extra", "c2_extra", "c3_extra", "c4_med", "c5_extra"):
        monkeypatch.setattr(v2checks, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    rec = record(T_RX, meds=[med(T_RX, S_RX, 0, "paracetamol", 500, "mg", 2)])
    v = verify(rec, tr1(T_RX), lexicon=LEX, config=CFG)
    assert not [c for c in v["checks"] if c["reason"].startswith("check_error")]


# =============================================================== fixtures (contracts/fixtures)
TR_DIRS = [FIX / "record.v2" / "transcripts", FIX / "transcript" / "valid"]


def _fixture_pair(name):
    rec = json.loads((FIX / "record.v2" / "valid" / name).read_text(encoding="utf-8"))
    tid = rec["source_transcript_id"]
    for d in TR_DIRS:
        p = d / f"{tid}__gold.json"
        if p.exists():
            return rec, json.loads(p.read_text(encoding="utf-8"))
    pytest.skip(f"no transcript for {tid}")


@pytest.mark.parametrize(
    "name", sorted(p.name for p in (FIX / "record.v2" / "valid").glob("rec2-*.json"))
)
def test_every_v2_fixture_gives_a_valid_verdict(name):
    rec, tr = _fixture_pair(name)
    v = verify(rec, tr, lexicon=LEX, config=CFG)
    assert validate_doc("verdict", v) == []
    assert not [c for c in v["checks"] if c["reason"].startswith("check_error")], v["checks"]


def test_fixture_child_no_strength_flags_liquid_strength_and_paediatric():
    rec, tr = _fixture_pair("rec2-fx-child-007-no-strength.json")
    v = verify(rec, tr, lexicon=LEX, config=CFG)
    classes = {severity_class(c["reason"]) for c in v["checks"] if c["status"] == "flag"}
    assert {"CR-LIQUID-STRENGTH", "CR-PAEDIATRIC"} <= classes
    assert v["auto_acceptable"] is False


def test_fixture_child_with_strength_still_paediatric_never_pass():
    rec, tr = _fixture_pair("rec2-fx-child-007.json")
    v = verify(rec, tr, lexicon=LEX, config=CFG)
    assert ("cannot_verify:paediatric", "CR-PAEDIATRIC") in codes(
        v, "C4", "/medications/0/dose_value"
    )
    assert not at(v, "C4", "/medications/0/dose_value", "pass")
    assert not strength_codes(v)  # strength 120 mg/5ml is supported by its span


@pytest.mark.parametrize(
    "name,path",
    [
        ("rec2-fx-past-009.json", "/medications/0/status"),
        ("rec2-fx-past-009.json", "/medications/1/status"),
        ("rec2-fx-asha-002.json", "/medications/0/status"),
        ("rec2-fx-inj-008.json", "/medications/0/route"),
        ("rec2-fx-pharm-003.json", "/medications/0/food_timing"),
        ("rec2-fx-child-007.json", "/medications/0/as_needed"),
    ],
)
def test_fixture_v2_fields_pass(name, path):
    rec, tr = _fixture_pair(name)
    v = verify(rec, tr, lexicon=LEX, config=CFG)
    assert not [c for c in v["checks"] if c["field_path"] == path and c["status"] == "flag"], [
        c for c in v["checks"] if c["field_path"] == path
    ]


def test_registry_ids_unchanged():
    assert list(checks_mod.REGISTRY) == [f"C{i}" for i in range(1, 9)]


def test_c8_v2_strength_phrase_is_not_a_conflicting_dose():
    # "120 mg/5 ml, 5 ml": 120 mg/5 ml is a concentration, not a second dose (v2 only)
    rec, tr = _fixture_pair("rec2-fx-child-007.json")
    v = verify(rec, tr, lexicon=LEX, config=CFG)
    assert not at(v, "C8", "/medications/0"), at(v, "C8", "/medications/0")
    # minimal pair: two real doses in one clause still flag
    t = ["ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg, 650 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."]
    m = med2(
        t,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg, 650 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ",
        0,
        "paracetamol",
        500,
        "mg",
        2,
        fe={"status": ("ತೆಗೆದುಕೊಳ್ಳಿ", 0)},
    )
    assert at(run(t, record2(t, meds=[m])), "C8", "/medications/0")


# =============================================================== dev-informed additions
def test_c2_oral_route_inferred_from_an_oral_formulation_word():
    t = ["ಸೆಟಿರಿಜಿನ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."]
    s = "ಸೆಟಿರಿಜಿನ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ"
    fe = {"route": ("ಮಾತ್ರೆ", 0), "formulation": ("ಮಾತ್ರೆ", 0), "status": ("ತೆಗೆದುಕೊಳ್ಳಿ", 0)}
    m = med2(t, s, 0, "cetirizine", 1, "tablet", 1, 5, route="oral", formulation="tablet", fe=fe)
    v = run(t, record2(t, meds=[m]))
    assert at(v, "C2", "/medications/0/route", "pass") and not at(v, "C2", "/medications/0/route")
    assert at(v, "C4", "/medications/0/route", "pass")
    m["route"] = "iv"  # a tablet word can never support IV
    v = run(t, record2(t, meds=[m]))
    assert at(v, "C2", "/medications/0/route") and at(v, "C4", "/medications/0/route")


T_REG = ["ಸೆಟಿರಿಜಿನ್ 10 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ."]
S_REG = "ಸೆಟಿರಿಜಿನ್ 10 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ"


def test_c3_verbless_regimen_supports_prescribed_but_not_with_past():
    m = med2(T_REG, S_REG, 0, "cetirizine", 10, "mg", 1, 5, fe={"status": (S_REG, 0)})
    v = run(T_REG, record2(T_REG, meds=[m]))
    assert at(v, "C3", "/medications/0/status", "pass")
    t = ["ನಿನ್ನೆ ಸೆಟಿರಿಜಿನ್ 10 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ."]
    m = med2(
        t, "ಸೆಟಿರಿಜಿನ್ 10 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ", 0, "cetirizine", 10, "mg", 1, fe={"status": ("ನಿನ್ನೆ", 0)}
    )
    assert ("status_conflict", "MA-STATUS") in status_codes(run(t, record2(t, meds=[m])))
    t = ["ಸೆಟಿರಿಜಿನ್ ಬಗ್ಗೆ ಕೇಳಿದೆ."]  # bare mention: no regimen, no directive
    m = med2(t, "ಸೆಟಿರಿಜಿನ್", 0, "cetirizine", fe={"status": ("ಸೆಟಿರಿಜಿನ್", 0)})
    assert ("status_unsupported", "MA-STATUS") in status_codes(run(t, record2(t, meds=[m])))


@pytest.mark.parametrize(
    "answer,status,ok",
    [
        ("ಇಲ್ಲ.", "advised_against", True),
        ("ಇಲ್ಲ.", "prescribed", False),
        ("ಹೌದು.", "prescribed", True),
        ("ಹೌದು.", "advised_against", False),
    ],
)
def test_c3_permission_question_answer(answer, status, ok):
    t = ["ಮನೆಯಲ್ಲಿರುವ ಅಮಾಕ್ಸಿಸಿಲಿನ್ ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ?", answer]
    m = med2(
        t,
        "ಅಮಾಕ್ಸಿಸಿಲಿನ್",
        0,
        "amoxicillin",
        negated=answer == "ಇಲ್ಲ.",
        status=status,
        speaker="patient",
        fe={"status": (answer[:-1], 1)},
    )
    v = run(t, record2(t, meds=[m]))
    assert bool(at(v, "C3", "/medications/0/status", "pass")) is ok, status_codes(v)
    if not ok:
        assert ("status_conflict", "CR-NEG") in status_codes(v)


@pytest.mark.parametrize("answer,ok", [("ಇಲ್ಲ.", True), ("ಹೌದು.", False)])
def test_c3_not_finished_supports_stopped_early(answer, ok):
    t = ["ಅಮಾಕ್ಸಿಸಿಲಿನ್ ಎಲ್ಲಾ ಮುಗಿಸಿದ್ರಾ?", answer]
    m = med2(
        t,
        "ಅಮಾಕ್ಸಿಸಿಲಿನ್",
        0,
        "amoxicillin",
        negated=answer == "ಇಲ್ಲ.",
        status="stopped_early",
        speaker="asha",
        fe={"status": (answer[:-1], 1)},
    )
    v = run(t, record2(t, meds=[m]))
    assert bool(at(v, "C3", "/medications/0/status", "pass")) is ok, status_codes(v)


def test_c3_ongoing_use_supports_already_taken():
    t = ["ಮಗು ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯುತ್ತೆ."]
    m = med2(
        t,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್",
        0,
        "paracetamol",
        status="already_taken",
        speaker="caregiver",
        fe={"status": ("ಕುಡಿಯುತ್ತೆ", 0)},
    )
    assert at(run(t, record2(t, meds=[m])), "C3", "/medications/0/status", "pass")


@pytest.mark.parametrize("confirmed", [True, False])
def test_c3_patient_advice_confirmed_by_a_bare_yes_is_not_flagged(confirmed):
    t = ["ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಬೇಕು, ಅಲ್ವ?"] + (["ಹೌದು."] if confirmed else [])
    a = adv2(t, "ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಬೇಕು", 0, "take after food", False, speaker="patient")
    v = run(t, record2(t, advice=[a]))
    assert bool(at(v, "C3", "/advice/0/speaker")) is (not confirmed)
