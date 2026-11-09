"""Check that no frozen TEST-split file (or its gold label) has changed.

Lock format (data/splits/test.lock, written by m1_data), one line per file:
    <sha256 hex, lower case><two spaces><POSIX path relative to repo root>
Lines starting with '#' and blank lines are ignored (same format as `sha256sum`).

A file listed in the lock that is missing is an ERROR, unless git ignores it
(large audio is git-ignored and rebuilt by `make data`); then it is a warning.

    uv run python infra/scripts/check_split_lock.py [--lock data/splits/test.lock] [--allow-missing]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LINE = re.compile(r"^(?P<sha>[0-9a-f]{64}) [ *](?P<path>\S.*)$")
ROOT = Path(__file__).resolve().parents[2]


def git_ignored(root: Path) -> Callable[[str], bool]:
    def _is(path: str) -> bool:
        try:
            r = subprocess.run(
                ["git", "check-ignore", "-q", path], cwd=root, capture_output=True, check=False
            )
        except OSError:
            return False
        return r.returncode == 0

    return _is


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(lock: Path, root: Path, is_ignored: Callable[[str], bool]) -> list[str]:
    problems: list[str] = []
    for n, raw in enumerate(lock.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE.match(line)
        if not m:
            problems.append(f"{lock.name}:{n}: malformed line {raw!r}")
            continue
        rel = m.group("path")
        p = root / rel
        if not p.exists():
            if is_ignored(rel):
                print(f"WARNING: {rel} missing (git-ignored; rebuild with `make data`)")
                continue
            problems.append(f"{rel}: listed in test.lock but missing")
            continue
        if sha256_file(p) != m.group("sha"):
            problems.append(f"{rel}: CHANGED since the test split was frozen")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lock", type=Path, default=ROOT / "data" / "splits" / "test.lock")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument(
        "--allow-missing",
        action="store_true",
        help="exit 0 with a warning if the lock file does not exist yet",
    )
    args = ap.parse_args(argv)
    if not args.lock.exists():
        msg = f"{args.lock} not found (m1_data has not frozen the test split yet)"
        if args.allow_missing:
            print(f"WARNING: {msg}; split-lock check skipped")
            return 0
        print(f"ERROR: {msg}")
        return 1
    problems = check(args.lock, args.root, git_ignored(args.root))
    for p in problems:
        print(f"ERROR: {p}")
    print("split-lock:", "FAIL" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
