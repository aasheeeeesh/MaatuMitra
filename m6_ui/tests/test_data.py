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
