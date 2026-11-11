"""Negation fixes from the Kannada review (reviews/m4_verify/2026-11-10-kannada.md, D-93).

Findings j..o of the m4 fix pass. Each cue has a positive, a minimal-pair twin and a trap.
All sentences are AI-written and NOT native-validated (ai_simulated_review only).
m4 keeps its OWN rules: nothing here reads .claude/skills/kannada-nlp/negation_table.yaml.
"""

from __future__ import annotations

import pytest

from m4_verify.negation import analyze, classify_token, span_polarity, text_polarity
from m4_verify.tests.helpers import ev, flags, med, record, transcript
from m4_verify.verifier import verify


def _span(text, span, occurrence=0):
    an = analyze(text)
    start = -1
    for _ in range(occurrence + 1):
        start = text.find(span, start + 1)
    assert start >= 0, span
    return span_polarity(an, start, start + len(span))


# --------------------------------------------------------------- (j) fused and spaced ಬೇಡ / ಬೇಡಿ
# (rule, positive, twin, trap)
FUSED_BEDA = [
    ("S-BEDI", "ಆ ಮಾತ್ರೆ ತಗೋಬೇಡಿ", "ಆ ಮಾತ್ರೆ ತಗೊಳ್ಳಿ", "ಔಷಧಿಗೆ ಬೇಡಿಕೆ ಇದೆ"),
    ("S-BEDI", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡ್ಬೇಡಿ", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡಿ", "ಈ ಮಾತ್ರೆಗೆ ತುಂಬಾ ಬೇಡಿಕೆ ಇದೆ"),
    ("S-BEDI", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡಬೇಡಿ", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡಿ", "ಬೇಡಿಕೆ ಹೆಚ್ಚಾಗಿದೆ"),
    ("W-BEDI", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡ ಬೇಡಿ", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡಿ", "ಬೇಡಿಕೆ ಇದೆ"),
    ("S-BEDA", "ಆ ಹಣ್ಣು ತಿನ್ಬೇಡ", "ಆ ಹಣ್ಣು ತಿನ್ನು", "ಬೇಡಿಕೆ ಇದೆ"),
    ("S-BEDA", "ಆ ಮಾತ್ರೆ ತಗೋಬೇಡಾ", "ಆ ಮಾತ್ರೆ ತಗೋ", "ಬೇಡಿಕೆ ಇದೆ"),
]


@pytest.mark.parametrize(("rule", "pos", "twin", "trap"), FUSED_BEDA)
def test_fused_beda_positive(rule, pos, twin, trap):
    p = text_polarity(pos)
    assert p.negated is True, pos
    assert rule in {c.rule_id for c in p.cues}, (pos, [c.rule_id for c in p.cues])
    assert not p.soft


@pytest.mark.parametrize(("rule", "pos", "twin", "trap"), FUSED_BEDA)
def test_fused_beda_twin_and_trap(rule, pos, twin, trap):
    for s in (twin, trap):
        p = text_polarity(s)
        assert p.negated is False and p.cues == [] and not p.soft, s


# --------------------------------------------------------------- (k) new whole-word cues
WHOLE = [
    ("W-BEDA", "ನೆಗಡಿಗೆ antibiotic ಬೇಡಾ", "ನೆಗಡಿಗೆ antibiotic ಬೇಕು", "ಔಷಧಿಗೆ ಬೇಡಿಕೆ ಇದೆ"),
    ("W-NEGQ", "ಈ ಮಾತ್ರೆ ಬೇಡವಾ?", "ಈ ಮಾತ್ರೆ ಬೇಕಾ?", "ಬೇಡಿಕೆ ಇದೆಯಾ?"),
    ("W-ILLA", "ಜ್ವರ ಇಲ್ರೀ", "ಜ್ವರ ಇದೆರೀ", "ಇಲ್ಲಿ ಬನ್ರೀ"),
    ("W-ILLA", "ಕೆಮ್ಮು ಇಲ್ಲಪ್ಪ", "ಕೆಮ್ಮು ಇದೆಯಪ್ಪ", "ಎಲ್ಲಾ ಮಾತ್ರೆ ಇದೆ ಅಪ್ಪ"),
]


@pytest.mark.parametrize(("rule", "pos", "twin", "trap"), WHOLE)
def test_new_whole_word_cue_positive(rule, pos, twin, trap):
    p = text_polarity(pos)
    assert p.negated is True, pos
    assert rule in {c.rule_id for c in p.cues}, (pos, [c.rule_id for c in p.cues])


@pytest.mark.parametrize(("rule", "pos", "twin", "trap"), WHOLE)
def test_new_whole_word_cue_twin_and_trap(rule, pos, twin, trap):
    for s in (twin, trap):
        p = text_polarity(s)
        assert p.negated is False and p.cues == [] and not p.soft, s


# --------------------------------------------------------------- (l) colloquial negative question -ಲ್ವಾ
@pytest.mark.parametrize("pos", ["ಮಗು ಹಾಲು ಕುಡಿಯಲ್ವಾ?", "ಅವನು ನಾಳೆ ಬರಲ್ವಾ?", "ಮಾತ್ರೆ ತಿನ್ನಲ್ವ?"])
def test_lva_negative_question_is_uncertain_not_plain_negation(pos):
    p = text_polarity(pos)
    assert p.soft is True, pos  # uncertain -> C8 flags
    assert any("negative question" in a for a in p.ambiguities), p.ambiguities
    assert "S-LVA" in {c.rule_id for c in p.cues}


def test_lva_twin_and_traps():
    for s in ("ಮಗು ಹಾಲು ಕುಡಿಯುತ್ತಾ?", "ಜ್ವರ ಇದೆ, ಅಲ್ವಾ?", "ಜ್ವರ ಇದೆ ಅಲ್ವ?"):
        p = text_polarity(s)
        assert p.negated is False and p.cues == [] and not p.soft, s
    assert classify_token("ಅಲ್ವಾ") is None and classify_token("ಅಲ್ವ") is None


def test_lva_reaches_c8_as_a_flag():
    turns = ["ಪ್ಯಾರಸಿಟಮಾಲ್ ಕುಡಿಯಲ್ವಾ?", "ಹೌದು."]
    tr = transcript(turns)
    rec = record(turns, meds=[med(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್", 0, "paracetamol")])
    v = verify(rec, tr)
    assert v["auto_acceptable"] is False
    assert any("negative question" in c["reason"] for c in flags(v, "C8"))


# --------------------------------------------------------------- (m) clause split without punctuation
@pytest.mark.parametrize(
    ("text", "pos_span", "neg_span"),
    [
        ("ಜ್ವರ ಇದೆ ಕೆಮ್ಮು ಇಲ್ಲ", "ಜ್ವರ", "ಕೆಮ್ಮು"),
        ("ಕೆಮ್ಮು ಇಲ್ಲ ಜ್ವರ ಇದೆ", "ಜ್ವರ", "ಕೆಮ್ಮು"),
        ("ವಾಂತಿ ಆಗಿಲ್ಲ ಜ್ವರ ಬಂದಿದೆ", "ಜ್ವರ", "ವಾಂತಿ"),
        ("ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ ವಾಂತಿ ಇಲ್ರೀ", "ಜ್ವರ", "ವಾಂತಿ"),
    ],
)
def test_second_subject_predicate_starts_a_new_clause(text, pos_span, neg_span):
    assert _span(text, pos_span).negated is False, (text, pos_span)
    assert _span(text, neg_span).negated is True, (text, neg_span)


def test_quotative_after_predicate_does_not_split():
    # "did not say there is no fever": still two cues in ONE clause -> ambiguity
    p = text_polarity("ಜ್ವರ ಇಲ್ಲ ಅಂತ ಹೇಳಲಿಲ್ಲ")
    assert any("two negation cues" in a for a in p.ambiguities)
    p2 = text_polarity("ಜ್ವರ ಇದೆ ಅಂತ ಹೇಳಿದರು")
    assert p2.negated is False and p2.cues == []


# --------------------------------------------------------------- (n) multi-token cross-turn answers
Q = "ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?"


def _turn_span(turns, span, turn):
    e = ev(turns, span, turn)
    return span_polarity(analyze("\n".join(turns)), e["char_start"], e["char_end"])


@pytest.mark.parametrize("ans", ["ಇಲ್ಲ ಅಕ್ಕ.", "ಇಲ್ರೀ.", "ಇಲ್ಲಪ್ಪ", "ಇಲ್ಲ ಮೇಡಂ", "ಇಲ್ಲ ಡಾಕ್ಟರ್."])
def test_multi_token_negative_answer(ans):
    p = _turn_span([Q, ans], "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0)
    assert p.negated is True and p.cross_turn == "negative", ans
    assert p.ambiguities == [], p.ambiguities


@pytest.mark.parametrize("ans", ["ಹೌದ್ರೀ.", "ಹೌದು ಸರ್.", "ಹೌದು ಅಕ್ಕ", "ಹೌದ್ರಿ"])
def test_multi_token_positive_answer(ans):
    p = _turn_span([Q, ans], "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0)
    assert p.negated is False and p.cross_turn == "affirmative", ans
    assert p.ambiguities == [], p.ambiguities


def test_multi_token_answer_traps():
    for ans in ("ಇಲ್ಲಿ ಅಕ್ಕ.", "ಅಕ್ಕ ಬಂದಿಲ್ಲ.", "ಎಲ್ಲ ಕುಡಿಯಿತು ಸರ್."):
        p = _turn_span([Q, ans], "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0)
        assert p.cross_turn is None, ans


def test_multi_token_answer_without_question_is_unresolved():
    an = analyze("ಪ್ಯಾರಸಿಟಮಾಲ್ ಕೊಟ್ಟೆ.\nಇಲ್ಲ ಅಕ್ಕ.")
    assert any("no resolvable question" in a for a in an.unresolved_answers)


# --------------------------------------------------------------- (o) dots inside abbreviations
def test_abbreviation_dots_do_not_split_the_clause():
    text = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 ಎಂ.ಜಿ. ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ."
    p = _span(text, "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 ಎಂ.ಜಿ.")
    assert p.negated is True, "the negation after ಎಂ.ಜಿ. must reach the dose"
    assert len(p.clause_ids) == 1
    twin = "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 ಎಂ.ಜಿ. ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ."
    assert _span(twin, "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 ಎಂ.ಜಿ.").negated is False


def test_ors_and_doctor_abbreviations_stay_in_one_clause():
    an = analyze("ಓ.ಆರ್.ಎಸ್. ಕುಡಿಸಬೇಡಿ ಅಂತ ಡಾ. ರಾವ್ ಹೇಳಿದರು.")
    assert len(an.clauses) == 1, [an.text[c.start : c.end] for c in an.clauses]


def test_real_sentence_end_still_splits():
    text = "ಜ್ವರ ಇದೆ. ಕೆಮ್ಮು ಇಲ್ಲ."
    assert _span(text, "ಜ್ವರ").negated is False
    assert _span(text, "ಕೆಮ್ಮು").negated is True


# --------------------------------------------------------------- traps for all new rules
NEW_TRAPS = [
    "ಬೇಡಿಕೆ", "ಅಲ್ವಾ", "ಅಲ್ವ", "ಇಲ್ಲಿ", "ಬೆಲ್ಲ", "ಎಲ್ಲ", "ಎಲ್ಲಾ", "ಅಲ್ಲಿ", "ಮಾತ್ರ", "ಮಾತ್ರೆ",
    "ಬೇಕು", "ಬೇಕಾ", "ಅಕ್ಕ", "ಸರ್", "ಹೌದ್ರೀ", "ಎಲ್ಲಿ", "ಬನ್ರೀ",
]  # fmt: skip


@pytest.mark.parametrize("tok", NEW_TRAPS)
def test_new_traps_never_trigger(tok):
    assert classify_token(tok) is None, tok
    p = text_polarity(f"{tok} ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಿ")
    assert p.negated is False and not p.soft and p.cues == []
