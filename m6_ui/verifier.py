"""Re-run the verifier after a reviewer edit.

- MockVerifier (MODE=mock): a SMALL STAND-IN, not the real m4 logic. It starts from the
  fixture verdict, clears the original flags on the exact paths the reviewer edited, then
  re-checks each edited value against its evidence span (numbers incl. Kannada digits and a
  starter list of number words; units; text) and re-checks every span against the
  transcript (C1). Negation edits are ALWAYS flagged for confirmation (it cannot check them).
- SubprocessVerifier (MODE=live): runs `uv run python -m m4_verify verify --record ...
  --transcript ... --out ...` in a subprocess. No Python import of m4. Any failure (exit code,
  timeout, invalid output) gives a fail-closed verdict with a 'check_error' flag.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import regex

from contracts.validate import validate_doc
from m6_ui import review

ROOT = Path(__file__).resolve().parents[1]
MOCK_VERSION = "m6-mock-verifier-standin-1"
TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
KN_DIGITS = {0x0CE6 + i: str(i) for i in range(10)}
NUMERIC = {"dose_value": "C2", "frequency_per_day": "C5", "duration_days": "C5"}
BOOLEAN = {"present", "negated"}
MIN_NAME_LEN = 3  # shortest accepted edited drug name (letters)


@lru_cache(maxsize=1)
def _number_words() -> dict[str, float]:
    doc = json.loads((Path(__file__).with_name("number_words.json")).read_text(encoding="utf-8"))
    return {k: float(v) for k, v in doc["words"].items()}


def _comparison_tokens(span: str) -> list[str]:
    """Comparison copy (kannada-nlp skill): drop ZWJ/ZWNJ, Kannada digits -> ASCII, casefold."""
    s = span.replace(chr(0x200C), "").replace(chr(0x200D), "").translate(KN_DIGITS).casefold()
    return [m.group() for m in TOKEN.finditer(s)]


def _numbers_in(span: str) -> set[float]:
    words = _number_words()
    out: set[float] = set()
    for tok in _comparison_tokens(span):
        if tok.isascii() and tok.isdigit():
            out.add(float(tok))
        elif tok in words:
            out.add(words[tok])
    return out


def _fmt(v) -> str:
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


def _item_path(path: str) -> str:
    return "/follow_up" if path.startswith("/follow_up") else path.rsplit("/", 1)[0]


def _check(cid: str, status: str, reason: str, path: str) -> dict:
    return {
        "check_id": cid,
        "name": "mock-rerun",
        "status": status,
        "reason": reason,
        "field_path": path,
    }


def _finish(record_id: str, checks: list[dict], version: str) -> dict:
    flags = any(c["status"] == "flag" for c in checks)
    passes = any(c["status"] == "pass" for c in checks)
    return {
        "schema_version": "verdict.v1",
        "record_id": record_id,
        "checks": checks,
        "auto_acceptable": bool(checks) and passes and not flags,
        "verifier_version": version,
    }


def fail_closed(record: dict, base_verdict: dict | None, why: str, version: str) -> dict:
    checks = copy.deepcopy((base_verdict or {}).get("checks", []))
    checks.append(_check("C1", "flag", f"check_error: {why} (fail-closed)", "/"))
    return _finish(record["record_id"], checks, version)


class MockVerifier:
    version = MOCK_VERSION

    def verify(
        self,
        record: dict,
        transcript: dict | None,
        base_verdict: dict | None,
        edited_paths: set[str],
    ) -> dict:
        if transcript is None or base_verdict is None:
            return fail_closed(
                record,
                base_verdict,
                "mock verifier has no transcript or fixture verdict",
                self.version,
            )
        checks = []
        for c in copy.deepcopy(base_verdict.get("checks", [])):
            if c["status"] == "flag" and c["field_path"] in edited_paths:
                c["status"] = "pass"
                c["reason"] = (
                    "mock re-run: reviewer edited this value; original flag cleared by the m6 stand-in (not m4 logic)"
                )
            checks.append(c)
        for path in sorted(edited_paths):
            checks.append(self._recheck(record, path))
        text = transcript.get("text", "")
        for ev in _evidence(record):
            if text[ev["char_start"] : ev["char_end"]] != ev["span_text"]:
                checks.append(
                    _check("C1", "flag", "mock re-run: evidence span not found at its offsets", "/")
                )
        return _finish(record["record_id"], checks, self.version)

    def _recheck(self, record: dict, path: str) -> dict:
        attr = path.rsplit("/", 1)[-1]
        value = review.get_pointer(record, path)
        try:
            span = review.get_pointer(record, _item_path(path))["evidence"]["span_text"]
        except (KeyError, IndexError, TypeError):
            return _check("C1", "flag", "mock re-run: no evidence span for the edited item", path)
        if attr in BOOLEAN:
            return _check(
                "C3",
                "flag",
                "mock re-run: yes/no meaning changed by the reviewer; the stand-in cannot check negation, please confirm",
                path,
            )
        if attr in NUMERIC:
            cid = NUMERIC[attr]
            if value is None:
                return _check(
                    cid, "flag", "mock re-run: value removed by the reviewer; please confirm", path
                )
            if float(value) in _numbers_in(span):
                return _check(
                    cid,
                    "pass",
                    f"mock re-run: edited value {_fmt(value)} is heard in the evidence span",
                    path,
                )
            return _check(
                cid,
                "flag",
                f"mock re-run: edited value {_fmt(value)} is not heard in the evidence span; listen and confirm",
                path,
            )
        # F7 (D-123): whole-token match and a minimum length. A letter or a word fragment of the
        # evidence is not a drug name. (A lexicon check is the real m4's job.)
        needle_toks = _comparison_tokens("" if value is None else str(value))
        span_toks = _comparison_tokens(span)
        if attr == "drug" and sum(len(t) for t in needle_toks) < MIN_NAME_LEN:
            needle_toks = []
        n = len(needle_toks)
        if n and any(span_toks[i : i + n] == needle_toks for i in range(len(span_toks) - n + 1)):
            return _check(
                "C2", "pass", f"mock re-run: edited text '{value}' is in the evidence span", path
            )
        return _check(
            "C2",
            "flag",
            f"mock re-run: edited text '{value}' is not in the evidence span; listen and confirm",
            path,
        )


def _evidence(record: dict):
    for key in ("symptoms", "medications", "advice"):
        for item in record.get(key, []):
            yield item["evidence"]
    if record.get("follow_up"):
        yield record["follow_up"]["evidence"]


class SubprocessVerifier:
    version = "m4_verify-subprocess"

    def __init__(self, cmd_prefix: list[str] | None = None, timeout_s: float = 120.0):
        uv = shutil.which("uv") or "uv"
        self.cmd_prefix = cmd_prefix or [uv, "run", "python", "-m", "m4_verify", "verify"]
        self.timeout_s = timeout_s

    def verify(
        self,
        record: dict,
        transcript: dict | None,
        base_verdict: dict | None,
        edited_paths: set[str],
    ) -> dict:
        if transcript is None:
            return fail_closed(
                record, base_verdict, "no transcript for the live verifier", self.version
            )
        with tempfile.TemporaryDirectory(prefix="m6_verify_") as d:
            rp, tp, op = Path(d, "record.json"), Path(d, "transcript.json"), Path(d, "verdict.json")
            rp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            tp.write_text(json.dumps(transcript, ensure_ascii=False), encoding="utf-8")
            cmd = [*self.cmd_prefix, "--record", str(rp), "--transcript", str(tp), "--out", str(op)]
            try:
                proc = subprocess.run(  # noqa: S603 - fixed argv list, no shell
                    cmd, cwd=ROOT, capture_output=True, timeout=self.timeout_s, check=False
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                return fail_closed(
                    record, base_verdict, f"verifier subprocess {type(e).__name__}", self.version
                )
            if proc.returncode != 0 or not op.exists():
                return fail_closed(
                    record,
                    base_verdict,
                    f"verifier subprocess exit {proc.returncode}",
                    self.version,
                )
            try:
                out = json.loads(op.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return fail_closed(
                    record, base_verdict, "verifier output is not JSON", self.version
                )
        if validate_doc("verdict.v1", out) or out.get("record_id") != record["record_id"]:
            return fail_closed(
                record,
                base_verdict,
                "verifier output is not a valid verdict for this record",
                self.version,
            )
        return out


def make_verifier():
    import os

    return SubprocessVerifier() if os.environ.get("MODE", "mock") == "live" else MockVerifier()
