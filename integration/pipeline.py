"""Shared steps for the integration tests: DEV id choice, mock ASR, m3 rules, m4 verify.

Only integration/ may import several modules. Only DEV ids are ever used (data/splits/dev.txt);
`select_ids` refuses an id that is in data/splits/test.txt.
"""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SEED = 20261112


def _ids(name: str) -> list[str]:
    p = REPO / "data" / "splits" / name
    return [x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def select_ids(n: int = 10, seed: int = SEED) -> list[str]:
    """Seeded sample of DEV ids that have gold text (never the test split)."""
    test = set(_ids("test.txt"))
    dev = sorted(i for i in _ids("dev.txt") if (REPO / "data" / "gold" / f"{i}.json").exists())
    ids = random.Random(seed).sample(dev, n)  # noqa: S311  (reproducible choice, not security)
    assert not (set(ids) & test), "a test id was selected"
    return ids


def gold_text(cid: str) -> str:
    doc = json.loads(
        (REPO / "data" / "transcripts" / "gold" / f"{cid}__gold.json").read_text(encoding="utf-8")
    )
    return doc["text"]


def mock_asr(cid: str) -> dict[str, Any]:
    """transcript.v1 as m2's mock adapter would return it (text = the gold text, no model)."""
    from m2_asr.asr.base import build_transcript

    return build_transcript(
        cid, "template_text", "mock", "mock-1", gold_text(cid), None, None, "none (mock)"
    )


def extract_record(cid: str, transcript: dict[str, Any]) -> dict[str, Any]:
    from m3_extract import splits
    from m3_extract.rules import extract

    rec, _log = extract(transcript, splits.encounter_context(splits.load_gold(cid)))
    return rec


def plant_negation_flip(record: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Planted error: flip `negated` of the first medication (or `present` of a symptom)."""
    rec = copy.deepcopy(record)
    if rec["medications"]:
        rec["medications"][0]["negated"] = not rec["medications"][0]["negated"]
        return rec, "/medications/0/negated"
    rec["symptoms"][0]["present"] = not rec["symptoms"][0]["present"]
    return rec, "/symptoms/0/present"


def write_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
