"""The TTS model reads Kannada script only, so Latin words in gold text are respelled for it."""

from __future__ import annotations

import glob
import json
import re

from m1_data.tts_pronounce import build_table, kannadify

from .conftest import DATA, ROOT

TABLE = build_table(ROOT / "data" / "lexicon" / "drugs.csv")


def test_known_drug_and_unit():
    out = kannadify("Paracetamol 500 mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ.", TABLE)
    assert not re.search(r"[A-Za-z]", out)
    assert "ಮಿಲಿಗ್ರಾಂ" in out and "500" in out  # digits stay: the TTS front end spells numbers


def test_misspelling_maps_to_the_same_drug():
    assert kannadify("paracetmol", TABLE) == kannadify("paracetamol", TABLE)
    assert kannadify("cetrizine", TABLE) == kannadify("cetirizine", TABLE)


def test_dotted_ors_and_non_latin_text_unchanged():
    assert not re.search(r"[A-Za-z]", kannadify("O.R.S ಕುಡಿಸಿ", TABLE))
    s = "ಮಗುವಿಗೆ ಜ್ವರ ಇಲ್ಲ."
    assert kannadify(s, TABLE) == s


def test_every_gold_turn_becomes_pure_kannada_script():
    bad = []
    for p in sorted(glob.glob(str(DATA / "gold" / "*.json"))):
        for t in json.load(open(p, encoding="utf-8"))["turns"]:
            out = kannadify(t["text"], TABLE)
            if re.search(r"[A-Za-z]", out):
                bad.append((p, out))
    assert bad == [], bad[:3]


def test_unknown_latin_word_raises():
    import pytest

    with pytest.raises(KeyError):
        kannadify("blorptabulin", TABLE)
