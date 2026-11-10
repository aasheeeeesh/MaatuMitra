"""Split-aware loaders. The TEST split is frozen: any id listed in data/splits/test.txt is refused
unless the environment has ALLOW_TEST=1 (only `make eval-test` sets it, once).

Only the id LIST test.txt is read here (to know what to refuse); no test file is ever opened
without ALLOW_TEST=1.
"""

from __future__ import annotations

import json
import os
import random
from functools import cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data" / "splits"
GOLD_DIR = ROOT / "data" / "gold"
GOLD_TRANSCRIPTS = ROOT / "data" / "transcripts" / "gold"

# Fixed BEFORE any rule was written (2026-11-10): one template id per category, chosen with
# random.Random(20261110).choice over the dev template ids of that category. Never read while
# writing rules; reported separately as "dev_holdout".
HOLDOUT_TEMPLATES = ("a3", "b4", "c5", "d2", "e6", "f3", "g5", "h6", "i3")
SUBSET_SEED = 20261110
SUBSET_SIZE = 40


def _read_ids(name: str) -> list[str]:
    return [
        line.strip()
        for line in (SPLITS / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@cache
def test_ids_for_guard() -> tuple[str, ...]:
    return tuple(_read_ids("test.txt"))


def test_allowed() -> bool:
    return os.environ.get("ALLOW_TEST") == "1"


def conversation_id_of(audio_or_record_id: str) -> str:
    """'m1-a1-000__gold' / 'm1-a1-000__tts_v1' -> 'm1-a1-000'."""
    return audio_or_record_id.split("__", 1)[0]


def assert_allowed(any_id: str) -> None:
    cid = conversation_id_of(any_id)
    if cid in set(test_ids_for_guard()) and not test_allowed():
        raise PermissionError(
            f"{cid} is in the frozen TEST split; refused (set ALLOW_TEST=1 only via `make eval-test`)"
        )


def split_ids(split: str) -> list[str]:
    if split == "dev":
        return dev_ids()
    if split == "test":
        if not test_allowed():
            raise PermissionError("TEST split refused: ALLOW_TEST=1 is required (make eval-test)")
        return list(test_ids_for_guard())
    raise ValueError(f"unknown split {split!r}")


@cache
def _dev() -> tuple[str, ...]:
    ids = tuple(_read_ids("dev.txt"))
    overlap = set(ids) & set(test_ids_for_guard())
    if overlap:
        raise RuntimeError(f"dev and test overlap: {sorted(overlap)[:5]}")
    return ids


def dev_ids() -> list[str]:
    return list(_dev())


def template_of(cid: str) -> str:
    return cid.split("-")[1]


def dev_parts() -> tuple[list[str], list[str]]:
    tune = [i for i in dev_ids() if template_of(i) not in HOLDOUT_TEMPLATES]
    hold = [i for i in dev_ids() if template_of(i) in HOLDOUT_TEMPLATES]
    return tune, hold


def dev_part_of(cid: str) -> str:
    return "dev_holdout" if template_of(cid) in HOLDOUT_TEMPLATES else "dev_tune"


def llm_subset(n: int = SUBSET_SIZE, seed: int = SUBSET_SEED) -> list[str]:
    """Seeded DEV subset for the slow LLM comparison (rules are scored on it too)."""
    return sorted(random.Random(seed).sample(sorted(dev_ids()), n))  # noqa: S311 (sampling, not crypto)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gold(cid: str, gold_dir: Path = GOLD_DIR) -> dict[str, Any]:
    assert_allowed(cid)
    return _load(gold_dir / f"{cid}.json")


def load_transcript(path: Path) -> dict[str, Any]:
    assert_allowed(path.stem)  # refuse BEFORE opening the file
    doc = _load(path)
    assert_allowed(doc["audio_id"])
    return doc


def gold_transcript_path(cid: str) -> Path:
    assert_allowed(cid)
    return GOLD_TRANSCRIPTS / f"{cid}__gold.json"


def encounter_context(gold: dict[str, Any]) -> dict[str, str]:
    """patient_ref and encounter_type are encounter METADATA (chosen in the app, not spoken).
    Only these two fields are taken from the gold file; they are not scored."""
    gr = gold["gold_record"]
    return {"patient_ref": gr["patient_ref"], "encounter_type": gr["encounter_type"]}
