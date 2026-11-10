import pytest

from m3_extract import textnorm as tn
from m3_extract.numbers import parse_number
from m3_extract.units import parse_attributes


@pytest.mark.parametrize(
    "tok,val",
    [
        ("500", 500),
        ("೫೦೦", 500),
        ("೨೫೦", 250),
        ("2.5", 2.5),
        ("ಒಂದು", 1),
        ("ಎರಡು", 2),
        ("ಮೂರು", 3),
        ("ನಾಲ್ಕು", 4),
        ("ಐದು", 5),
        ("ಏಳು", 7),
        ("ಹತ್ತು", 10),
        ("ಹದಿನಾಲ್ಕು", 14),
        ("ಅರ್ಧ", 0.5),
    ],
)
def test_parse_number(tok, val):
    assert parse_number(tn.comparison_form(tok)) == val


@pytest.mark.parametrize("tok", ["ದಿನ", "mg", "ಮಾತ್ರೆ", "ಎಲ್ಲ", ""])
def test_not_a_number(tok):
    assert parse_number(tn.comparison_form(tok)) is None


def attrs(text):
    return parse_attributes(tn.tokenize(text))


def test_full_instruction():
    a = attrs("500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ")
    assert (a.dose_value, a.dose_unit, a.frequency_per_day, a.duration_days) == (500, "mg", 3, 5)


def test_kannada_unit_and_week():
    a = attrs("1000 ಎಂ.ಜಿ injection ದಿನಕ್ಕೆ ಒಂದು ಸಾರಿ ಒಂದು ವಾರ")
    assert (a.dose_value, a.dose_unit, a.frequency_per_day, a.duration_days) == (1000, "mg", 1, 7)


def test_tablet_and_capsule_counts():
    a = attrs("ಎರಡು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಸಲ ಮೂರು ದಿವಸ")
    assert (a.dose_value, a.dose_unit, a.frequency_per_day, a.duration_days) == (2, "tablet", 4, 3)
    a = attrs("ಒಂದು ಕ್ಯಾಪ್ಸೂಲ್ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಹದಿನಾಲ್ಕು ದಿವಸ")
    assert (a.dose_value, a.dose_unit, a.duration_days) == (1, "capsule", 14)


def test_first_unit_after_number_wins():
    a = attrs("250 mg ಕ್ಯಾಪ್ಸೂಲ್ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ")
    assert (a.dose_value, a.dose_unit) == (250, "mg")


def test_since_and_within_are_not_durations():
    assert attrs("ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ").duration_days is None
    assert attrs("ಎರಡು ದಿನದಲ್ಲಿ ಮತ್ತೆ ಬನ್ನಿ").duration_days is None


def test_this_week_is_not_a_duration():
    assert attrs("ಈ ವಾರ").duration_days is None


def test_attribute_token_span_reported():
    toks = tn.tokenize("500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಮಾತ್ರ")
    a = parse_attributes(toks)
    assert a.last_token_index == 4  # ... ಬಾರಿ, not ಮಾತ್ರ (trap word "only")
