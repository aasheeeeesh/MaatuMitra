"""End-to-end tests: mock tree (always), real DEV data (skipped if absent), test-split refusal,
'no test file opened' proof (patches open/read), and byte-identical reruns."""

import builtins
import csv
import io
import os
import pathlib
import subprocess
import sys
from pathlib import Path

import pytest

from m7_eval import guard, mock, report

REPO = Path(__file__).resolve().parents[2]
HAVE_DEV = (REPO / "data/splits/dev.txt").exists() and (REPO / "results/m4_verify/dev/e4").exists()


def _read_csv(p: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8"))))


@pytest.fixture(scope="module")
def mock_tree(tmp_path_factory):
    return mock.build_mock_root(REPO, tmp_path_factory.mktemp("mock_tree"))


class OpenRecorder:
    """Records every file path opened through builtins.open, io.open, Path.open/read_bytes."""

    def __init__(self, monkeypatch):
        self.paths: list[str] = []
        orig_open = builtins.open
        orig_read_bytes = pathlib.Path.read_bytes
        orig_path_open = pathlib.Path.open

        def rec_open(file, *a, **k):
            if isinstance(file, str | os.PathLike):
                self.paths.append(Path(file).as_posix())
            return orig_open(file, *a, **k)

        def rec_read_bytes(p):
            self.paths.append(Path(p).as_posix())
            return orig_read_bytes(p)

        def rec_path_open(p, *a, **k):
            self.paths.append(Path(p).as_posix())
            return orig_path_open(p, *a, **k)

        monkeypatch.setattr(builtins, "open", rec_open)
        monkeypatch.setattr(io, "open", rec_open)
        monkeypatch.setattr(pathlib.Path, "read_bytes", rec_read_bytes)
        monkeypatch.setattr(pathlib.Path, "open", rec_path_open)


def _independent_test_check(root: Path, paths: list[str]) -> list[str]:
    """Independent of guard.py: a path is a test file if it is in test.lock, or its file name
    contains a test id from test.txt, or it is under a 'test' folder inside data/ or results/."""
    test_ids = (root / "data/splits/test.txt").read_text(encoding="utf-8").split()
    lock = {
        line.split(maxsplit=1)[1]
        for line in (root / "data/splits/test.lock").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    bad = []
    for p in paths:
        rel = p.replace(root.resolve().as_posix() + "/", "")
        name = rel.rsplit("/", 1)[-1]
        if rel in ("data/splits/test.txt", "data/splits/test.lock"):
            continue  # membership files: read only to know which ids to avoid
        if rel in lock or any(
            f"{t}." in name or f"{t}_" in name or name.endswith(f"-{t}.json") for t in test_ids
        ):
            bad.append(rel)
        elif "/test/" in f"/{rel}" and (rel.startswith("data/") or rel.startswith("results/")):
            bad.append(rel)
    return bad


def test_mock_dev_run_writes_everything_and_opens_no_test_file(mock_tree, tmp_path, monkeypatch):
    rec = OpenRecorder(monkeypatch)
    out = tmp_path / "out"
    res = report.run(mock_tree, "dev", out, gh="mock")
    monkeypatch.undo()
    assert _independent_test_check(mock_tree, rec.paths) == []
    assert res["manifest"]["test_files_opened"] == []
    for name in (
        "e1_asr_summary",
        "e1_asr_paired",
        "e2_extraction_severity",
        "e3_ablation",
        "e4_planted_by_type",
        "e5_access",
        "e6_helper",
        "h1_dev_preview",
    ):
        assert (out / "tables" / f"{name}.csv").exists(), name
    for f in ("summary.md", "failure_gallery.md", "cost_report.md", "manifest.json"):
        assert (out / f).exists()
    assert list((out / "plots").glob("*.png"))
    e1 = _read_csv(out / "tables/e1_asr_summary.csv")
    assert {r["source"] for r in e1} == {"tts"}
    paired = _read_csv(out / "tables/e1_asr_paired.csv")
    assert paired[0]["baseline"] == "faster-whisper-small-int8"
    assert int(paired[0]["n_common_utterances"]) == 8
    # m8 test rows are dropped
    e6 = _read_csv(out / "tables/e6_helper.csv")
    assert e6[0]["in_scope_answered_from_correct_card_n"] == "2"


def test_mock_reproducible(mock_tree, tmp_path):
    a = report.run(mock_tree, "dev", tmp_path / "a", gh="mock")["manifest"]
    b = report.run(mock_tree, "dev", tmp_path / "b", gh="mock")["manifest"]
    assert a["outputs"] == b["outputs"]


def test_e1_reports_m2_not_run_when_absent(mock_tree, tmp_path):
    import shutil

    tree = tmp_path / "t"
    shutil.copytree(mock_tree, tree)
    shutil.rmtree(tree / "results/m2_asr")
    report.run(tree, "dev", tmp_path / "o", gh="mock")
    rows = _read_csv(tmp_path / "o/tables/e1_asr_summary.csv")
    assert rows[0]["status"] == "m2 not run yet"


def test_eval_test_refuses_without_allow_test(mock_tree, tmp_path):
    with pytest.raises(guard.TestSplitRefused):
        report.run(mock_tree, "test", tmp_path / "o", env={}, gh="mock")
    assert not (mock_tree / "results/test_access_log.md").exists()
    assert not (tmp_path / "o").exists()


def test_eval_test_path_works_on_fake_tree_after_logging(mock_tree, tmp_path, monkeypatch):
    import shutil

    tree = tmp_path / "t"
    shutil.copytree(mock_tree, tree)
    (tree / "results/m3_extract/test/rules").mkdir(parents=True)
    for cid in mock.TEST:
        shutil.copy(
            tree / f"results/m3_extract/rules/rules-{cid}.json",
            tree / "results/m3_extract/test/rules",
        )
    log = tree / "results/test_access_log.md"
    log.write_text(
        "| 2026-11-12T00:00:00Z | fake123 | pytest | fake tree only |\n", encoding="utf-8"
    )
    env = {"ALLOW_TEST": "1", "PURPOSE": "unit test on a FAKE tree"}
    res = report.run(tree, "test", tmp_path / "o", env=env, gh="fake123")
    sl = _read_csv(tmp_path / "o/tables/e2_extraction_slices.csv")
    assert any(r["slice"] == "frame_status" for r in sl)
    assert any(r["slice"] == "required_test_slice" for r in sl)
    assert res["manifest"]["split"] == "test"


def test_cli_eval_test_refuses_on_real_repo_and_logs_nothing():
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_TEST", "PURPOSE")}
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "m7_eval",
            "eval-test",
            "--out",
            str(REPO / "results/m7_eval/_refused"),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 3
    assert "REFUSED" in r.stderr
    assert not (REPO / "results/test_access_log.md").exists()
    assert not (REPO / "results/m7_eval/_refused").exists()


@pytest.mark.skipif(not HAVE_DEV, reason="real DEV outputs not present")
def test_real_dev_run_opens_no_test_file_and_matches_module_tables(tmp_path, monkeypatch):
    rec = OpenRecorder(monkeypatch)
    out = tmp_path / "dev"
    res = report.run(REPO, "dev", out, gh="pytest")
    monkeypatch.undo()
    assert _independent_test_check(REPO, rec.paths) == []
    assert res["manifest"]["test_files_opened"] == []
    # independent re-scoring agrees with m3's own dev table (same field unit)
    sev = {
        (r["system"], r["subset"], r["severity"]): r
        for r in _read_csv(out / "tables/e2_extraction_severity.csv")
    }
    full = sev[("rules", "full_dev", "critical")]
    assert (full["errors"], full["n_fields"]) == ("0", "3624")
    assert sev[("rules", "full_dev", "major")]["errors"] == "48"
    # E4 recomputed from raw rows equals m4's own catch_rates.csv
    m4 = {
        (r["level"], r["condition"], r["type"]): r
        for r in _read_csv(REPO / "results/m4_verify/dev/e4/catch_rates.csv")
    }
    for r in _read_csv(out / "tables/e4_planted_by_type.csv"):
        ref = m4[(r["level"], r["condition"], r["type"])]
        assert r["caught_at_field_k"] == ref["caught_at_field_unique"]
        assert r["caught_at_field_n"] == ref["n_unique"]
        assert r["detected_k"] == ref["detected_unique"]
    gal = res["gallery"]
    assert len(gal) >= 10
    assert sum(1 for g in gal if g["dangerous"] and g["slipped_through"]) >= 3


def test_fresh_llm_outputs_are_scored_and_paired(mock_tree, tmp_path):
    import json as _json
    import shutil

    tree = tmp_path / "t"
    shutil.copytree(mock_tree, tree)
    llm = tree / "results/m3_extract/llm"
    llm.mkdir(parents=True)
    for cid in mock.DEV[:3]:
        rec = _json.loads(
            (tree / f"results/m3_extract/rules/rules-{cid}.json").read_text(encoding="utf-8")
        )
        rec["symptoms"] = []  # the fake LLM misses every symptom
        (llm / f"llm-{cid}.json").write_text(_json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    report.run(tree, "dev", tmp_path / "o", gh="mock")
    sev = _read_csv(tmp_path / "o/tables/e2_extraction_severity.csv")
    assert any(r["system"] == "llm" and r["severity"] == "major" for r in sev)
    assert not any("STALE" in r.get("label", "") for r in sev)
    paired = _read_csv(tmp_path / "o/tables/e2_rules_vs_llm_paired.csv")
    assert paired[0]["n_common_conversations"] == "3"
    assert float(paired[1]["mean_diff_errors_per_field"]) > 0
