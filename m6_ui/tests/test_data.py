"""Fixture loading: every input the app reads is validated with contracts.validate."""

from __future__ import annotations

from contracts.validate import validate_doc
from m6_ui import data
from m6_ui.tests.helpers import M6, ROOT


def test_m6_fixtures_are_valid_contract_documents():
    for schema, sub in (
        ("transcript.v1", "transcript"),
        ("record.v1", "record"),
        ("verdict.v1", "verdict"),
    ):
        files = list((M6 / "fixtures" / sub).glob("*.json"))
        assert files
        for f in files:
            assert validate_doc(schema, data.read_json(f)) == [], f


def test_catalogue_contains_shared_and_m6_fixtures_with_matching_parts():
    cat = data.Catalogue(ROOT)
    ids = cat.record_ids()
    assert "rec-fx-pharm-003-asr" in ids and "rec-m6-xss" in ids
    case = cat.case("rec-fx-pharm-003-asr")
    assert case.transcript["audio_id"] == case.record["source_transcript_id"]
    assert case.verdict["record_id"] == case.record["record_id"]
    assert case.errors == []


def test_evidence_spans_match_transcript_text():
    cat = data.Catalogue(ROOT)
    for rid in cat.record_ids():
        case = cat.case(rid)
        if case.transcript is None:
            continue
        for ev in data.evidence_items(case.record):
            assert case.transcript["text"][ev["char_start"] : ev["char_end"]] == ev["span_text"], (
                rid
            )


def test_record_without_verdict_is_reported_not_hidden():
    case = data.Catalogue(ROOT).case("rec-fx-pharm-003")
    assert case.verdict is None
    assert "no_verdict" in case.errors


def test_cards_are_loaded_and_valid():
    cards = data.Catalogue(ROOT).cards()
    assert len(cards) >= 5
    assert all(validate_doc("card.v1", c) == [] for c in cards)


def test_record_v2_fixtures_are_loaded_and_checked():
    cat = data.Catalogue(ROOT)
    ids = cat.record_ids()
    assert "rec2-fx-child-007-no-strength" in ids
    case = cat.case("rec2-fx-child-007-no-strength")
    assert case.record["schema_version"] == "record.v2"
    assert case.transcript is not None and "span_mismatch" not in case.errors
    assert "no_verdict" in case.errors  # no stored verdict: shown as fail-closed, never as fine


def test_each_role_sees_only_its_own_records_in_mock():
    # F1 (D-123), mock stand-in for m5 row-level security
    cat = data.Catalogue(ROOT)
    asha = cat.record_ids("asha")
    assert asha and all(
        cat.case(r).record["encounter_type"] == "asha_household_visit" for r in asha
    )
    assert "rec-fx-pharm-003-asr" not in asha and "rec-fx-phys-004" not in asha
    pharm = cat.record_ids("pharmacist")
    assert pharm and "rec-fx-asha-001" not in pharm
    assert set(cat.record_ids("physician")) == set(cat.record_ids())


def test_bidi_in_a_record_is_reported(tmp_path):
    rec = data.read_json(ROOT / "fixtures" / "record" / "valid" / "rec-fx-asha-001.json")
    rec["patient_ref"] = "pt\u202e-0001"
    assert data.bidi_problems(rec)
    assert (
        data.bidi_problems(
            data.read_json(ROOT / "fixtures" / "record" / "valid" / "rec-fx-asha-001.json")
        )
        == []
    )
