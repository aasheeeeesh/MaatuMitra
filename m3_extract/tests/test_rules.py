"""Rules pipeline on hand-made fixtures and unit sentences (never dev/test data)."""

import pytest

from contracts.validate import validate_doc
from m3_extract.evidence import check_evidence
from m3_extract.rules import extract
from m3_extract.scoring import score_record
from m3_extract.tests._helpers import CTX, FIX, fixture_pairs, load_json, make_transcript


def run(text, lex):
    rec, log = extract(make_transcript(text), CTX, lexicon=lex, schema="record.v1")
    assert validate_doc("record.v1", rec) == []
    assert check_evidence(rec, text) == []
    return rec, log


@pytest.mark.parametrize("pair", fixture_pairs(), ids=lambda p: p[0]["conversation_id"])
def test_fixture_records_valid_and_no_critical_or_major_errors(pair, fx_lexicon):
    gold, tr = pair
    ctx = {k: gold["gold_record"][k] for k in ("patient_ref", "encounter_type")}
    rec, _ = extract(tr, ctx, lexicon=fx_lexicon, schema="record.v1")
    assert validate_doc("record.v1", rec) == []
    assert check_evidence(rec, tr["text"]) == []
    errs = [r for r in score_record(rec, gold) if r.code and r.severity in ("critical", "major")]
    assert errs == [], [(e.code, e.detail) for e in errs]


def test_cross_turn_negation_span_in_question_turn(fx_lexicon):
    text = "ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?\nಇಲ್ಲ."
    rec, log = run(text, fx_lexicon)
    (m,) = rec["medications"]
    assert m["negated"] is True
    ev = m["evidence"]
    assert ev["char_end"] <= text.index("\n")  # evidence stays in the question turn
    assert "ಪ್ಯಾರಸಿಟಮಾಲ್" in ev["span_text"]
    assert any(e["rule"] == "cross_turn" for e in log["events"])


def test_cross_turn_affirmative_symptom(full_lexicon):
    rec, _ = run("ತಲೆನೋವು ಇದೆಯಾ?\nಹೌದು.", full_lexicon)
    assert [(s["name"], s["present"]) for s in rec["symptoms"]] == [("headache", True)]


def test_negated_medication_span_includes_cue(full_lexicon):
    text = "ಕೊಡುತ್ತೇವೆ, ಆದರೆ ಮಗು ಸೆಟಿರಿಜಿನ್ ಸಿರಪ್ ಕುಡಿಯಲಿಲ್ಲ."
    rec, _ = run(text, full_lexicon)
    (m,) = rec["medications"]
    assert m["negated"] is True
    assert m["evidence"]["span_text"] == "ಸೆಟಿರಿಜಿನ್ ಸಿರಪ್ ಕುಡಿಯಲಿಲ್ಲ"


def test_identity_negation_alla(full_lexicon):
    text = "ಇದು ಒಂಡಾನ್ಸೆಟ್ರಾನ್ ಮಾತ್ರೆನಾ?\nಇದು ಒಂಡಾನ್ಸೆಟ್ರಾನ್ ಅಲ್ಲ, ನಾನು ಹೇಳಿದ ಮಾತ್ರೆ ಬೇರೆ."
    rec, _ = run(text, full_lexicon)
    (m,) = rec["medications"]
    assert m["drug"] == "ondansetron" and m["negated"] is True


def test_trap_sentence_not_negated(full_lexicon):
    text = "ಎರಿಥ್ರೋಮೈಸಿನ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಮಾತ್ರ ತೆಗೆದುಕೊಳ್ಳಿ.\nಎಲ್ಲಾ ಮಾತ್ರೆ ಇಲ್ಲಿ ಇವೆ, ಅಲ್ವಾ?"
    rec, _ = run(text, full_lexicon)
    (m,) = rec["medications"]
    assert (m["drug"], m["dose_value"], m["dose_unit"], m["frequency_per_day"], m["negated"]) == (
        "erythromycin",
        1,
        "tablet",
        4,
        False,
    )
    assert rec["symptoms"] == [] and rec["advice"] == []


def test_two_drugs_in_one_turn_do_not_share_attributes(full_lexicon):
    text = "OK. erythromycin ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಒಂದು ವಾರ ತೆಗೆದುಕೊಳ್ಳಿ. Cetirizine ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ ಕೂಡ."
    rec, _ = run(text, full_lexicon)
    got = {m["drug"]: (m["frequency_per_day"], m["duration_days"]) for m in rec["medications"]}
    assert got == {"erythromycin": (4, 7), "cetirizine": (1, 5)}


def test_symptom_in_conditional_clause_is_ignored(full_lexicon):
    rec, _ = run("ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಎರಡು ದಿನದಲ್ಲಿ ಮತ್ತೆ ಬನ್ನಿ.", full_lexicon)
    assert rec["symptoms"] == []
    assert rec["follow_up"] is not None


def test_coordinated_symptoms_share_predicate(full_lexicon):
    rec, _ = run("ವಾಂತಿ ಮತ್ತು ಅತಿಸಾರ ಇದೆ.", full_lexicon)
    assert sorted((s["name"], s["present"]) for s in rec["symptoms"]) == [
        ("diarrhoea", True),
        ("vomiting", True),
    ]


def test_how_many_days_question_presupposes_symptom(full_lexicon):
    rec, _ = run("ಜ್ವರ ಎಷ್ಟು ದಿನದಿಂದ ಇದೆ?\nನಾಲ್ಕು ದಿನದಿಂದ, ಚಳಿ ಇಲ್ಲ.", full_lexicon)
    assert sorted((s["name"], s["present"]) for s in rec["symptoms"]) == [
        ("chills", False),
        ("fever", True),
    ]


def test_plain_question_without_answer_is_not_a_symptom(full_lexicon):
    rec, _ = run("ಜ್ವರ ಕಡಿಮೆ ಆದ ಮೇಲೆ ಏನು ಮಾಡಿದಿರಿ?", full_lexicon)
    assert rec["symptoms"] == []


def test_clause_with_drug_is_not_advice(full_lexicon):
    rec, _ = run("ಓ ಆರ್ ಎಸ್ ಸ್ವಲ್ಪ ಸ್ವಲ್ಪ ಕುಡಿಸಿ.", full_lexicon)
    assert rec["advice"] == []
    rec, _ = run("ಸ್ವಲ್ಪ ಸ್ವಲ್ಪ ಕುಡಿಸಿ.", full_lexicon)
    assert [a["text"] for a in rec["advice"]] == ["give it to drink little by little"]


def test_advice_polarity_from_table(full_lexicon):
    rec, _ = run("ಉಳಿದ ಮಾತ್ರೆ ಬೇರೆಯವರಿಗೆ ಕೊಡಬೇಡಿ.", full_lexicon)
    assert [(a["text"], a["negated"]) for a in rec["advice"]] == [
        ("do not give leftover tablets to others", True)
    ]


def test_asr_fixture_keeps_audio_times_and_faithful_value(fx_lexicon):
    tr = load_json(FIX / "transcript" / "valid" / "fx-pharm-003__asr_digit_error.json")
    rec, _ = extract(
        tr,
        {"patient_ref": "pt-fx-0003", "encounter_type": "pharmacist_dispensing"},
        lexicon=fx_lexicon,
        schema="record.v1",
    )
    (m,) = rec["medications"]
    assert m["dose_value"] == 50  # faithful to what the ASR wrote (the error is upstream)
    assert m["evidence"]["audio_start"] == 0.3
    assert m["evidence"]["audio_end"] is not None
    assert validate_doc("record.v1", rec) == []


def test_extraction_log_records_drug_match_type(full_lexicon):
    _, log = run("azithromycn 500 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ", full_lexicon)
    assert any(e["rule"] == "drug_match" and e["match_type"] == "edit1" for e in log["events"])


def test_multi_token_symptom(full_lexicon):
    rec, _ = run("ಎರಡು ದಿನದಿಂದ, ಉಸಿರಾಟದ ತೊಂದರೆ ಇದೆ.", full_lexicon)
    assert [(s["name"], s["present"]) for s in rec["symptoms"]] == [("breathing difficulty", True)]
    assert rec["symptoms"][0]["evidence"]["span_text"] == "ಉಸಿರಾಟದ ತೊಂದರೆ ಇದೆ"


def test_follow_up_gloss_follows_if_not_cue(full_lexicon):
    rec, _ = run("ವಾಂತಿ ನಿಲ್ಲದಿದ್ದರೆ ತಕ್ಷಣ ಬನ್ನಿ.", full_lexicon)
    assert rec["follow_up"]["text"] == "if the vomiting does not stop, come immediately"
    rec, _ = run("ವಾಂತಿ ನಿಂತರೆ ತಕ್ಷಣ ಬನ್ನಿ.", full_lexicon)
    assert rec["follow_up"]["text"] == "if the vomiting stops, come immediately"


def test_trouble_is_not_a_conditional(full_lexicon):
    rec, _ = run("ಯಾವುದೇ ಉಸಿರಾಟದ ತೊಂದರೆ ಇಲ್ಲ.", full_lexicon)
    assert [(s["name"], s["present"]) for s in rec["symptoms"]] == [("breathing difficulty", False)]


def test_statement_clause_inside_question_sentence_is_not_answered(full_lexicon):
    # rules v2 fix (found on dev_holdout, see decisions): "I have fever, can I take X? / No."
    # The bare "No" answers the question about the drug, NOT the statement about fever.
    text = "ನನಗೆ ಜ್ವರ ಇದೆ, ಮನೆಯಲ್ಲಿ ಇದ್ದ ಅಜಿತ್ರೋಮೈಸಿನ್ ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ?\nಇಲ್ಲ."
    rec, _ = run(text, full_lexicon)
    assert [(s["name"], s["present"]) for s in rec["symptoms"]] == [("fever", True)]
    assert [(m["drug"], m["negated"]) for m in rec["medications"]] == [("azithromycin", True)]


def test_listed_nouns_in_question_stay_question(full_lexicon):
    rec, _ = run("ನೆಗಡಿ, ಚಳಿ, ಸುಸ್ತು ಇದೆಯಾ?\nಇಲ್ಲ.", full_lexicon)
    assert sorted((s["name"], s["present"]) for s in rec["symptoms"]) == [
        ("chills", False),
        ("cold", False),
        ("tiredness", False),
    ]


# ---- fix pass 2026-11-11 (D-93 Kannada review findings) ----


def test_fever_follow_up_accepts_aagiddare(full_lexicon):
    rec, _ = run("ಜ್ವರ ಕಡಿಮೆ ಆಗಿದ್ದರೆ ಎರಡು ದಿನದಲ್ಲಿ ಮತ್ತೆ ಬನ್ನಿ.", full_lexicon)
    assert rec["follow_up"]["text"] == "if the fever comes down, come back in two days"
    rec, _ = run("ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಎರಡು ದಿನದಲ್ಲಿ ಮತ್ತೆ ಬನ್ನಿ.", full_lexicon)
    assert rec["follow_up"]["text"] == "if the fever does not come down, come back in two days"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ಜ್ವರವಿಲ್ಲ.", [("fever", False)]),
        ("ಕೆಮ್ಮಿಲ್ಲ, ತಲೆನೋವಿದೆ.", [("cough", False), ("headache", True)]),
        ("ವಾಂತಿಯಿಲ್ಲ.", [("vomiting", False)]),
        ("ಜ್ವರವಿದೆ.", [("fever", True)]),
    ],
)
def test_fused_symptom_with_ila_or_ide(full_lexicon, text, expected):
    rec, _ = run(text, full_lexicon)
    assert sorted((s["name"], s["present"]) for s in rec["symptoms"]) == sorted(expected)


def test_fused_symptom_evidence_is_the_fused_token(full_lexicon):
    rec, _ = run("ಜ್ವರವಿಲ್ಲ.", full_lexicon)
    assert rec["symptoms"][0]["evidence"]["span_text"] == "ಜ್ವರವಿಲ್ಲ"


def test_packet_is_a_sachet_unit(full_lexicon):
    rec, _ = run("ಓ.ಆರ್.ಎಸ್ ಒಂದು ಪ್ಯಾಕೆಟ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಕುಡಿಯಿರಿ.", full_lexicon)
    (m,) = rec["medications"]
    assert (m["drug"], m["dose_value"], m["dose_unit"], m["frequency_per_day"]) == (
        "ors",
        1,
        "sachet",
        3,
    )


# ---- child paracetamol syrup in ml (REFREEZE-1, D-110) ----


@pytest.mark.parametrize(
    "text,value",
    [
        ("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಎರಡೂವರೆ ಎಂ.ಎಲ್ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಕೊಡಿ.", 2.5),
        ("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 2.5 ಎಂ.ಎಲ್ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಕೊಡಿ.", 2.5),
        ("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 10 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಕೊಡಿ.", 10),
        ("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಹತ್ತು ಎಂ.ಎಲ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಕೊಡಿ.", 10),
    ],
)
def test_child_syrup_ml_dose(full_lexicon, text, value):
    rec, _ = run("ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ. " + text, full_lexicon)
    (m,) = rec["medications"]
    assert (m["drug"], m["dose_value"], m["dose_unit"]) == ("paracetamol", value, "ml")


def test_child_turn_without_dose_gets_no_invented_tablet_dose(full_lexicon):
    rec, _ = run("ಮಗುವಿಗೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕೊಡಿ.", full_lexicon)
    (m,) = rec["medications"]
    assert (m["dose_value"], m["dose_unit"]) == (None, None)


# ---- REFREEZE-1 wording regressions seen on dev_tune (in-sample additions, disclosed) ----


def test_only_if_fever_condition_inside_a_drug_clause(full_lexicon):
    rec, _ = run("ಜ್ವರ ಇದ್ದರೆ ಮಾತ್ರ ಪ್ಯಾರಸಿಟಮೋಲ್ ಸಿರಪ್ ಎರಡೂವರೆ ಎಂ.ಎಲ್ ಕೊಡಿ.", full_lexicon)
    assert [a["text"] for a in rec["advice"]] == ["only if there is fever"]
    (m,) = rec["medications"]
    assert (m["dose_value"], m["dose_unit"]) == (2.5, "ml")
    assert rec["symptoms"] == []  # the fever sits inside an "if" clause


def test_vomiting_if_come_immediately_follow_up(full_lexicon):
    rec, _ = run("ವಾಂತಿ ಇದ್ದರೆ ತಕ್ಷಣ ಬನ್ನಿ.", full_lexicon)
    assert rec["follow_up"]["text"] == "if there is vomiting, come immediately"
