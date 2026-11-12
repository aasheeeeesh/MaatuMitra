"""Statistics for m7_eval (docs/metrics.md section 2; eval-rigor skill section 2).

- Wilson 95% interval for proportions (z = 1.959964), always with k and n.
- Rule of three for zero events: 95% upper bound ~ 3/n.
- Percentile bootstrap (1000 resamples, fixed seed) for means over utterances.
- PAIRED bootstrap on per-utterance differences (same utterances for both systems).
- CLUSTER bootstrap by template family for error rates (errors cluster by template, D-121):
  resample whole families with replacement, recompute sum(errors)/sum(fields).

Pure Python + numpy. Every function is deterministic given its seed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np

Z = 1.959964
N_RESAMPLES = 1000


def wilson(k: int, n: int, z: float = Z) -> tuple[float | None, float | None]:
    """Wilson 95% interval for k successes in n trials. (None, None) when n == 0."""
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"invalid proportion k={k} n={n}")
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return lo, hi


def rule_of_three(n: int) -> float | None:
    """95% upper bound for 0 events in n trials (about 3/n)."""
    return None if n <= 0 else 3.0 / n


def proportion(k: int, n: int) -> dict:
    """k, n, rate, Wilson CI and (only when k == 0) the rule-of-three upper bound."""
    lo, hi = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "rate": (k / n) if n else None,
        "wilson_lo": lo,
        "wilson_hi": hi,
        "rule_of_three_upper": rule_of_three(n) if k == 0 else None,
    }


def per_1000(k: int, n: int) -> dict:
    """Errors per 1,000 fields with Wilson bounds (scaled by 1000)."""
    lo, hi = wilson(k, n)
    return {
        "errors": k,
        "n_fields": n,
        "per_1000": 1000 * k / n if n else None,
        "wilson_lo_per_1000": None if lo is None else 1000 * lo,
        "wilson_hi_per_1000": None if hi is None else 1000 * hi,
    }


def _percentile_ci(values: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def bootstrap_mean_ci(
    xs: Sequence[float], seed: int, n_resamples: int = N_RESAMPLES
) -> tuple[float | None, float | None]:
    """Percentile bootstrap 95% CI of the mean."""
    if len(xs) == 0:
        return None, None
    arr = np.asarray(xs, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(n_resamples, len(arr)))
    means = arr[idx].mean(axis=1)
    return _percentile_ci(means)


def paired_bootstrap(
    a: Sequence[float], b: Sequence[float], seed: int, n_resamples: int = N_RESAMPLES
) -> dict:
    """Paired bootstrap of mean(a_i - b_i) on the SAME items. 'Different' only if the CI
    excludes 0."""
    if len(a) != len(b):
        raise ValueError("paired bootstrap needs the same items for both systems")
    if not a:
        return {"n": 0, "mean_diff": None, "ci_lo": None, "ci_hi": None, "excludes_zero": None}
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    lo, hi = bootstrap_mean_ci(d.tolist(), seed=seed, n_resamples=n_resamples)
    return {
        "n": len(d),
        "mean_diff": float(d.mean()),
        "ci_lo": lo,
        "ci_hi": hi,
        "excludes_zero": bool(lo > 0 or hi < 0),
        "seed": seed,
        "n_resamples": n_resamples,
    }


def cluster_bootstrap_rate(
    clusters: Mapping[str, tuple[int, int]], seed: int, n_resamples: int = N_RESAMPLES
) -> tuple[float | None, float | None]:
    """Cluster bootstrap 95% CI of sum(k)/sum(n), resampling whole clusters.
    clusters: {cluster_id: (k, n)}. Clusters are sorted by id so the result depends only on
    the data and the seed."""
    keys = sorted(clusters)
    if not keys:
        return None, None
    k = np.asarray([clusters[c][0] for c in keys], dtype=float)
    n = np.asarray([clusters[c][1] for c in keys], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(n_resamples, len(keys)))
    ks, ns = k[idx].sum(axis=1), n[idx].sum(axis=1)
    rates = np.divide(ks, ns, out=np.zeros_like(ks), where=ns > 0)
    return _percentile_ci(rates)


def fmt_prop(k: int, n: int) -> str:
    """'k/n = p [lo, hi]' with the rule-of-three note for zero events."""
    if n == 0:
        return f"{k}/{n} (not measurable)"
    lo, hi = wilson(k, n)
    s = f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]"
    if k == 0:
        s += f" (0 of {n}; 95% upper bound ~ 3/{n} = {3 / n:.3f})"
    return s
