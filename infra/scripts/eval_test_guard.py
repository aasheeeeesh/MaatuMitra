"""Guard for `make eval-test` (PROJECT_BRIEF section 6.5).

Refuses unless ALL of these hold:
  1. env ALLOW_TEST=1
  2. env PURPOSE is a non-empty sentence (why the test split is being opened)
  3. docs/hypothesis.md is tracked by git AND has no uncommitted changes
     (the pre-registration must be committed before any test-split run)
If allowed, appends one row to results/test_access_log.md:
  date (UTC) | git hash | who ($USER or $USERNAME / $AGENT) | purpose

    ALLOW_TEST=1 PURPOSE="final pre-registered run" uv run python infra/scripts/eval_test_guard.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HYPOTHESIS = "docs/hypothesis.md"
LOG = Path("results") / "test_access_log.md"
HEADER = (
    "# Test-split access log\n\n"
    "Every `make eval-test` run appends one row here (see docs/hypothesis.md, section 6.5).\n\n"
    "| date (UTC) | git hash | who | purpose |\n|---|---|---|---|\n"
)


class Git:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True, check=False
        )

    def is_tracked(self, path: str) -> bool:
        return self._run("ls-files", "--error-unmatch", path).returncode == 0

    def is_clean(self, path: str) -> bool:
        return self._run("diff", "--quiet", "HEAD", "--", path).returncode == 0

    def head_hash(self) -> str:
        r = self._run("rev-parse", "--short", "HEAD")
        return r.stdout.strip() if r.returncode == 0 else "NO-COMMIT"


def check(env: dict[str, str], root: Path, git) -> tuple[bool, str]:
    if env.get("ALLOW_TEST") != "1":
        return False, (
            "the TEST split is frozen. Set ALLOW_TEST=1 (and PURPOSE=...) only for the single "
            "pre-registered final run. Everything else must use the DEV split."
        )
    if not env.get("PURPOSE", "").strip():
        return False, "set PURPOSE='<why you are opening the test split>' (it is logged)."
    if not git.is_tracked(HYPOTHESIS):
        return False, f"{HYPOTHESIS} is not committed in git; commit the pre-registration first."
    if not git.is_clean(HYPOTHESIS):
        return False, f"{HYPOTHESIS} has uncommitted changes; commit (and log) them first."
    return True, "ok"


def append_log(env: dict[str, str], root: Path, git, now: str | None = None) -> str:
    now = now or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    who = env.get("USER") or env.get("USERNAME") or "unknown"
    if env.get("AGENT"):
        who = f"{who} / {env['AGENT']}"
    purpose = " ".join(env.get("PURPOSE", "").split()).replace("|", "\\|")
    row = f"| {now} | {git.head_hash()} | {who} | {purpose} |\n"
    log = root / LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text(HEADER, encoding="utf-8", newline="\n")
    with log.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(row)
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Guard for make eval-test")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check-only", action="store_true", help="check the guard, do not log")
    args = ap.parse_args(argv)
    env = dict(os.environ)
    git = Git(args.root)
    ok, msg = check(env, args.root, git)
    if not ok:
        print(f"eval-test REFUSED: {msg}", file=sys.stderr)
        return 3
    if args.check_only:
        print("eval-test guard: conditions met (not logged yet)")
        return 0
    row = append_log(env, args.root, git)
    print(f"eval-test allowed; logged to {LOG.as_posix()}: {row.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
