"""record.v2 vocabulary of the verifier (m4_verify/v2rules.py): one positive, one minimal-pair
negative twin and one trap per cue family. Kannada written by an AI agent, NOT native-validated.
"""

from __future__ import annotations

import pytest

from m4_verify import v2rules as R


# ---------------------------------------------------------------- route words
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ceftriaxone 1000 mg IV ಕೊಡಿ", {"iv"}),  # positive
        ("Ceftriaxone 1000 mg ಕೊಡಿ", set()),  # minimal pair: route word removed
        ("ceftriaxone i.v. ಕೊಡಿ", {"iv"}),
        ("IM injection ಕೊಡಿ", {"im", "injection"}),
        ("SC injection", {"sc", "injection"}),
        ("ಇಂಜೆಕ್ಷನ್ ಕೊಡಿ", {"injection"}),
        ("ಇಂಜೆಕ್ಷನ್ನು ಕೊಡಿ", {"injection"}),  # case ending on a Kannada form
        ("ಚುಚ್ಚುಮದ್ದು ಕೊಡಿ", {"injection"}),
        ("ಸಿರಪ್ ಕುಡಿಸಿ", {"oral"}),
        ("ಮಾತ್ರೆ ನುಂಗಿ", {"oral"}),
        ("ಮುಲಾಮು ಹಚ್ಚಿ", {"topical"}),
        ("inhaler ಬಳಸಿ", {"inhaled"}),
        # traps: ಇಂದು (today), ಇಲ್ಲಿ (here), "i" alone, ಕುಡುಕ-like words that only share letters
        ("ಇಂದು ಇಲ್ಲಿ ಬನ್ನಿ", set()),
        ("i am fine", set()),
        ("ಎರಡು ದಿನ ಸಿಮ್ ಕಾರ್ಡ್", set()),
    ],
)
def test_route_cues(text, expected):
    assert R.route_cues(text) == expected


# ---------------------------------------------------------------- formulation words
@pytest.mark.parametrize(
    "text,expected",
    [
        ("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", {"syrup"}),
        ("ಪ್ಯಾರಸಿಟಮಾಲ್", set()),
        ("500 mg ಮಾತ್ರೆ", {"tablet"}),
        ("ಎರಡು ಮಾತ್ರ", set()),  # trap: ಮಾತ್ರ (only) is not ಮಾತ್ರೆ (tablet)
        ("ಕ್ಯಾಪ್ಸೂಲ್", {"capsule"}),
        ("suspension 5 ml", {"suspension"}),
        ("ಎರಡು ಹನಿ", {"drops"}),
        ("ORS ಪ್ಯಾಕೆಟ್", {"sachet"}),
        ("injection", {"injection"}),
    ],
)
def test_formulation_cues(text, expected):
    assert R.formulation_cues(text) == expected


# ---------------------------------------------------------------- strength phrases
def _keys(text):
    return {s.key for s in R.parse_strengths(text)}


def test_strength_per_5ml_and_equivalents():
    k = _keys("ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 120 mg/5 ml, 5 ml")
    assert R.strength_key(120, "mg/5ml") in k
    assert R.strength_key(24, "mg/ml") in k  # same concentration, other unit
    assert R.strength_key(250, "mg/5ml") not in k  # minimal pair: other value


def test_strength_per_word_and_kannada_digits():
    assert R.strength_key(125, "mg/5ml") in _keys("ಸಿರಪ್ ೧೨೫ mg per 5 ml")
    assert R.strength_key(500, "mg") in _keys("500 mg ಮಾತ್ರೆ")
    assert R.strength_key(0.5, "g") in _keys("500 mg ಮಾತ್ರೆ")  # 0.5 g == 500 mg


def test_strength_trap_dose_volume_is_not_a_concentration():
    # "5 ml" alone is a volume (a dose), never a strength; "1 % ..." needs a % sign
    assert _keys("5 ml ಕುಡಿಸಿ") == set()
    assert R.strength_key(1, "%") in _keys("1% cream")
    assert R.strength_key(1, "%") not in _keys("1 cream")


# ---------------------------------------------------------------- age and weight
@pytest.mark.parametrize(
    "text,band",
    [
        ("ಮಗುವಿಗೆ ಒಂದು ವರ್ಷ", "child"),  # 1 year -> child (1-9 y)
        ("ಆರು ತಿಂಗಳು", "infant"),
        ("ಏಳು ವರ್ಷ", "child"),
        ("14 ವರ್ಷ", "adolescent"),
        ("30 ವರ್ಷ", "adult"),
        ("70 ವರ್ಷ", "older_adult"),
    ],
)
def test_age_from_number(text, band):
    bands, _ = R.age_bands(text)
    assert bands == {band}


def test_age_child_word_without_number_allows_child_or_infant():
    bands, _ = R.age_bands("ಮಗು")
    assert bands == {"child", "infant"}


def test_age_trap_number_without_age_word():
    # "ಮೂರು ದಿನ" is a duration in a consultation, not an age: nothing derivable
    bands, _ = R.age_bands("ಮೂರು ದಿನದಿಂದ ಜ್ವರ")
    assert bands is None


def test_weights():
    assert R.weights("ತೂಕ 10 kg") == [10]
    assert R.weights("ತೂಕ ಹತ್ತು ಕೆಜಿ") == [10]
    assert R.weights("10 ದಿನ") == []  # trap: a number without a weight unit


# ---------------------------------------------------------------- as needed / regular
@pytest.mark.parametrize(
    "text,prn",
    [
        ("ಜ್ವರ ಇದ್ದರೆ ಮಾತ್ರ ಕೊಡಿ", True),
        ("ಜ್ವರ ಇದೆ, ಕೊಡಿ", False),  # minimal pair
        ("ನೋವು ಬಂದರೆ ತೆಗೆದುಕೊಳ್ಳಿ", True),
        ("ಬೇಕಾದರೆ ತೆಗೆದುಕೊಳ್ಳಿ", True),
        ("take if needed", True),
        ("SOS", True),
        ("ಜ್ವರ ಇದೆ, ಆದರೆ ಕೆಮ್ಮು ಇಲ್ಲ", False),  # trap: ಆದರೆ = "but"
        ("ಅಂದರೆ ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ", False),  # trap: ಅಂದರೆ = "that is"
    ],
)
def test_prn_cues(text, prn):
    assert bool(R.prn_cues(text)) is prn


def test_regular_cues():
    assert R.regular_cues("ಪ್ರತಿದಿನ ತಪ್ಪದೆ ತೆಗೆದುಕೊಳ್ಳಿ")
    assert not R.regular_cues("ಜ್ವರ ಇದ್ದರೆ ತೆಗೆದುಕೊಳ್ಳಿ")


# ---------------------------------------------------------------- food timing
@pytest.mark.parametrize(
    "text,expected",
    [
        ("ಊಟದ ನಂತರ", {"after_food"}),
        ("ಊಟದ ಮೊದಲು", {"before_food"}),  # minimal pair
        ("ಊಟಕ್ಕೆ ಮುಂಚೆ", {"before_food"}),
        ("ಊಟ ಆದ ಮೇಲೆ", {"after_food"}),
        ("ಊಟದ ಜೊತೆ", {"with_food"}),
        ("ಖಾಲಿ ಹೊಟ್ಟೆಯಲ್ಲಿ", {"empty_stomach"}),
        ("after food", {"after_food"}),
        ("ಊಟ ಮಾಡಿ", set()),  # trap: food word without a timing word
        ("ನಂತರ ಬನ್ನಿ", set()),  # trap: timing word without food
    ],
)
def test_food_timing(text, expected):
    assert R.food_timings(text) == expected


# ---------------------------------------------------------------- status cues
@pytest.mark.parametrize(
    "text,past",
    [
        ("ನಿನ್ನೆ ರಾತ್ರಿ ಸಿರಪ್ ಕೊಟ್ಟೆ", True),
        ("ರಾತ್ರಿ ಸಿರಪ್ ಕೊಡಿ", False),  # minimal pair: imperative
        ("ಮಾತ್ರೆ ತೆಗೆದುಕೊಂಡೆ", True),
        ("ಮಾತ್ರೆ ತಗೊಂಡಿದ್ದೇನೆ", True),
        ("ಮಗು ಸಿರಪ್ ಕುಡಿಯಿತಾ", True),
        ("ಈಗಾಗಲೇ ಕೊಟ್ಟಿದ್ದೇವೆ", True),
        ("ಹೊಟ್ಟೆ ನೋವು ಇದೆ", False),  # trap: ಹೊಟ್ಟೆ (stomach) ends like ಕೊಟ್ಟೆ
        ("ಸರಿ ಆಯಿತು", False),  # trap: ಆಯಿತು filler "ok, done"
        ("ಮೊಟ್ಟೆ ತಿನ್ನಬಹುದು", False),  # trap: ಮೊಟ್ಟೆ (egg)
    ],
)
def test_past_cues(text, past):
    assert bool(R.past_cues(text)) is past


@pytest.mark.parametrize(
    "text,aa",
    [
        ("Ibuprofen ಕೊಡಬೇಡಿ", True),
        ("Ibuprofen ಕೊಡಿ", False),  # minimal pair
        ("antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು", True),
        ("ಇದು ಬೇಡ", True),
        ("do not give aspirin", True),
        ("ಔಷಧಿಗೆ ಬೇಡಿಕೆ ಇದೆ", False),  # trap: ಬೇಡಿಕೆ = demand
        ("ಮಾತ್ರೆ ಬೇಕು", False),  # trap: ಬೇಕು = needed (positive)
    ],
)
def test_advise_against_cues(text, aa):
    assert bool(R.advise_against_cues(text)) is aa


@pytest.mark.parametrize(
    "text,directive",
    [
        ("ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಿ", True),
        ("ಮಾತ್ರೆ ತೆಗೆದುಕೊಂಡೆ", False),  # minimal pair: past
        ("ಸಿರಪ್ ಕೊಡಿ", True),
        ("ಸಿರಪ್ ಕುಡಿಸಿ", True),
        ("ಇದೇ ಮಾತ್ರೆ ಮುಂದುವರಿಸಿ", True),
        ("take one tablet", True),
        ("Ibuprofen ಕೊಡಬೇಡಿ", False),  # trap: ends in -ಡಿ but is "don't give"
        ("ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಬೇಕಾ", False),  # trap: question "should I take?"
    ],
)
def test_directive_cues(text, directive):
    assert bool(R.directive_cues(text)) is directive


def test_stop_and_continue_cues():
    assert R.stop_cues("ಮೂರು ದಿನದ ನಂತರ ನಿಲ್ಲಿಸಿದೆ")
    assert not R.stop_cues("ಮೂರು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ")
    assert R.continue_cues("ಅದೇ ಮಾತ್ರೆ ಮುಂದುವರಿಸಿ")
    assert not R.continue_cues("ಮಾತ್ರೆ ಮುಗಿಸಿ")


def test_sentences_split_at_terminal_punctuation_and_newline_not_at_abbreviation():
    text = "ನಿನ್ನೆ ಕೊಟ್ಟೆ.\nಸರಿ. Ibuprofen ಕೊಡಬೇಡಿ."
    got = [text[a:b] for a, b in R.sentences(text)]
    assert got == ["ನಿನ್ನೆ ಕೊಟ್ಟೆ.", "ಸರಿ.", "Ibuprofen ಕೊಡಬೇಡಿ."]
    t2 = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 ಎಂ.ಜಿ. ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಕೊಡಿ."
    assert [t2[a:b] for a, b in R.sentences(t2)] == [t2]


# ---------------------------------------------------------------- dev-informed additions (D-? in handoff)
@pytest.mark.parametrize(
    "text,hit",
    [
        ("ಮಗು ಸಿರಪ್ ಕುಡಿಯುತ್ತೆ", True),  # ongoing use: "the child drinks the syrup"
        ("ಮಗುವಿಗೆ ಸಿರಪ್ ಕುಡಿಸಿ", False),  # minimal pair: imperative
        ("ನಾನು ದಿನಾ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳುತ್ತೇನೆ", True),
        ("ಜ್ವರ ರಾತ್ರಿ ಬರುತ್ತೆ", False),  # trap: habitual, but not a giving/taking verb
    ],
)
def test_ongoing_use_cues(text, hit):
    assert bool(R.ongoing_cues(text)) is hit


@pytest.mark.parametrize(
    "text,hit",
    [
        ("ಅಮಾಕ್ಸಿಸಿಲಿನ್ ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ", True),  # "may I take?"
        ("ಅಮಾಕ್ಸಿಸಿಲಿನ್ ತೆಗೆದುಕೊಳ್ಳಬಹುದು", False),  # minimal pair: statement "you may take"
        ("ಮಾತ್ರೆ ಕೊಡಲಾ", True),  # "shall I give?"
        ("ಜ್ವರ ಇದೆಯಾ", False),  # trap: a yes/no question that asks no permission
    ],
)
def test_permission_question_cues(text, hit):
    assert bool(R.permission_cues(text)) is hit


@pytest.mark.parametrize(
    "text,hit",
    [
        ("ಎಲ್ಲ ಮಾತ್ರೆ ಮುಗಿಸಿದಿರಾ", True),
        ("ಎಲ್ಲ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಿ", False),  # minimal pair
        ("course finish ಮಾಡಿದ್ರಾ", True),
        ("ಅವನು ಮುಗ್ಗರಿಸಿದ", False),  # trap: ಮುಗ್ಗರಿಸು (stumble) shares the first letters
    ],
)
def test_finish_cues(text, hit):
    assert bool(R.finish_cues(text)) is hit


def test_regimen_in_span():
    assert R.has_regimen("ಸೆಟಿರಿಜಿನ್ 10 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಐದು ದಿನ")
    assert not R.has_regimen("ಸೆಟಿರಿಜಿನ್")


def test_ongoing_eat_tablet():
    assert R.ongoing_cues("ಮಗು ಮಾತ್ರೆ ತಿನ್ನುತ್ತೆ")  # colloquial "takes (eats) the tablet"
    assert not R.ongoing_cues("ಮಗು ಮಾತ್ರೆ ತಿನ್ನಲಿ")  # minimal pair: optative "let it eat"
