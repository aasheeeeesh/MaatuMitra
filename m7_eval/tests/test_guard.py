"""Test-split discipline (PROJECT_BRIEF 6.5): the dev run refuses every test file, and the
test path refuses unless ALLOW_TEST=1, PURPOSE and a log row for this commit exist."""

import pytest

from m7_eval import guard


def _tree(tmp_path):
    s = tmp_path / "data" / "splits"
    s.mkdir(parents=True)
    (s / "dev.txt").write_text("m1-a1-000\nm1-a1-001\n", encoding="utf-8")
    (s / "test.txt").write_text("m1-a5-000\n", encoding="utf-8")
    (s / "test.lock").write_text(
        "# comment\nabc  data/gold/m1-a5-000.json\ndef  data/twins/twins_test.jsonl\n",
        encoding="utf-8",
    )
    g = tmp_path / "data" / "gold"
    g.mkdir()
    (g / "m1-a1-000.json").write_text("{}", encoding="utf-8")
    (g / "m1-a5-000.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_dev_guard_refuses_test_files(tmp_path):
    root = _tree(tmp_path)
    g = guard.SplitGuard(root, "dev")
    assert g.read_json(root / "data/gold/m1-a1-000.json") == {}
    for bad in [
        "data/gold/m1-a5-000.json",  # listed in test.lock
        "results/m3_extract/rules/rules-m1-a5-000.json",  # test conversation id in the name
        "data/audio/tts/test/mms_kan_base/clean/m1-a1-000.wav",  # a 'test' folder
        "data/audio/tts/dev/mms_kan_pitch084/clean/m1-a1-000.wav",  # held-out voice
        "data/twins/twins_test.jsonl",
    ]:
        assert g.is_test_path(root / bad), bad
        with pytest.raises(guard.TestSplitRefused):
            g.read_text(root / bad)
    assert not g.is_test_path(root / "results/m3_extract/rules/rules-m1-a1-000.json")
    assert not g.is_test_path(root / "results/m3_extract/rules/rules-m1-a5-0001.json")
    assert [p for p in g.opened] == ["data/gold/m1-a1-000.json"]


def test_conversation_split_membership(tmp_path):
    g = guard.SplitGuard(_tree(tmp_path), "dev")
    assert g.conv_split("m1-a1-000") == "dev"
    assert g.conv_split("m1-a5-000") == "test"
    assert g.conv_split("zzz") is None
    assert g.ids == {"m1-a1-000", "m1-a1-001"}


def test_test_split_refused_without_allow_test(tmp_path):
    root = _tree(tmp_path)
    with pytest.raises(guard.TestSplitRefused, match="ALLOW_TEST"):
        guard.require_test_access(root, {}, "abc1234")
    with pytest.raises(guard.TestSplitRefused, match="PURPOSE"):
        guard.require_test_access(root, {"ALLOW_TEST": "1"}, "abc1234")


def test_test_split_needs_log_row_for_this_commit(tmp_path):
    root = _tree(tmp_path)
    env = {"ALLOW_TEST": "1", "PURPOSE": "final run"}
    with pytest.raises(guard.TestSplitRefused, match="test_access_log"):
        guard.require_test_access(root, env, "abc1234")
    log = root / "results" / "test_access_log.md"
    log.parent.mkdir(parents=True)
    log.write_text("| 2026 | other00 | x | y |\n", encoding="utf-8")
    with pytest.raises(guard.TestSplitRefused, match="abc1234"):
        guard.require_test_access(root, env, "abc1234")
    log.write_text("| 2026-11-20T00:00:00Z | abc1234 | x | final run |\n", encoding="utf-8")
    guard.require_test_access(root, env, "abc1234")  # no exception
    g = guard.SplitGuard(root, "test")
    assert g.read_json(root / "data/gold/m1-a5-000.json") == {}


def test_split_guard_rejects_unknown_split(tmp_path):
    with pytest.raises(ValueError):
        guard.SplitGuard(_tree(tmp_path), "train")
