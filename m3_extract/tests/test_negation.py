"""Negation FLAG: uses ONLY the shared table (.claude/skills/kannada-nlp/negation_table.yaml).

Positive cue, minimal-pair twin and trap for the table rules. Kannada not native-validated.
"""

import pytest

from m3_extract import negation as neg
from m3_extract import textnorm as tn

TABLE = neg.load_table()


def clause_negs(text):
    toks = tn.tokenize(text)
    return [
        (c.text(text), neg.clause_negation(c, TABLE).negated)
        for c in neg.split_clauses(text, toks, TABLE)
    ]


def is_neg(text):
    return any(n for _, n in clause_negs(text))


def test_table_is_the_shared_file():
    assert TABLE.path.name == "negation_table.yaml"
    assert ".claude" in str(TABLE.path)
    assert TABLE.version >= 1


@pytest.mark.parametrize(
    "neg_text,pos_twin",
    [
        ("ಕೆಮ್ಮು ಇಲ್ಲ.", "ಕೆಮ್ಮು ಇದೆ."),
        ("ಜ್ವರ ಇಲ್ಲಾ.", "ಜ್ವರ ಇದೆ."),
        ("ಇದು ಈ ಮಾತ್ರೆ ಅಲ್ಲ.", "ಇದು ಈ ಮಾತ್ರೆ."),
        ("ನೆಗಡಿಗೆ ಆಂಟಿಬಯಾಟಿಕ್ ಬೇಡ.", "ನೆಗಡಿಗೆ ಆಂಟಿಬಯಾಟಿಕ್ ಬೇಕು."),
        ("ಉಳಿದ ಮಾತ್ರೆ ಕೊಡುವುದು ಬೇಡಿ.", "ಉಳಿದ ಮಾತ್ರೆ ಕೊಡಿ."),
        ("ಈ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳ ಬಾರದು.", "ಈ ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳಬಹುದು."),
        ("ಹಂಚಿಕೊಳ್ಳ ಕೂಡದು.", "ಹಂಚಿಕೊಳ್ಳಬಹುದು."),
        ("ವಾಂತಿ ಆಗಿಲ್ಲ.", "ವಾಂತಿ ಆಗಿದೆ."),
        ("ನಾನು ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳುವುದಿಲ್ಲ.", "ನಾನು ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳುತ್ತೇನೆ."),
        ("ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು.", "ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಹುದು."),
        ("ಉಳಿದ ಮಾತ್ರೆ ಹಂಚಿಕೊಳ್ಳಕೂಡದು.", "ಉಳಿದ ಮಾತ್ರೆ ಹಂಚಿಕೊಳ್ಳಬಹುದು."),
        ("ಉಳಿದ ಮಾತ್ರೆಗಳನ್ನು ಬೇರೆಯವರಿಗೆ ಕೊಡಬೇಡಿ.", "ಉಳಿದ ಮಾತ್ರೆಗಳನ್ನು ಬೇರೆಯವರಿಗೆ ಕೊಡಿ."),
        ("ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳದೆ ಹೋದರು.", "ಔಷಧಿ ತೆಗೆದುಕೊಂಡು ಹೋದರು."),
        ("ಮಗು ಸಿರಪ್ ಕುಡಿಯಲ್ಲ.", "ಮಗು ಸಿರಪ್ ಕುಡಿಯುತ್ತೆ."),
        ("ಯಾವುದೇ ತೊಂದರೆ ಇಲ್ಲ.", "ತೊಂದರೆ ಇದೆ."),
    ],
)
def test_cue_and_minimal_pair(neg_text, pos_twin):
    assert is_neg(neg_text), neg_text
    assert not is_neg(pos_twin), pos_twin


@pytest.mark.parametrize(
    "trap",
    [
        "ಎಲ್ಲ ಮಾತ್ರೆ ಮುಗಿಸಿ.",
        "ಎಲ್ಲಾ ಮಾತ್ರೆ ಇಲ್ಲಿ ಇವೆ, ಅಲ್ವಾ?",
        "ಆಸ್ಪತ್ರೆ ಅಲ್ಲಿ ಇದೆ.",
        "ಜ್ವರ ಕಡಿಮೆ ಆಯ್ತು ಅಲ್ವ?",
        "ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಮಾತ್ರ.",
        "ಜ್ವರ ಬಂದಿದೆ.",
        "ಜ್ವರ ಇದ್ದರೆ ಬನ್ನಿ.",
        "ಚೀಟಿ ಓದಿದ್ದರೆ ಗೊತ್ತಾಗುತ್ತಿತ್ತು.",
        "ಔಷಧಿಗೆ ಬೇಡಿಕೆ ಇದೆ.",
    ],
)
def test_traps_do_not_trigger(trap):
    assert not is_neg(trap), trap


def test_clause_scope():
    res = clause_negs("ತಲೆನೋವು ಇದೆ, ಆದರೆ ವಾಂತಿ ಆಗಿಲ್ಲ.")
    assert res == [("ತಲೆನೋವು ಇದೆ", False), ("ವಾಂತಿ ಆಗಿಲ್ಲ", True)]
    res = clause_negs("ಜ್ವರ ಇಲ್ಲ ಮತ್ತು ಕೆಮ್ಮು ಇದೆ.")
    assert res == [("ಜ್ವರ ಇಲ್ಲ", True), ("ಕೆಮ್ಮು ಇದೆ", False)]


def test_abbreviation_dot_does_not_split_clause():
    text = "ceftriaxone 1000 ಎಂ.ಜಿ ಬೇಡ."
    res = clause_negs(text)
    assert res == [("ceftriaxone 1000 ಎಂ.ಜಿ ಬೇಡ", True)]


def test_conditional_if_not_is_marked_conditional():
    toks = tn.tokenize("ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಬನ್ನಿ.")
    (c,) = neg.split_clauses("ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಬನ್ನಿ.", toks, TABLE)
    r = neg.clause_negation(c, TABLE)
    assert "NEG-S03" in r.cue_ids
    assert r.conditional and not r.negated


def test_cross_turn_answer():
    assert neg.cross_turn_answer(tn.tokenize("ಇಲ್ಲ."), TABLE) == "negative"
    assert neg.cross_turn_answer(tn.tokenize("ಇಲ್ಲಾ."), TABLE) == "negative"
    assert neg.cross_turn_answer(tn.tokenize("ಹೌದು."), TABLE) == "affirmative"
    assert neg.cross_turn_answer(tn.tokenize("ಇಲ್ಲ, ಕುಡಿಯಲಿಲ್ಲ."), TABLE) is None


def test_soft_cue_with_unknown_stem_is_soft():
    toks = tn.tokenize("ಅವನು ಓಡಲ್ಲ.")
    (c,) = neg.split_clauses("ಅವನು ಓಡಲ್ಲ.", toks, TABLE)
    r = neg.clause_negation(c, TABLE)
    assert r.soft and r.negated  # soft cue: counted as negation, but logged as soft
