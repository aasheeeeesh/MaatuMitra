"""The verifier on the contract fixtures, and the CLI."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from contracts.validate import validate_doc
from m4_verify.config import default_config
from m4_verify.lexicon import load_lexicon
from m4_verify.tests.helpers import FIX, ROOT, flags
from m4_verify.verifier import verify

LEX = load_lexicon(FIX / "lexicon" / "drugs_fixture.csv")
TDIR = FIX / "transcript" / "valid"
RDIR = FIX / "record" / "valid"

# record fixture -> transcript fixture it was built from
PAIRS = {
    "rec-fx-asha-001": "fx-asha-001__gold",
    "rec-fx-asha-002": "fx-asha-002__gold",
    "rec-fx-pharm-003": "fx-pharm-003__gold",
    "rec-fx-phys-004": "fx-phys-004__gold",
    "rec-fx-nurse-005": "fx-nurse-005__gold",
    "rec-fx-trap-006": "fx-trap-006__gold",
    "rec-fx-pharm-003-asr": "fx-pharm-003__asr_digit_error",
}


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize("rid", sorted(PAIRS))
def test_fixture_verdicts_validate(rid):
    v = verify(
        _load(RDIR / f"{rid}.json"),
        _load(TDIR / f"{PAIRS[rid]}.json"),
        lexicon=LEX,
        config=default_config(),
    )
    assert validate_doc("verdict", v) == []
    assert v["record_id"] == rid


@pytest.mark.parametrize("rid", [r for r in sorted(PAIRS) if not r.endswith("-asr")])
def test_clean_gold_fixture_records_are_auto_acceptable(rid):
    v = verify(
        _load(RDIR / f"{rid}.json"),
        _load(TDIR / f"{PAIRS[rid]}.json"),
        lexicon=LEX,
        config=default_config(),
    )
    assert flags(v) == [], flags(v)
    assert v["auto_acceptable"] is True


def test_asr_digit_error_fixture_is_flagged_by_c4_and_c7():
    rid = "rec-fx-pharm-003-asr"
    v = verify(
        _load(RDIR / f"{rid}.json"),
        _load(TDIR / f"{PAIRS[rid]}.json"),
        lexicon=LEX,
        config=default_config(),
    )
    assert v["auto_acceptable"] is False
    assert flags(v, "C4") and flags(v, "C7")


def test_asr_digit_error_caught_by_second_transcript():
    rid = "rec-fx-pharm-003-asr"
    v = verify(
        _load(RDIR / f"{rid}.json"),
        _load(TDIR / f"{PAIRS[rid]}.json"),
        lexicon=LEX,
        config=default_config(),
        second_transcript=_load(TDIR / "fx-pharm-003__gold.json"),
    )
    assert any("second transcript" in c["reason"] for c in flags(v, "C7"))


def _cli(*args, env_extra=None):
    import os

    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-m", "m4_verify", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def test_cli_verify_prints_valid_verdict(tmp_path):
    out = tmp_path / "v.json"
    r = _cli(
        "verify",
        "--record", str(RDIR / "rec-fx-pharm-003-asr.json"),
        "--transcript", str(TDIR / "fx-pharm-003__asr_digit_error.json"),
        "--second-transcript", str(TDIR / "fx-pharm-003__gold.json"),
        "--disable", "C3",
        "--out", str(out),
    )  # fmt: skip
    assert r.returncode == 0, r.stderr
    v = json.loads(out.read_text(encoding="utf-8"))
    assert validate_doc("verdict", v) == []
    c3 = [c for c in v["checks"] if c["check_id"] == "C3"]
    assert c3[0]["status"] == "n/a" and "disabled" in c3[0]["reason"]
    assert v["auto_acceptable"] is False


def test_cli_rejects_unknown_check_id():
    r = _cli(
        "verify",
        "--record", str(RDIR / "rec-fx-asha-001.json"),
        "--transcript", str(TDIR / "fx-asha-001__gold.json"),
        "--disable", "C9",
    )  # fmt: skip
    assert r.returncode == 2


def test_cli_mock_mode(tmp_path):
    r = _cli("mock", "--out-dir", str(tmp_path), env_extra={"MODE": "mock"})
    assert r.returncode == 0, r.stderr
    verdicts = sorted((tmp_path / "verdicts").glob("*.json"))
    assert len(verdicts) == len(PAIRS)
    for p in verdicts:
        assert validate_doc("verdict", _load(p)) == []
