"""MOCK MODE: the generator runs on fixtures/lexicon/drugs_fixture.csv alone (no data/ needed)."""

from __future__ import annotations

import json

from contracts.validate import validate_doc
from m1_data.generate import generate

from .conftest import ROOT


def test_mock_mode_runs_on_fixture_lexicon(tmp_path):
    res = generate(
        out_root=tmp_path,
        lexicon_path=ROOT / "fixtures" / "lexicon" / "drugs_fixture.csv",
        per_template=2,
        mock=True,
    )
    assert res["conversations"] > 20
    golds = sorted((tmp_path / "data" / "gold").glob("*.json"))
    assert golds
    for p in golds:
        assert validate_doc("gold", json.loads(p.read_text("utf-8"))) == [], p.name
    for line in (tmp_path / "data" / "manifest.jsonl").read_text("utf-8").splitlines():
        assert validate_doc("manifest", json.loads(line)) == []
