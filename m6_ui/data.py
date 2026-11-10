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

from contracts.validate import validate_doc

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
    if record.get("follow_up"):
        yield record["follow_up"]["evidence"]


class Catalogue:
    def __init__(self, root: Path):
        self.root = Path(root)
        shared = self.root / "fixtures"
        own = M6 / "fixtures"
        self._dirs = {
            kind: [shared / kind / "valid", own / kind]
            for kind in ("record", "verdict", "transcript")
        }
        self._records = self._load("record", "record.v1", "record_id")
        self._verdicts = self._load("verdict", "verdict.v1", "record_id")
        self._transcripts = self._load("transcript", "transcript.v1", "audio_id")

    def _load(self, kind: str, schema: str, key: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for d in self._dirs[kind]:
            for p in sorted(d.glob("*.json")) if d.exists() else []:
                try:
                    doc = read_json(p)
                except (OSError, ValueError):
                    continue
                if validate_doc(schema, doc):
                    continue  # invalid documents are never shown as if they were fine
                out.setdefault(doc[key], doc)
        return out

    def record_ids(self) -> list[str]:
        return sorted(self._records)

    def case(self, record_id: str) -> Case:
        rec = self._records[record_id]
        ver = self._verdicts.get(record_id)
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
