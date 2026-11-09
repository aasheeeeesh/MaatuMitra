"""Unit tests: Kannada helpers, the negation-table matcher and the template renderer."""

from __future__ import annotations

import random

from m1_data import kn, negation, render


def test_tokens_keep_matras_and_split_on_zwnj():
    toks = [t for t, _, _ in kn.tokens("ಕೆಮ್ಮು ಇಲ್ಲ, 500 mg.")]
    assert toks == ["ಕೆಮ್ಮು", "ಇಲ್ಲ", "500", "mg"]
    # ZWNJ (U+200C) is not a letter/mark/number, so the STORED text splits there ...
    assert [t for t, _, _ in kn.tokens("ಆಂಟಿಬಯಾಟಿಕ್‌ಗಳು")] == ["ಆಂಟಿಬಯಾಟಿಕ್", "ಗಳು"]
    # ... but the comparison copy removes it first (skill section 1.3).
    assert kn.compare_copy("ಆಂಟಿಬಯಾಟಿಕ್‌ಗಳು") == "ಆಂಟಿಬಯಾಟಿಕ್ಗಳು"


def test_digits():
    assert kn.to_kn_digits(500) == "೫೦೦"
    assert kn.compare_copy("೫೦೦ mg") == "500 mg"
    assert kn.has_latin("500 mg") and not kn.has_latin("೫೦೦ ಎಂ.ಜಿ")


def test_negation_matcher_cues_and_traps():
    t = negation.load_table()
    assert "NEG-W01" in t.detect_turn("ಕೆಮ್ಮು ಇಲ್ಲ.")
    assert t.detect_turn("ಮಾತ್ರೆ ಇಲ್ಲಿ ಇದೆ.") == set()  # trap: here, not "no"
    assert t.detect_turn("ಎಲ್ಲಾ ಮಾತ್ರೆ ಇಲ್ಲಿ ಇವೆ, ಅಲ್ವಾ?") == set()
    assert {"NEG-S02", "NEG-S01"} <= t.detect_turn("ಆಂಟಿಬಯಾಟಿಕ್ ಬೇಕಾಗುವುದಿಲ್ಲ.")
    assert "NEG-V01" in t.detect_turn("ಕೋರ್ಸ್ ಮುಗಿಸದೆ ನಿಲ್ಲಿಸಿದೆವು.")
    assert "NEG-S03" in t.detect_turn("ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಬನ್ನಿ.")
    assert "NEG-S03" not in t.detect_turn("ಚೀಟಿ ಓದಿದ್ದರೆ ಗೊತ್ತಾಗುತ್ತಿತ್ತು.")
    assert "NEG-SOFT01" in t.detect_turn("ಮಗು ಸಿರಪ್ ಕುಡಿಯಲ್ಲ.")
    assert "NEG-C01" in t.detect_turn("ಯಾವುದೇ ನೋವು ಇಲ್ಲ.")
    conv = t.detect_conversation(["ಕೆಮ್ಮು ಇದೆಯಾ?", "ಇಲ್ಲ."])
    assert "NEG-X01" in conv
    assert "NEG-X02" in t.detect_conversation(["ಕೆಮ್ಮು ಇದೆಯಾ?", "ಹೌದು."])


def test_render_spans_are_exact_and_twin_flips():
    slots = {
        "S2": render.SymptomFill(name="cough", kn="ಕೆಮ್ಮು"),
        "N1": render.NegFill(neg="ಇಲ್ಲ", pos="ಇದೆ", patterns=["NEG-W01"], negative=True),
    }
    text, spans = render.render_text("ಜ್ವರ ಇದೆ, [[s2|{S2.kn} {N1}]].", slots)
    assert text == "ಜ್ವರ ಇದೆ, ಕೆಮ್ಮು ಇಲ್ಲ."
    s, e = spans["s2"]
    assert text[s:e] == "ಕೆಮ್ಮು ಇಲ್ಲ"
    twin, tspans = render.render_text("ಜ್ವರ ಇದೆ, [[s2|{S2.kn} {N1}]].", slots, flip={"N1"})
    assert twin == "ಜ್ವರ ಇದೆ, ಕೆಮ್ಮು ಇದೆ."
    assert twin[tspans["s2"][0] : tspans["s2"][1]] == "ಕೆಮ್ಮು ಇದೆ"


def test_render_rejects_unfilled_placeholders():
    try:
        render.render_text("{D9.name} ತೆಗೆದುಕೊಳ್ಳಿ.", {})
    except KeyError:
        return
    raise AssertionError("an unknown slot must raise")


def test_drug_surface_forms_are_deterministic():
    from m1_data.lexicon import load_lexicon

    lex = load_lexicon()
    amox = lex["amoxicillin"]
    a = [render.drug_surface(amox, "name", random.Random(7)) for _ in range(3)]
    b = [render.drug_surface(amox, "name", random.Random(7)) for _ in range(3)]
    assert a == b
