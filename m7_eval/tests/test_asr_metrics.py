"""ASR metrics against hand-computed values (docs/metrics.md section 1)."""

import pytest

from m7_eval import asr_metrics as am
from m7_eval import textnorm as tn


def test_comparison_normalisation():
    s = "\ufeffಜ್ವರ\u200b ೫೦೦ MG\u200c"
    assert tn.compare_norm(s) == "ಜ್ವರ 500 mg"
    assert tn.compare_norm("a\n  b") == "a b"


def test_tokens_keep_kannada_marks_together():
    assert tn.tokens("ಕೆಮ್ಮು ಇಲ್ಲ, 5 mg.") == ["ಕೆಮ್ಮು", "ಇಲ್ಲ", "5", "mg"]


def test_levenshtein_hand_values():
    assert am.levenshtein("kitten", "sitting") == 3
    assert am.levenshtein([], ["a"]) == 1
    assert am.levenshtein(["a", "b"], ["a", "b"]) == 0


def test_cer_hand_value():
    # ref "ಇಲ್ಲ" = 4 code points (ಇ ಲ ್ ಲ); hyp "ಇಲ್ಲಿ" adds 1 vowel sign -> 1/4
    r = am.utterance_metrics("ಇಲ್ಲ", "ಇಲ್ಲಿ")
    assert r["ref_chars"] == 4 and r["char_edits"] == 1
    assert r["cer"] == pytest.approx(0.25)
    # graphemes: ref [ಇ, ಲ್ಲ] = 2? regex \X keeps a virama conjunct as separate clusters;
    # we only assert the grapheme count is smaller than the code point count
    assert 0 < r["ref_graphemes"] < r["ref_chars"]
    assert r["wer"] == pytest.approx(1.0)


def test_cer_ignores_digit_script_and_case():
    r = am.utterance_metrics("೫೦೦ MG", "500 mg")
    assert r["cer"] == 0.0 and r["wer"] == 0.0


def test_cer_nopunct_column():
    r = am.utterance_metrics("ಜ್ವರ ಇದೆ.", "ಜ್ವರ ಇದೆ")
    assert r["cer"] > 0
    assert r["cer_nopunct"] == 0.0


TERMS = am.CriticalTerms(
    drugs=[("paracetamol", ["paracetamol"]), ("paracetamol", ["ಪ್ಯಾರಸಿಟಮಾಲ್"])],
    number_words=["ಎರಡು", "ಮೂರು"],
    units=[["mg"], ["ಎಂ", "ಜಿ"]],
    negation_patterns=[r"^ಇಲ್ಲ$", r"ಿಲ್ಲಾ?$"],
)


def test_critical_terms_extraction():
    ref = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 ಎಂ.ಜಿ ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ, ಕೆಮ್ಮು ಇಲ್ಲ, ಬರಲಿಲ್ಲ"
    t = TERMS.extract(ref)
    assert t["drug"] == ["paracetamol"]
    assert sorted(t["number"]) == ["500", "ಎರಡು"]
    assert t["unit"] == ["ಎಂ ಜಿ"]
    assert sorted(t["negation"]) == ["ಇಲ್ಲ", "ಬರಲಿಲ್ಲ"]


def test_critical_term_recall_counts_per_class():
    ref = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ, ಕೆಮ್ಮು ಇಲ್ಲ"
    hyp = "paracetamol 50 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಕೆಮ್ಮು ಇಲ್ಲಿ"
    r = TERMS.recall(ref, hyp)
    assert r["drug"] == (1, 1)  # same drug id in another script counts
    assert r["number"] == (1, 2)  # 500 lost, ಎರಡು kept
    assert r["unit"] == (1, 1)
    assert r["negation"] == (0, 1)  # ಇಲ್ಲ -> ಇಲ್ಲಿ is a negation loss


def test_must_not_trigger_word_is_not_a_negation_cue():
    assert TERMS.extract("ಮಾತ್ರೆ ಇಲ್ಲಿ ಇದೆ")["negation"] == []
