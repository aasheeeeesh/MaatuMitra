"""Shared test helpers (paths, fixture loading). Independent of m6_ui.data on purpose."""

from __future__ import annotations

import json
from pathlib import Path

M6 = Path(__file__).resolve().parents[1]
ROOT = M6.parent
APP = M6 / "app.py"


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dirs(kind: str) -> list[Path]:
    return [ROOT / "fixtures" / kind / "valid", M6 / "fixtures" / kind]


def fixture_triplet(record_id: str):
    """(record, verdict or None, transcript or None) from fixtures/ or m6_ui/fixtures/."""
    rec = next(
        (load_json(p) for d in _dirs("record") if (p := d / f"{record_id}.json").exists()), None
    )
    if rec is None:
        raise FileNotFoundError(record_id)
    ver = next(
        (load_json(p) for d in _dirs("verdict") if (p := d / f"{record_id}.json").exists()), None
    )
    tr = None
    for d in _dirs("transcript"):
        for p in d.glob("*.json"):
            doc = load_json(p)
            if doc.get("audio_id") == rec["source_transcript_id"]:
                tr = doc
    return rec, ver, tr
