"""Screen 6 data: real escaped errors from evaluation results, else a fixture list."""

from __future__ import annotations

from m6_ui import failures
from m6_ui.tests.helpers import ROOT


def test_reads_real_m4_e4_misses_when_present():
    rows = failures.load_failures(ROOT)
    assert rows
    if (ROOT / "results" / "m4_verify" / "e4" / "catch_rates.csv").exists():
        e4 = [r for r in rows if r.source.endswith("catch_rates.csv")]
        assert e4 and all(r.caught < r.n for r in e4)
        assert all(r.measured for r in e4)


def test_falls_back_to_fixture_list(tmp_path):
    rows = failures.load_failures(tmp_path)
    assert rows and all(not r.measured for r in rows)


def test_failure_markdown_files_are_listed(tmp_path):
    d = tmp_path / "results" / "m9_x"
    d.mkdir(parents=True)
    (d / "failure_cases.md").write_text("# a <script>x</script>", encoding="utf-8")
    rows = failures.load_failures(tmp_path)
    assert any(r.source.endswith("failure_cases.md") for r in rows)
