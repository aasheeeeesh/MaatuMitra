"""data/lexicon/drugs.csv: exact columns, provenance, and the 'no invented dose range' rule."""

from __future__ import annotations

import csv
import unicodedata

import pytest

from m1_data.lexicon import CSV_COLUMNS, LEXICON_CSV

REQUIRED_ANTIBIOTICS = {
    "amoxicillin",
    "amoxicillin-clavulanate",
    "azithromycin",
    "cefixime",
    "ciprofloxacin",
    "doxycycline",
    "metronidazole",
    "cotrimoxazole",
    "cephalexin",
    "ceftriaxone",
    "nitrofurantoin",
    "clarithromycin",
}
REQUIRED_OTHERS = {"paracetamol", "ibuprofen", "ors", "zinc", "cetirizine"}
KANNADA = range(0x0C80, 0x0D00)


@pytest.fixture(scope="module")
def rows():
    with LEXICON_CSV.open(encoding="utf-8", newline="") as fh:
        r = csv.DictReader(fh)
        assert r.fieldnames == CSV_COLUMNS
        return list(r)


def test_size_and_required_drugs(rows):
    assert 30 <= len(rows) <= 40
    names = {r["generic_en"] for r in rows}
    assert REQUIRED_ANTIBIOTICS | REQUIRED_OTHERS <= names
    assert sum(r["class"] == "antibiotic" for r in rows) >= 12
    assert len(names) == len(rows)
    assert len({r["id"] for r in rows}) == len(rows)


def test_every_row_cites_fetched_urls(rows):
    for r in rows:
        urls = r["source_url"].split("|")
        assert urls and all(u.startswith("https://") for u in urls), r["id"]
        assert "example.org" not in r["source_url"]
        if r["class"] == "antibiotic":
            assert "aware.essentialmeds.org" in r["source_url"], r["id"]
            assert r["aware_class"] in {"Access", "Watch", "Reserve"}
        else:
            assert r["aware_class"] == "not_applicable"


def test_dose_ranges_only_from_a_fetched_label(rows):
    for r in rows:
        has_label = "api.fda.gov" in r["source_url"]
        if r["adult_dose_range_mg"]:
            assert has_label, f"{r['id']}: dose range without a fetched label"
            lo, hi = (float(x) for x in r["adult_dose_range_mg"].split("-"))
            assert 0 < lo <= hi
        else:
            assert "dose UNVERIFIED" in r["verified_by"], r["id"]
        if r["max_daily_mg"]:
            assert has_label


def test_kannada_spellings_are_kannada_nfc_and_marked(rows):
    for r in rows:
        for s in [r["kn_primary"], *r["kn_variants"].split("|")]:
            assert s and unicodedata.normalize("NFC", s) == s
            assert any(ord(c) in KANNADA for c in s), (r["id"], s)
        assert "not native-validated" in r["verified_by"]
        assert r["kn_primary"] not in r["kn_variants"].split("|")


def test_nlem_values(rows):
    assert {r["nlem_listed"] for r in rows} <= {"yes", "UNVERIFIED"}
    for r in rows:
        if r["nlem_listed"] == "yes":
            assert "nppa.gov.in" in r["source_url"]


def test_confusables_are_documented(rows):
    names = {r["generic_en"] for r in rows}
    with_conf = [r for r in rows if r["confusable_with"]]
    assert len(with_conf) >= 20
    for r in with_conf:
        for c in r["confusable_with"].split("|"):
            assert c != r["generic_en"]
            if c not in names:  # out-of-lexicon names must be ISMP-cited
                assert "ISMP" in r["verified_by"], (r["id"], c)


def test_lexicon_rebuild_matches_committed():
    pytest.importorskip("indic_transliteration")  # optional extra `data`
    from m1_data.lexicon import build_rows, csv_text

    assert csv_text(build_rows()) == LEXICON_CSV.read_text(encoding="utf-8")
