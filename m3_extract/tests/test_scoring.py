import copy

import pytest

from m3_extract.scoring import aggregate, score_record, wilson
from m3_extract.tests._helpers import FIX, load_json


def test_wilson_hand_values():
    # Wilson 95%, z = 1.959964:
    # centre = (p + z^2/2n)/(1+z^2/n); half = z*sqrt(p(1-p)/n + z^2/4n^2)/(1+z^2/n)
    lo, hi = wilson(0, 50)
    assert lo == pytest.approx(0.0, abs=1e-4) and hi == pytest.approx(0.0713, abs=1e-4)
    lo, hi = wilson(3, 50)
    assert lo == pytest.approx(0.0206, abs=1e-4) and hi == pytest.approx(0.1622, abs=1e-4)
    assert wilson(0, 0) == (None, None)


def gold_and_perfect(cid="fx-pharm-003"):
    g = load_json(FIX / "gold" / "valid" / f"{cid}.json")
    rec = load_json(FIX / "record" / "valid" / f"rec-{cid}.json")
    return g, rec


def codes(results):
    return sorted(r.code for r in results if r.code)


def test_perfect_record_has_no_errors_and_counts_fields():
    g, rec = gold_and_perfect()
    res = score_record(rec, g)
    assert codes(res) == []
    # 1 medication x 6 + 2 advice x 2 + follow-up 1 = 11 fields
    assert len(res) == 11


def test_negation_flip_is_critical():
    g, rec = gold_and_perfect()
    rec["medications"][0]["negated"] = True
    res = score_record(rec, g)
    assert codes(res) == ["CR-NEG"]
    assert [r.severity for r in res if r.code] == ["critical"]


def test_dose_freq_duration_mismatches():
    g, rec = gold_and_perfect()
    m = rec["medications"][0]
    m["dose_value"], m["dose_unit"], m["frequency_per_day"], m["duration_days"] = 50, "ml", 2, None
    assert codes(score_record(rec, g)) == ["CR-DOSE", "CR-DOSE", "CR-DUR", "CR-FREQ"]


def test_missing_and_unsupported_drug():
    g, rec = gold_and_perfect()
    extra = copy.deepcopy(rec["medications"][0])
    extra["drug"] = "cefixime"
    extra["evidence"]["char_start"], extra["evidence"]["char_end"] = 500, 501  # no overlap
    rec["medications"] = [extra]
    assert codes(score_record(rec, g)) == ["CR-UNSUPPORTED", "MA-MISSED-DRUG"]


def test_wrong_drug_on_same_span_is_cr_drug():
    g, rec = gold_and_perfect()
    rec["medications"][0]["drug"] = "ampicillin"
    assert codes(score_record(rec, g)) == ["CR-DRUG"]


def test_symptom_errors():
    g, rec = gold_and_perfect("fx-asha-001")
    rec["symptoms"][1]["present"] = True  # cough absent -> present
    assert codes(score_record(rec, g)) == ["CR-NEG"]
    g, rec = gold_and_perfect("fx-asha-001")
    extra = copy.deepcopy(rec["symptoms"][0])
    extra["name"] = "vomiting"
    rec["symptoms"] = [rec["symptoms"][0], extra]
    assert codes(score_record(rec, g)) == ["MA-EXTRA-SYMPTOM", "MA-MISSED-SYMPTOM"]


def test_advice_wording_unjudged_is_major():
    g, rec = gold_and_perfect()
    rec["advice"][0]["text"] = "after meals"
    res = score_record(rec, g)
    assert codes(res) == ["MA-WORDING-UNJUDGED"]
    assert [r.severity for r in res if r.code] == ["major"]


def test_rejected_record_scores_as_all_missed():
    g, _ = gold_and_perfect()
    res = score_record(None, g)
    assert codes(res) == ["MA-MISSED-ADVICE", "MA-MISSED-ADVICE", "MA-MISSED-DRUG"]


def test_aggregate_per_1000_with_ci():
    g, rec = gold_and_perfect()
    rec["medications"][0]["negated"] = True
    rows = aggregate(score_record(rec, g))
    crit = next(r for r in rows if r["severity"] == "critical")
    assert crit["errors"] == 1 and crit["n_fields"] == 11
    assert crit["per_1000"] == pytest.approx(1000 / 11)
    assert crit["ci_low_per_1000"] < crit["per_1000"] < crit["ci_high_per_1000"]
