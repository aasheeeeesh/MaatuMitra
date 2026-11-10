"""MOCK MODE: the whole module runs on fixtures only and every output validates."""

import json

from contracts.validate import validate_path
from m3_extract import run


def test_mock_run_writes_valid_records(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOW_TEST", raising=False)
    summary = run.run_mock(out_root=tmp_path)
    recs = sorted((tmp_path / "rules").glob("*.json"))
    assert len(recs) == summary["n_records"] >= 6
    # top-level files are records (rejected/ and logs/ are not record.v1 by design)
    for p in recs:
        assert validate_path("record.v1", p) == {str(p): []}
    assert summary["n_rejected"] == 0
    scores = (tmp_path / "mock_scores.csv").read_text(encoding="utf-8")
    assert "critical" in scores and "major" in scores
    assert summary["critical_errors"] == 0


def test_rejected_records_are_kept(tmp_path):
    from m3_extract.tests._helpers import FIX, load_json

    tr = load_json(FIX / "transcript" / "valid" / "fx-pharm-003__gold.json")
    rec = load_json(FIX / "record" / "valid" / "rec-fx-pharm-003.json")
    rec["medications"][0]["evidence"]["span_text"] = rec["medications"][0]["evidence"][
        "span_text"
    ].replace("500", "250")
    path = run.save_record(rec, tr, tmp_path / "rules")
    assert path.parent.name == "rejected"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["reasons"] and saved["record"]["record_id"] == rec["record_id"]
    assert not list((tmp_path / "rules").glob("*.json"))
