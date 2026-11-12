"""Statistics unit tests against HAND-COMPUTED values (eval-rigor skill section 2).

Wilson 95% interval, z = 1.959964 (z^2 = 3.841459):
    p = k/n; centre = (p + z^2/(2n)) / (1 + z^2/n)
    half = z * sqrt(p(1-p)/n + z^2/(4n^2)) / (1 + z^2/n)
0/50: centre = 0.038415/1.076829 = 0.035674; half = 1.959964*0.0196/1.076829 = 0.035674
      -> [0, 0.0713]
3/50: p = 0.06; centre = (0.06 + 0.038415)/1.076829 = 0.091393
      half = 1.959964*sqrt(0.001128 + 0.0000384)/1.076829 = 0.070795 -> [0.0206, 0.1622]
"""

import pytest

from m7_eval import stats


def test_wilson_zero_of_fifty():
    lo, hi = stats.wilson(0, 50)
    assert lo == 0.0
    assert round(hi, 4) == 0.0713


def test_wilson_three_of_fifty():
    lo, hi = stats.wilson(3, 50)
    assert (round(lo, 4), round(hi, 4)) == (0.0206, 0.1622)


def test_wilson_all_successes_and_empty():
    lo, hi = stats.wilson(50, 50)
    assert round(lo, 4) == round(1 - 0.0713, 4) and hi == 1.0
    assert stats.wilson(0, 0) == (None, None)


def test_wilson_rejects_bad_input():
    with pytest.raises(ValueError):
        stats.wilson(5, 3)
    with pytest.raises(ValueError):
        stats.wilson(-1, 3)


def test_rule_of_three():
    assert stats.rule_of_three(500) == pytest.approx(0.006)
    assert stats.rule_of_three(1398) == pytest.approx(3 / 1398)
    assert stats.rule_of_three(0) is None


def test_proportion_row_has_k_n_ci_and_rule_of_three_for_zero():
    row = stats.proportion(0, 50)
    assert row["k"] == 0 and row["n"] == 50
    assert row["rule_of_three_upper"] == pytest.approx(0.06)
    assert round(row["wilson_hi"], 4) == 0.0713
    assert stats.proportion(3, 50)["rule_of_three_upper"] is None


def test_per_1000_uses_wilson_bounds():
    r = stats.per_1000(3, 50)
    assert r["per_1000"] == pytest.approx(60.0)
    assert round(r["wilson_lo_per_1000"], 1) == 20.6
    assert round(r["wilson_hi_per_1000"], 1) == 162.2


def test_bootstrap_mean_is_reproducible_with_seed():
    xs = [0.1, 0.4, 0.2, 0.9, 0.3, 0.5, 0.0, 0.7]
    a = stats.bootstrap_mean_ci(xs, seed=20261109, n_resamples=1000)
    b = stats.bootstrap_mean_ci(xs, seed=20261109, n_resamples=1000)
    c = stats.bootstrap_mean_ci(xs, seed=1, n_resamples=1000)
    assert a == b
    assert a != c
    assert a[0] <= sum(xs) / len(xs) <= a[1]
    assert 0.0 <= a[0] and a[1] <= 0.9


def test_bootstrap_constant_values_give_point_interval():
    assert stats.bootstrap_mean_ci([2.0] * 5, seed=3) == (2.0, 2.0)


def test_paired_bootstrap_reproducible_and_constant_difference():
    a = [0.30, 0.20, 0.50, 0.10]
    b = [0.20, 0.10, 0.40, 0.00]  # every difference is exactly 0.10
    r = stats.paired_bootstrap(a, b, seed=20261109)
    assert r["mean_diff"] == pytest.approx(0.10)
    assert r["ci_lo"] == pytest.approx(0.10) and r["ci_hi"] == pytest.approx(0.10)
    assert r["excludes_zero"] is True
    r1 = stats.paired_bootstrap([0.1, 0.5, 0.2, 0.9], [0.2, 0.1, 0.4, 0.3], seed=7)
    r2 = stats.paired_bootstrap([0.1, 0.5, 0.2, 0.9], [0.2, 0.1, 0.4, 0.3], seed=7)
    assert r1 == r2


def test_paired_bootstrap_needs_same_length():
    with pytest.raises(ValueError):
        stats.paired_bootstrap([1.0], [1.0, 2.0], seed=1)


def test_cluster_bootstrap_rate():
    # two clusters with the same rate 0.1 -> every resample has rate 0.1
    clusters = {"f1": (1, 10), "f2": (2, 20)}
    lo, hi = stats.cluster_bootstrap_rate(clusters, seed=20261109)
    assert lo == pytest.approx(0.1) and hi == pytest.approx(0.1)
    # unequal rates: interval is wider than the pooled Wilson interval would suggest
    clusters = {"f1": (0, 100), "f2": (0, 100), "f3": (30, 100)}
    lo, hi = stats.cluster_bootstrap_rate(clusters, seed=20261109)
    assert lo == 0.0 and hi >= 0.2
    assert stats.cluster_bootstrap_rate(clusters, seed=5) == stats.cluster_bootstrap_rate(
        clusters, seed=5
    )


def test_cluster_bootstrap_empty():
    assert stats.cluster_bootstrap_rate({}, seed=1) == (None, None)


def test_fmt_ci():
    assert stats.fmt_prop(3, 50) == "3/50 = 0.060 [0.021, 0.162]"
    assert stats.fmt_prop(0, 50).endswith("(0 of 50; 95% upper bound ~ 3/50 = 0.060)")
    assert stats.fmt_prop(0, 0) == "0/0 (not measurable)"
