"""E4 planted-mistake generator: determinism, counts, log format, and the DONE-WHEN catch rates."""

from __future__ import annotations

import hashlib
import json

import pytest

from contracts.validate import validate_doc
from m4_verify.config import default_config
from m4_verify.lexicon import load_lexicon
from m4_verify.planted import (
    TYPES,
    generate_record_level,
    generate_transcript_level,
    gold_to_pair,
    load_gold_dir,
    refuse_test_split,
)
from m4_verify.tests.helpers import FIX
from m4_verify.verifier import verify

LEX = load_lexicon(FIX / "lexicon" / "drugs_fixture.csv")
GOLDS = load_gold_dir(FIX / "gold" / "valid")
N = 200


def _hash(injs):
    log = [
        {k: i[k] for k in ("id", "type", "level", "source_id", "field_path", "before", "after")}
        for i in injs
    ]
    return hashlib.sha256(json.dumps(log, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@pytest.fixture(scope="module")
def rec_level():
    return generate_record_level(GOLDS, LEX, n_per_type=N, seed=20261109)


@pytest.fixture(scope="module")
def tr_level():
    return generate_transcript_level(GOLDS, LEX, n_per_type=N, seed=20261109)


def test_types_are_a_to_i():
    assert list(TYPES) == list("abcdefghi")


@pytest.mark.parametrize("gold", GOLDS, ids=lambda g: g["conversation_id"])
def test_gold_to_pair_is_valid_and_clean(gold):
    tr, rec = gold_to_pair(gold)
    assert validate_doc("transcript", tr) == []
    assert validate_doc("record", rec) == []
    v = verify(
        rec,
        tr,
        lexicon=LEX,
        config=default_config(),
        encounter_index={tr["audio_id"]: rec["patient_ref"]},
    )
    assert v["auto_acceptable"] is True, [c for c in v["checks"] if c["status"] == "flag"]


def test_record_level_deterministic_and_counts(rec_level):
    again = generate_record_level(GOLDS, LEX, n_per_type=N, seed=20261109)
    assert _hash(rec_level) == _hash(again)
    for t in TYPES:
        assert sum(1 for i in rec_level if i["type"] == t) >= N, t
    for i in rec_level[:50]:
        assert set(i) >= {"id", "type", "level", "source_id", "field_path", "before", "after"}
        assert i["before"] != i["after"]
        assert i["level"] == "record"
        assert validate_doc("record", i["record"]) == []


def test_transcript_level_counts_and_validity(tr_level):
    for t in TYPES:
        if t == "i":
            continue  # a wrong patient link is not an ASR (transcript) error
        assert sum(1 for i in tr_level if i["type"] == t) >= N, t
    for i in tr_level[:50]:
        assert validate_doc("transcript", i["transcript"]) == []
        assert validate_doc("record", i["record"]) == []


def _caught(inj, second=False, index=True):
    tr = inj["transcript"]
    rec = inj["record"]
    v = verify(
        rec,
        tr,
        lexicon=LEX,
        config=default_config(),
        second_transcript=inj["clean_transcript"] if second else None,
        encounter_index={tr["audio_id"]: inj["true_patient_ref"]} if index else None,
    )
    assert validate_doc("verdict", v) == []
    return not v["auto_acceptable"]


@pytest.mark.parametrize("t", list("abcdefghi"))
def test_record_level_every_planted_mistake_is_flagged(rec_level, t):
    """DONE WHEN: 100% of record-level negation drops (a) and number swaps (c, d) are flagged.
    We hold every type to 100% on the fixtures (i needs the encounter index)."""
    items = [i for i in rec_level if i["type"] == t]
    missed = [i["id"] for i in items if not _caught(i)]
    assert missed == [], (t, missed[:5])


def test_wrong_patient_is_invisible_without_encounter_index(rec_level):
    items = [i for i in rec_level if i["type"] == "i"][:20]
    assert not any(_caught(i, index=False) for i in items)


def test_transcript_level_negation_drop_needs_second_transcript(tr_level):
    items = [i for i in tr_level if i["type"] == "a"][:40]
    assert all(_caught(i, second=True) for i in items)


def test_refuse_test_split_paths(tmp_path):
    with pytest.raises(ValueError):
        refuse_test_split(tmp_path / "data" / "splits" / "test")
    with pytest.raises(ValueError):
        refuse_test_split(tmp_path / "gold_test.jsonl")
    refuse_test_split(FIX / "gold" / "valid")  # fixtures are fine
