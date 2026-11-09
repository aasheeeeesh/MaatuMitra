"""Generator: determinism, contract validity, tags, negation self-check, coverage, twins."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from contracts.validate import conversation_text, validate_doc
from m1_data import kn, negation
from m1_data.coverage import compute_coverage

from .conftest import DATA, ROOT, read_jsonl


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _generated_files(base: Path) -> list[Path]:
    out = []
    for sub in ("gold", "transcripts", "twins", "splits"):
        out += [
            p for p in (base / "data" / sub).rglob("*") if p.is_file() and p.name != "README.md"
        ]
    out.append(base / "data" / "manifest.jsonl")
    return sorted(out)


def test_regeneration_is_byte_identical_to_committed(regenerated):
    committed = {p.relative_to(ROOT).as_posix(): _sha(p) for p in _generated_files(ROOT)}
    fresh = {p.relative_to(regenerated).as_posix(): _sha(p) for p in _generated_files(regenerated)}
    assert fresh.keys() == committed.keys()
    diff = [k for k in committed if committed[k] != fresh[k]]
    assert not diff, f"{len(diff)} files differ, e.g. {diff[:3]}"


def test_every_gold_and_transcript_validates(gold_docs):
    for cid, doc in gold_docs.items():
        assert validate_doc("gold", doc) == [], cid
        tr = json.loads((DATA / "transcripts" / "gold" / f"{cid}__gold.json").read_text("utf-8"))
        assert validate_doc("transcript", tr) == [], cid
        assert tr["text"] == conversation_text(doc["turns"])
        assert tr["model"]["name"] == "gold" and tr["source"] == "template_text"
        assert 2 <= len(doc["turns"]) <= 6


def test_tags_match_the_text(gold_docs):
    table = negation.load_table()
    for cid, doc in gold_docs.items():
        turns = [t["text"] for t in doc["turns"]]
        text = "\n".join(turns)
        assert doc["tags"]["code_switched"] == kn.has_latin(text), cid
        assert doc["tags"]["trap_tokens"] == negation.trap_tokens_in(text), cid
        detected = table.detect_conversation(turns)
        assert doc["tags"]["has_negation"] == bool(detected - negation.NON_CUE_IDS), cid
        assert doc["tags"]["cross_turn_negation"] == ("NEG-X01" in detected), cid


def test_coverage_requirements(gold_docs):
    cov = compute_coverage(DATA)
    t = cov["totals"]
    assert t["conversations"] >= 200
    assert t["with_negation"] >= 60
    assert t["with_trap_tokens"] >= 20
    assert t["code_switched_fraction"] >= 0.25
    assert t["cross_turn_negation"] >= 15
    for pid, n in cov["negation_patterns_detected"].items():
        assert n >= 5, f"{pid} appears in only {n} conversations"
    for pid, n in cov["negation_patterns_declared"].items():
        assert n >= 5, f"{pid} is used on purpose in only {n} conversations"


def test_every_negated_sentence_has_a_twin(gold_docs):
    twins = read_jsonl(DATA / "twins" / "twins_dev.jsonl") + read_jsonl(
        DATA / "twins" / "twins_test.jsonl"
    )
    assert twins
    table = negation.load_table()
    by_conv = {}
    for tw in twins:
        by_conv.setdefault(tw["conversation_id"], []).append(tw)
        doc = gold_docs[tw["conversation_id"]]
        assert doc["turns"][tw["turn_index"]]["text"] == tw["negated_text"]
        assert tw["twin_text"] != tw["negated_text"]
        assert tw["native_validated"] is False
        # the twin removes the cue: its own primary pattern no longer fires there
        assert tw["primary_pattern"] in table.detect_turn(tw["negated_text"]) or tw["cross_turn"]
        for it in tw["items"]:
            prev = it["span_in"] == "previous_turn"  # cross-turn: entity is in the question
            base = tw["previous_turn_text"] if prev else tw["negated_text"]
            tbase = tw["previous_turn_text"] if prev else tw["twin_text"]
            s, e = it["negated_span"]
            assert base[s:e] == it["negated_span_text"]
            s, e = it["twin_span"]
            assert tbase[s:e] == it["twin_span_text"]
    for cid, doc in gold_docs.items():
        negated_items = [
            i
            for g in ("symptoms", "medications", "advice")
            for i in doc["gold_record"][g]
            if i.get("negated") is True or i.get("present") is False
        ]
        if negated_items:
            assert cid in by_conv, f"{cid} has negated items but no twin"
