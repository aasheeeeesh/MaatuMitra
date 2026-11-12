"""Hand-computed metric examples. Every expected value is worked out in a comment."""

import math

import pytest

from m2_asr.asr import metrics as M


def test_levenshtein_kitten_sitting():
    # k->s, e->i, insert g = 3 edits
    assert M.levenshtein("kitten", "sitting") == 3
    assert M.levenshtein("", "abc") == 3
    assert M.levenshtein("abc", "abc") == 0


def test_wilson_matches_skill_values():
    # formula in the eval-rigor skill, z = 1.959964, 4 places
    lo, hi = M.wilson(0, 50)
    assert (round(lo, 4), round(hi, 4)) == (0.0, 0.0713)
    lo, hi = M.wilson(3, 50)
    assert (round(lo, 4), round(hi, 4)) == (0.0206, 0.1622)
    assert M.wilson(0, 0) == (None, None)


def test_compare_norm():
    assert M.compare_norm("೨ MG") == "2 mg"  # Kannada digit -> ASCII, casefold
    assert M.compare_norm("ಕ‌ಕ") == M.compare_norm("ಕಕ")  # ZWNJ removed in comparison copy
    assert M.compare_norm("﻿a​  b") == "a b"  # BOM, ZWSP, whitespace collapse


def test_dropped_negation_small_cer_but_meaning_lost():
    # ref "ನೆಗಡಿ ಇಲ್ಲ" = ನೆ(2 cp) ಗ(1) ಡಿ(2) space(1) ಇ ಲ ್ ಲ (4) = 10 code points
    ref, hyp = "ನೆಗಡಿ ಇಲ್ಲ", "ನೆಗಡಿ"
    m = M.utterance_metrics(ref, hyp)
    assert m["ref_chars"] == 10
    assert m["char_edits"] == 5  # delete " ಇಲ್ಲ"
    assert m["cer"] == 0.5
    assert m["wer"] == 0.5  # 2 words, 1 deleted
    terms = M.CriticalTerms(drugs=[], number_words=[], units=[], negation_patterns=[r"^ಇಲ್ಲ$"])
    assert terms.recall(ref, hyp)["negation"] == (0, 1)


def test_negation_flipped_by_substitution():
    # ಇಲ್ಲ -> ಇದೆ: keep ಇ, ಲ->ದ, ್->ೆ, delete ಲ = 3 edits of 10 code points
    m = M.utterance_metrics("ನೆಗಡಿ ಇಲ್ಲ", "ನೆಗಡಿ ಇದೆ")
    assert m["char_edits"] == 3
    assert m["cer"] == pytest.approx(0.3)


def test_grapheme_cer_differs_from_cer():
    # ref "ಕಾಲು ಇದೆ": graphemes ಕಾ ಲು ' ' ಇ ದೆ = 5 ; code points 2+2+1+1+2 = 8
    # hyp "ಕಾಲು": 2 graphemes, 4 code points. Deleting " ಇದೆ" = 3 graphemes, 4 code points.
    m = M.utterance_metrics("ಕಾಲು ಇದೆ", "ಕಾಲು")
    assert (m["ref_chars"], m["char_edits"], m["cer"]) == (8, 4, 0.5)
    assert (m["ref_graphemes"], m["grapheme_edits"], m["gcer"]) == (5, 3, 0.6)


def test_cer_nopunct_and_empty_reference():
    m = M.utterance_metrics("ab, cd.", "ab cd")
    assert m["cer_nopunct"] == 0.0
    assert m["cer"] == pytest.approx(2 / 7)  # ref "ab, cd." has 7 chars; hyp lacks "," and "."
    assert M.utterance_metrics("", "x")["cer"] is None


def test_term_recall_by_class_count_aware():
    terms = M.CriticalTerms(
        drugs=[("paracetamol", ["ಪ್ಯಾರಸಿಟಮಾಲ್"])],
        number_words=["ಎರಡು", "ಮೂರು"],
        units=[["ಮಾತ್ರೆ"], ["mg"]],
        negation_patterns=[r"^ಬೇಡ$"],
    )
    ref = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಎರಡು ಮಾತ್ರೆ 500 mg ಬೇಡ"
    hyp = "ಪ್ಯಾರಸಿಟಮಾಲ್ ಮೂರು ಮಾತ್ರೆ 500 mg"
    rec = terms.recall(ref, hyp)
    assert rec["drug"] == (1, 1)
    assert rec["number"] == (1, 2)  # "500" matched, ಎರಡು replaced by ಮೂರು
    assert rec["unit"] == (2, 2)
    assert rec["negation"] == (0, 1)


def test_percentile_and_rtf():
    assert M.percentile([1, 2, 3, 4, 5], 50) == 3
    assert M.percentile([1, 2, 3, 4, 5], 95) == pytest.approx(4.8)  # 4 + 0.8*(5-4)
    assert M.rtf(2000.0, 4.0) == 0.5  # 2 s of compute for 4 s of audio
    assert M.rtf(None, 4.0) is None


def test_bootstrap_ci_seeded_and_constant():
    lo, hi = M.bootstrap_ci([0.3] * 10)
    assert lo == pytest.approx(0.3) and hi == pytest.approx(0.3)
    xs = [0.0, 0.1, 0.5, 0.9, 1.0, 0.2]
    assert M.bootstrap_ci(xs, seed=1) == M.bootstrap_ci(xs, seed=1)
    lo, hi = M.bootstrap_ci(xs, seed=1)
    assert 0.0 <= lo <= sum(xs) / len(xs) <= hi <= 1.0
    assert all(math.isnan(v) for v in M.bootstrap_ci([], seed=1))


def test_code_switched_flag():
    assert M.is_code_switched("ಜ್ವರ paracetamol ಇದೆ")
    assert not M.is_code_switched("ಜ್ವರ ಇದೆ")
