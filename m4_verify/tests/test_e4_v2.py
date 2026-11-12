"""E4-v2: planted record.v2 mistakes (route swap, strength drop, status flip, age band flip).

Source records = contracts/migrate_v1_to_v2.py applied to the v1 gold-derived record, plus the
new fields filled from gold.v2. Tests use fixtures and synthetic pairs only (no data/ needed).
"""

from __future__ import annotations

import json

from contracts.migrate_v1_to_v2 import migrate_gold
from contracts.validate import record_spans_match_transcript, validate_doc
from m4_verify import e4_v2
from m4_verify.config import default_config
from m4_verify.lexicon import load_lexicon
from m4_verify.split_guard import load_gold
from m4_verify.tests.helpers import FIX
from m4_verify.tests.helpers_v2 import med2, record2, transcript

LEX = load_lexicon(FIX / "lexicon" / "drugs_fixture.csv")
CFG = default_config()


def _fixture_pairs():
    g1 = load_gold(FIX / "gold" / "valid").docs
    g2 = load_gold(FIX / "gold.v2" / "valid", schema="gold.v2").docs
    return e4_v2.build_pairs(g1, g2)


def test_build_pairs_is_migrate_plus_fill_and_valid():
    pairs, problems = _fixture_pairs()
    assert len(pairs) == 6  # the six conversations that exist as gold.v1 AND gold.v2 fixtures
    assert problems["no_v1_gold"] == 3  # fx-child-007, fx-inj-008, fx-past-009 are v2-only
    for p in pairs:
        assert validate_doc("record.v2", p.record) == []
        assert record_spans_match_transcript(p.record, p.transcript["text"]) == []
    by = {p.cid: p for p in pairs}
    m = by["fx-pharm-003"].record["medications"][0]
    assert m["food_timing"] == "after_food" and m["status"] == "prescribed"
    assert by["fx-asha-002"].record["patient_age_band"]["band"] == "child"


def test_fill_refuses_a_v2_gold_that_disagrees_with_v1():
    g1 = load_gold(FIX / "gold" / "valid").docs
    g2 = load_gold(FIX / "gold.v2" / "valid", schema="gold.v2").docs
    bad = json.loads(json.dumps(g2))
    for g in bad:
        if g["conversation_id"] == "fx-pharm-003":
            g["gold_record"]["medications"][0]["dose_value"] = 250
    pairs, problems = e4_v2.build_pairs(g1, bad)
    assert "fx-pharm-003" not in {p.cid for p in pairs}
    assert problems["v1_v2_mismatch"] == 1


def test_migrated_gold_gives_same_v1_fields():
    # migrate_gold(v1) then fill == migrate_record(v1 record): nothing but the new fields differ
    g1 = load_gold(FIX / "gold" / "valid").docs
    pairs, _ = e4_v2.build_pairs(g1, [migrate_gold(g) for g in g1])
    assert len(pairs) == len(g1)
    for p in pairs:
        assert all(m["status"] == "unknown" for m in p.record["medications"])


# ---- synthetic v2 pair that has every plantable field
T = ["ಮಗುವಿಗೆ ಏಳು ವರ್ಷ.", "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 120 mg/5 ml, 10 ml ಬಾಯಿಗೆ ಕುಡಿಸಿ."]


def _synthetic():
    m = med2(
        T,
        "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ 120 mg/5 ml, 10 ml",
        1,
        "paracetamol",
        10,
        "ml",
        route="oral",
        strength=(120, "mg/5ml"),
        formulation="syrup",
        fe={
            "route": ("ಬಾಯಿಗೆ", 1),
            "strength": ("120 mg/5 ml", 1),
            "formulation": ("ಸಿರಪ್", 1),
            "status": ("ಕುಡಿಸಿ", 1),
        },
    )
    rec = record2(T, meds=[m], age=("child", "ಮಗುವಿಗೆ ಏಳು ವರ್ಷ", 0))
    return e4_v2.Pair("syn-001", transcript(T), rec)


def test_generator_makes_every_type_valid_logged_and_deterministic():
    pairs = [_synthetic()]
    inj = e4_v2.generate_v2(pairs, n_per_type=5, seed=7)
    assert {i["type"] for i in inj} == set(e4_v2.TYPES_V2)
    for i in inj:
        assert validate_doc("record.v2", i["record"]) == [], (i["type"], i["after"])
        assert i["before"] != i["after"]
        assert set(e4_v2.LOG_KEYS) <= set(i)
    k = next(i for i in inj if i["type"] == "k")
    m = k["record"]["medications"][0]
    assert m["strength_value"] is None and "strength" not in m["field_evidence"]
    assert e4_v2.log_rows(inj) == e4_v2.log_rows(e4_v2.generate_v2(pairs, 5, seed=7))


def test_every_planted_v2_type_is_caught_at_its_field():
    pairs = [_synthetic()]
    inj = e4_v2.generate_v2(pairs, n_per_type=5, seed=7)
    rows = e4_v2.evaluate(pairs, inj, LEX, CFG)["results"]
    for t in e4_v2.TYPES_V2:
        got = [r for r in rows if r["type"] == t]
        assert got and all(r["caught_at_field"] for r in got), (t, got)


def test_run_on_fixtures_writes_tables(tmp_path):
    s = e4_v2.run_e4_v2(
        FIX / "gold" / "valid", FIX / "gold.v2" / "valid", LEX, CFG, tmp_path, n_per_type=10
    )
    out = tmp_path / "e4_v2"
    for f in (
        "summary.md",
        "summary.json",
        "catch_rates.csv",
        "injection_log_record.jsonl",
        "injection_results.jsonl",
        "clean_flag_rate.csv",
    ):
        assert (out / f).exists(), f
    assert s["verdict_validation_errors"] == []
    md = (out / "summary.md").read_text(encoding="utf-8")
    assert "Wilson" in md and "strength drop" in md
    # strength drop has no candidate in the fixtures: reported as not measurable, never as 0 errors
    k = next(r for r in s["catch_rates"] if r["type"] == "k")
    assert k["n_unique"] == 0 and "not measurable" in k["note"]
