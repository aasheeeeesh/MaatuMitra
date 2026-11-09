"""Checks C1..C8, the registry, and FAIL-CLOSED behaviour."""

from __future__ import annotations

import copy

import pytest

from contracts.validate import validate_doc
from m4_verify import checks as checks_mod
from m4_verify.config import default_config
from m4_verify.lexicon import load_lexicon
from m4_verify.tests.helpers import (
    FIX,
    adv,
    flags,
    med,
    record,
    statuses,
    sym,
    transcript,
)
from m4_verify.verifier import verify

LEX = load_lexicon(FIX / "lexicon" / "drugs_fixture.csv")

T_AMOX = ["ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."]
SPAN_AMOX = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ"


def amox(**kw):
    base = dict(drug="amoxicillin", dose=500, unit="mg", freq=3, dur=5, negated=False)
    base.update(kw)
    return med(T_AMOX, SPAN_AMOX, 0, **base)


def run(turns, rec, conf=None, second=None, cfg=None, **kw):
    t = transcript(turns, conf=conf)
    v = verify(rec, t, lexicon=LEX, config=cfg or default_config(), second_transcript=second, **kw)
    errs = validate_doc("verdict", v)
    assert errs == [], errs
    return v


def test_clean_case_is_auto_acceptable():
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]))
    assert flags(v) == [], flags(v)
    assert v["auto_acceptable"] is True
    assert {c["check_id"] for c in v["checks"]} == {f"C{i}" for i in range(1, 9)}


# ------------------------------------------------------------------ C1
def test_c1_span_mismatch_flags():
    rec = record(T_AMOX, meds=[amox()])
    rec["medications"][0]["evidence"]["char_start"] += 1
    rec["medications"][0]["evidence"]["char_end"] += 1
    v = run(T_AMOX, rec)
    assert "flag" in statuses(v, "C1")
    assert v["auto_acceptable"] is False


def test_c1_wrong_transcript_id_flags():
    rec = record(T_AMOX, meds=[amox()], audio_id="other-id")
    v = run(T_AMOX, rec)
    assert any(c["field_path"] == "/source_transcript_id" for c in flags(v, "C1"))


# ------------------------------------------------------------------ C2
def test_c2_dose_not_derivable_flags():
    v = run(T_AMOX, record(T_AMOX, meds=[amox(dose=50)]))
    assert any(c["field_path"] == "/medications/0/dose_value" for c in flags(v, "C2"))


def test_c2_drug_swap_flags_and_unknown_drug_flags():
    v = run(T_AMOX, record(T_AMOX, meds=[amox(drug="azithromycin")]))
    assert any(c["field_path"] == "/medications/0/drug" for c in flags(v, "C2"))
    v = run(T_AMOX, record(T_AMOX, meds=[amox(drug="unobtainium")]))
    assert any("not in the lexicon" in c["reason"] for c in flags(v, "C2"))


def test_c2_unknown_symptom_flags_and_advice_is_na():
    turns = ["ಜ್ವರ ಇದೆ. ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಿ."]
    rec = record(
        turns,
        symptoms=[sym(turns, "ಜ್ವರ ಇದೆ", 0, "sneezing-fits", True)],
        advice=[adv(turns, "ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಿ", 0, "take after food", False)],
    )
    v = run(turns, rec)
    assert any(c["field_path"] == "/symptoms/0/name" for c in flags(v, "C2"))
    c2_adv = [
        c for c in v["checks"] if c["check_id"] == "C2" and c["field_path"] == "/advice/0/text"
    ]
    assert c2_adv and c2_adv[0]["status"] == "n/a"


# ------------------------------------------------------------------ C3
def test_c3_negation_drop_and_add():
    turns = ["ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ, ಕೆಮ್ಮು ಇಲ್ಲ."]
    good = record(
        turns,
        symptoms=[
            sym(turns, "ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ", 0, "fever", True),
            sym(turns, "ಕೆಮ್ಮು ಇಲ್ಲ", 0, "cough", False),
        ],
    )
    assert flags(run(turns, good)) == []
    drop = copy.deepcopy(good)
    drop["symptoms"][1]["present"] = True
    v = run(turns, drop)
    assert any(c["field_path"] == "/symptoms/1/present" for c in flags(v, "C3"))
    add = copy.deepcopy(good)
    add["symptoms"][0]["present"] = False
    v = run(turns, add)
    assert any(c["field_path"] == "/symptoms/0/present" for c in flags(v, "C3"))


def test_c3_cross_turn():
    turns = ["ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?", "ಇಲ್ಲ."]
    ok = record(turns, meds=[med(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0, "paracetamol", negated=True)])
    assert flags(run(turns, ok)) == []
    bad = record(turns, meds=[med(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0, "paracetamol", negated=False)])
    assert flags(run(turns, bad), "C3")


def test_c3_advice_negation():
    turns = ["ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು."]
    span = "ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು"
    ok = record(turns, advice=[adv(turns, span, 0, "do not take antibiotics for a cold", True)])
    assert flags(run(turns, ok)) == []
    bad = record(turns, advice=[adv(turns, span, 0, "take antibiotics for a cold", False)])
    assert flags(run(turns, bad), "C3")


# ------------------------------------------------------------------ C4
def test_c4_range_checks():
    assert flags(run(T_AMOX, record(T_AMOX, meds=[amox()])), "C4") == []
    turns = ["ಅಮಾಕ್ಸಿಸಿಲಿನ್ 5000 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."]
    span = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 5000 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ"
    v = run(turns, record(turns, meds=[med(turns, span, 0, "amoxicillin", 5000, "mg", 1, 5)]))
    assert any("outside" in c["reason"] for c in flags(v, "C4"))
    turns = ["ಅಮಾಕ್ಸಿಸಿಲಿನ್ 50 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."]
    span = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 50 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ"
    v = run(turns, record(turns, meds=[med(turns, span, 0, "amoxicillin", 50, "mg", 1, 5)]))
    assert flags(v, "C4")


def test_c4_unit_mismatch_flags():
    v = run(T_AMOX, record(T_AMOX, meds=[amox(unit="ml")]))
    assert any(c["field_path"] == "/medications/0/dose_unit" for c in flags(v, "C4"))
    v = run(T_AMOX, record(T_AMOX, meds=[amox(unit="tablet")]))
    assert flags(v, "C4")


def test_c4_unusual_inside_range_is_a_soft_note():
    turns = ["ಅಮಾಕ್ಸಿಸಿಲಿನ್ 1000 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."]
    span = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 1000 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಐದು ದಿನ"
    v = run(turns, record(turns, meds=[med(turns, span, 0, "amoxicillin", 1000, "mg", 2, 5)]))
    assert flags(v, "C4") == []
    assert any("unusual" in c["reason"] for c in v["checks"] if c["check_id"] == "C4")


def test_c4_max_daily_exceeded_flags():
    turns = ["ಅಮಾಕ್ಸಿಸಿಲಿನ್ 1000 mg ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."]
    span = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 1000 mg ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಐದು ದಿನ"
    v = run(turns, record(turns, meds=[med(turns, span, 0, "amoxicillin", 1000, "mg", 4, 5)]))
    assert any("max daily" in c["reason"] for c in flags(v, "C4"))


def test_c4_blank_range_fails_closed():
    turns = ["ಒ.ಆರ್.ಎಸ್ 200 ml ಕುಡಿಸಿ."]
    v = run(turns, record(turns, meds=[med(turns, "ಒ.ಆರ್.ಎಸ್ 200 ml", 0, "ors", 200, "ml")]))
    assert any("no verified range" in c["reason"] for c in flags(v, "C4"))


def test_c4_no_dose_is_na():
    turns = ["ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?", "ಇಲ್ಲ."]
    v = run(
        turns, record(turns, meds=[med(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0, "paracetamol", negated=True)])
    )
    assert statuses(v, "C4") == ["n/a"]


# ------------------------------------------------------------------ C5
def test_c5_frequency_and_duration():
    v = run(T_AMOX, record(T_AMOX, meds=[amox(freq=2)]))
    assert any(c["field_path"] == "/medications/0/frequency_per_day" for c in flags(v, "C5"))
    v = run(T_AMOX, record(T_AMOX, meds=[amox(dur=7)]))
    assert any(c["field_path"] == "/medications/0/duration_days" for c in flags(v, "C5"))
    v = run(T_AMOX, record(T_AMOX, meds=[amox(freq=None)]))
    assert any("record has none" in c["reason"] for c in flags(v, "C5"))
    turns = ["ಸೆಫಿಕ್ಸಿಮ್ 200 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಒಂದು ವಾರ ತೆಗೆದುಕೊಳ್ಳಿ."]
    span = "ಸೆಫಿಕ್ಸಿಮ್ 200 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಒಂದು ವಾರ"
    v = run(turns, record(turns, meds=[med(turns, span, 0, "cefixime", 200, "mg", 2, 7)]))
    assert flags(v) == []


# ------------------------------------------------------------------ C6
def test_c6_unsupported_drug_and_omission():
    v = run(T_AMOX, record(T_AMOX, meds=[amox(drug="cefixime")]))
    assert any(c["field_path"] == "/medications/0/drug" for c in flags(v, "C6"))
    turns = [*T_AMOX, "ಸೆಫಿಕ್ಸಿಮ್ ಕೂಡ ಇದೆ."]
    v = run(turns, record(turns, meds=[med(turns, SPAN_AMOX, 0, "amoxicillin", 500, "mg", 3, 5)]))
    om = [c for c in flags(v, "C6") if "possible omission" in c["reason"]]
    assert om and "cefixime" in om[0]["reason"]


def test_c6_number_in_follow_up_text_must_be_in_span():
    turns = ["ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಎರಡು ದಿನದಲ್ಲಿ ಮತ್ತೆ ಬನ್ನಿ."]
    span = "ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಎರಡು ದಿನದಲ್ಲಿ ಮತ್ತೆ ಬನ್ನಿ"
    from m4_verify.tests.helpers import ev

    ok = record(turns, follow_up={"text": "come back in two days", "evidence": ev(turns, span, 0)})
    assert flags(run(turns, ok)) == []
    bad = record(
        turns, follow_up={"text": "come back in five days", "evidence": ev(turns, span, 0)}
    )
    assert any(c["field_path"] == "/follow_up/text" for c in flags(run(turns, bad), "C6"))


def test_c6_patient_link_needs_encounter_index():
    rec = record(T_AMOX, meds=[amox()], patient="pt-WRONG")
    v = run(T_AMOX, rec)
    pl = [c for c in v["checks"] if c["check_id"] == "C6" and c["field_path"] == "/patient_ref"]
    assert pl and pl[0]["status"] == "n/a"  # blind without an index (documented limitation)
    v = run(T_AMOX, rec, encounter_index={"t-test-1": "pt-test-1"})
    assert any(c["field_path"] == "/patient_ref" for c in flags(v, "C6"))
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]), encounter_index={"t-test-1": "pt-test-1"})
    assert flags(v) == []


# ------------------------------------------------------------------ C7
def test_c7_no_confidence_is_na_with_limitation():
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]))
    c7 = [c for c in v["checks"] if c["check_id"] == "C7"]
    assert [c["status"] for c in c7] == ["n/a"]
    assert "limitation" in c7[0]["reason"]


def test_c7_low_confidence_critical_token_flags():
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]), conf={"500": 0.41})
    assert any(c["field_path"].startswith("/medications/0") for c in flags(v, "C7"))
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]), conf={"ದಿನಕ್ಕೆ": 0.30})  # not critical
    assert flags(v, "C7") == []


def test_c7_two_transcripts_disagree():
    second = transcript(["ಅಮಾಕ್ಸಿಸಿಲಿನ್ 50 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."], audio_id="t2")
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]), second=second)
    assert flags(v, "C7")
    same = transcript(T_AMOX, audio_id="t2")
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]), second=same)
    assert flags(v, "C7") == []
    neg = transcript(["ಕೆಮ್ಮು ಇಲ್ಲ."], audio_id="t3")
    turns = ["ಕೆಮ್ಮು."]
    v = run(turns, record(turns, symptoms=[sym(turns, "ಕೆಮ್ಮು", 0, "cough", True)]), second=neg)
    assert any("negation" in c["reason"] for c in flags(v, "C7"))


# ------------------------------------------------------------------ C8
def test_c8_soft_cue_flags():
    turns = ["ಮಗು ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಲ್ಲ."]  # ಕುಡಿಯಲ್ಲ: stem in list -> strong
    rec = record(turns, meds=[med(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0, "paracetamol", negated=True)])
    assert flags(run(turns, rec), "C8") == []
    turns = ["ಮಗು ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ನುಂಗಲ್ಲ."]  # ನುಂಗ not in list -> soft
    rec = record(turns, meds=[med(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0, "paracetamol", negated=True)])
    assert any("soft" in c["reason"] for c in flags(run(turns, rec), "C8"))


def test_c8_bare_illa_without_question_flags():
    turns = ["ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕೊಟ್ಟೆ.", "ಇಲ್ಲ."]
    rec = record(turns, meds=[med(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0, "paracetamol", negated=False)])
    assert any("no resolvable question" in c["reason"] for c in flags(run(turns, rec), "C8"))


def test_c8_conflicting_numbers_in_clause_flags():
    turns = ["ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಅಥವಾ 250 mg ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."]
    span = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಅಥವಾ 250 mg ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ"
    rec = record(turns, meds=[med(turns, span, 0, "amoxicillin", 500, "mg", 3, 5)])
    assert any("conflicting" in c["reason"] for c in flags(run(turns, rec), "C8"))


def test_c8_two_cues_flags():
    turns = ["ಜ್ವರ ಇಲ್ಲ ಅಂತ ಹೇಳಲಿಲ್ಲ."]
    rec = record(turns, symptoms=[sym(turns, "ಜ್ವರ", 0, "fever", False)])
    assert any("two negation cues" in c["reason"] for c in flags(run(turns, rec), "C8"))


# ------------------------------------------------------------------ registry + fail-closed
def test_registry_has_c1_to_c8():
    assert list(checks_mod.REGISTRY) == [f"C{i}" for i in range(1, 9)]


def test_disable_a_check_by_config():
    cfg = default_config(disabled=["C3"])
    turns = ["ಕೆಮ್ಮು ಇಲ್ಲ."]
    rec = record(turns, symptoms=[sym(turns, "ಕೆಮ್ಮು ಇಲ್ಲ", 0, "cough", True)])  # negation drop
    v = run(turns, rec, cfg=cfg)
    c3 = [c for c in v["checks"] if c["check_id"] == "C3"]
    assert [c["status"] for c in c3] == ["n/a"] and "disabled" in c3[0]["reason"]
    v_on = run(turns, rec)
    assert flags(v_on, "C3")


def test_all_checks_disabled_is_never_auto_acceptable():
    cfg = default_config(disabled=[f"C{i}" for i in range(1, 9)])
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]), cfg=cfg)
    assert v["auto_acceptable"] is False


@pytest.mark.parametrize("cid", [f"C{i}" for i in range(1, 9)])
def test_fail_closed_when_a_check_raises(monkeypatch, cid):
    def boom(ctx):
        raise RuntimeError("forced failure for the fail-closed test")

    monkeypatch.setattr(checks_mod.REGISTRY[cid], "fn", boom)
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]))
    errs = [c for c in v["checks"] if c["check_id"] == cid]
    assert len(errs) == 1
    assert errs[0]["status"] == "flag"
    assert errs[0]["reason"].startswith("check_error")
    assert v["auto_acceptable"] is False


def test_fail_closed_when_a_check_returns_garbage(monkeypatch):
    monkeypatch.setattr(checks_mod.REGISTRY["C5"], "fn", lambda ctx: [("maybe", "?", "/")])
    v = run(T_AMOX, record(T_AMOX, meds=[amox()]))
    c5 = [c for c in v["checks"] if c["check_id"] == "C5"]
    assert c5[0]["status"] == "flag" and c5[0]["reason"].startswith("check_error")


def test_malformed_record_does_not_crash_and_flags():
    rec = record(T_AMOX, meds=[amox()])
    del rec["medications"][0]["negated"]
    rec["medications"][0]["dose_value"] = "five hundred"
    v = verify(rec, transcript(T_AMOX), lexicon=LEX, config=default_config())
    assert validate_doc("verdict", v) == []
    assert v["auto_acceptable"] is False
    assert any(c["reason"].startswith("check_error") for c in flags(v))


def test_record_id_unusable_still_gives_valid_verdict():
    v = verify(
        {"record_id": "bad id with spaces"}, {"text": ""}, lexicon=LEX, config=default_config()
    )
    assert validate_doc("verdict", v) == []
    assert v["auto_acceptable"] is False


def test_deterministic():
    rec = record(T_AMOX, meds=[amox(dose=50)])
    a = run(T_AMOX, rec)
    b = run(T_AMOX, rec)
    assert a == b
