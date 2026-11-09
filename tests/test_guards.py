"""Tests for the test-split guards (written before the scripts):
infra/scripts/check_split_lock.py and infra/scripts/eval_test_guard.py."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "infra" / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- split lock


@pytest.fixture()
def locked(tmp_path):
    lock = _load("check_split_lock")
    (tmp_path / "data" / "gold").mkdir(parents=True)
    f = tmp_path / "data" / "gold" / "c1.json"
    f.write_bytes(b'{"x": 1}\n')
    digest = hashlib.sha256(f.read_bytes()).hexdigest()
    lp = tmp_path / "test.lock"
    lp.write_text(f"# comment\n{digest}  data/gold/c1.json\n", "utf-8")
    return lock, tmp_path, lp, f


def test_lock_passes_when_unchanged(locked):
    lock, root, lp, _ = locked
    assert lock.check(lp, root, is_ignored=lambda p: False) == []


def test_lock_fails_when_file_edited(locked):
    lock, root, lp, f = locked
    f.write_bytes(b'{"x": 2}\n')
    problems = lock.check(lp, root, is_ignored=lambda p: False)
    assert problems and "CHANGED" in problems[0]


def test_lock_fails_when_tracked_file_missing(locked):
    lock, root, lp, f = locked
    f.unlink()
    assert lock.check(lp, root, is_ignored=lambda p: False)


def test_lock_tolerates_missing_gitignored_audio(locked):
    lock, root, lp, f = locked
    f.unlink()
    assert lock.check(lp, root, is_ignored=lambda p: True) == []


def test_lock_rejects_malformed_line(locked):
    lock, root, lp, _ = locked
    lp.write_text("not-a-hash data/x\n", "utf-8")
    assert lock.check(lp, root, is_ignored=lambda p: False)


def test_lock_cli_missing_lock_is_warning_only_with_flag(tmp_path, capsys):
    lock = _load("check_split_lock")
    assert lock.main(["--lock", str(tmp_path / "nope.lock"), "--allow-missing"]) == 0
    assert "WARNING" in capsys.readouterr().out
    assert lock.main(["--lock", str(tmp_path / "nope.lock")]) == 1


# ---------------------------------------------------------------- eval-test guard


class FakeGit:
    def __init__(self, tracked=True, clean=True, head="abc1234"):
        self.tracked, self.clean, self.head = tracked, clean, head

    def is_tracked(self, path):
        return self.tracked

    def is_clean(self, path):
        return self.clean

    def head_hash(self):
        return self.head


def test_guard_refuses_without_allow_test(tmp_path):
    g = _load("eval_test_guard")
    ok, msg = g.check({}, tmp_path, FakeGit())
    assert not ok and "ALLOW_TEST=1" in msg


def test_guard_refuses_without_purpose(tmp_path):
    g = _load("eval_test_guard")
    ok, msg = g.check({"ALLOW_TEST": "1"}, tmp_path, FakeGit())
    assert not ok and "PURPOSE" in msg


def test_guard_refuses_when_hypothesis_not_committed(tmp_path):
    g = _load("eval_test_guard")
    env = {"ALLOW_TEST": "1", "PURPOSE": "final run"}
    ok, msg = g.check(env, tmp_path, FakeGit(tracked=False))
    assert not ok and "hypothesis.md" in msg
    ok, msg = g.check(env, tmp_path, FakeGit(clean=False))
    assert not ok and "uncommitted" in msg


def test_guard_allows_and_logs(tmp_path):
    g = _load("eval_test_guard")
    env = {"ALLOW_TEST": "1", "PURPOSE": "final | run", "USER": "alice", "AGENT": "orchestrator"}
    ok, _ = g.check(env, tmp_path, FakeGit())
    assert ok
    g.append_log(env, tmp_path, FakeGit(head="deadbee"), now="2026-11-20T10:00:00Z")
    g.append_log(env, tmp_path, FakeGit(head="deadbee"), now="2026-11-20T11:00:00Z")
    log = (tmp_path / "results" / "test_access_log.md").read_text("utf-8")
    assert log.count("| date (UTC) |") == 1  # header written once
    assert "| 2026-11-20T10:00:00Z | deadbee | alice / orchestrator | final \\| run |" in log
    assert log.count("deadbee") == 2


def test_guard_main_exit_code_without_allow_test(tmp_path, monkeypatch, capsys):
    g = _load("eval_test_guard")
    monkeypatch.delenv("ALLOW_TEST", raising=False)
    assert g.main(["--root", str(tmp_path)]) != 0
    assert "REFUSED" in capsys.readouterr().err
