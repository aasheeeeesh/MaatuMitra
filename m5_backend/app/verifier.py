"""Server-side verifier hook (F1 / D-80).

The API never accepts verdict content from a client. When a record is verified, the SERVER loads
the stored record and calls a verifier function `record_json -> verdict.v1 dict`, validates the
result against verdict.v1 and stores it (clinic.verdicts, append-only).

m5 does NOT import the m4 verifier (module rule). At integration time the orchestrator passes
the real one: `create_app(..., verifier=my_m4_adapter)`. Until then the default below is used.
"""

from __future__ import annotations

import importlib
import inspect
import re
from collections.abc import Callable
from typing import Any

Verifier = Callable[..., dict[str, Any]]


def call_verifier(
    fn: Verifier, record: dict[str, Any], encounter_id: str, transcript: dict[str, Any] | None
) -> dict[str, Any]:
    """Hook signature (Phase C): `fn(record, *, encounter_id, transcript)`.

    `encounter_id` and `transcript` are read by m5 from the DATABASE encounter of the stored record
    (never from fields inside the editable record JSON). `transcript` is a validated transcript.v1
    dict, or None when m5 has none (the verifier must then fail closed). Backward compatible:
    a legacy `fn(record)` is still called with the record only.
    """
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(record)
    takes_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    kw = {
        k: v
        for k, v in (("encounter_id", encounter_id), ("transcript", transcript))
        if takes_any or k in params
    }
    return fn(record, **kw)


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


_SPEC = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*$")


def load_verifier(spec: str | None) -> Verifier:
    """Load the verifier named by MAATUMITRA_VERIFIER (`package.module:function`).

    Empty/None -> the fail-closed default (flag everything). Anything else must import and be a
    callable, otherwise RuntimeError: the API refuses to start rather than silently running with
    a different verifier than the operator asked for. The setting comes from the operator's
    environment (.env), never from a request.
    """
    if not spec or not spec.strip():
        return manual_review_verifier
    spec = spec.strip()
    if not _SPEC.fullmatch(spec) or spec.split(":", 1)[1].startswith("__"):
        raise RuntimeError("MAATUMITRA_VERIFIER must look like 'package.module:function'")
    mod_name, fn_name = spec.split(":", 1)
    try:
        fn = getattr(importlib.import_module(mod_name), fn_name)
    except Exception:
        raise RuntimeError(f"cannot load verifier {spec!r}") from None
    if not callable(fn):
        raise RuntimeError(f"verifier {spec!r} is not callable")
    return fn
