"""Shared fixtures for m1_data tests.

`regenerated` re-runs the generator into a temporary folder ONCE per test session, so the
determinism test can compare it byte-for-byte with the committed data/ files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def regenerated(tmp_path_factory) -> Path:
    from m1_data.generate import generate

    out = tmp_path_factory.mktemp("regen")
    generate(out_root=out)
    return out


@pytest.fixture(scope="session")
def split_ids() -> dict[str, list[str]]:
    out = {}
    for s in ("dev", "test"):
        out[s] = (DATA / "splits" / f"{s}.txt").read_text(encoding="utf-8").split()
    return out


@pytest.fixture(scope="session")
def gold_docs(split_ids) -> dict[str, dict]:
    docs = {}
    for ids in split_ids.values():
        for cid in ids:
            docs[cid] = json.loads((DATA / "gold" / f"{cid}.json").read_text(encoding="utf-8"))
    return docs


@pytest.fixture(scope="session")
def manifest_rows() -> list[dict]:
    return read_jsonl(DATA / "manifest.jsonl")
