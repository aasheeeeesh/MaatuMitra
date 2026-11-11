"""Contract tests (written before contracts/validate.py).

Proves: every schema is a valid draft 2020-12 schema; every valid fixture passes;
every invalid fixture fails; record evidence offsets match the paired transcript
fixture; gold spans match the conversation text; the CLI works on .json, .jsonl
and directories.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from contracts import validate as V

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
CONTRACTS = [
    "transcript",
    "record",
    "verdict",
    "gold",
    "manifest",
    "access_case",
    "card",
    "review_report",
]


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_all_eight_schemas_exist_and_are_valid_2020_12():
    names = V.list_schemas()
    # All eight v1 contracts stay. Later versions are additive (record.v2 / gold.v2, Phase C):
    # each extra schema must be a numbered version of one of the eight contracts.
    assert {f"{c}.v1" for c in CONTRACTS} <= set(names)
    for n in names:
        base, _, ver = n.rpartition(".v")
        assert base in CONTRACTS and ver.isdigit() and int(ver) >= 1, n
    for n in names:
        schema = V.load_schema(n)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(schema)
        assert schema["properties"]["schema_version"] == {"const": n}


@pytest.mark.parametrize("contract", CONTRACTS)
def test_fixture_counts(contract):
    valid = sorted((FIX / contract / "valid").glob("*.json"))
    invalid = sorted((FIX / contract / "invalid").glob("*.json"))
    assert len(valid) >= 5, f"{contract}: need >= 5 valid fixtures"
    assert len(invalid) >= 3, f"{contract}: need >= 3 invalid fixtures"


@pytest.mark.parametrize("contract", CONTRACTS)
def test_valid_fixtures_pass(contract):
    for p in sorted((FIX / contract / "valid").glob("*.json")):
        errs = V.validate_doc(contract, _load(p))
        assert errs == [], f"{p.name}: {errs}"


@pytest.mark.parametrize("contract", CONTRACTS)
def test_invalid_fixtures_fail(contract):
    for p in sorted((FIX / contract / "invalid").glob("*.json")):
        errs = V.validate_doc(contract, _load(p))
        assert errs, f"{p.name} should be rejected but passed"


@pytest.mark.parametrize("contract", CONTRACTS)
def test_every_invalid_fixture_is_documented(contract):
    readme = (FIX / contract / "invalid" / "README.md").read_text(encoding="utf-8")
    for p in (FIX / contract / "invalid").glob("*.json"):
        assert p.name in readme, f"{p.name} not explained in invalid/README.md"


def test_record_evidence_matches_paired_transcript():
    transcripts = {
        _load(p)["audio_id"]: _load(p) for p in (FIX / "transcript" / "valid").glob("*.json")
    }
    checked = 0
    for p in sorted((FIX / "record" / "valid").glob("*.json")):
        rec = _load(p)
        tr = transcripts.get(rec["source_transcript_id"])
        assert tr is not None, f"{p.name}: no transcript fixture {rec['source_transcript_id']}"
        text = tr["text"]
        items = rec["symptoms"] + rec["medications"] + rec["advice"]
        if rec["follow_up"] is not None:
            items.append(rec["follow_up"])
        for item in items:
            ev = item["evidence"]
            got = unicodedata.normalize("NFC", text[ev["char_start"] : ev["char_end"]])
            assert got == unicodedata.normalize("NFC", ev["span_text"]), (p.name, ev)
            checked += 1
    assert checked >= 10


def test_gold_transcript_text_equals_joined_gold_turns():
    gold = {_load(p)["conversation_id"]: _load(p) for p in (FIX / "gold" / "valid").glob("*.json")}
    paired = 0
    for p in (FIX / "transcript" / "valid").glob("*.json"):
        tr = _load(p)
        if tr["model"]["name"] == "gold" and tr["audio_id"] in gold:
            assert tr["text"] == V.conversation_text(gold[tr["audio_id"]]["turns"])
            paired += 1
    assert paired >= 1


# ---- semantic rules beyond JSON Schema --------------------------------------


def _first_valid(contract):
    return _load(sorted((FIX / contract / "valid").glob("*.json"))[0])


def test_rejects_non_nfc_kannada():
    rec = _first_valid("record")
    decomposed = "ಕೀ"  # KA + I sign + length mark; NFC composes to KA + II sign
    assert unicodedata.normalize("NFC", decomposed) != decomposed
    rec["patient_ref"] = decomposed
    assert any("NFC" in e for e in V.validate_doc("record", rec))


def test_rejects_zero_width_space_and_bom():
    rec = _first_valid("record")
    rec["patient_ref"] = "p​1"
    assert V.validate_doc("record", rec)
    rec["patient_ref"] = "﻿p1"
    assert V.validate_doc("record", rec)


def test_evidence_end_must_exceed_start():
    rec = _first_valid("record")
    ev = rec["medications"][0]["evidence"] if rec["medications"] else rec["symptoms"][0]["evidence"]
    ev["char_end"] = ev["char_start"]
    assert V.validate_doc("record", rec)


def test_verdict_flag_forces_auto_acceptable_false():
    v = _first_valid("verdict")
    v["checks"][0]["status"] = "flag"
    v["auto_acceptable"] = True
    assert any("auto_acceptable" in e for e in V.validate_doc("verdict", v))


def test_verdict_empty_checks_cannot_be_auto_acceptable():
    v = _first_valid("verdict")
    v["checks"] = []
    v["auto_acceptable"] = True
    assert V.validate_doc("verdict", v)


def test_transcript_word_offsets_checked():
    tr = _first_valid("transcript")
    tr["words"][0]["char_start"] += 1
    assert V.validate_doc("transcript", tr)


def test_bad_timestamp_rejected():
    tr = _first_valid("transcript")
    tr["created_at"] = "2026-13-45T25:00:00Z"
    assert V.validate_doc("transcript", tr)


def test_schema_name_aliases():
    tr = _first_valid("transcript")
    assert V.validate_doc("transcript.v1", tr) == []
    with pytest.raises(KeyError):
        V.validate_doc("nonexistent", tr)


# ---- CLI --------------------------------------------------------------------


def _cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "contracts.validate", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_accepts_valid_dir_and_rejects_invalid_dir():
    ok = _cli("transcript", str(FIX / "transcript" / "valid"))
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = _cli("transcript", str(FIX / "transcript" / "invalid"))
    assert bad.returncode == 1


def test_cli_handles_jsonl(tmp_path):
    rows = [_load(p) for p in sorted((FIX / "manifest" / "valid").glob("*.json"))]
    f = tmp_path / "m.jsonl"
    f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", "utf-8")
    assert _cli("manifest", str(f)).returncode == 0
    rows[1]["split"] = "train"
    f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", "utf-8")
    res = _cli("manifest", str(f))
    assert res.returncode == 1
    assert ":2" in res.stdout  # reports the failing line number


def test_cli_check_fixtures_mode():
    res = _cli("--check-fixtures", str(FIX))
    assert res.returncode == 0, res.stdout + res.stderr
