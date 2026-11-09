"""Tests for shared, non-contract assets written by the architect (tests first):
- fixtures/lexicon/drugs_fixture.csv (exact m1 column set, clearly FIXTURE ONLY)
- .claude/skills/kannada-nlp/negation_table.yaml (machine-readable starter table)
- .claude/agents (14) and .claude/skills (5) exist with frontmatter
"""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

import regex
import yaml

ROOT = Path(__file__).resolve().parents[1]
LEXICON_COLUMNS = [
    "id", "generic_en", "kn_primary", "kn_variants", "roman_variants", "class", "aware_class",
    "nlem_listed", "strengths_mg", "adult_dose_range_mg", "max_daily_mg", "confusable_with",
    "source_url", "verified_by",
]  # fmt: skip
TABLE = ROOT / ".claude" / "skills" / "kannada-nlp" / "negation_table.yaml"
TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
TYPES = {
    "strong_whole_token", "suffix", "verb_lexicon_suffix", "soft_suffix", "compound",
    "clause_splitter_punct", "clause_splitter_word", "cross_turn", "must_not_trigger",
}  # fmt: skip


def test_lexicon_fixture_columns_and_marking():
    p = ROOT / "fixtures" / "lexicon" / "drugs_fixture.csv"
    with p.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fh.seek(0)
        header = next(csv.reader(fh))
    assert header == LEXICON_COLUMNS
    assert 6 <= len(rows) <= 8
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert "FIXTURE_ONLY" in r["verified_by"]
        assert r["source_url"].startswith("https://example.org/")
        for v in r.values():
            assert unicodedata.normalize("NFC", v) == v
        assert any("ಀ" <= ch <= "೿" for ch in r["kn_primary"])
    drugs = {r["generic_en"] for r in rows}
    # every drug used by the record fixtures exists in the fixture lexicon
    assert {"amoxicillin", "azithromycin", "paracetamol"} <= drugs


def _table():
    return yaml.safe_load(TABLE.read_text(encoding="utf-8"))


def test_negation_table_entries_well_formed():
    t = _table()
    ids = [e["id"] for e in t["entries"]]
    assert len(ids) == len(set(ids))
    for e in t["entries"]:
        assert {"id", "type", "pattern", "example", "status"} <= e.keys(), e
        assert e["type"] in TYPES, e
        assert e["status"] == "hypothesis_unverified", e
        regex.compile(e["pattern"])
        assert unicodedata.normalize("NFC", e["example"]) == e["example"]
    for needed in TYPES:
        assert any(e["type"] == needed for e in t["entries"]), needed


def test_strong_and_suffix_examples_contain_a_matching_token():
    for e in _table()["entries"]:
        if e["type"] in {"strong_whole_token", "suffix", "verb_lexicon_suffix", "soft_suffix"}:
            toks = TOKEN.findall(e["example"])
            assert any(regex.search(e["pattern"], tok) for tok in toks), e["id"]


def test_trap_tokens_do_not_match_any_strong_or_suffix_cue():
    entries = _table()["entries"]
    cues = [e for e in entries if e["type"] in {"strong_whole_token", "suffix"}]
    traps = [e for e in entries if e["type"] == "must_not_trigger"]
    assert {"ಎಲ್ಲ", "ಎಲ್ಲಾ", "ಇಲ್ಲಿ", "ಅಲ್ಲಿ", "ಅಲ್ವಾ", "ಅಲ್ವ", "ಮಾತ್ರ", "ಮಾತ್ರೆ"} <= {
        t["token"] for t in traps
    }
    for t in traps:
        for c in cues:
            assert not regex.search(c["pattern"], t["token"]), (t["id"], c["id"])


def test_soft_cue_exclusions_cover_whole_token_traps():
    t = _table()
    soft = [e for e in t["entries"] if e["type"] == "soft_suffix"]
    for s in soft:
        for trap in ("ಎಲ್ಲ", "ಎಲ್ಲಾ", "ಇಲ್ಲ", "ಅಲ್ಲ"):
            assert (trap in s["exclude_tokens"]) or not regex.search(s["pattern"], trap)


def _frontmatter(p: Path) -> dict:
    text = p.read_text(encoding="utf-8")
    assert text.startswith("---\n"), p
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_fourteen_agents_with_preamble():
    files = sorted((ROOT / ".claude" / "agents").glob("*.md"))
    assert len(files) == 14
    for f in files:
        fm = _frontmatter(f)
        assert fm["name"] == f.stem and fm["description"] and fm["tools"]
        body = f.read_text(encoding="utf-8").split("---\n", 2)[2]
        assert "Stay inside your allowed files. Follow PROJECT_BRIEF.md" in body.splitlines()[1]
        assert "Return a report of at most 300 words." in body
        assert "handoff" in body
        if fm["name"] in {"kannada-language-reviewer", "clinical-reviewer"}:
            assert set(fm["tools"].split(", ")) == {
                "Read", "Grep", "Glob", "WebSearch", "WebFetch", "Write",
            }  # fmt: skip


def test_five_skills():
    names = {"kannada-nlp", "secure-backend", "eval-rigor", "frontend-design",
             "plain-language-decisions"}  # fmt: skip
    for n in names:
        fm = _frontmatter(ROOT / ".claude" / "skills" / n / "SKILL.md")
        assert fm["name"] == n and len(fm["description"]) > 40
