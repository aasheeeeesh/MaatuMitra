"""E7 user-study kit: 20 synthetic records (10 with planted critical errors), balanced
within-subject design, and a descriptive analysis with Wilson CIs (no significance tests)."""

import csv
import json
from pathlib import Path

import pytest

from contracts.validate import validate_doc
from m7_eval.e7_kit import analyse, build_records

KIT = Path(__file__).resolve().parents[1] / "e7_kit"


def test_kit_records_exist_and_are_valid():
    recs = sorted((KIT / "records").glob("*.json"))
    assert len(recs) == 20
    for p in recs:
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert validate_doc("record", doc) == [], p.name


def test_answer_key_has_ten_planted_critical_errors():
    key = list(csv.DictReader((KIT / "answer_key.csv").open(encoding="utf-8")))
    assert len(key) == 20
    planted = [r for r in key if r["has_planted_error"] == "yes"]
    assert len(planted) == 10
    assert all(r["error_code"].startswith("CR-") for r in planted)


def test_design_is_balanced_within_subject():
    rows = list(csv.DictReader((KIT / "design.csv").open(encoding="utf-8")))
    key = {
        r["record_id"]: r for r in csv.DictReader((KIT / "answer_key.csv").open(encoding="utf-8"))
    }
    by_p = {}
    for r in rows:
        by_p.setdefault(r["participant_id"], []).append(r)
    assert len(by_p) >= 8
    for pid, rs in by_p.items():
        assert len(rs) == 20 and len({r["record_id"] for r in rs}) == 20
        for cond in ("flags_shown", "flags_hidden"):
            c = [r for r in rs if r["condition"] == cond]
            assert len(c) == 10
            assert sum(key[r["record_id"]]["has_planted_error"] == "yes" for r in c) == 5
    # order differs between participants (randomised) but is reproducible
    orders = {
        tuple(r["record_id"] for r in sorted(rs, key=lambda x: int(x["position"])))
        for rs in by_p.values()
    }
    assert len(orders) > 1


def test_simulated_flags_are_imperfect_on_purpose():
    key = list(csv.DictReader((KIT / "answer_key.csv").open(encoding="utf-8")))
    err = [r for r in key if r["has_planted_error"] == "yes"]
    clean = [r for r in key if r["has_planted_error"] == "no"]
    assert sum(r["simulated_flag"] == "yes" for r in err) == 7  # 3 misses -> automation bias
    assert sum(r["simulated_flag"] == "yes" for r in clean) == 2  # 2 false alarms


def test_build_is_deterministic(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    if not (repo / "data/splits/dev.txt").exists():
        pytest.skip("dev data not present")
    a = build_records.build(repo, tmp_path / "a")
    b = build_records.build(repo, tmp_path / "b")
    assert a == b


SHEET = """participant_id,record_id,condition,position,review_seconds,marked_error,marked_field,notes
P01,r1,flags_shown,1,30,yes,,
P01,r2,flags_shown,2,20,no,,
P01,r3,flags_hidden,3,40,no,,
P01,r4,flags_hidden,4,50,yes,,
"""
KEY = """record_id,has_planted_error,error_code,error_field,simulated_flag,source_conversation
r1,yes,CR-DOSE,/medications/0/dose_value,yes,x
r2,no,,,no,x
r3,yes,CR-NEG,/symptoms/0/present,no,x
r4,no,,,no,x
"""


def test_analysis_hand_values(tmp_path):
    (tmp_path / "sheet.csv").write_text(SHEET, encoding="utf-8")
    (tmp_path / "key.csv").write_text(KEY, encoding="utf-8")
    rows = analyse.analyse(tmp_path / "sheet.csv", tmp_path / "key.csv")
    by = {r["condition"]: r for r in rows}
    s, h = by["flags_shown"], by["flags_hidden"]
    assert (s["catch_k"], s["catch_n"]) == (1, 1)
    assert (h["catch_k"], h["catch_n"]) == (0, 1)
    assert (h["false_alarm_k"], h["false_alarm_n"]) == (1, 1)
    assert s["review_seconds_median"] == 25.0
    assert s["n_participants"] == 1
    # Wilson 0/1: centre=(0+1.92)/(1+3.84)=0.3968, half=0.3968 -> [0, 0.7935]
    assert round(h["catch_wilson_hi"], 4) == 0.7935
    out = analyse.report(rows)
    assert "no significance" in out.lower()
