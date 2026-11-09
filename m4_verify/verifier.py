"""verify(record, transcript, ...) -> verdict.v1. Deterministic and FAIL-CLOSED.

Fail-closed means:
  * any exception inside a check -> that check reports status "flag",
    reason "check_error: <ExceptionType>: <message>" (never swallowed, never "pass");
  * a check that returns something malformed -> also "check_error";
  * inputs that fail their contract -> a C1 "check_error" flag (the other checks still run);
  * auto_acceptable is true ONLY if no entry flags AND at least one enabled check passed
    (so "everything disabled" or "nothing could run" is never auto-acceptable).
"""

from __future__ import annotations

import unicodedata
from typing import Any

import regex

from m4_verify import checks as _checks
from m4_verify.config import CHECK_IDS, VERIFIER_VERSION, Config, default_config
from m4_verify.lexicon import Lexicon

RECORD_ID_RE = regex.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")
STATUSES = {"pass", "flag", "n/a"}


def _safe_record_id(record: Any) -> str:
    rid = record.get("record_id") if isinstance(record, dict) else None
    if isinstance(rid, str) and RECORD_ID_RE.match(rid) and len(rid) <= 200:
        return rid
    return "invalid-record-id"


def _input_errors(record: Any, transcript: Any) -> list[str]:
    from contracts.validate import validate_doc

    errs = []
    for name, doc in (("record", record), ("transcript", transcript)):
        try:
            e = validate_doc(name, doc)
        except Exception as ex:  # validator itself failed on garbage input
            e = [f"validator raised {type(ex).__name__}: {ex}"]
        errs += [f"{name}: {x}" for x in e[:3]]
    return errs


def _clip(s: str, n: int = 600) -> str:
    """One line, NFC, no BOM/zero-width chars (verdict strings must pass contracts.validate)."""
    s = unicodedata.normalize("NFC", str(s))
    s = s.replace("﻿", "").replace("​", "")
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 3] + "..."


def verify(
    record: dict[str, Any],
    transcript: dict[str, Any],
    lexicon: Lexicon | None = None,
    config: Config | None = None,
    second_transcript: dict[str, Any] | None = None,
    encounter_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    cfg = config or default_config()
    out_checks: list[dict[str, str]] = []
    try:
        lex = lexicon or cfg.lexicon()
    except Exception as ex:
        lex = None
        lex_error = f"check_error: lexicon could not be loaded: {type(ex).__name__}: {ex}"
    ctx = _checks.Ctx(record, transcript, lex, cfg, second_transcript, encounter_index)  # type: ignore[arg-type]

    input_errs = _input_errors(record, transcript)
    any_pass = False
    for cid in CHECK_IDS:
        chk = _checks.REGISTRY[cid]
        if cid in cfg.disabled:
            out_checks.append(_entry(cid, chk.name, "n/a", "disabled by config (ablation)", "/"))
            continue
        try:
            if lex is None:
                raise RuntimeError(lex_error)
            results = chk.fn(ctx)
            if not isinstance(results, list) or not results:
                raise ValueError(f"check returned {type(results).__name__} with no results")
            entries = []
            for res in results:
                status, reason, path = res
                if status not in STATUSES or not isinstance(reason, str) or not reason:
                    raise ValueError(f"malformed result {res!r}")
                if not isinstance(path, str) or not path.startswith("/"):
                    raise ValueError(f"malformed field_path {path!r}")
                entries.append(_entry(cid, chk.name, status, _clip(reason), path))
        except Exception as ex:  # FAIL-CLOSED: never swallowed, always a flag
            msg = str(ex)
            if not msg.startswith("check_error"):
                msg = f"check_error: {type(ex).__name__}: {msg}"
            entries = [_entry(cid, chk.name, "flag", _clip(msg), "/")]
        if cid == "C1" and input_errs:
            entries.append(
                _entry(
                    cid,
                    chk.name,
                    "flag",
                    _clip("check_error: input fails its contract: " + " | ".join(input_errs)),
                    "/",
                )
            )
        any_pass = any_pass or any(e["status"] == "pass" for e in entries)
        out_checks.extend(entries)

    flagged = any(c["status"] == "flag" for c in out_checks)
    return {
        "schema_version": "verdict.v1",
        "record_id": _safe_record_id(record),
        "checks": out_checks,
        "auto_acceptable": bool(out_checks) and not flagged and any_pass,
        "verifier_version": VERIFIER_VERSION,
    }


def _entry(cid: str, name: str, status: str, reason: str, path: str) -> dict[str, str]:
    return {"check_id": cid, "name": name, "status": status, "reason": reason, "field_path": path}
