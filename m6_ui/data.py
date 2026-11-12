"""Load and validate the documents the app shows (MOCK MODE: fixtures only).

Sources: fixtures/{record,verdict,transcript,card}/valid/ (shared, architect-owned) plus
m6_ui/fixtures/{record,verdict,transcript}/ (m6-only security fixture). Every document is
validated with contracts.validate; an invalid or missing part is REPORTED (case.errors),
never silently replaced.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from contracts.validate import bidi_errors, validate_doc

M6 = Path(__file__).resolve().parent


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class Case:
    record: dict
    verdict: dict | None
    transcript: dict | None
    errors: list[str] = field(default_factory=list)


def evidence_items(record: dict):
    for key in ("symptoms", "medications", "advice"):
        for item in record.get(key, []):
            yield item["evidence"]
            yield from (item.get("field_evidence") or {}).values()  # record.v2
    if record.get("follow_up"):
        yield record["follow_up"]["evidence"]
    for key in ("patient_age_band", "weight_kg"):  # record.v2
        if record.get(key):
            yield record[key]["evidence"]


def bidi_problems(doc: dict) -> list[str]:
    """F6: paths of strings that contain Unicode bidi controls (via contracts.validate)."""
    return bidi_errors(doc)


# Mock stand-in for m5 row-level security: which encounter types each role may open.
ROLE_VISIBLE = {
    "asha": {"asha_household_visit"},
    "nurse": {"asha_household_visit", "nurse_consult"},
    "pharmacist": {"pharmacist_dispensing"},
}


class Catalogue:
    def __init__(self, root: Path):
        self.root = Path(root)
        shared = self.root / "fixtures"
        own = M6 / "fixtures"
        self._dirs = {
            kind: [shared / kind / "valid", own / kind]
            for kind in ("record", "verdict", "transcript")
        }
        self._dirs["record"].append(shared / "record.v2" / "valid")
        self._dirs["transcript"].append(shared / "record.v2" / "transcripts")
        self._records = self._load("record", ("record.v1", "record.v2"), "record_id")
        self._verdicts = self._load("verdict", "verdict.v1", "record_id")
        self._transcripts = self._load("transcript", "transcript.v1", "audio_id")

    def _load(self, kind: str, schema: str | tuple, key: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for d in self._dirs[kind]:
            for p in sorted(d.glob("*.json")) if d.exists() else []:
                try:
                    doc = read_json(p)
                except (OSError, ValueError):
                    continue
                name = (
                    schema
                    if isinstance(schema, str)
                    else (
                        doc.get("schema_version")
                        if doc.get("schema_version") in schema
                        else schema[0]
                    )
                )
                if validate_doc(name, doc):
                    continue  # invalid documents are never shown as if they were fine
                out.setdefault(doc[key], doc)
        return out

    def record_ids(self, role: str | None = None) -> list[str]:
        """Record ids, optionally only those the (mock) role may see; physician sees all."""
        allowed = ROLE_VISIBLE.get(role) if role else None
        return sorted(
            r for r, d in self._records.items() if allowed is None or d["encounter_type"] in allowed
        )

    def case(self, record_id: str) -> Case:
        rec = self._records[record_id]
        return self.case_for(rec, self._verdicts.get(record_id))

    def case_for(self, rec: dict, ver: dict | None) -> Case:
        """Case for any record (local fixture or one loaded from m5): transcript found by id."""
        tr = self._transcripts.get(rec["source_transcript_id"])
        errors = []
        if ver is None:
            errors.append("no_verdict")
        if tr is None:
            errors.append("no_transcript")
        else:
            for ev in evidence_items(rec):
                if tr["text"][ev["char_start"] : ev["char_end"]] != ev["span_text"]:
                    errors.append("span_mismatch")
                    break
        return Case(rec, ver, tr, errors)

    def cards(self) -> list[dict]:
        d = self.root / "fixtures" / "card" / "valid"
        cards = []
        for p in sorted(d.glob("*.json")) if d.exists() else []:
            doc = read_json(p)
            if not validate_doc("card.v1", doc):
                cards.append(doc)
        return cards
