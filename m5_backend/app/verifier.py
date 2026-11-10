"""Server-side verifier hook (F1 / D-80).

The API never accepts verdict content from a client. When a record is verified, the SERVER loads
the stored record and calls a verifier function `record_json -> verdict.v1 dict`, validates the
result against verdict.v1 and stores it (clinic.verdicts, append-only).

m5 does NOT import the m4 verifier (module rule). At integration time the orchestrator passes
the real one: `create_app(..., verifier=my_m4_adapter)`. Until then the default below is used.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Verifier = Callable[[dict[str, Any]], dict[str, Any]]


def manual_review_verifier(record: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed default: flags the whole record, so a physician must explicitly confirm it.

    This is NOT a safety check; it only makes the save flow usable when no real verifier is wired
    in. It never returns a clean verdict.
    """
    return {
        "schema_version": "verdict.v1",
        "record_id": record["record_id"],
        "checks": [
            {
                "check_id": "C6",
                "name": "unsupported-addition",
                "status": "flag",
                "reason": "no automatic verifier is configured; the physician must review the whole record",
                "field_path": "/",
            }
        ],
        "auto_acceptable": False,
        "verifier_version": "m5-manual-review-v1",
    }
