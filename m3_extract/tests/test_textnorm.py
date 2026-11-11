import unicodedata

import pytest

from m3_extract import textnorm as tn


def test_comparison_form_digits_zw_case():
    assert tn.comparison_form("೫೦೦") == "500"
    assert tn.comparison_form("Azithromycin") == "azithromycin"
    # ZWNJ removed only in the comparison copy
    assert tn.comparison_form("ಮಾತ್ರೆ‌ಗಳು") == "ಮಾತ್ರೆಗಳು"


def test_normalise_strips_bom_zwsp_and_nfc():
    decomposed = "﻿ಕೆೇ​"  # not used as Kannada, just code points
    out = tn.normalise(decomposed)
    assert "﻿" not in out and "​" not in out
    assert unicodedata.is_normalized("NFC", out)


def test_check_stored_fails_closed():
    with pytest.raises(ValueError):
        tn.check_stored("﻿ಜ್ವರ")
    with pytest.raises(ValueError):
        tn.check_stored("ಕೆೇ".replace("ಕೆ", "ಕ"))  # decomposed vowel sign -> not NFC
    tn.check_stored("ಜ್ವರ ಇದೆ.")


def test_tokenize_keeps_offsets_into_stored_text():
    text = "ಪ್ಯಾರಸಿಟಮಾಲ್ ೫೦೦ mg, ಮಾತ್ರೆ‌ಗಳು 2.5"
    toks = tn.tokenize(text)
    for t in toks:
        assert text[t.start : t.end] == t.text
    norms = [t.norm for t in toks]
    assert norms == ["ಪ್ಯಾರಸಿಟಮಾಲ್", "500", "mg", "ಮಾತ್ರೆಗಳು", "2.5"]


def test_matras_and_virama_do_not_split_words():
    toks = tn.tokenize("ತೆಗೆದುಕೊಳ್ಳಬಾರದು ಮಾತ್ರೆ")
    assert [t.text for t in toks] == ["ತೆಗೆದುಕೊಳ್ಳಬಾರದು", "ಮಾತ್ರೆ"]


def test_turn_index_of_tokens():
    toks = tn.tokenize("ಕೆಮ್ಮು ಇದೆಯಾ?\nಇಲ್ಲ.")
    assert [t.turn for t in toks] == [0, 0, 1]


def test_abbreviation_dot_is_not_a_boundary():
    text = "ceftriaxone 1000 ಎಂ.ಜಿ injection. ಒ.ಆರ್.ಎಸ್ ಕುಡಿಸಿ."
    i_abbrev = text.index(".")  # the dot inside ಎಂ.ಜಿ
    assert not tn.is_boundary_dot(text, i_abbrev)
    i_end = text.index("injection.") + len("injection")
    assert tn.is_boundary_dot(text, i_end)
