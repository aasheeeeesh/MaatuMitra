"""Small statistics helpers (own copy; m7_eval code is not imported)."""

from __future__ import annotations

import math

Z = 1.959964


def wilson(k: int, n: int, z: float = Z) -> tuple[float, float]:
    """Wilson 95% score interval for k successes out of n (docs/metrics.md)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def rule_of_three(n: int) -> float:
    return 3.0 / n if n else float("nan")
