"""Test doubles. The real verifier (m4) is plugged in at integration time; m5 never imports it.

FakeVerifier flags by a marker in the first advice text so tests can make a record "clean" or
"flagged" just by editing it (and the verdict then depends ONLY on the stored record).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECORD_FX = REPO / "fixtures" / "record" / "valid" / "rec-fx-phys-004.json"


def fake_verifier(record: dict) -> dict:
    text = (record.get("advice") or [{}])[0].get("text", "")
    checks = [
        {
            "check_id": "C1",
            "name": "span-exists",
            "status": "pass",
            "reason": "ok",
            "field_path": "/",
        },
    ]
    if "FLAGME" in text:
        checks.append({"check_id": "C3", "name": "negation-consistency", "status": "flag",
                       "reason": "test flag", "field_path": "/advice/0/negated"})  # fmt: skip
    if "FLAGDOSE" in text:
        checks.append({"check_id": "C4", "name": "dose-range", "status": "flag",
                       "reason": "test flag", "field_path": "/medications/0/dose_value"})  # fmt: skip
    return {
        "schema_version": "verdict.v1",
        "record_id": record["record_id"],
        "checks": checks,
        "auto_acceptable": not any(c["status"] == "flag" for c in checks),
        "verifier_version": "fake-test",
    }


def empty_verifier(record: dict) -> dict:
    return {"schema_version": "verdict.v1", "record_id": record["record_id"], "checks": [],
            "auto_acceptable": False, "verifier_version": "fake-test"}  # fmt: skip


def base_record(marker: str = "") -> dict:
    rec = json.loads(RECORD_FX.read_text(encoding="utf-8"))
    if marker:
        rec["advice"][0]["text"] = rec["advice"][0]["text"] + " " + marker
    return rec
