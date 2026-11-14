"""record.v2 fields of the rules pipeline (unit sentences only; never dev/test data).

Sentences are patterned on the gold.v2 conventions (m1_data/goldv2.py): evidence = the words
that say the field; route is only filled when said or implied by a form word."""

from __future__ import annotations

import pytest

from contracts.validate import validate_doc
from m3_extract.evidence import check_evidence
from m3_extract.rules import extract
from m3_extract.tests._helpers import CTX, make_transcript


def run2(text, lex, roles=None, schema=None):
    ctx = dict(CTX)
    if roles is not None:
        ctx["turn_roles"] = roles
    kw = {} if schema is None else {"schema": schema}
    rec, log = extract(make_transcript(text), ctx, lexicon=lex, **kw)
    name = "record.v1" if schema == "record.v1" else "record.v2"
    assert validate_doc(name, rec, transcript_text=text) == []
    assert check_evidence(rec, text) == []
    return rec, log


def med(rec, drug=None):
    ms = rec["medications"]
    if drug is None:
        assert len(ms) == 1, ms
        return ms[0]
    return next(m for m in ms if m["drug"] == drug)


def fe(m, key):
    return m["field_evidence"][key]["span_text"] if key in m["field_evidence"] else None


# ----------------------------------------------------------------------------- schema flag


def test_default_is_v2_and_v1_flag_still_works(full_lexicon):
    text = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."
    r2, _ = run2(text, full_lexicon)
    assert r2["schema_version"] == "record.v2"
    r1, _ = run2(text, full_lexicon, schema="record.v1")
    assert r1["schema_version"] == "record.v1"
    assert "route" not in r1["medications"][0] and "patient_age_band" not in r1
    # the v1 values are the same in both
    for k in ("drug", "dose_value", "dose_unit", "frequency_per_day", "duration_days", "negated"):
        assert r1["medications"][0][k] == r2["medications"][0][k]


# ----------------------------------------------------------------------------- formulation, route


def test_syrup_formulation_and_route_from_the_form_word(full_lexicon):
    text = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 2.5 ml ದಿನಕ್ಕೆ ನಾಲ್ಕು ಸಾರಿ ಮೂರು ದಿನ ಕೊಡಿ."
    m = med(run2(text, full_lexicon)[0])
    assert (m["formulation"], m["route"]) == ("syrup", "oral")
    assert fe(m, "formulation") == "ಸಿರಪ್" and fe(m, "route") == "ಸಿರಪ್"
    assert (m["dose_value"], m["dose_unit"]) == (2.5, "ml")
    assert m["strength_value"] is None and m["strength_unit"] is None  # not said


def test_latin_tablet_word_before_the_drug(full_lexicon):
    text = "Tablet Levofloxacin 500 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಏಳು ದಿವಸ."
    m = med(run2(text, full_lexicon)[0])
    assert (m["formulation"], m["route"]) == ("tablet", "oral")
    assert fe(m, "formulation") == "Tablet"
    assert (m["dose_value"], m["dose_unit"]) == (500, "mg") and m["strength_value"] is None


def test_injection_is_injection_unspecified(full_lexicon):
    text = "ceftriaxone 1000 ಎಂ.ಜಿ injection ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿವಸ ಕೊಡುತ್ತೇವೆ."
    m = med(run2(text, full_lexicon)[0])
    assert (m["formulation"], m["route"]) == ("injection", "injection_unspecified")
    assert fe(m, "route") == "injection"
    assert (m["dose_value"], m["dose_unit"]) == (1000, "mg")


def test_no_form_word_means_null_route_and_no_evidence(full_lexicon):
    text = "Ibuprofen 200 mg ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ."
    m = med(run2(text, full_lexicon, roles=["physician"])[0])
    assert m["formulation"] is None and m["route"] is None
    assert "route" not in m["field_evidence"] and "formulation" not in m["field_evidence"]


def test_drink_verb_gives_oral_route_when_no_form_word(full_lexicon):
    text = "ಓ ಆರ್ ಎಸ್ ಸ್ವಲ್ಪ ಸ್ವಲ್ಪ ಕುಡಿಸಿ."
    m = med(run2(text, full_lexicon, roles=["asha"])[0])
    assert m["route"] == "oral" and fe(m, "route") == "ಕುಡಿಸಿ"
    assert m["formulation"] is None


def test_capsule_word(full_lexicon):
    text = "ಕ್ಲಿಂಡಾಮೈಸಿನ್ ಒಂದು ಕ್ಯಾಪ್ಸೂಲ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಒಂದು ವಾರ."
    m = med(run2(text, full_lexicon)[0])
    assert m["formulation"] == "capsule" and fe(m, "formulation") == "ಕ್ಯಾಪ್ಸೂಲ್"


# ----------------------------------------------------------------------------- strength vs dose


def test_strength_and_quantity_are_separate(full_lexicon):
    for text in (
        "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg, ಎರಡು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.",
        "ಪ್ಯಾರಸಿಟಮಾಲ್ ಎರಡು ಮಾತ್ರೆ 500 mg ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.",
    ):
        m = med(run2(text, full_lexicon)[0])
        assert (m["dose_value"], m["dose_unit"]) == (2, "tablet"), text
        assert (m["strength_value"], m["strength_unit"]) == (500, "mg"), text
        assert fe(m, "strength") == "500 mg"


def test_mass_with_tablet_word_but_no_count_is_dose_not_strength(full_lexicon):
    m = med(run2("ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.", full_lexicon)[0])
    assert (m["dose_value"], m["dose_unit"]) == (500, "mg")
    assert m["strength_value"] is None and m["formulation"] == "tablet"


def test_liquid_strength_per_5_ml(full_lexicon):
    text = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 120 mg/5 ml, 5 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ."
    m = med(run2(text, full_lexicon)[0])
    assert (m["dose_value"], m["dose_unit"]) == (5, "ml")
    assert (m["strength_value"], m["strength_unit"]) == (120, "mg/5ml")
    assert fe(m, "strength") == "120 mg/5 ml"


def test_liquid_mass_and_volume_without_a_separator_is_left_null(full_lexicon):
    text = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 250 mg 5 ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ."
    rec, log = run2(text, full_lexicon)
    m = med(rec)
    assert m["dose_value"] is None and m["dose_unit"] is None
    assert m["strength_value"] is None
    assert any(e["rule"] == "ambiguous_mass_and_volume" for e in log["events"])


def test_glued_number_unit_is_read(full_lexicon):
    m = med(run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 5ml ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.", full_lexicon)[0])
    assert (m["dose_value"], m["dose_unit"]) == (5, "ml")


# ----------------------------------------------------------------------------- status


def test_statement_status_from_the_verb(full_lexicon):
    cases = [
        ("ನಿನ್ನೆ ರಾತ್ರಿ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕೊಟ್ಟೆ.", "already_taken", "ಕೊಟ್ಟೆ"),
        ("ಮಗು ಅಮಾಕ್ಸಿಸಿಲಿನ್ ಸಿರಪ್ ಕುಡಿಯುತ್ತೆ.", "already_taken", "ಕುಡಿಯುತ್ತೆ"),
        ("ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ.", "prescribed", "ತೆಗೆದುಕೊಳ್ಳಿ"),
        ("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 5 ml ಕೊಡಿ.", "prescribed", "ಕೊಡಿ"),
        ("ಸೆಟಿರಿಜಿನ್ ಸಿರಪ್ ಮಗು ಕುಡಿಯಲಿಲ್ಲ.", "not_taken", "ಕುಡಿಯಲಿಲ್ಲ"),
        ("metro ಮಾತ್ರೆ ಮಗು ತಿನ್ನಲ್ಲ.", "not_taken", "ತಿನ್ನಲ್ಲ"),
        ("ನೆಗಡಿಗೆ ಸೆಫಡ್ರೋಕ್ಸಿಲ್ ಬೇಡ.", "advised_against", "ಬೇಡ"),
        ("Amoxicillin 250 mg ಕ್ಯಾಪ್ಸೂಲ್ ತೆಗೆದುಕೊಳ್ಳದೆ ಬಿಟ್ಟೆ.", "stopped_early", "ತೆಗೆದುಕೊಳ್ಳದೆ ಬಿಟ್ಟೆ"),
    ]
    for text, status, span in cases:
        m = med(run2(text, full_lexicon, roles=["caregiver"])[0])
        assert m["status"] == status, text
        assert fe(m, "status") == span, text


def test_negated_stays_sentence_level(full_lexicon):
    m = med(run2("ಸೆಟಿರಿಜಿನ್ ಸಿರಪ್ ಮಗು ಕುಡಿಯಲಿಲ್ಲ.", full_lexicon)[0])
    assert m["negated"] is True  # the sentence is negated; the meaning is in status
    m = med(run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 5 ml ಕೊಡಿ.", full_lexicon)[0])
    assert m["negated"] is False


@pytest.mark.parametrize(
    ("text", "status", "span"),
    [
        ("ಈ ವಾರ ಪ್ಯಾರಸಿಟಮಾಲ್ ತೆಗೆದುಕೊಂಡಿದ್ದೀರಾ?\nಇಲ್ಲ.", "not_taken", "ಇಲ್ಲ"),
        ("ಈ ವಾರ ಸೆಫ್ಯುರೋಕ್ಸಿಮ್ ತೆಗೆದುಕೊಂಡಿದ್ದೀರಾ?\nಹೌದು.", "already_taken", "ಹೌದು"),
        ("ಸೆಫ್ಯುರಾಕ್ಸಿಮ್ ಎಲ್ಲ ಮುಗಿಸಿದಿರಾ?\nಇಲ್ಲ.", "stopped_early", "ಇಲ್ಲ"),
        ("ಕ್ಲಾರಿಥ್ರೋಮೈಸಿನ್ ಎಲ್ಲ ಮುಗಿಸಿದಿರಾ?\nಹೌದು.", "already_taken", "ಹೌದು"),
        (
            "ನನಗೆ ಜ್ವರ ಇದೆ, ಮನೆಯಲ್ಲಿ ಇದ್ದ ಸೆಫಾಡ್ರಾಕ್ಸಿಲ್ ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ?\nಇಲ್ಲ.",
            "advised_against",
            "ಇಲ್ಲ",
        ),
        (
            "ನನಗೆ ಜ್ವರ ಇದೆ, ಮನೆಯಲ್ಲಿ ಇದ್ದ doxycycline ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ?\nಹೌದು.",
            "prescribed",
            "ಹೌದು",
        ),
    ],
)
def test_cross_turn_answer_status_depends_on_the_question(text, status, span, full_lexicon):
    m = med(run2(text, full_lexicon, roles=["nurse", "patient"])[0])
    assert m["status"] == status
    assert fe(m, "status") == span
    assert m["field_evidence"]["status"]["char_start"] > text.index("\n")  # in the answer turn
    assert m["speaker"] == "nurse"  # the main span is the question: the asker


def test_unanswered_question_is_unknown_status(full_lexicon):
    m = med(run2("ಈ ವಾರ ಪ್ಯಾರಸಿಟಮಾಲ್ ತೆಗೆದುಕೊಂಡಿದ್ದೀರಾ?", full_lexicon, roles=["nurse"])[0])
    assert m["status"] == "unknown" and "status" not in m["field_evidence"]


def test_identity_negation_is_unknown(full_lexicon):
    text = "ಇದು ಒಂಡಾನ್ಸೆಟ್ರಾನ್ ಅಲ್ಲ, ನಾನು ಹೇಳಿದ ಮಾತ್ರೆ ಬೇರೆ."
    m = med(run2(text, full_lexicon, roles=["pharmacist"])[0])
    assert m["status"] == "unknown" and "status" not in m["field_evidence"]


def test_bare_list_item_is_prescribed_only_for_a_clinician_speaker(full_lexicon):
    text = "ಸಾಲ್ಬ್ಯುಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿವಸ."
    m = med(run2(text, full_lexicon, roles=["pharmacist"])[0])
    assert m["status"] == "prescribed"
    assert fe(m, "status") == m["evidence"]["span_text"]  # the dictated item itself
    for roles in (["patient"], None):
        assert med(run2(text, full_lexicon, roles=roles)[0])["status"] == "unknown"


# ----------------------------------------------------------------------------- speaker


def test_speaker_comes_from_the_turn_role(full_lexicon):
    text = "ಜ್ವರ ಮೂರು ದಿನದಿಂದ ಇದೆ.\nಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."
    assert med(run2(text, full_lexicon, roles=["patient", "physician"])[0])["speaker"] == "doctor"
    assert med(run2(text, full_lexicon)[0])["speaker"] == "unknown"  # no roles: never guessed


def test_advice_has_a_speaker(full_lexicon):
    text = "ನೆಗಡಿಗೆ ಪ್ರತಿಜೈವಿಕ ಬೇಡ."
    rec, _ = run2(text, full_lexicon, roles=["pharmacist"])
    assert all(a["speaker"] == "pharmacist" for a in rec["advice"])


# ----------------------------------------------------------------------------- as needed, food


def test_as_needed_includes_the_symptom_word(full_lexicon):
    t1 = "ಜ್ವರ ಇದ್ದರೆ ಮಾತ್ರ Paracetamol ಸಿರಪ್ 2.5 ಎಂ.ಎಲ್ ಕೊಡಿ."
    m = med(run2(t1, full_lexicon, roles=["asha"])[0])
    assert m["as_needed"] is True and fe(m, "as_needed") == "ಜ್ವರ ಇದ್ದರೆ ಮಾತ್ರ"
    t2 = "paracetamol ಎರಡು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಮಾತ್ರ, fever ಇದ್ದರೆ ಮಾತ್ರ."
    m = med(run2(t2, full_lexicon, roles=["physician"])[0])
    assert m["as_needed"] is True and fe(m, "as_needed") == "fever ಇದ್ದರೆ ಮಾತ್ರ"
    assert m["frequency_per_day"] == 4


def test_plain_only_word_is_not_as_needed(full_lexicon):
    text = "ಎರಿಥ್ರೋಮೈಸಿನ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಮಾತ್ರ ತೆಗೆದುಕೊಳ್ಳಿ."
    m = med(run2(text, full_lexicon)[0])
    assert m["as_needed"] is None and "as_needed" not in m["field_evidence"]


def test_as_needed_goes_to_the_drug_in_its_own_sentence(full_lexicon):
    text = (
        "ಕ್ಲಿಂಡಾಮೈಸಿನ್ ಒಂದು ಕ್ಯಾಪ್ಸೂಲ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಒಂದು ವಾರ.\n"
        "paracetamol ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ, fever ಇದ್ದರೆ ಮಾತ್ರ."
    )
    rec, _ = run2(text, full_lexicon, roles=["physician", "physician"])
    assert med(rec, "paracetamol")["as_needed"] is True
    assert med(rec, "clindamycin")["as_needed"] is None


def test_food_timing_same_sentence_goes_to_its_own_drug_only(full_lexicon):
    text = (
        "ಕ್ಲಿಂಡಾಮೈಸಿನ್ ಒಂದು ಕ್ಯಾಪ್ಸೂಲ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಒಂದು ವಾರ.\n"
        "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 250 mg ಕ್ಯಾಪ್ಸೂಲ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಒಂದು ವಾರ, ಊಟದ ನಂತರ."
    )
    rec, _ = run2(text, full_lexicon, roles=["pharmacist"] * 2)
    a = med(rec, "amoxicillin")
    assert a["food_timing"] == "after_food" and fe(a, "food_timing") == "ಊಟದ ನಂತರ"
    assert med(rec, "clindamycin")["food_timing"] is None


def test_food_timing_asked_by_the_patient_and_confirmed(full_lexicon):
    base = "ನೈಟ್ರೋಫ್ಯುರಾಂಟೋಯಿನ್ 100 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಒಂದು ವಾರ ತೆಗೆದುಕೊಳ್ಳಿ.\n"
    ask = "ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಬೇಕು, ಅಲ್ವ?\n"
    roles = ["pharmacist", "patient", "pharmacist"]
    m = med(run2(base + ask + "ಹೌದು.", full_lexicon, roles=roles)[0])
    assert m["food_timing"] == "after_food" and fe(m, "food_timing") == "ಊಟದ ನಂತರ"
    m = med(run2(base + ask + "ಇಲ್ಲ.", full_lexicon, roles=roles)[0])
    assert m["food_timing"] is None  # denied: not recorded


# ----------------------------------------------------------------------------- age, weight


@pytest.mark.parametrize(
    ("text", "band", "span"),
    [
        ("ಮಗುವಿಗೆ ಜ್ವರ ಬಂದಿದೆ.", "child", "ಮಗುವಿಗೆ"),
        ("ಮಗು ಸ್ವಲ್ಪ ಸ್ವಲ್ಪ ಕುಡಿಯುತ್ತೆ.", "child", "ಮಗು"),
        ("ಐದು ವರ್ಷದ ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ.", "child", "ಐದು ವರ್ಷದ"),
        ("ಎಂಟು ತಿಂಗಳ ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ.", "infant", "ಎಂಟು ತಿಂಗಳ"),
        ("ಹನ್ನೆರಡು ವರ್ಷದ ಹುಡುಗನಿಗೆ ಜ್ವರ ಇದೆ.", "adolescent", "ಹನ್ನೆರಡು ವರ್ಷದ"),
        ("ನನಗೆ ಎಪ್ಪತ್ತು ವರ್ಷ.", None, None),  # ಎಪ್ಪತ್ತು is not in the number list: not guessed
        ("ನನಗೆ ಜ್ವರ ಇದೆ.", None, None),
    ],
)
def test_age_band(text, band, span, full_lexicon):
    rec, _ = run2(text, full_lexicon)
    if band is None:
        assert rec["patient_age_band"] is None
    else:
        assert rec["patient_age_band"]["band"] == band
        assert rec["patient_age_band"]["evidence"]["span_text"] == span


def test_age_number_and_digits(full_lexicon):
    rec, _ = run2("65 ವರ್ಷದ ರೋಗಿಗೆ ಜ್ವರ ಇದೆ.", full_lexicon)
    assert rec["patient_age_band"]["band"] == "older_adult"
    rec, _ = run2("೩೫ ವರ್ಷದ ರೋಗಿಗೆ ಜ್ವರ ಇದೆ.", full_lexicon)
    assert rec["patient_age_band"]["band"] == "adult"
    assert rec["patient_age_band"]["evidence"]["span_text"] == "೩೫ ವರ್ಷದ"


def test_a_duration_in_years_is_not_an_age(full_lexicon):
    rec, _ = run2("ಮೂರು ವರ್ಷದಿಂದ ಜ್ವರ ಇದೆ.", full_lexicon)
    assert rec["patient_age_band"] is None


def test_weight(full_lexicon):
    rec, _ = run2("ಮಗುವಿನ ತೂಕ ಹತ್ತು ಕೆಜಿ.", full_lexicon)
    assert rec["weight_kg"]["value"] == 10
    assert rec["weight_kg"]["evidence"]["span_text"] == "ಹತ್ತು ಕೆಜಿ"
    rec, _ = run2("weight 12.5 kg ಇದೆ.", full_lexicon)
    assert rec["weight_kg"]["value"] == 12.5
    rec, _ = run2("ಪ್ಯಾರಸಿಟಮಾಲ್ 15 mg ಪ್ರತಿ ಕೆಜಿ.", full_lexicon)
    assert rec["weight_kg"] is None  # a per-kg dose is not a weight


# ----------------------------------------------------------------------------- accepted review items


def test_once_every_two_days_is_not_per_day(full_lexicon):
    text = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ಎರಡು ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."
    rec, log = run2(text, full_lexicon)
    assert med(rec)["frequency_per_day"] is None
    assert any(e["rule"] == "frequency_not_per_day" for e in log["events"])
    ok = med(run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ.", full_lexicon)[0])
    assert ok["frequency_per_day"] == 1


def test_one_and_a_half(full_lexicon):
    m = med(run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದೂವರೆ ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.", full_lexicon)[0])
    assert (m["dose_value"], m["dose_unit"]) == (1.5, "tablet")


def test_spoon_needs_a_liquid_context(full_lexicon):
    m = med(run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಎರಡು ಚಮಚ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.", full_lexicon)[0])
    assert (m["dose_value"], m["dose_unit"]) == (2, "teaspoon")
    rec, log = run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಎರಡು ಚಮಚ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.", full_lexicon)
    assert (med(rec)["dose_value"], med(rec)["dose_unit"]) == (None, None)
    assert any(e["rule"] == "unit_needs_context" for e in log["events"])


def test_packet_is_a_sachet_only_for_ors(full_lexicon):
    m = med(run2("ಓ ಆರ್ ಎಸ್ ಒಂದು ಪ್ಯಾಕೆಟ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.", full_lexicon)[0])
    assert (m["dose_value"], m["dose_unit"]) == (1, "sachet")
    rec, _ = run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಎರಡು ಪ್ಯಾಕೆಟ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.", full_lexicon)
    assert (med(rec)["dose_value"], med(rec)["dose_unit"]) == (None, None)


def test_symptom_duration_is_not_the_course_length(full_lexicon):
    text = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಜ್ವರ ಮೂರು ದಿನ ಇದ್ದರೆ ಕೊಡಿ."
    rec, log = run2(text, full_lexicon)
    assert med(rec)["duration_days"] is None
    assert any(e["rule"] == "duration_next_to_symptom" for e in log["events"])
    m = med(run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಮೂರು ದಿನ.", full_lexicon)[0])
    assert m["duration_days"] == 3


# ----------------------------------------------------------------------------- combination products


def test_amoxiclav_625_is_one_drug(full_lexicon):
    for text in (
        "ಅಮಾಕ್ಸಿಕ್ಲಾವ್ 625 ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ.",
        "amoxiclav 625 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ.",
        "amox 625 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ.",
        "625 ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ.",
    ):
        rec, _ = run2(text, full_lexicon)
        assert [m["drug"] for m in rec["medications"]] == ["amoxicillin-clavulanate"], text


def test_bare_625_is_not_a_drug(full_lexicon):
    rec, _ = run2("ನನ್ನ ಬಿಲ್ 625 ರೂಪಾಯಿ.", full_lexicon)
    assert rec["medications"] == []
    rec, _ = run2("ಪ್ಯಾರಸಿಟಮಾಲ್ ಒಂದು ಮಾತ್ರೆ 625 ಬಾರಿ.", full_lexicon)
    assert [m["drug"] for m in rec["medications"]] == ["paracetamol"]


def test_plain_amoxicillin_dose_not_hijacked(full_lexicon):
    rec, _ = run2("amox 500 mg ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ.", full_lexicon)
    (m,) = rec["medications"]
    assert m["drug"] == "amoxicillin" and (m["dose_value"], m["dose_unit"]) == (500, "mg")


def test_iron_folic_acid_count_dose_and_ambiguous_mass(full_lexicon):
    m = med(run2("IFA 1 tablet ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ.", full_lexicon)[0])
    assert m["drug"] == "iron-folic acid" and (m["dose_value"], m["dose_unit"]) == (1, "tablet")
    rec, log = run2("IFA 100 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ.", full_lexicon)
    m = med(rec)
    assert (m["dose_value"], m["dose_unit"]) == (None, None)  # which component? not guessed
    assert any(e["rule"] == "combination_mass_unit" for e in log["events"])


def test_evidence_check_covers_field_spans_age_and_weight(full_lexicon):
    import copy

    text = "ಐದು ವರ್ಷದ ಮಗು 12 kg. ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 5 ml ಕೊಡಿ."
    rec, _ = run2(text, full_lexicon, roles=["asha"])
    forged = copy.deepcopy(rec)
    forged["medications"][0]["field_evidence"]["route"]["span_text"] = "ಇಂಜೆಕ್ಷನ್"
    assert any("route" in e for e in check_evidence(forged, text))
    forged = copy.deepcopy(rec)
    forged["patient_age_band"]["evidence"]["char_start"] += 1
    forged["patient_age_band"]["evidence"]["char_end"] += 1
    assert any("patient_age_band" in e for e in check_evidence(forged, text))
    forged = copy.deepcopy(rec)
    forged["weight_kg"]["evidence"]["span_text"] = "99 kg"
    assert any("weight_kg" in e for e in check_evidence(forged, text))


def test_identity_denial_does_not_take_the_other_tablets_form(full_lexicon):
    text = "ಇದು ಒಂಡಾನ್ಸೆಟ್ರಾನ್ ಅಲ್ಲ, ನಾನು ಹೇಳಿದ ಮಾತ್ರೆ ಬೇರೆ."
    m = med(run2(text, full_lexicon, roles=["pharmacist"])[0])
    assert m["formulation"] is None and m["route"] is None


def test_the_other_tablet_phrase_gives_no_form(full_lexicon):
    text = "ಇದು ಮೆಟ್ಫಾರ್ಮಿನ್, ನಾನು ಹೇಳಿದ ಮಾತ್ರೆ ಬೇರೆ."
    m = med(run2(text, full_lexicon, roles=["pharmacist"])[0])
    assert m["formulation"] is None and m["route"] is None
