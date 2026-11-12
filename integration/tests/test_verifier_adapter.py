"""The adapter m5 calls: record JSON in, verdict.v1 out. No database needed."""

from __future__ import annotations

import copy

import pytest

from contracts.validate import validate_doc
from integration import pipeline
from integration.verifier_adapter import find_transcript, verify_record

CLEAN_ID = "m1-e5-007"  # a DEV id whose m3 record passes every m4 check


@pytest.fixture(scope="module")
def clean_record():
    tr = pipeline.mock_asr(CLEAN_ID)
    return pipeline.extract_record(CLEAN_ID, tr)


def flagged(v):
    return {(c["check_id"], c["field_path"]) for c in v["checks"] if c["status"] == "flag"}


def test_clean_dev_record_is_auto_acceptable_and_valid_verdict(clean_record):
    v = verify_record(clean_record)
    assert validate_doc("verdict", v) == []
    assert v["record_id"] == clean_record["record_id"]
    assert flagged(v) == set() and v["auto_acceptable"] is True


def test_planted_negation_flip_is_flagged_at_the_field(clean_record):
    bad, path = pipeline.plant_negation_flip(clean_record)
    v = verify_record(bad)
    assert ("C3", path) in flagged(v)
    assert v["auto_acceptable"] is False


def test_m5_can_load_the_adapter_by_name():
    from m5_backend.app.verifier import load_verifier

    fn = load_verifier("integration.verifier_adapter:verify_record")
    assert fn is verify_record


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(schema_version="record.v2"),  # m4 has no v2 yet: fail closed
        lambda r: r.update(source_transcript_id="no-such-conversation"),
        lambda r: r.update(source_transcript_id="../../.env"),  # path characters refused
        lambda r: r.update(source_transcript_id=None),
    ],
)
def test_fail_closed_gives_one_valid_flag_never_a_pass(clean_record, mutate):
    rec = copy.deepcopy(clean_record)
    mutate(rec)
    v = verify_record(rec)
    assert validate_doc("verdict", v) == []
    assert v["auto_acceptable"] is False
    assert len(flagged(v)) == 1


def test_non_dict_input_fails_closed():
    for junk in (None, [], "x", 5):
        v = verify_record(junk)  # type: ignore[arg-type]
        assert validate_doc("verdict", v) == [] and v["auto_acceptable"] is False


def test_transcript_lookup_only_finds_dev_gold_by_exact_id():
    assert find_transcript(CLEAN_ID)["audio_id"] == CLEAN_ID
    assert find_transcript("m1-e5-0") is None
    assert find_transcript("a/b") is None


def test_edited_span_that_no_longer_matches_is_flagged(clean_record):
    rec = copy.deepcopy(clean_record)
    rec["medications"][0]["evidence"]["span_text"] += "x"
    rec["medications"][0]["evidence"]["char_end"] += 1
    v = verify_record(rec)
    assert v["auto_acceptable"] is False and flagged(v)


# ---- Phase C hook signature: fn(record, *, encounter_id, transcript) from the DATABASE encounter
def test_hook_uses_the_transcript_m5_passes(clean_record):
    tr = pipeline.mock_asr(CLEAN_ID)
    v = verify_record(
        copy.deepcopy(clean_record),
        encounter_id="00000000-0000-0000-0000-000000000001",
        transcript=tr,
    )
    assert validate_doc("verdict", v) == []
    assert flagged(v) == set() and v["auto_acceptable"] is True


def test_hook_forged_source_transcript_id_is_not_followed_and_is_flagged(clean_record):
    tr = pipeline.mock_asr(CLEAN_ID)
    rec = copy.deepcopy(clean_record)
    rec["source_transcript_id"] = "no-such-conversation"  # editable field: ignored for the lookup
    v = verify_record(rec, encounter_id="e", transcript=tr)
    assert validate_doc("verdict", v) == [] and v["auto_acceptable"] is False
    assert ("C1", "/source_transcript_id") in flagged(v)  # m4 itself notices the mismatch


def test_hook_without_transcript_fails_closed_even_if_source_id_resolves(clean_record):
    # hook mode (encounter_id given) + no transcript: no fallback to the record's own field
    v = verify_record(copy.deepcopy(clean_record), encounter_id="e", transcript=None)
    assert v["auto_acceptable"] is False and len(flagged(v)) == 1


def test_call_verifier_passes_kwargs_to_adapter(clean_record):
    from m5_backend.app.verifier import call_verifier

    tr = pipeline.mock_asr(CLEAN_ID)
    v = call_verifier(verify_record, copy.deepcopy(clean_record), "enc-1", tr)
    assert v["auto_acceptable"] is True
    v = call_verifier(verify_record, copy.deepcopy(clean_record), "enc-1", None)  # no transcript
    assert v["auto_acceptable"] is False and len(flagged(v)) == 1
