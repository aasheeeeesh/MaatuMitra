"""Negation rules of the verifier (hand-coded, independent of the shared YAML table).

For EVERY cue: one positive, one minimal-pair negative twin (cue removed/replaced) and one
trap (a look-alike that must NOT trigger). Plus clause scope and cross-turn tests.
All sentences are AI-written and NOT native-validated (hypotheses, see negation_audit.md).
"""

from __future__ import annotations

import pytest

from m4_verify.negation import analyze, classify_token, span_polarity, text_polarity
from m4_verify.tests.helpers import ev

# (rule_id, positive, twin, trap)
CUE_CASES = [
    ("W-ILLA", "ಕೆಮ್ಮು ಇಲ್ಲ", "ಕೆಮ್ಮು ಇದೆ", "ಮಾತ್ರೆ ಇಲ್ಲಿ ಇದೆ"),
    ("W-ILLAA", "ಜ್ವರ ಇಲ್ಲಾ", "ಜ್ವರ ಇದೆ", "ಎಲ್ಲಾ ಮಾತ್ರೆ ಇವೆ"),
    ("W-ALLA", "ಇದು ಆ ಮಾತ್ರೆ ಅಲ್ಲ", "ಇದು ಆ ಮಾತ್ರೆ", "ಆಸ್ಪತ್ರೆ ಅಲ್ಲಿ ಇದೆ"),
    ("W-BEDA", "ನೆಗಡಿಗೆ ಆಂಟಿಬಯಾಟಿಕ್ ಬೇಡ", "ನೆಗಡಿಗೆ ಆಂಟಿಬಯಾಟಿಕ್ ಬೇಕು", "ಔಷಧಿಗೆ ಬೇಡಿಕೆ ಇದೆ"),
    ("W-BEDI", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡುವುದು ಬೇಡಿ", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡಿ", "ಬೇಡಿಕೆ ಹೆಚ್ಚಾಗಿದೆ"),
    ("W-BAARADU", "ಆ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳ ಬಾರದು", "ಆ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳ ಬೇಕು", "ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ"),
    ("W-KOODADU", "ಮಾತ್ರೆ ಹಂಚಿಕೊಳ್ಳ ಕೂಡದು", "ಮಾತ್ರೆ ಹಂಚಿಕೊಳ್ಳ ಬಹುದು", "ಅವರು ಕೂಡ ಬಂದರು"),
    ("S-ILLA", "ವಾಂತಿ ಆಗಿಲ್ಲ", "ವಾಂತಿ ಆಗಿದೆ", "ಮಾತ್ರೆ ಇಲ್ಲಿಗೆ ತನ್ನಿ"),
    ("S-ILLA", "ಅವನು ಬರಲಿಲ್ಲ", "ಅವನು ಬಂದನು", "ಎಲ್ಲರೂ ಬಂದರು"),
    ("S-ILLA", "ಅವನು ಮಾತ್ರೆ ಮಾಡಿಲ್ಲ", "ಅವನು ಮಾತ್ರೆ ಮಾಡಿದ್ದಾನೆ", "ಅಲ್ಲಿ ಮಾತ್ರ ಇದೆ"),
    (
        "S-UDILLA",
        "ನಾನು ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳುವುದಿಲ್ಲ",
        "ನಾನು ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳುತ್ತೇನೆ",
        "ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳುವುದು ಒಳ್ಳೆಯದು",
    ),
    ("S-DIDDARE", "ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಬನ್ನಿ", "ಜ್ವರ ಕಡಿಮೆ ಆಗಿದ್ದರೆ ಬನ್ನಿ", "ಚೀಟಿ ಓದಿದ್ದರೆ ಗೊತ್ತಾಗುತ್ತಿತ್ತು"),
    ("S-DIDRE", "ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ರೆ ಬನ್ನಿ", "ಜ್ವರ ಕಡಿಮೆ ಆಗಿದ್ರೆ ಬನ್ನಿ", "ಅವನು ಬಂದಿದ್ರೆ ಹೇಳಿ"),
    (
        "S-BAARADU",
        "ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು",
        "ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಹುದು",
        "ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ತೆಗೆದುಕೊಳ್ಳಿ",
    ),
    ("S-KOODADU", "ಉಳಿದ ಮಾತ್ರೆ ಹಂಚಿಕೊಳ್ಳಕೂಡದು", "ಉಳಿದ ಮಾತ್ರೆ ಹಂಚಿಕೊಳ್ಳಬಹುದು", "ಅವಳು ಕೂಡ ಮಾತ್ರೆ ತಗೊಂಡಳು"),
    (
        "S-BEDI",
        "ಉಳಿದ ಮಾತ್ರೆಗಳನ್ನು ಬೇರೆಯವರಿಗೆ ಕೊಡಬೇಡಿ",
        "ಉಳಿದ ಮಾತ್ರೆಗಳನ್ನು ಬೇರೆಯವರಿಗೆ ಕೊಡಿ",
        "ಔಷಧಿಗೆ ಬೇಡಿಕೆ ಇದೆ",
    ),
    ("S-BEDA", "ಆ ಹಣ್ಣು ತಿನ್ನಬೇಡ", "ಆ ಹಣ್ಣು ತಿನ್ನು", "ಬೇಡಿಕೆ ಇದೆ"),
    ("V-DE", "ಔಷಧಿ ಮುಗಿಸದೆ ನಿಲ್ಲಿಸಿದರು", "ಔಷಧಿ ಮುಗಿಸಿ ನಿಲ್ಲಿಸಿದರು", "ಜ್ವರ ಬಂದಿದೆ"),
    ("V-DE", "ಔಷಧಿ ಮುಗಿಸದೇ ನಿಲ್ಲಿಸಿದರು", "ಔಷಧಿ ಮುಗಿಸಿ ನಿಲ್ಲಿಸಿದರು", "ಮರೆಯದೆ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಿ"),
    ("V-LLA", "ಅವನು ನಾಳೆ ಬರಲ್ಲ", "ಅವನು ನಾಳೆ ಬರ್ತಾನೆ", "ಬೆಲ್ಲ ತಿನ್ನಿ"),
    ("C-YAAVUDE", "ಯಾವುದೇ ತೊಂದರೆ ಇಲ್ಲ", "ಯಾವುದೇ ತೊಂದರೆ ಇದೆಯಾ", "ಯಾವುದೇ ಮಾತ್ರೆ ಇಲ್ಲಿ ಇದೆ"),
    # added after the negation audit on real text (negation_audit.md)
    ("S-VALLA", "ಇದು ಮಾರಕ ರೋಗವಲ್ಲ", "ಇದು ಮಾರಕ ರೋಗ", "ಜ್ವರ ಮಾತ್ರವಲ್ಲ"),
    ("S-DIRU", "ಹಸಿವು ಆಗದಿರುವುದು", "ಹಸಿವು ಆಗಿರುವುದು", "ಜ್ವರ ಬಂದಿರುವುದು"),
    ("W-NEGQ", "ಜ್ವರ ಇಲ್ಲವೇ?", "ಜ್ವರ ಇದೆಯೇ?", "ಜ್ವರ ಇಲ್ಲವೇ ಕೆಮ್ಮು ಬಂದಿದೆ"),
    ("S-ILLA-FUSED", "ಮಾರ್ಗವಿಲ್ಲದೆ ಉಳಿಯಿತು", "ಮಾರ್ಗವಿದ್ದು ಉಳಿಯಿತು", "ಜಿಲ್ಲೆ ಆಸ್ಪತ್ರೆಗೆ ಹೋಗಿ"),
    ("S-ILLA-FUSED", "ಸೋಂಕು ಹರಡುವುದಿಲ್ಲವಾದ್ದರಿಂದ ಭಯ ಬೇಕಾಗಿಲ್ಲ", "ಸೋಂಕು ಹರಡುವುದರಿಂದ ಎಚ್ಚರ ಇರಲಿ", "ಚಿಲ್ಲರೆ ಕೊಡಿ"),
    ("S-DANTE", "ರೋಗ ಬರದಂತೆ ತಡೆಯಿರಿ", "ರೋಗ ಬಂದಂತೆ ಕಾಣುತ್ತದೆ", "ವೈದ್ಯರು ಹೇಳಿದಂತೆ ಮಾಡಿ"),
    ("V-AAGADE", "ಜ್ವರ ಕಡಿಮೆಯಾಗದೆ ಉಳಿಯಿತು", "ಜ್ವರ ಕಡಿಮೆಯಾಗಿ ಉಳಿಯಿತು", "ಜ್ವರ ಕಡಿಮೆಯಾಗಿದೆ"),
    ("V-ISADE", "ಜ್ವರವನ್ನು ಗಣಿಸದೆ ಕೆಲಸ ಮಾಡಿದರು", "ಜ್ವರವನ್ನು ಗಣಿಸಿ ಕೆಲಸ ಮಾಡಿದರು", "ಮಾತ್ರೆ ಸೇವಿಸಿದೆ"),
]


@pytest.mark.parametrize(("rule", "pos", "twin", "trap"), CUE_CASES)
def test_cue_positive(rule, pos, twin, trap):
    p = text_polarity(pos)
    assert p.negated is True, pos
    assert rule in {c.rule_id for c in p.cues}, (rule, [c.rule_id for c in p.cues])
    assert not p.soft


@pytest.mark.parametrize(("rule", "pos", "twin", "trap"), CUE_CASES)
def test_cue_minimal_pair_twin(rule, pos, twin, trap):
    p = text_polarity(twin)
    assert p.negated is False, twin
    assert p.cues == []
    assert not p.soft


@pytest.mark.parametrize(("rule", "pos", "twin", "trap"), CUE_CASES)
def test_cue_trap(rule, pos, twin, trap):
    p = text_polarity(trap)
    assert p.negated is False, trap
    assert p.cues == []
    assert not p.soft, trap


MUST_NOT_TRIGGER = [
    "ಎಲ್ಲ", "ಎಲ್ಲಾ", "ಇಲ್ಲಿ", "ಅಲ್ಲಿ", "ಅಲ್ವಾ", "ಅಲ್ವ", "ಮಾತ್ರ", "ಮಾತ್ರೆ",
    "ಇದೆ", "ಬಂದಿದೆ", "ಇದ್ದರೆ", "ಓದಿದ್ದರೆ", "ಬೇಡಿಕೆ", "ಮರೆಯದೆ", "ಅಲ್ಲದೆ", "ಬೆಲ್ಲ",
    "ಕೂಡ", "ಬಾರಿ", "ಎಲ್ಲರೂ", "ಇಲ್ಲಿಗೆ", "ಕುಡಿದಿದ್ದರೆ", "ಬಂದಿದ್ದರೆ", "ಎಲ್ಲಿ", "ಬೇಕು",
    "ಮಾತ್ರವಲ್ಲ", "ತಪ್ಪದೆ", "ಇದಲ್ಲದೆ", "ನಮಗೆಲ್ಲಾ", "ಬಂದಿರುವುದು",
]  # fmt: skip


@pytest.mark.parametrize("tok", MUST_NOT_TRIGGER)
def test_trap_tokens_never_trigger(tok):
    assert classify_token(tok) is None, tok
    p = text_polarity(f"{tok} ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಿ")
    assert p.negated is False and not p.soft and p.cues == []


def test_fixture_trap_sentence_has_no_negation():
    p = text_polarity("ಪ್ಯಾರಸಿಟಮಾಲ್ ೫೦೦ mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಮಾತ್ರ ತೆಗೆದುಕೊಳ್ಳಿ. ಎಲ್ಲಾ ಮಾತ್ರೆ ಇಲ್ಲಿ ಇವೆ, ಅಲ್ವಾ?")
    assert p.negated is False and p.cues == [] and not p.soft


def test_cue_matching_is_on_tokens_not_substrings():
    # "ಇಲ್ಲಿ" contains the substring "ಇಲ್ಲ"; raw substring matching would fire.
    assert "ಇಲ್ಲ" in "ಇಲ್ಲಿ"
    assert text_polarity("ಔಷಧಿ ಇಲ್ಲಿ ಇದೆ").negated is False


def test_zwnj_and_zwj_do_not_break_cues():
    p = text_polarity("ಕೆಮ್ಮು ಇಲ್‌ಲ")
    assert p.negated is True
    p = text_polarity("ವಾಂತಿ ಆಗಿಲ್‍ಲ")
    assert p.negated is True


# --------------------------------------------------------------------- soft cue
def test_soft_cue_on_unknown_stem_is_soft_and_counted():
    p = text_polarity("ಅವನು ಓಡಲ್ಲ")  # stem ಓಡ not in the verifier's verb list
    assert p.soft is True
    assert p.negated is True  # counted conservatively; C8 flags it
    twin = text_polarity("ಅವನು ಓಡುತ್ತಾನೆ")
    assert twin.soft is False and twin.negated is False
    trap = text_polarity("ಬೆಲ್ಲ ಮತ್ತು ಹಾಲು")
    assert trap.soft is False and trap.negated is False


def test_illada_absence_is_soft():
    p = text_polarity("ಜ್ವರ ಇಲ್ಲದ ಮಗು")
    assert p.negated is True and p.soft is True
    twin = text_polarity("ಜ್ವರ ಇರುವ ಮಗು")
    assert twin.negated is False and not twin.soft
    trap = text_polarity("ಇಲ್ಲಿ ಮಗು ಇದೆ")
    assert trap.negated is False and not trap.soft
    assert text_polarity("ಊಟ ಇಲ್ಲದೆ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ").soft is True


def test_illave_as_or_splits_clauses():
    """Audit finding: in running text ಇಲ್ಲವೇ / ಇಲ್ಲವೆ usually means 'or', not 'is it not?'."""
    text = "ಜ್ವರ ಇಲ್ಲವೇ ಕೆಮ್ಮು ಬಂದಿದೆ"
    assert _span(text, "ಕೆಮ್ಮು").negated is False
    assert _span(text, "ಜ್ವರ").negated is False


def test_two_cues_in_one_clause_is_ambiguous():
    p = text_polarity("ಜ್ವರ ಇಲ್ಲ ಅಂತ ಹೇಳಲಿಲ್ಲ")
    assert p.negated is True
    assert any("two negation cues" in a for a in p.ambiguities)
    twin = text_polarity("ಜ್ವರ ಇಲ್ಲ ಅಂತ ಹೇಳಿದರು")
    assert not any("two negation cues" in a for a in twin.ambiguities)


def test_compound_yaavude_counts_as_one_cue():
    p = text_polarity("ಯಾವುದೇ ತೊಂದರೆ ಇಲ್ಲ")
    assert not any("two negation cues" in a for a in p.ambiguities)


# --------------------------------------------------------------------- clause scope
def _span(text, span, occurrence=0):
    an = analyze(text)
    start = -1
    for _ in range(occurrence + 1):
        start = text.find(span, start + 1)
    assert start >= 0
    return span_polarity(an, start, start + len(span))


@pytest.mark.parametrize(
    ("text", "pos_span", "neg_span"),
    [
        ("ತಲೆನೋವು ಇದೆ, ಆದರೆ ವಾಂತಿ ಆಗಿಲ್ಲ.", "ತಲೆನೋವು ಇದೆ", "ವಾಂತಿ ಆಗಿಲ್ಲ"),
        ("ತಲೆನೋವು ಇದೆ ಆದರೆ ವಾಂತಿ ಆಗಿಲ್ಲ", "ತಲೆನೋವು", "ವಾಂತಿ"),
        ("ಜ್ವರ ಇಲ್ಲ ಮತ್ತು ಕೆಮ್ಮು ಇದೆ", "ಕೆಮ್ಮು", "ಜ್ವರ"),
        ("ಜ್ವರ ಇಲ್ಲ ಹಾಗೂ ಕೆಮ್ಮು ಇದೆ", "ಕೆಮ್ಮು", "ಜ್ವರ"),
        ("ಜ್ವರ ಇಲ್ಲ ಆದ್ದರಿಂದ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಿ", "ಮಾತ್ರೆ", "ಜ್ವರ"),
        ("ಜ್ವರ ಇದೆ. ಕೆಮ್ಮು ಇಲ್ಲ.", "ಜ್ವರ", "ಕೆಮ್ಮು"),
        ("ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ, ಕೆಮ್ಮು ಇಲ್ಲ.", "ಜ್ವರ ಇದೆ", "ಕೆಮ್ಮು ಇಲ್ಲ"),
    ],
)
def test_clause_scope(text, pos_span, neg_span):
    assert _span(text, pos_span).negated is False
    assert _span(text, neg_span).negated is True


def test_coordinated_bare_noun_inherits_negation_and_is_ambiguous():
    text = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ ಮತ್ತು ಪ್ಯಾರಸಿಟಮಾಲ್ ಬೇಡ."
    p = _span(text, "ಅಮಾಕ್ಸಿಸಿಲಿನ್")
    assert p.negated is True
    assert any("coordinat" in a for a in p.ambiguities)
    # twin: a full clause before ಮತ್ತು keeps its own polarity
    text2 = "ಅಮಾಕ್ಸಿಸಿಲಿನ್ ತೆಗೆದುಕೊಳ್ಳಿ ಮತ್ತು ಪ್ಯಾರಸಿಟಮಾಲ್ ಬೇಡ."
    p2 = _span(text2, "ಅಮಾಕ್ಸಿಸಿಲಿನ್")
    assert p2.negated is False
    assert not any("coordinat" in a for a in p2.ambiguities)


# --------------------------------------------------------------------- cross-turn
def _turn_span(turns, span, turn):
    text = "\n".join(turns)
    e = ev(turns, span, turn)
    return span_polarity(analyze(text), e["char_start"], e["char_end"])


def test_cross_turn_bare_illa_negates_question_entity():
    turns = ["ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?", "ಇಲ್ಲ."]
    p = _turn_span(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0)
    assert p.negated is True
    assert p.cross_turn == "negative"
    assert p.ambiguities == []


def test_cross_turn_twin_bare_haudu_affirms():
    turns = ["ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?", "ಹೌದು."]
    p = _turn_span(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0)
    assert p.negated is False
    assert p.cross_turn == "affirmative"
    assert p.ambiguities == []


def test_cross_turn_trap_illi_is_not_an_answer():
    turns = ["ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?", "ಇಲ್ಲಿ ಇದೆ."]
    p = _turn_span(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0)
    assert p.negated is False
    assert p.cross_turn is None


def test_cross_turn_answer_in_first_clause():
    turns = ["ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?", "ಇಲ್ಲ, ಅವನು ಮಲಗಿದ್ದ."]
    p = _turn_span(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0)
    assert p.negated is True and p.cross_turn == "negative"


def test_cross_turn_two_questions_is_ambiguous():
    turns = ["ಜ್ವರ ಇದೆಯಾ? ಕೆಮ್ಮು ಇದೆಯಾ?", "ಇಲ್ಲ."]
    p = _turn_span(turns, "ಜ್ವರ", 0)
    assert p.negated is True
    assert any("more than one question" in a for a in p.ambiguities)


def test_cross_turn_haudu_to_negative_question_is_ambiguous():
    turns = ["ಮಗುವಿಗೆ ಜ್ವರ ಇಲ್ಲವಾ?", "ಹೌದು."]
    p = _turn_span(turns, "ಜ್ವರ", 0)
    assert any("negative question" in a for a in p.ambiguities)


def test_question_without_bare_answer_is_ambiguous():
    turns = ["ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?", "ಅವನು ಮಲಗಿದ್ದ."]
    p = _turn_span(turns, "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್", 0)
    assert any("question" in a for a in p.ambiguities)


def test_unresolvable_bare_illa_is_reported():
    an = analyze("ಪ್ಯಾರಸಿಟಮಾಲ್ ಕೊಟ್ಟೆ.\nಇಲ್ಲ.")
    assert any("no resolvable question" in a for a in an.unresolved_answers)
    an2 = analyze("ಇಲ್ಲ.\nಜ್ವರ ಇದೆ.")
    assert any("no resolvable question" in a for a in an2.unresolved_answers)
    an3 = analyze("ಜ್ವರ ಇದೆಯಾ?\nಇಲ್ಲ.")
    assert an3.unresolved_answers == []
