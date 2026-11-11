"""record.v2 / gold.v2 contract tests (written before the v2 schemas, validator rules and migrator).

Proves: v2 schemas exist and are additive (v1 still resolves by default); every v2 valid fixture
passes and every v2 invalid fixture fails; every non-null new field has evidence; strength value
and unit come as a pair; record evidence (also per-field evidence, age band, weight) points into
the paired transcript; gold.v2 speaker equals the role of the turn of its span; bidi control
characters are rejected in v2 and by the opt-in check for v1; the v1 -> v2 migrator is
conservative (negated never becomes advised_against) and its output validates.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from contracts import migrate_v1_to_v2 as M
from contracts import validate as V

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
V2 = ["record.v2", "gold.v2"]
BIDI = [chr(c) for c in [*range(0x202A, 0x202F), *range(0x2066, 0x206A)]]
NEW_MED_FIELDS = ["route", "formulation", "as_needed", "food_timing"]


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _valid(name: str) -> list[dict]:
    return [_load(p) for p in sorted((FIX / name / "valid").glob("*.json"))]


def _by_id(name: str, rid: str) -> dict:
    key = "record_id" if name.startswith("record") else "conversation_id"
    return copy.deepcopy(next(d for d in _valid(name) if d[key] == rid))


def _transcripts() -> dict[str, dict]:
    out = {}
    for d in (FIX / "transcript" / "valid", FIX / "record.v2" / "transcripts"):
        for p in d.glob("*.json"):
            out[_load(p)["audio_id"]] = _load(p)
    return out


# ---- versioning is additive -------------------------------------------------------------


def test_v2_schemas_exist_and_v1_stays_default():
    names = V.list_schemas()
    assert {"record.v1", "record.v2", "gold.v1", "gold.v2"} <= set(names)
    assert V._canonical("record") == "record.v1"  # bare name keeps meaning v1 (no silent upgrade)
    assert V._canonical("gold") == "gold.v1"
    for n in V2:
        assert V.load_schema(n)["properties"]["schema_version"] == {"const": n}


def test_v1_document_is_not_a_v2_document():
    rec = _valid("record")[0]
    assert V.validate_doc("record.v1", rec) == []
    assert V.validate_doc("record.v2", rec)  # different schema_version, missing new fields


# ---- fixtures ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", V2)
def test_v2_fixture_counts_and_readme(name):
    valid = sorted((FIX / name / "valid").glob("*.json"))
    invalid = sorted((FIX / name / "invalid").glob("*.json"))
    assert len(valid) >= 5 and len(invalid) >= 3
    readme = (FIX / name / "invalid" / "README.md").read_text(encoding="utf-8")
    for p in invalid:
        assert p.name in readme, f"{p.name} not explained in invalid/README.md"


@pytest.mark.parametrize("name", V2)
def test_v2_valid_fixtures_pass(name):
    for p in sorted((FIX / name / "valid").glob("*.json")):
        assert V.validate_doc(name, _load(p)) == [], p.name


@pytest.mark.parametrize("name", V2)
def test_v2_invalid_fixtures_fail(name):
    for p in sorted((FIX / name / "invalid").glob("*.json")):
        assert V.validate_doc(name, _load(p)), f"{p.name} should be rejected"


def test_required_example_fixtures_exist():
    recs = {r["record_id"]: r for r in _valid("record.v2")}
    child = recs["rec2-fx-child-007"]
    med = child["medications"][0]
    assert med["formulation"] == "syrup" and med["dose_unit"] == "ml"
    assert (med["strength_value"], med["strength_unit"]) == (120, "mg/5ml")
    assert child["patient_age_band"]["band"] == "child" and child["weight_kg"]["value"] == 10
    assert recs["rec2-fx-inj-008"]["medications"][0]["formulation"] == "injection"
    assert recs["rec2-fx-inj-008"]["medications"][0]["route"] == "injection_unspecified"
    past = recs["rec2-fx-past-009"]["medications"]
    assert {m["status"] for m in past} == {"already_taken", "advised_against"}
    no_strength = recs["rec2-fx-child-007-no-strength"]["medications"][0]
    assert no_strength["strength_value"] is None  # structurally valid; m4 must flag it
    inv = {p.name for p in (FIX / "record.v2" / "invalid").glob("*.json")}
    assert any("bidi" in n for n in inv)


def test_v2_record_evidence_points_into_paired_transcript():
    trs = _transcripts()
    checked = 0
    for rec in _valid("record.v2"):
        tr = trs.get(rec["source_transcript_id"])
        assert tr is not None, rec["record_id"]
        assert V.validate_doc("transcript.v1", tr) == []
        errs = V.validate_doc("record.v2", rec, transcript_text=tr["text"])
        assert errs == [], (rec["record_id"], errs)
        checked += len(list(V._all_evidence(rec)))
    assert checked >= 30


def test_gold_v2_turns_match_record_v2_transcripts():
    trs = _transcripts()
    for g in _valid("gold.v2"):
        assert trs[g["conversation_id"]]["text"] == V.conversation_text(g["turns"])


# ---- semantic rules ---------------------------------------------------------------------


def test_transcript_mismatch_is_reported():
    rec = _by_id("record.v2", "rec2-fx-child-007")
    text = _transcripts()[rec["source_transcript_id"]]["text"]
    assert V.record_spans_match_transcript(rec, text) == []
    ev = rec["medications"][0]["field_evidence"]["strength"]
    ev["char_start"] += 1
    ev["char_end"] += 1
    assert V.record_spans_match_transcript(rec, text)
    ev["char_start"], ev["char_end"] = len(text) + 5, len(text) + 5 + len(ev["span_text"])
    assert any("beyond" in e for e in V.record_spans_match_transcript(rec, text))


def test_transcript_check_works_for_v1_too():
    rec = _valid("record")[0]
    tr = _transcripts()[rec["source_transcript_id"]]
    assert V.validate_doc("record.v1", rec, transcript_text=tr["text"]) == []
    assert V.validate_doc("record.v1", rec, transcript_text="x" * 200)


@pytest.mark.parametrize("field", [*NEW_MED_FIELDS, "strength", "status"])
def test_non_null_new_field_needs_evidence(field):
    rec = _by_id("record.v2", "rec2-fx-child-007")
    med = rec["medications"][0]
    med["route"] = "oral"
    med["field_evidence"]["route"] = copy.deepcopy(med["evidence"])
    med["food_timing"] = "after_food"
    med["field_evidence"]["food_timing"] = copy.deepcopy(med["evidence"])
    assert V.validate_doc("record.v2", rec) == []
    del med["field_evidence"][field]
    assert any("evidence" in e for e in V.validate_doc("record.v2", rec)), field


def test_dangling_evidence_for_null_field_rejected():
    rec = _by_id("record.v2", "rec2-fx-child-007")
    med = rec["medications"][0]
    assert med["route"] is None
    med["field_evidence"]["route"] = copy.deepcopy(med["evidence"])
    assert V.validate_doc("record.v2", rec)


def test_status_unknown_needs_no_evidence():
    rec = _by_id("record.v2", "rec2-fx-child-007")
    med = rec["medications"][0]
    med["status"] = "unknown"
    del med["field_evidence"]["status"]
    assert V.validate_doc("record.v2", rec) == []


def test_strength_value_and_unit_are_a_pair():
    rec = _by_id("record.v2", "rec2-fx-child-007")
    rec["medications"][0]["strength_unit"] = None
    assert any("strength" in e for e in V.validate_doc("record.v2", rec))


def test_age_band_and_weight_need_evidence():
    rec = _by_id("record.v2", "rec2-fx-child-007")
    del rec["weight_kg"]["evidence"]
    assert V.validate_doc("record.v2", rec)
    rec = _by_id("record.v2", "rec2-fx-child-007")
    rec["patient_age_band"] = {"band": "child"}
    assert V.validate_doc("record.v2", rec)


def test_old_negated_meaning_is_not_a_status():
    rec = _by_id("record.v2", "rec2-fx-child-007")
    rec["medications"][0]["status"] = "negated"
    assert V.validate_doc("record.v2", rec)


@pytest.mark.parametrize("ch", BIDI)
def test_bidi_controls_rejected_in_record_v2(ch):
    rec = _by_id("record.v2", "rec2-fx-child-007")
    rec["patient_ref"] = f"pt{ch}-1"
    assert any("bidi" in e for e in V.validate_doc("record.v2", rec))


def test_bidi_rejected_in_gold_v2_and_nested_strings():
    g = _valid("gold.v2")[0]
    g["template_family_id"] = "fam\u202ex"
    assert any("bidi" in e for e in V.validate_doc("gold.v2", g))
    rec = _by_id("record.v2", "rec2-fx-pharm-003")
    rec["extractor"]["name"] = "x\u2066y"
    assert any("bidi" in e for e in V.validate_doc("record.v2", rec))


def test_bidi_is_opt_in_for_v1():
    rec = _valid("record")[0]
    rec["patient_ref"] = "pt\u202e-1"
    assert V.validate_doc("record.v1", rec) == []  # v1 behaviour unchanged by default
    assert V.bidi_errors(rec)
    assert V.validate_doc("record.v1", rec, reject_bidi=True)
    assert V.bidi_errors(_valid("record")[0]) == []
    assert V.bidi_errors({"a": ["ok", {"b": "ಮಗು\u200f"}]}) == []  # U+200F (RLM) is not in the list


def test_gold_v2_speaker_must_match_turn_role():
    g = _by_id("gold.v2", "fx-pharm-003")
    assert V.validate_doc("gold.v2", g) == []
    g["gold_record"]["medications"][0]["speaker"] = "caregiver"
    assert any("speaker" in e for e in V.validate_doc("gold.v2", g))


def test_gold_v2_field_span_must_match_text():
    g = _by_id("gold.v2", "fx-child-007")
    sp = g["gold_record"]["medications"][0]["gold_field_spans"]["strength"]
    sp["char_start"] += 1
    sp["char_end"] += 1
    assert V.validate_doc("gold.v2", g)


def test_gold_v2_has_negation_rule_kept():
    g = _by_id("gold.v2", "fx-past-009")
    g["tags"]["has_negation"] = False
    assert any("has_negation" in e for e in V.validate_doc("gold.v2", g))


# ---- migrator ---------------------------------------------------------------------------


def test_migrate_every_v1_record_fixture_validates_as_v2():
    for rec in _valid("record"):
        out = M.migrate_record(rec)
        assert V.validate_doc("record.v2", out) == [], rec["record_id"]
        assert out["schema_version"] == "record.v2"
        for med_in, med_out in zip(rec["medications"], out["medications"], strict=True):
            for k in ("drug", "dose_value", "dose_unit", "frequency_per_day", "duration_days"):
                assert med_out[k] == med_in[k]
            assert med_out["negated"] == med_in["negated"]
            assert med_out["status"] == "unknown"
            assert med_out["speaker"] == "unknown"
            assert med_out["field_evidence"] == {}
            for f in [*NEW_MED_FIELDS, "strength_value", "strength_unit"]:
                assert med_out[f] is None
        assert out["patient_age_band"] is None and out["weight_kg"] is None


def test_migrate_negated_never_becomes_advised_against():
    rec = _by_id("record", "rec-fx-asha-002")
    assert rec["medications"][0]["negated"] is True
    out = M.migrate_record(rec)
    assert out["medications"][0]["status"] == "unknown"


def test_migrate_does_not_mutate_input_and_refuses_bad_input():
    rec = _valid("record")[2]
    before = copy.deepcopy(rec)
    M.migrate_record(rec)
    assert rec == before
    with pytest.raises(ValueError):
        M.migrate_record({**rec, "schema_version": "record.v2"})
    bad = copy.deepcopy(rec)
    bad["status"] = "done"
    with pytest.raises(ValueError):
        M.migrate_record(bad)


def test_migrate_gold_sets_speaker_from_turn_role():
    for g in _valid("gold"):
        out = M.migrate_gold(g)
        assert V.validate_doc("gold.v2", out) == [], g["conversation_id"]
        for med in out["gold_record"]["medications"]:
            assert med["status"] == "unknown"
            role = g["turns"][med["gold_span"]["turn_index"]]["speaker_role"]
            assert med["speaker"] == M.SPEAKER_FROM_ROLE[role]


def test_migrate_cli_jsonl(tmp_path):
    src = tmp_path / "in.jsonl"
    rows = _valid("record")
    src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", "utf-8")
    dst = tmp_path / "out.jsonl"
    res = subprocess.run(
        [sys.executable, "-m", "contracts.migrate_v1_to_v2", "record", str(src), "-o", str(dst)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert V.validate_path("record.v2", dst) and all(
        errs == [] for errs in V.validate_path("record.v2", dst).values()
    )
    assert len(dst.read_text(encoding="utf-8").splitlines()) == len(rows)
