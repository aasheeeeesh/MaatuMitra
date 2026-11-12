"""Split discipline (PROJECT_BRIEF 6.5): family-level and drug-dose-level separation, sizes,
and a manifest row for every generated file."""

from __future__ import annotations

import hashlib

from contracts.validate import validate_doc

from .conftest import DATA, ROOT


def _split_of(split_ids):
    return {cid: s for s, ids in split_ids.items() for cid in ids}


def test_no_template_family_in_both_splits(split_ids, gold_docs):
    fams = {s: {gold_docs[c]["template_family_id"] for c in ids} for s, ids in split_ids.items()}
    assert fams["dev"] and fams["test"]
    assert not (fams["dev"] & fams["test"]), fams["dev"] & fams["test"]


def test_every_category_present_in_both_splits(split_ids, gold_docs):
    for s, ids in split_ids.items():
        cats = {gold_docs[c]["template_family_id"][0] for c in ids}
        assert cats == set("abcdefghi"), (s, cats)


def test_no_dosed_drug_combination_in_both_splits(split_ids, gold_docs):
    combos = {}
    for s, ids in split_ids.items():
        combos[s] = {
            (m["drug"], m["dose_value"], m["dose_unit"])
            for c in ids
            for m in gold_docs[c]["gold_record"]["medications"]
            if m["dose_value"] is not None
        }
    assert not (combos["dev"] & combos["test"]), combos["dev"] & combos["test"]


def test_test_split_size(split_ids, gold_docs):
    test = split_ids["test"]
    assert len(test) >= 40
    meds = sum(len(gold_docs[c]["gold_record"]["medications"]) for c in test)
    assert meds >= 300, meds
    assert not set(split_ids["dev"]) & set(test)


def test_manifest_covers_every_generated_file(manifest_rows, split_ids):
    split_of = _split_of(split_ids)
    text_rows = [r for r in manifest_rows if not r["file"].startswith("data/audio/")]
    files = {r["file"]: r for r in text_rows}
    assert len(files) == len(text_rows)  # audio rows are covered by test_audio_*.py
    expected = set()
    for cid in split_of:
        expected |= {
            f"data/gold/{cid}.json",
            f"data/gold_v2/{cid}.json",
            f"data/transcripts/gold/{cid}__gold.json",
        }
    expected |= {"data/twins/twins_dev.jsonl", "data/twins/twins_test.jsonl"}
    assert set(files) == expected
    for f, r in files.items():
        assert validate_doc("manifest", r) == [], f
        p = ROOT / f
        assert hashlib.sha256(p.read_bytes()).hexdigest() == r["sha256"], f
        assert p.stat().st_size == r["bytes"]
        assert r["source"] == "template_text" and r["native_validated"] is False
        cid = r["parent_id"] or p.stem
        if f.startswith("data/twins/"):
            assert r["split"] == ("test" if "test" in f else "dev")
        else:
            assert r["split"] == split_of[cid.removesuffix("__gold")], f


def test_split_plan_written(root):
    assert (DATA / "splits" / "split_plan.json").exists()
