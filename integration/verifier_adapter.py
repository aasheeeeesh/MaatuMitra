"""Glue between m5 (access + save gate) and m4 (safety verifier).

m5 calls `fn(record_json, *, encounter_id, transcript) -> verdict dict` on the STORED record (never imports m4). m4 needs
the transcript as well. The record names its transcript in `source_transcript_id`, so this adapter
finds `<id>.json` or `<id>__*.json` in the directories listed in MAATUMITRA_TRANSCRIPT_DIRS
(os.pathsep separated; default `data/transcripts/gold`).

Start the API with:  MAATUMITRA_VERIFIER=integration.verifier_adapter:verify_record

Fail closed: anything that stops m4 from really checking (no transcript, unsupported schema,
a crash, an invalid verdict) returns a valid verdict.v1 with ONE flag, so a physician must
resolve it explicitly. It never returns a clean verdict by accident.

PHASE C HOOK SIGNATURE: m5 calls `fn(record, *, encounter_id, transcript)`. The transcript is
loaded by m5 from the DATABASE encounter of the record (as GET /records/{id}/transcript does),
never from `source_transcript_id` inside the editable record. transcript=None -> fail closed.
Legacy `verify_record(record)` (no encounter_id) still looks the transcript up by
`source_transcript_id`; that old weakness remains only in that offline mode.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from contracts.validate import validate_doc

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DIRS = (REPO / "data" / "transcripts" / "gold",)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,120}$")
VERSION = "integration-adapter-1.0+m4"


def transcript_dirs() -> list[Path]:
    raw = os.environ.get("MAATUMITRA_TRANSCRIPT_DIRS", "")
    dirs = [Path(p) for p in raw.split(os.pathsep) if p.strip()]
    return dirs or list(DEFAULT_DIRS)


def find_transcript(source_id: Any) -> dict[str, Any] | None:
    """transcript.v1 for `source_id`, or None. The id is whitelisted (no path characters)."""
    if not isinstance(source_id, str) or not ID_RE.fullmatch(source_id) or ".." in source_id:
        return None
    for d in transcript_dirs():
        cands = [d / f"{source_id}.json", *sorted(d.glob(f"{source_id}__*.json"))]
        for p in cands:
            if p.is_file():
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(doc, dict) and doc.get("audio_id") == source_id:
                    return doc
    return None


def _safe_id(record: Any) -> str:
    rid = record.get("record_id") if isinstance(record, dict) else None
    return rid if isinstance(rid, str) and ID_RE.fullmatch(rid) else "invalid-record-id"


def _closed(record: Any, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "verdict.v1",
        "record_id": _safe_id(record),
        "checks": [
            {
                "check_id": "C1",
                "name": "span-grounding",
                "status": "flag",
                "reason": f"check_error: adapter could not run m4: {reason}"[:300],
                "field_path": "/",
            }
        ],
        "auto_acceptable": False,
        "verifier_version": VERSION,
    }


_LEGACY: Any = object()


def verify_record(
    record: dict[str, Any], *, encounter_id: Any = _LEGACY, transcript: Any = None
) -> dict[str, Any]:
    """The function m5 expects: record JSON (+ DB encounter id and transcript) in, verdict.v1 out."""
    try:
        if not isinstance(record, dict):
            return _closed(record, "record is not an object")
        if record.get("schema_version") != "record.v1":
            return _closed(record, f"m4 does not accept {record.get('schema_version')!r} yet")
        if encounter_id is _LEGACY:  # legacy call without the hook arguments
            transcript = find_transcript(record.get("source_transcript_id"))
        if not isinstance(transcript, dict):
            return _closed(record, "no transcript for the encounter")
        from m4_verify.verifier import verify

        verdict = verify(record, transcript, encounter_index=_encounter_index())
        if validate_doc("verdict", verdict):
            return _closed(record, "m4 returned an invalid verdict")
        return verdict
    except Exception as exc:  # fail closed, never let a crash look like a pass
        return _closed(record, type(exc).__name__)


def _encounter_index() -> dict[str, str] | None:
    """Optional {audio_id: patient_ref} JSON file (MAATUMITRA_ENCOUNTER_INDEX) for check C6."""
    p = os.environ.get("MAATUMITRA_ENCOUNTER_INDEX")
    if not p:
        return None
    return json.loads(Path(p).read_text(encoding="utf-8"))
