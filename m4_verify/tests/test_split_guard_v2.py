"""The DEV-only guard also covers data/gold_v2 (Phase C). No TEST file content is read: test ids
come from data/splits/test.txt, and the "test documents" are fixture gold.v2 documents with a test
id written into them.
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest

from m4_verify.split_guard import SplitRefused, load_gold, read_guarded_json
from m4_verify.tests.helpers import FIX, ROOT

SPLITS = ROOT / "data" / "splits"
DEV_IDS = set((SPLITS / "dev.txt").read_text(encoding="utf-8").split())
TEST_IDS = sorted(set((SPLITS / "test.txt").read_text(encoding="utf-8").split()))
GOLD_V2 = ROOT / "data" / "gold_v2"
FIX_V2 = FIX / "gold.v2" / "valid" / "fx-pharm-003.json"


@pytest.fixture(autouse=True)
def _no_test_access_env(monkeypatch):
    monkeypatch.delenv("ALLOW_TEST", raising=False)
    monkeypatch.delenv("PURPOSE", raising=False)


def _spy(monkeypatch):
    opened: list[str] = []
    real_open = builtins.open

    def spy_open(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    return opened, real_open


@pytest.mark.skipif(not GOLD_V2.exists(), reason="data/gold_v2 not generated yet")
def test_data_gold_v2_loads_only_dev_ids_and_never_opens_a_test_file(monkeypatch):
    opened, real_open = _spy(monkeypatch)
    res = load_gold(GOLD_V2, schema="gold.v2")
    monkeypatch.setattr(builtins, "open", real_open)
    ids = {d["conversation_id"] for d in res.docs}
    assert ids and ids <= DEV_IDS
    assert not ids & set(TEST_IDS)
    assert all(d["schema_version"] == "gold.v2" for d in res.docs)
    present_test = [t for t in TEST_IDS if (GOLD_V2 / f"{t}.json").exists()]
    assert res.skipped_not_allowed >= len(present_test) > 0
    names = {f"{t}.json" for t in TEST_IDS}
    assert not [p for p in opened if Path(p).name in names], "a TEST gold.v2 file was opened"


@pytest.mark.skipif(not GOLD_V2.exists(), reason="data/gold_v2 not generated yet")
def test_reading_a_test_id_from_data_gold_v2_is_refused_without_opening(monkeypatch):
    tid = next(t for t in TEST_IDS if (GOLD_V2 / f"{t}.json").exists())
    opened, real_open = _spy(monkeypatch)
    with pytest.raises(SplitRefused, match=r"test.txt"):
        read_guarded_json(GOLD_V2 / f"{tid}.json")
    monkeypatch.setattr(builtins, "open", real_open)
    assert not [p for p in opened if Path(p).name == f"{tid}.json"]


def test_gold_v2_copy_with_a_test_id_is_refused_anywhere(tmp_path):
    doc = json.loads(FIX_V2.read_text(encoding="utf-8"))
    doc["conversation_id"] = TEST_IDS[0]
    d = tmp_path / "harmless_name"
    d.mkdir()
    (d / "x.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SplitRefused):
        load_gold(d, schema="gold.v2")


def test_schema_filter_keeps_v1_default():
    assert load_gold(FIX / "gold.v2" / "valid").docs == []  # default schema is still gold.v1
    got = load_gold(FIX / "gold.v2" / "valid", schema="gold.v2").docs
    assert got and all(d["schema_version"] == "gold.v2" for d in got)


def test_cli_e4_v2_on_a_dir_with_a_test_id_is_refused(tmp_path, capsys):
    from m4_verify.__main__ import main

    doc = json.loads(FIX_V2.read_text(encoding="utf-8"))
    doc["conversation_id"] = TEST_IDS[0]
    d = tmp_path / "gold_v2_copy"
    d.mkdir()
    (d / "a.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    rc = main(["e4-v2", "--gold-v2-dir", str(d), "--n", "5", "--out-dir", str(out)])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().err
    assert not (out / "e4_v2").exists()
