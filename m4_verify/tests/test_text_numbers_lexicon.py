"""Normaliser, tokeniser, number parser, lexicon matcher and quantity phrases (own code)."""

from __future__ import annotations

import pytest

from m4_verify.lexicon import (
    load_lexicon,
    parse_dose_phrases,
    parse_durations,
    parse_frequencies,
    symptom_in,
)
from m4_verify.numbers import english_numbers, parse_numbers
from m4_verify.tests.helpers import FIX
from m4_verify.textnorm import comparison, tokens

LEX = FIX / "lexicon" / "drugs_fixture.csv"


def test_comparison_copy_rules():
    s = "﻿ಕೆಮ್ಮು​ ಇಲ್‌ಲ ೫೦೦ MG"
    c = comparison(s)
    assert "﻿" not in c and "​" not in c and "‌" not in c
    assert "500" in c
    assert "mg" in c  # casefold


def test_tokens_keep_marks_and_map_offsets_to_stored_text():
    s = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ ೫೦೦ mg"
    toks = tokens(s)
    assert [t.text for t in toks] == ["ಅಮಾಕ್ಸಿಸಿಲಿನ್", "500", "mg"]
    assert s[toks[1].start : toks[1].end] == "೫೦೦"
    s2 = "ಇಲ್‌ಲ ಜ್ವರ"
    t2 = tokens(s2)
    assert t2[0].text == "ಇಲ್ಲ"
    assert s2[t2[0].start : t2[0].end] == "ಇಲ್‌ಲ"


def test_nfc_applied():
    decomposed = "ಕೀ"  # NFC composes to U+0C95 U+0CC0
    assert comparison(decomposed) == "ಕೀ"


@pytest.mark.parametrize(
    ("text", "values"),
    [
        ("500 mg", [500]),
        ("೫೦೦ mg", [500]),
        ("2.5 ml", [2.5]),
        ("ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ", [3, 5]),
        ("ಐನೂರು ಮಿಲಿಗ್ರಾಂ", [500]),
        ("ಇನ್ನೂರ ಐವತ್ತು ಮಿಲಿಗ್ರಾಂ", [250]),
        ("ಆರುನೂರ ಐವತ್ತು", [650]),
        ("ಅರ್ಧ ಮಾತ್ರೆ", [0.5]),
        ("ಒಂದೂವರೆ ಚಮಚ", [1.5]),
        ("ಹತ್ತು ದಿನ", [10]),
        ("ಎಲ್ಲಾ ಮಾತ್ರೆ ಮಾತ್ರ", []),
    ],
)
def test_parse_numbers(text, values):
    assert [n.value for n in parse_numbers(text)] == values


def test_english_numbers():
    assert english_numbers("come back in two days") == [2]
    assert english_numbers("take 500 mg three times") == [500, 3]
    assert english_numbers("take after food") == []


def test_lexicon_loads_and_matches_variants():
    lex = load_lexicon(LEX)
    assert "amoxicillin" in lex.drugs
    assert lex.drugs["amoxicillin"].range_mg == (250.0, 1000.0)
    assert lex.drugs["ors"].range_mg is None
    assert [d for d, *_ in lex.drugs_in("ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg")] == ["amoxicillin"]
    assert [d for d, *_ in lex.drugs_in("Azithromycin 500 mg")] == ["azithromycin"]
    assert [d for d, *_ in lex.drugs_in("ಅಮೋಕ್ಸಿಸಿಲಿನ್ ತೆಗೆದುಕೊಳ್ಳಿ")] == ["amoxicillin"]
    assert [d for d, *_ in lex.drugs_in("ಓ ಆರ್ ಎಸ್ ಕುಡಿಸಿ")] == ["ors"]
    assert [d for d, *_ in lex.drugs_in("ಒ.ಆರ್.ಎಸ್ ಕುಡಿಸಿ")] == ["ors"]
    assert lex.drugs_in("ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು") == []
    assert lex.drugs["amoxicillin"].confusable == ["amoxicillin-clavulanate", "azithromycin"]


def test_lexicon_inflected_kannada_drug_name():
    lex = load_lexicon(LEX)
    assert [d for d, *_ in lex.drugs_in("ಪ್ಯಾರಸಿಟಮಾಲ್ನ್ನು ಕೊಡಿ")] == ["paracetamol"]


def test_dose_frequency_duration_phrases():
    s = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ"
    assert [(d.value, d.unit) for d in parse_dose_phrases(s)] == [(500, "mg")]
    assert [f.value for f in parse_frequencies(s)] == [3]
    assert [d.value for d in parse_durations(s)] == [5]
    assert [d.value for d in parse_durations("ಒಂದು ವಾರ ತೆಗೆದುಕೊಳ್ಳಿ")] == [7]
    assert [(d.value, d.unit) for d in parse_dose_phrases("ಒಂದು ಮಾತ್ರೆ")] == [(1, "tablet")]
    assert [(d.value, d.unit) for d in parse_dose_phrases("5 ಎಂ.ಎಲ್ ಸಿರಪ್")] == [(5, "ml")]
    assert [f.value for f in parse_frequencies("ದಿನಕ್ಕೆ ಎರಡು ಸಲ")] == [2]
    assert parse_durations("ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ") == []  # "per day" is not a duration


def test_symptom_terms():
    assert symptom_in("fever", "ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ")
    assert symptom_in("cough", "ಕೆಮ್ಮು ಇಲ್ಲ")
    assert not symptom_in("cough", "ಜ್ವರ ಇದೆ")
    assert symptom_in("vomiting", "ವಾಂತಿ ಆಗಿಲ್ಲ")
    assert symptom_in("headache", "ತಲೆನೋವು ಇದೆ")
