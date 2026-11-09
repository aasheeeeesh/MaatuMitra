"""Research export pure functions (no database): pseudonym, month coarsening, structured-only."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from m5_backend.app.export import deidentify_record, month_of, pseudonym

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "record" / "valid"


def test_pseudonym_is_keyed_truncated_hmac():
    pid = uuid.uuid4()
    a = pseudonym(b"k" * 32, pid)
    assert a == pseudonym(b"k" * 32, pid)
    assert a != pseudonym(b"j" * 32, pid)
    assert len(a) == 20 and all(c in "0123456789abcdef" for c in a)
    assert a not in hashlib.sha256(str(pid).encode()).hexdigest()
    assert str(pid).replace("-", "")[:8] not in a


def test_month_coarsening():
    assert month_of(datetime(2026, 10, 17, 10, 15, tzinfo=UTC)) == "2026-10"


def test_deidentify_keeps_only_structured_allowlisted_fields():
    for f in sorted(FIX.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        out = deidentify_record(rec)
        blob = json.dumps(out, ensure_ascii=False)
        assert set(out) == {"symptoms_present", "symptoms_absent", "medications"}
        for item in rec.get("advice", []):
            assert item["text"] not in blob
        for group in ("symptoms", "medications", "advice"):
            for item in rec.get(group, []):
                assert item["evidence"]["span_text"] not in blob
        assert rec["record_id"] not in blob and rec["patient_ref"] not in blob


def test_deidentify_drops_non_vocab_strings():
    rec = {
        "symptoms": [{"name": "SYNTHETIC-Kaveri said she felt odd", "present": True}],
        "medications": [
            {
                "drug": "secret-free-text",
                "dose_value": 1,
                "dose_unit": "mg",
                "frequency_per_day": 1,
                "duration_days": 1,
                "negated": False,
            },
            {
                "drug": "paracetamol",
                "dose_value": 500,
                "dose_unit": "mg'; --",
                "frequency_per_day": 3,
                "duration_days": 3,
                "negated": False,
            },
        ],
    }
    out = deidentify_record(rec)
    assert out["symptoms_present"] == []
    assert out["medications"] == [
        {
            "drug": "paracetamol",
            "dose_value": 500,
            "dose_unit": None,
            "frequency_per_day": 3,
            "duration_days": 3,
            "negated": False,
        }
    ]
