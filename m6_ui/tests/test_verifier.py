"""Edits re-run the verifier (mock stand-in; live = subprocess, fail-closed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from contracts.validate import validate_doc
from m6_ui import review, verifier
from m6_ui.tests.helpers import fixture_triplet


def _flags(v, path=None):
    return [
        c
        for c in v["checks"]
        if c["status"] == "flag" and (path is None or c["field_path"] == path)
    ]


def test_mock_rerun_clears_flags_on_edited_field_but_flags_unsupported_value():
    rec, ver, tr = fixture_triplet("rec-fx-pharm-003-asr")
    edited = review.set_pointer(rec, "/medications/0/dose_value", 500)
    v2 = verifier.MockVerifier().verify(edited, tr, ver, {"/medications/0/dose_value"})
    assert validate_doc("verdict.v1", v2) == []
    flags = _flags(v2)
    assert {c["check_id"] for c in flags} == {"C2"}
    assert "500" in flags[0]["reason"]
    assert v2["auto_acceptable"] is False


def test_mock_rerun_accepts_value_heard_in_span():
    rec, ver, tr = fixture_triplet("rec-fx-pharm-003-asr")
    # frequency 3 is spoken as a Kannada number word in the evidence span
    edited = review.set_pointer(rec, "/medications/0/frequency_per_day", 3)
    v2 = verifier.MockVerifier().verify(edited, tr, ver, {"/medications/0/frequency_per_day"})
    added = [c for c in v2["checks"] if c["field_path"] == "/medications/0/frequency_per_day"]
    assert added and all(c["status"] == "pass" for c in added)
    # untouched flags stay
    assert any(c["check_id"] == "C4" for c in _flags(v2))


def test_mock_rerun_compares_kannada_digits_as_ascii():
    rec, ver, tr = fixture_triplet("rec-fx-trap-006")
    edited = review.set_pointer(rec, "/medications/0/dose_value", 500)
    v2 = verifier.MockVerifier().verify(edited, tr, ver, {"/medications/0/dose_value"})
    assert _flags(v2) == []


def test_negation_edit_always_needs_confirmation():
    rec, ver, tr = fixture_triplet("rec-fx-nurse-005")
    edited = review.set_pointer(rec, "/symptoms/1/present", True)
    v2 = verifier.MockVerifier().verify(edited, tr, ver, {"/symptoms/1/present"})
    assert _flags(v2, "/symptoms/1/present")


def test_missing_verdict_or_transcript_fails_closed():
    rec, _, _ = fixture_triplet("rec-fx-asha-001")
    v2 = verifier.MockVerifier().verify(rec, None, None, set())
    assert validate_doc("verdict.v1", v2) == []
    assert v2["auto_acceptable"] is False and _flags(v2)


def test_subprocess_verifier_success(tmp_path: Path):
    rec, ver, tr = fixture_triplet("rec-fx-asha-001")
    payload = tmp_path / "verdict_src.json"
    payload.write_text(json.dumps(ver), encoding="utf-8")
    script = tmp_path / "fake_m4.py"
    script.write_text(
        "import sys, pathlib\n"
        "a = sys.argv\n"
        f"src = pathlib.Path({str(payload)!r}).read_text(encoding='utf-8')\n"
        "pathlib.Path(a[a.index('--out') + 1]).write_text(src, encoding='utf-8')\n",
        encoding="utf-8",
    )
    sv = verifier.SubprocessVerifier(cmd_prefix=[sys.executable, str(script)], timeout_s=60)
    assert sv.verify(rec, tr, ver, set()) == ver


def test_subprocess_verifier_failure_is_fail_closed():
    rec, ver, tr = fixture_triplet("rec-fx-asha-001")
    sv = verifier.SubprocessVerifier(
        cmd_prefix=[sys.executable, "-c", "import sys; sys.exit(3)"], timeout_s=60
    )
    out = sv.verify(rec, tr, ver, set())
    assert validate_doc("verdict.v1", out) == []
    flags = _flags(out)
    assert flags and flags[0]["reason"].startswith("check_error")
    assert out["auto_acceptable"] is False


def test_default_live_command_uses_m4_cli_not_import():
    sv = verifier.SubprocessVerifier()
    assert sv.cmd_prefix[-3:] == ["-m", "m4_verify", "verify"]
    src = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "import m4_verify" not in src and "from m4_verify" not in src
