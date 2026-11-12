"""A tiny stand-in for a real verifier module, loaded by import path in test_followups.py.

Integration (Phase C) points MAATUMITRA_VERIFIER at the real one instead, e.g. `pkg.mod:fn`.
"""

NOT_CALLABLE = 42


def always_flag_c4(record: dict) -> dict:
    return {
        "schema_version": "verdict.v1",
        "record_id": record["record_id"],
        "checks": [
            {
                "check_id": "C4",
                "name": "dose-range",
                "status": "flag",
                "reason": "fake module",
                "field_path": "/medications/0/dose_value",
            }
        ],
        "auto_acceptable": False,
        "verifier_version": "fake-module-v1",
    }
