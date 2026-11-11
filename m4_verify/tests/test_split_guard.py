"""M4-1 (integrity review 2026-11-10, CRITICAL): the DEV-only guard must be an ALLOW-LIST.

The old guard refused a path only if its name contained "test", so `e4 --gold-dir data/gold`
would have read the 264 TEST gold files that sit next to the dev files. These tests prove:
  * reading data/gold loads ONLY ids from data/splits/dev.txt, and never even opens a test file;
  * a test conversation id, a test template family or a file whose sha256 is in test.lock is
    REFUSED from any directory, including a copied or renamed one outside data/;
  * the same holds for tune-c7 inputs and for the `e4` command line;
  * ALLOW_TEST=1 alone is not enough (PURPOSE is also required) and every allowed access is logged.
No TEST file content is read by these tests: test ids come from data/splits/test.txt (the split
list itself) and the "test documents" are fixture documents with a test id written into them.
"""

from __future__ import annotations

import builtins
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from m4_verify.planted import load_gold_dir
from m4_verify.split_guard import (
    SplitGuardError,
    SplitRefused,
    conv_id,
    guard_doc,
    load_gold,
    split_info,
)
from m4_verify.tests.helpers import FIX, ROOT

SPLITS = ROOT / "data" / "splits"
DEV_IDS = [x.strip() for x in (SPLITS / "dev.txt").read_text(encoding="utf-8").split() if x.strip()]
TEST_IDS = [
    x.strip() for x in (SPLITS / "test.txt").read_text(encoding="utf-8").split() if x.strip()
]
TEST_FAMILIES = json.loads((SPLITS / "split_plan.json").read_text(encoding="utf-8"))["families"][
    "test"
]
FIXTURE_GOLD = FIX / "gold" / "valid" / "fx-pharm-003.json"


def _fake_gold(cid: str, family: str = "fixture_family") -> dict:
    """A fixture gold document re-labelled with another conversation id (no test content)."""
    doc = json.loads(FIXTURE_GOLD.read_text(encoding="utf-8"))
    doc["conversation_id"] = cid
    doc["template_family_id"] = family
    return doc


@pytest.fixture(autouse=True)
def _no_test_access_env(monkeypatch):
    monkeypatch.delenv("ALLOW_TEST", raising=False)
    monkeypatch.delenv("PURPOSE", raising=False)


def test_split_lists_are_disjoint_and_nonempty():
    info = split_info()
    assert len(info.dev_ids) == len(DEV_IDS) > 0
    assert len(info.test_ids) == len(TEST_IDS) > 0
    assert not (info.dev_ids & info.test_ids)
    assert len(info.test_hashes) > 0


def test_conv_id_strips_transcript_suffix():
    assert conv_id("m1-a1-000__gold") == "m1-a1-000"
    assert conv_id("m1-a1-000__gold.json") == "m1-a1-000"
    assert conv_id("m1-a1-000.json") == "m1-a1-000"


def test_data_gold_loads_only_dev_ids_and_never_opens_a_test_file(monkeypatch):
    opened: list[str] = []
    real_open = builtins.open

    def spy_open(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    res = load_gold(ROOT / "data" / "gold")
    monkeypatch.setattr(builtins, "open", real_open)
    ids = {d["conversation_id"] for d in res.docs}
    assert ids == set(DEV_IDS)
    assert not ids & set(TEST_IDS)
    assert res.skipped_not_allowed == len(TEST_IDS)
    test_names = {f"{t}.json" for t in TEST_IDS}
    assert not [p for p in opened if Path(p).name in test_names], "a TEST gold file was opened"
    # the old wrapper goes through the same guard
    assert {d["conversation_id"] for d in load_gold_dir(ROOT / "data" / "gold")} == set(DEV_IDS)


def test_copied_directory_with_a_test_id_is_refused(tmp_path):
    d = tmp_path / "my_dev_copy"  # no "test" anywhere in this name
    d.mkdir()
    shutil.copy(FIXTURE_GOLD, d / "fx-pharm-003.json")
    tid = TEST_IDS[0]
    (d / f"{tid}.json").write_text(json.dumps(_fake_gold(tid), ensure_ascii=False), "utf-8")
    with pytest.raises(SplitRefused, match=tid):
        load_gold_dir(d)


def test_renamed_file_with_a_test_id_inside_is_refused(tmp_path):
    d = tmp_path / "renamed"
    d.mkdir()
    tid = TEST_IDS[-1]
    (d / "harmless_name.json").write_text(json.dumps(_fake_gold(tid), ensure_ascii=False), "utf-8")
    with pytest.raises(SplitRefused, match=r"test.txt"):
        load_gold_dir(d)


def test_test_family_under_a_new_id_is_refused(tmp_path):
    d = tmp_path / "relabelled"
    d.mkdir()
    doc = _fake_gold("m1-zz-999", family=TEST_FAMILIES[0])
    (d / "m1-zz-999.json").write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
    with pytest.raises(SplitRefused, match="family"):
        load_gold_dir(d)


def test_jsonl_with_a_test_id_is_refused(tmp_path):
    p = tmp_path / "gold_dump.jsonl"
    rows = [_fake_gold(DEV_IDS[0]), _fake_gold(TEST_IDS[3])]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), "utf-8")
    with pytest.raises(SplitRefused):
        load_gold_dir(p)


def test_file_whose_hash_is_in_test_lock_is_refused(tmp_path):
    """Mechanism test with a fake splits dir: a byte-identical copy of a locked file is refused
    even if its id and family were unknown."""
    splits = tmp_path / "splits"
    splits.mkdir()
    (splits / "dev.txt").write_text("m1-dev-000\n", "utf-8")
    (splits / "test.txt").write_text("m1-tst-000\n", "utf-8")
    (splits / "split_plan.json").write_text(json.dumps({"families": {"test": []}}), "utf-8")
    copy = tmp_path / "copy"
    copy.mkdir()
    doc = _fake_gold("m1-other-001")
    raw = json.dumps(doc, ensure_ascii=False).encode("utf-8")
    (copy / "m1-other-001.json").write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    (splits / "test.lock").write_text(f"# header\n{sha}  data/gold/m1-tst-000.json\n", "utf-8")
    with pytest.raises(SplitRefused, match=r"test.lock"):
        load_gold(copy, splits_dir=splits)


def test_missing_split_lists_fail_closed(tmp_path):
    with pytest.raises(SplitGuardError):
        split_info(str(tmp_path / "nowhere"))


def test_allow_test_needs_purpose_and_is_logged(tmp_path, monkeypatch):
    log = tmp_path / "access_log.md"
    doc = _fake_gold(TEST_IDS[0])
    monkeypatch.setenv("ALLOW_TEST", "1")
    with pytest.raises(SplitRefused, match="PURPOSE"):
        guard_doc(doc, "unit-test", log_path=log)
    assert not log.exists()
    monkeypatch.setenv("PURPOSE", "guard unit test (synthetic document, no test content)")
    guard_doc(doc, "unit-test", log_path=log)
    txt = log.read_text(encoding="utf-8")
    assert TEST_IDS[0] in txt and "guard unit test" in txt


def test_fixture_gold_still_loads():
    assert len(load_gold_dir(FIX / "gold" / "valid")) == 6


# --------------------------------------------------------------------- tune-c7
def _pairs_file(tmp_path, asr: Path, gold: Path) -> Path:
    p = tmp_path / "pairs.jsonl"
    p.write_text(json.dumps({"asr_transcript": str(asr), "gold_transcript": str(gold)}), "utf-8")
    return p


def test_tune_c7_refuses_test_transcript_by_audio_id(tmp_path):
    from m4_verify.tune_c7 import main

    src = FIX / "transcript" / "valid" / "fx-pharm-003__gold.json"
    tr = json.loads(src.read_text(encoding="utf-8"))
    tr["audio_id"] = f"{TEST_IDS[5]}__whisper-small"
    asr = tmp_path / "asr_copy.json"
    asr.write_text(json.dumps(tr, ensure_ascii=False), "utf-8")
    with pytest.raises(SplitRefused, match=TEST_IDS[5]):
        main(str(_pairs_file(tmp_path, asr, src)), 0.2)


def test_tune_c7_refuses_a_data_path_of_a_test_id_without_opening_it(tmp_path, monkeypatch):
    from m4_verify.tune_c7 import main

    tid = TEST_IDS[7]
    gold = ROOT / "data" / "transcripts" / "gold" / f"{tid}__gold.json"
    src = FIX / "transcript" / "valid" / "fx-pharm-003__gold.json"
    real_open = builtins.open
    opened: list[str] = []

    def spy_open(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    with pytest.raises(SplitRefused):
        main(str(_pairs_file(tmp_path, src, gold)), 0.2)
    monkeypatch.setattr(builtins, "open", real_open)
    assert not [p for p in opened if tid in p]


def test_tune_c7_accepts_fixture_pairs(tmp_path):
    from m4_verify.tune_c7 import main

    a = FIX / "transcript" / "valid" / "fx-pharm-003__asr_digit_error.json"
    g = FIX / "transcript" / "valid" / "fx-pharm-003__gold.json"
    assert main(str(_pairs_file(tmp_path, a, g)), 0.2) == 0


# --------------------------------------------------------------------- CLI
def test_cli_e4_on_a_dir_with_a_test_id_is_refused(tmp_path, capsys):
    from m4_verify.__main__ import main

    d = tmp_path / "gold_copy"
    d.mkdir()
    tid = TEST_IDS[1]
    (d / f"{tid}.json").write_text(json.dumps(_fake_gold(tid), ensure_ascii=False), "utf-8")
    rc = main(["e4", "--gold-dir", str(d), "--n", "5", "--out-dir", str(tmp_path / "out")])
    assert rc == 2
    assert "REFUSED" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
