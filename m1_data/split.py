"""Dev/test split planning and the frozen-test lock (PROJECT_BRIEF 6.5).

Split unit 1: TEMPLATE FAMILY. Inside each category (a)..(i) the families are shuffled
with a fixed seed and half (at least one) go to test, so every category is in both splits
but no family (= no set of near-duplicate sentence frames) is in both.
Split unit 2: DRUG-DOSE COMBINATION. Each drug's dosed combinations (drug, value, unit)
alternate between dev and test (seeded); a conversation draws dosed drugs only from its own
split's pool. Bare drug mentions without a dose may appear in both splits.

Lock format = infra/scripts/check_split_lock.py: `<sha256>  <posix path>` per line.
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from pathlib import Path

from m1_data.config import ROOT, SEED

LOCK_PATH = ROOT / "data" / "splits" / "test.lock"


def seed_int(*parts: object) -> int:
    h = hashlib.sha256(":".join(str(p) for p in (SEED, *parts)).encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def plan_families(templates) -> dict[str, str]:
    by_cat: dict[str, set[str]] = defaultdict(set)
    for t in templates:
        by_cat[t.category].add(t.family)
    out = {}
    for cat in sorted(by_cat):
        fams = sorted(by_cat[cat])
        random.Random(seed_int("family-split", cat)).shuffle(fams)  # noqa: S311
        n_test = max(1, len(fams) // 2) if len(fams) > 1 else 0
        for i, f in enumerate(fams):
            out[f] = "test" if i < n_test else "dev"
    return out


def plan_combos(lex) -> dict[tuple, str]:
    out = {}
    for g in sorted(lex):
        combos = sorted(lex[g].dosed_combos(), key=lambda c: (c[2], float(c[1])))
        rng = random.Random(seed_int("combo-split", g))  # noqa: S311
        rng.shuffle(combos)
        start = rng.randrange(2)
        for i, c in enumerate(combos):
            out[c] = ("dev", "test")[(i + start) % 2]
    return out


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def lock_text(entries: dict[str, str], header: str) -> str:
    lines = [f"# {h}" for h in header.splitlines()]
    lines += [f"{sha}  {path}" for path, sha in sorted(entries.items())]
    return "\n".join(lines) + "\n"


def read_lock(lock: Path) -> dict[str, str]:
    out = {}
    for raw in lock.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sha, path = line.split(maxsplit=1)
        out[path.lstrip("*").strip()] = sha
    return out


def verify_lock(lock: Path, root: Path) -> list[str]:
    """Problems (empty = OK): any locked file missing or with a different sha256."""
    problems = []
    for rel, sha in read_lock(lock).items():
        p = root / rel
        if not p.exists():
            problems.append(f"{rel}: listed in test.lock but missing")
        elif sha256_bytes(p.read_bytes()) != sha:
            problems.append(f"{rel}: CHANGED since the test split was frozen")
    return problems
