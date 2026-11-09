"""Tests for infra/scripts/merge_handoff.py (written before the script)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "infra" / "scripts" / "merge_handoff.py"


def _mod():
    spec = importlib.util.spec_from_file_location("merge_handoff", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


DECISIONS = """# Decisions explained

## Index

| ID | Phase / module | Short title | Status | One-line outcome |
|---|---|---|---|---|
| D-1 | Phase A / architect | First | done | ok |
| D-2 | Phase A / architect | Second | done | ok |
| D-3 | Phase A / architect | Third | done | ok |
<!-- INDEX-END -->

## Entries

### D-1: First   (Phase A / architect / architect / 2026-11-09)
- Status: done

### D-2: Second   (Phase A / architect / architect / 2026-11-09)
- Status: done

### D-3: Third   (Phase A / architect / architect / 2026-11-09)
- Status: done

<!-- ENTRIES-END -->

## REVIEWER FINDINGS

(none yet)
"""

MODULE_DECISIONS = """### D-?: Use seed 1234 for the generator   (Phase B / m1_data / data-scientist / 2026-11-10)
- What we needed to decide: which seed.
- Options we considered: any.
- What we chose: seed 1234 | fixed in data/generate.py
- Why: reproducible.
- What we actually did: added --seed.
- What could go wrong / weaknesses: none known.
- What else could be done: nothing.
- How to change this decision later: edit data/generate.py.
- Status: done

### D-17: Split by template family   (Phase B / m1_data / data-scientist / 2026-11-10)
- What we chose: family-level split
- Status: partly done
"""

GLOSSARY = """# Glossary

- **NFC**: a standard way to store Unicode text.
- **CER**: character error rate.
<!-- GLOSSARY-END -->
"""

LICENCES = """# Licences

| Item | Type | Licence | URL fetched | Allowed for coursework |
|---|---|---|---|---|
| uv | tool | MIT OR Apache-2.0 | UNVERIFIED | yes |
<!-- LICENCES-END -->
"""


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DECISIONS_EXPLAINED.md").write_text(DECISIONS, "utf-8")
    (tmp_path / "docs" / "glossary.md").write_text(GLOSSARY, "utf-8")
    (tmp_path / "docs" / "ai_usage.md").write_text("# AI usage\n", "utf-8")
    (tmp_path / "docs" / "open_questions.md").write_text("# Open questions\n", "utf-8")
    (tmp_path / "docs" / "licences.md").write_text(LICENCES, "utf-8")
    (tmp_path / "HUMAN_TODO.md").write_text("# HUMAN TODO\n", "utf-8")
    h = tmp_path / "m1_data" / "handoff"
    h.mkdir(parents=True)
    (h / "decisions.md").write_text(MODULE_DECISIONS, "utf-8")
    (h / "glossary.md").write_text(
        "- **cer**: duplicate, must be skipped\n"
        "- **Template family**: a group of sentence templates\n"
        "  that share one frame.\n",
        "utf-8",
    )
    (h / "ai_usage.md").write_text("- data-scientist generated data/generate.py\n", "utf-8")
    (h / "human_todo.md").write_text("- [ ] check Kannada templates\n", "utf-8")
    (h / "open_questions.md").write_text("- Is ಬಾರದು always negation?\n", "utf-8")
    (h / "licences.md").write_text(
        "| Item | Type | Licence | URL fetched | Allowed for coursework |\n"
        "|---|---|---|---|---|\n"
        "| uv | tool | MIT OR Apache-2.0 | UNVERIFIED | yes |\n"
        "| FLEURS | dataset | CC-BY-4.0 | https://example.org/x | UNVERIFIED |\n",
        "utf-8",
    )
    return tmp_path


def _read(p: Path) -> str:
    return p.read_text("utf-8")


def test_decisions_renumbered_and_indexed(repo):
    _mod().merge(repo, "m1_data", timestamp="20261110T000000Z")
    d = _read(repo / "docs" / "DECISIONS_EXPLAINED.md")
    assert "### D-4: Use seed 1234 for the generator" in d
    assert "### D-5: Split by template family" in d
    assert "D-?" not in d and "D-17" not in d
    # entries go before the end marker, i.e. before REVIEWER FINDINGS
    assert d.index("### D-5:") < d.index("<!-- ENTRIES-END -->") < d.index("## REVIEWER FINDINGS")
    # index rows added before the index marker, with status parsed and pipes escaped
    idx = d[: d.index("<!-- INDEX-END -->")]
    assert "| D-4 | Phase B / m1_data | Use seed 1234 for the generator | done |" in idx
    assert "seed 1234 \\| fixed in data/generate.py" in idx
    assert "| D-5 | Phase B / m1_data | Split by template family | partly done |" in idx


def test_glossary_skips_existing_terms_case_insensitive(repo):
    _mod().merge(repo, "m1_data", timestamp="20261110T000000Z")
    g = _read(repo / "docs" / "glossary.md")
    assert "duplicate, must be skipped" not in g
    assert "- **Template family**: a group of sentence templates\n  that share one frame." in g
    assert g.index("Template family") < g.index("<!-- GLOSSARY-END -->")


def test_licence_rows_deduplicated(repo):
    _mod().merge(repo, "m1_data", timestamp="20261110T000000Z")
    lic = _read(repo / "docs" / "licences.md")
    assert lic.count("| uv | tool |") == 1
    assert lic.count("|---|---|---|---|---|") == 1
    assert "| FLEURS | dataset | CC-BY-4.0 |" in lic
    assert lic.index("FLEURS") < lic.index("<!-- LICENCES-END -->")


def test_plain_parts_appended_with_module_heading(repo):
    _mod().merge(repo, "m1_data", timestamp="20261110T000000Z")
    assert "## From m1_data" in _read(repo / "HUMAN_TODO.md")
    assert "- [ ] check Kannada templates" in _read(repo / "HUMAN_TODO.md")
    assert "Is ಬಾರದು always negation?" in _read(repo / "docs" / "open_questions.md")
    assert "generated data/generate.py" in _read(repo / "docs" / "ai_usage.md")


def test_parts_moved_and_second_run_is_noop(repo):
    m = _mod()
    m.merge(repo, "m1_data", timestamp="20261110T000000Z")
    h = repo / "m1_data" / "handoff"
    assert not (h / "decisions.md").exists()
    assert (h / "merged" / "20261110T000000Z" / "decisions.md").exists()
    before = _read(repo / "docs" / "DECISIONS_EXPLAINED.md")
    m.merge(repo, "m1_data", timestamp="20261110T000001Z")
    assert _read(repo / "docs" / "DECISIONS_EXPLAINED.md") == before


def test_comment_only_part_is_skipped_and_left_in_place(repo):
    h = repo / "m1_data" / "handoff"
    (h / "human_todo.md").write_text("<!-- builder: add items here -->\n\n", "utf-8")
    _mod().merge(repo, "m1_data", timestamp="20261110T000000Z")
    assert "## From m1_data" not in _read(repo / "HUMAN_TODO.md")
    assert (h / "human_todo.md").exists()


def test_missing_marker_fails_without_changing_anything(repo):
    p = repo / "docs" / "DECISIONS_EXPLAINED.md"
    p.write_text(DECISIONS.replace("<!-- ENTRIES-END -->", ""), "utf-8")
    snapshot = {f: _read(f) for f in repo.rglob("*.md")}
    with pytest.raises(ValueError, match="ENTRIES-END"):
        _mod().merge(repo, "m1_data", timestamp="20261110T000000Z")
    assert {f: _read(f) for f in repo.rglob("*.md")} == snapshot


def test_unknown_module_rejected(repo):
    with pytest.raises(FileNotFoundError):
        _mod().merge(repo, "m9_nothing", timestamp="20261110T000000Z")


def test_dry_run_changes_nothing(repo):
    snapshot = {f: _read(f) for f in repo.rglob("*.md")}
    report = _mod().merge(repo, "m1_data", timestamp="20261110T000000Z", dry_run=True)
    assert "D-4" in report
    assert {f: _read(f) for f in repo.rglob("*.md")} == snapshot


def test_cli_runs(repo):
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "m1_data", "--root", str(repo)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, res.stderr
    assert "### D-4:" in _read(repo / "docs" / "DECISIONS_EXPLAINED.md")


def test_insert_uses_last_marker_when_text_quotes_it():
    """Regression: an entry that quotes the marker must not receive inserted text."""
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location(
        "merge_handoff_mod", pathlib.Path(__file__).parents[1] / "infra/scripts/merge_handoff.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = "entry quotes `<!-- M -->` here\nreal end\n<!-- M -->\n"
    out = mod._insert_before(doc, "<!-- M -->", "NEW\n", "x")
    assert out.index("NEW") > out.index("real end")
    assert "quotes `<!-- M -->` here" in out
