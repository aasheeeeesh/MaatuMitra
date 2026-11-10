"""REFREEZE-1 (D-91, D-93, D-94): child doses, lexicon fixes, negation table v2, guide leak.

Written before the fixes; each test fails on the pre-refreeze data.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

import pytest
import regex

from m1_data import kn, negation
from m1_data.config import ROOT
from m1_data.generate import conflicts
from m1_data.lexicon import LEXICON_CSV, load_lexicon
from m1_data.split import plan_families
from m1_data.templates import load_templates

DATA = ROOT / "data"
GUIDE = ROOT / "docs" / "annotation_guide.md"
SEVERITY = ROOT / "docs" / "severity.md"
ADULT_UNITS = {"mg", "tablet", "capsule", "g"}
EIGHT_LEAKED = [
    "ಆದ್ದರಿಂದ",
    "ಕೋರ್ಸ್",
    "ತಗೊಂಡ್ರೆ",
    "ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ",
    "ನಿಲ್ಲಿಸಿ",
    "ನಿಲ್ಲಿಸಿದೆ",
    "ನಿಲ್ಲಿಸಿದೆವು",
    "ಮುಗಿಸದೆ",
]


def _gold():
    return [json.loads(p.read_text("utf-8")) for p in sorted((DATA / "gold").glob("*.json"))]


@pytest.fixture(scope="module")
def gold():
    return _gold()


# ---------------------------------------------------------------- 1. child doses


def test_no_child_conversation_has_an_adult_dose(gold):
    n_child = 0
    for d in gold:
        text = "\n".join(t["text"] for t in d["turns"])
        if "ಮಗು" not in text:
            continue
        n_child += 1
        for m in d["gold_record"]["medications"]:
            if (
                m["drug"] == "zinc"
            ):  # 20 mg dispersible tablet IS the paediatric dose (WHO, review U5)
                continue
            assert m["dose_unit"] not in ADULT_UNITS, (d["conversation_id"], m)
    assert n_child > 50


def test_child_syrup_templates_use_ml_and_the_word_syrup(gold):
    seen = Counter()
    for d in gold:
        tid = d["conversation_id"].split("-")[1]
        if tid not in {"e8", "h2", "h3", "i5"}:
            continue
        paracetamol = [m for m in d["gold_record"]["medications"] if m["drug"] == "paracetamol"]
        assert len(paracetamol) == 1, d["conversation_id"]
        m = paracetamol[0]
        assert m["dose_unit"] == "ml" and m["dose_value"] in {2.5, 5, 7.5, 10}
        assert "ಸಿರಪ್" in m["gold_span"]["span_text"]
        seen[tid] += 1
    assert set(seen) == {"e8", "h2", "h3", "i5"}


def test_a3_child_turn_gives_no_dose(gold):
    docs = [d for d in gold if d["conversation_id"].split("-")[1] == "a3"]
    assert docs
    for d in docs:
        (m,) = d["gold_record"]["medications"]
        assert m["dose_value"] is None and m["dose_unit"] is None
        assert "ಸಿರಪ್" in m["gold_span"]["span_text"]


def test_ml_combinations_are_split_exclusive_and_present_on_both_sides():
    plan = json.loads((DATA / "splits" / "split_plan.json").read_text("utf-8"))
    ml = {
        s: {tuple(c) for c in plan["dosed_drug_combinations"][s] if c[2] == "ml"}
        for s in plan["families"]
    }
    assert ml["dev"] and ml["test"] and not (ml["dev"] & ml["test"])


# ---------------------------------------------------------------- 2. e2 and interaction pairs


def test_e2_patient_line_and_no_chelation_pair(gold):
    e2 = [d for d in gold if d["conversation_id"].split("-")[1] == "e2"]
    assert e2
    lex = load_lexicon()
    for d in e2:
        assert d["turns"][2]["text"] == "ಎರಡೂ ಔಷಧಿ ಒಟ್ಟಿಗೆ ಕೊಡಬಹುದಾ?"
        names = [m["drug"] for m in d["gold_record"]["medications"]]
        assert not conflicts(lex[names[0]], lex[names[1]]), names


def test_no_conversation_has_a_conflicting_dosed_pair(gold):
    lex = load_lexicon()
    for d in gold:
        dosed = [m["drug"] for m in d["gold_record"]["medications"] if m["dose_value"] is not None]
        for i, a in enumerate(dosed):
            for b in dosed[i + 1 :]:
                assert not conflicts(lex[a], lex[b]), (d["conversation_id"], a, b)


def test_conflicts_rule():
    lex = load_lexicon()
    assert conflicts(lex["ciprofloxacin"], lex["zinc"])
    assert conflicts(lex["doxycycline"], lex["iron-folic acid"])
    assert conflicts(lex["ibuprofen"], lex["diclofenac"])
    assert not conflicts(lex["amoxicillin"], lex["zinc"])


# ---------------------------------------------------------------- 3. lexicon rows


@pytest.fixture(scope="module")
def rows():
    with LEXICON_CSV.open(encoding="utf-8", newline="") as fh:
        return {r["generic_en"]: r for r in csv.DictReader(fh)}


@pytest.mark.parametrize(
    "drug,rng,max_daily",
    [
        ("paracetamol", "500-1000", "4000"),
        ("ondansetron", "4-24", ""),
        ("metformin", "500-1000", "2550"),
        ("ibuprofen", "200-800", "3200"),
    ],
)
def test_clinical_review_ranges(rows, drug, rng, max_daily):
    assert rows[drug]["adult_dose_range_mg"] == rng
    assert rows[drug]["max_daily_mg"] == max_daily
    assert rows[drug]["source_url"].startswith("https://")


def test_paracetamol_range_cites_the_nhs_page(rows):
    assert "nhs.uk/medicines/paracetamol-for-adults" in rows["paracetamol"]["source_url"]


def test_ors_unit_and_iron_folic_units_are_documented_not_invented(rows):
    assert "sachet" in rows["ors"]["verified_by"] and "never mg" in rows["ors"]["verified_by"]
    assert rows["ors"]["adult_dose_range_mg"] == ""
    ifa = rows["iron-folic acid"]
    assert "mcg" in ifa["verified_by"] and ifa["adult_dose_range_mg"] == ""
    assert "UNVERIFIED" in ifa["verified_by"]


def test_aliases(rows):
    assert "625" in rows["amoxicillin-clavulanate"]["roman_variants"].split("|")
    assert "levo" not in rows["levofloxacin"]["roman_variants"].split("|")
    assert "ಲೇವೋ" not in rows["levofloxacin"]["kn_variants"].split("|")


def test_numeric_alias_is_never_spoken_as_a_drug_name(gold):
    for d in gold:
        for m in d["gold_record"]["medications"]:
            if m["drug"] == "amoxicillin-clavulanate":
                assert not m["gold_span"]["span_text"].startswith("625")


def test_unreviewed_rows_stay_unverified(rows):
    for g in ("metronidazole", "cotrimoxazole"):
        assert rows[g]["adult_dose_range_mg"] in {"250-2000", "800-800"}  # unchanged on purpose
        assert "UNVERIFIED" in rows[g]["verified_by"]


def test_ors_is_spelled_with_long_o(rows):
    assert rows["ors"]["kn_primary"] == "ಓ.ಆರ್.ಎಸ್"
    assert "ಒ.ಆರ್.ಎಸ್" not in (rows["ors"]["kn_primary"] + rows["ors"]["kn_variants"])


# ---------------------------------------------------------------- 4. Kannada fixes


def test_ungrammatical_dont_give_form_is_gone():
    forms = set()
    for t in load_templates():
        for sp in t.slots.values():
            for f in sp.get("forms", []) if isinstance(sp.get("forms"), list) else []:
                forms.add(f["neg"])
    assert "ಕೊಡುವುದು ಬೇಡಿ" not in forms
    assert "ಕೊಡಬೇಡಿ" in forms


def test_positive_twins_of_h5_e7_h2_are_meaningful_sentences():
    tw = [
        json.loads(x)
        for s in ("dev", "test")
        for x in (DATA / "twins" / f"twins_{s}.jsonl").read_text("utf-8").splitlines()
    ]
    pos = {t["template_id"]: t["positive_text"] for t in tw}
    assert pos["h5"] == "ಇದ್ದರೆ" and pos["h2"] == "ಇದ್ದರೆ"
    assert pos["e7"] == "ವಾಂತಿ ಮಾಡಿದರೆ"
    for bad in ("ನಿಂತರೆ", "ಕುಡಿದರೆ", "ಇಳಿದರೆ"):
        assert bad not in pos.values()


# ---------------------------------------------------------------- 5. guide leak


def _kn_tokens(text: str) -> set[str]:
    return {t for t, _, _ in kn.tokens(kn.compare_copy(text)) if kn.has_kannada(t)}


def _template_vocab(families: set[str]) -> set[str]:
    out: set[str] = set()
    for t in load_templates():
        if t.family not in families:
            continue
        for turn in t.turns:
            out |= _kn_tokens(turn["text"])
        for s in t.slots.values():
            for f in s.get("forms", []) if isinstance(s.get("forms"), list) else []:
                out |= _kn_tokens(f["neg"]) | _kn_tokens(f["pos"])
            for key in ("choices",):
                for w in s.get(key, []):
                    out |= _kn_tokens(w)
    return out


def test_guide_has_no_test_only_vocabulary():
    plan = plan_families(load_templates())
    dev = {f for f, s in plan.items() if s == "dev"}
    test = {f for f, s in plan.items() if s == "test"}
    test_only = _template_vocab(test) - _template_vocab(dev)
    assert test_only  # the check is not vacuous
    guide = _kn_tokens(GUIDE.read_text("utf-8"))
    assert not (guide & test_only), sorted(guide & test_only)


def test_guide_does_not_print_the_eight_leaked_words():
    text = kn.compare_copy(GUIDE.read_text("utf-8"))
    words = {t for t, _, _ in kn.tokens(text)}
    assert not (set(EIGHT_LEAKED) & words), sorted(set(EIGHT_LEAKED) & words)


def test_guide_spells_ors_with_long_o():
    g = GUIDE.read_text("utf-8")
    assert "ಒ.ಆರ್.ಎಸ್" not in g and "ಓ.ಆರ್.ಎಸ್" in g


def test_guide_states_the_dev_only_example_rule():
    assert "dev-family" in GUIDE.read_text("utf-8")


# ---------------------------------------------------------------- 6. severity


def test_severity_has_the_three_new_critical_classes():
    s = SEVERITY.read_text("utf-8")
    for code in ("CR-ROUTE", "CR-PAEDIATRIC", "CR-LIQUID-STRENGTH"):
        assert code in s
    assert "REFREEZE-1" in s and "D-91" in s and "before any test run" in s


# ---------------------------------------------------------------- 7. negation table v2

TABLE = negation.load_table()


def _cues(sentence: str) -> set[str]:
    return TABLE.detect_turn(sentence) - negation.NON_CUE_IDS


def test_table_version_bumped():
    assert TABLE.version >= 2


def test_jaggery_no_longer_triggers():
    assert _cues("ಬೆಲ್ಲ ಕೊಡಿ.") == set()
    assert TABLE.token_cues("ಬೆಲ್ಲ") == set()


def test_soft_cue_still_fires_on_verb_stems():
    assert TABLE.token_cues("ಕುಡಿಯಲ್ಲ") == {"NEG-SOFT01"}
    assert TABLE.token_cues("ತಿನ್ನಲ್ಲ") == {"NEG-SOFT01"}
    assert TABLE.token_cues("ಬರಲ್ಲ") == {"NEG-SOFT01"}


def test_negative_question_and_aagade():
    assert "NEG-S07" in TABLE.token_cues("ಕುಡಿಯಲ್ವಾ")
    assert "NEG-S07" in TABLE.token_cues("ಬರಲ್ವಾ")
    assert "NEG-V01" in TABLE.token_cues("ಆಗದೆ")
    assert "NEG-V01" in _cues("ಜ್ವರ ಕಡಿಮೆ ಆಗದೆ ಇದ್ದರೆ ಬನ್ನಿ.")


def test_no_clause_split_inside_abbreviations():
    for s in ("ಪ್ಯಾರಸಿಟಮಾಲ್ 500 ಎಂ.ಜಿ ಮಾತ್ರೆ ಕೊಡಿ", "ಐದು ಎಂ.ಎಲ್ ಕುಡಿಸಿ", "ಓ.ಆರ್.ಎಸ್ ಕುಡಿಸಿ"):
        assert len(TABLE.clauses_by_punct(s)) == 1, s
    assert len(TABLE.clauses_by_punct("ಜ್ವರ ಇದೆ. ಕೆಮ್ಮು ಇಲ್ಲ.")) == 2
    assert len(TABLE.clauses_by_punct("ಜ್ವರ ಇದೆ, ಕೆಮ್ಮು ಇಲ್ಲ")) == 2


def test_every_trap_gives_zero_false_triggers():
    entries = [e for e in TABLE.entries if e["type"] == "must_not_trigger"]
    assert len(entries) >= 14
    for e in entries:
        tok = e["token"]
        assert TABLE.token_cues(tok) == set(), tok
        assert _cues(e["example"]) == set(), (e["id"], e["example"])
    for tok in ("ಅಲ್ವಾ", "ಅಲ್ವ"):
        assert "NEG-S07" not in TABLE.token_cues(tok)


def test_table_file_marks_the_new_entry_not_generated():
    e = {x["id"]: x for x in TABLE.entries}
    assert e["NEG-S07"]["generate"] is False
    assert regex.search(e["NEG-S07"]["pattern"], "ಕುಡಿಯಲ್ವಾ")
