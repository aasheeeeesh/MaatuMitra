"""E4 reporting rules from the integrity review (D-90): field-level attribution, unique N with
Wilson CIs, review burden next to recall, cannot_verify kept apart, oracle second transcript
labelled as an upper bound."""

from __future__ import annotations

import json

import pytest

from m4_verify.config import default_config
from m4_verify.evaluate import ORACLE, at_field, run_e4, unique_outcomes
from m4_verify.lexicon import load_lexicon
from m4_verify.stats import wilson
from m4_verify.tests.helpers import FIX


# Wilson 95% (z = 1.959964): p=k/n; centre=(p+z^2/2n)/(1+z^2/n);
# half=z*sqrt(p(1-p)/n+z^2/4n^2)/(1+z^2/n). Hand values from the eval-rigor skill.
@pytest.mark.parametrize(
    ("k", "n", "lo", "hi"),
    [(0, 50, 0.0, 0.0713), (3, 50, 0.0206, 0.1622), (4, 4, 0.5101, 1.0), (1, 18, 0.0099, 0.2576)],
)
def test_wilson_hand_values(k, n, lo, hi):
    a, b = wilson(k, n)
    assert round(a, 4) == pytest.approx(lo, abs=1e-4) and round(b, 4) == pytest.approx(hi, abs=1e-4)


def F(path, reason="x", cid="C2"):
    return {"check_id": cid, "status": "flag", "reason": reason, "field_path": path}


def test_at_field_requires_the_injected_field_or_its_item():
    # integrity M4-2: a paracetamol C4 flag must NOT count as catching a wrong patient_ref
    assert not at_field(F("/medications/1/dose_value"), "/patient_ref")
    assert at_field(F("/patient_ref", cid="C6"), "/patient_ref")
    assert not at_field(F("/"), "/medications/0/drug")  # record-level flags are not attributed
    assert at_field(F("/medications/0"), "/medications/0/drug")  # item-level (C7/C8)
    assert not at_field(F("/medications/1"), "/medications/0/drug")
    assert at_field(F("/medications/0/dose_unit"), "/medications/0/dose_value")  # dose pair
    assert not at_field(F("/medications/0/duration_days"), "/medications/0/dose_value")
    mx = F("/medications/0/frequency_per_day", "exceeds_max_daily [CR-DOSE]: y", "C4")
    assert at_field(mx, "/medications/0/dose_value")
    assert at_field(F("/symptoms/2/present", cid="C3"), "/symptoms/2/present")


def test_unique_outcomes_count_each_mutation_once():
    rows = [{"unique_key": "a", "caught": True}] * 50 + [{"unique_key": "b", "caught": False}] * 150
    k, n, mixed = unique_outcomes(rows, "caught")
    assert (k, n, mixed) == (1, 2, 0)
    k, n, mixed = unique_outcomes([*rows, {"unique_key": "a", "caught": False}], "caught")
    assert mixed == 1  # repeats of one mutation disagree: reported, counted as NOT caught


@pytest.fixture(scope="module")
def small_e4(tmp_path_factory):
    out = tmp_path_factory.mktemp("e4out")
    lex = load_lexicon(FIX / "lexicon" / "drugs_fixture.csv")
    s = run_e4(FIX / "gold" / "valid", lex, default_config(), out, n_per_type=12, seed=5)
    return s, out


def test_e4_summary_reports_unique_field_level_and_burden(small_e4):
    s, out = small_e4
    assert s["gold_load"]["n_loaded"] == 6
    row = s["catch_rates"][0]
    for k in (
        "n_unique",
        "caught_at_field_unique",
        "caught_at_field_wilson_lo",
        "detected_unique",
        "sent_to_review_unique",
        "n_injections",
    ):
        assert k in row, k
    conds = {r["condition"] for r in s["catch_rates"]}
    assert ORACLE in conds and "with_second_transcript" not in conds
    clean = {r["unit"]: r for r in s["clean_flag_rate"]}
    assert {"flagged", "flagged_excl_cannot_verify"} <= set(clean["field"])
    md = (out / "e4" / "summary.md").read_text(encoding="utf-8")
    assert "upper bound" in md.lower() and "Review burden" in md
    assert "n_unique" in md or "unique" in md
    per_field = (out / "e4" / "per_field.csv").read_text(encoding="utf-8")
    assert "dose_value" in per_field and "patient_ref" in per_field
    res = [
        json.loads(x)
        for x in (out / "e4" / "injection_results.jsonl").read_text("utf-8").split("\n")
        if x
    ]
    assert all("caught_at_field" in r and "detected_at_field" in r for r in res)


def test_e4_record_level_negation_and_digit_errors_are_caught_at_the_field(small_e4):
    """DONE-WHEN (brief AGENT 5): 100% of record-level negation drops and number swaps."""
    s, _ = small_e4
    for r in s["catch_rates"]:
        if r["level"] == "record" and r["type"] in ("a", "c", "d"):
            assert r["caught_at_field_unique"] == r["n_unique"] > 0, r
            assert r["detected_unique"] == r["n_unique"], r
