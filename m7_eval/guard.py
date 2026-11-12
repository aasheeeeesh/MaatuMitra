"""Test-split guard for m7_eval (PROJECT_BRIEF 6.5, docs/hypothesis.md).

Every file m7 reads goes through `SplitGuard.read_*`. In a DEV run the guard REFUSES any path
that is (1) listed in data/splits/test.lock, (2) has a TEST conversation id in its file name,
(3) sits in a folder named `test`, or (4) belongs to the held-out test voice. Membership files
(dev.txt, test.txt, test.lock) are read only to know WHICH ids to avoid.

The TEST path (`python -m m7_eval run --split test`) first calls `require_test_access`:
ALLOW_TEST=1, a PURPOSE, and a row in results/test_access_log.md for the current git hash
(written by infra/scripts/eval_test_guard.py, which the root `make eval-test` runs BEFORE m7).
So the access is logged before any test file is opened.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import regex

HELD_OUT_VOICES = ("mms_kan_pitch084",)  # D-132: test only
ACCESS_LOG = Path("results") / "test_access_log.md"


class TestSplitRefusedError(PermissionError):
    """Raised when a test-split file would be opened without the eval-test guard."""


TestSplitRefused = TestSplitRefusedError  # short alias used in tests and docs


def _ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        x.strip()
        for x in path.read_text(encoding="utf-8").splitlines()
        if x.strip() and not x.startswith("#")
    }


def _lock_paths(path: Path) -> set[str]:
    out = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    out.add(parts[1].strip().replace("\\", "/"))
    return out


class SplitGuard:
    def __init__(self, root: Path, split: str = "dev") -> None:
        if split not in ("dev", "test"):
            raise ValueError(f"unknown split {split!r}")
        self.root = Path(root).resolve()
        self.split = split
        sp = self.root / "data" / "splits"
        self.dev_ids = _ids(sp / "dev.txt")
        self.test_ids = _ids(sp / "test.txt")
        self.lock = _lock_paths(sp / "test.lock")
        self.ids = self.dev_ids if split == "dev" else self.test_ids
        alts = "|".join(regex.escape(i) for i in sorted(self.test_ids, key=len, reverse=True))
        self._test_id_re = (
            regex.compile(rf"(?<![A-Za-z0-9])(?:{alts})(?![A-Za-z0-9])") if alts else None
        )
        self.opened: list[str] = []
        self.hashes: dict[str, str] = {}

    # ------------------------------------------------------------------ membership
    def rel(self, path: Path | str) -> str:
        p = Path(path)
        p = p if p.is_absolute() else self.root / p
        try:
            return p.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return p.resolve().as_posix()

    def conv_split(self, conv_id: str) -> str | None:
        if conv_id in self.dev_ids:
            return "dev"
        if conv_id in self.test_ids:
            return "test"
        return None

    def is_test_path(self, path: Path | str) -> bool:
        rel = self.rel(path)
        if rel in self.lock:
            return True
        parts = rel.split("/")
        if "test" in parts[:-1] or any(v in parts for v in HELD_OUT_VOICES):
            return True
        return bool(self._test_id_re and self._test_id_re.search(parts[-1]))

    def _check(self, path: Path | str) -> str:
        rel = self.rel(path)
        if self.split == "dev" and self.is_test_path(rel):
            raise TestSplitRefusedError(
                f"refused to open TEST-split file {rel} in a DEV run (use the guarded "
                "`make eval-test` with ALLOW_TEST=1)"
            )
        return rel

    # ------------------------------------------------------------------ readers
    def read_bytes(self, path: Path | str) -> bytes:
        rel = self._check(path)
        data = (self.root / rel).read_bytes()
        if rel not in self.hashes:
            self.opened.append(rel)
            self.hashes[rel] = hashlib.sha256(data).hexdigest()
        return data

    def read_text(self, path: Path | str) -> str:
        return self.read_bytes(path).decode("utf-8")

    def read_json(self, path: Path | str) -> Any:
        return json.loads(self.read_text(path))

    def iter_jsonl(self, path: Path | str) -> Iterator[dict]:
        for line in self.read_text(path).splitlines():
            if line.strip():
                yield json.loads(line)

    def exists(self, path: Path | str) -> bool:
        p = Path(path)
        return (p if p.is_absolute() else self.root / p).exists()

    def listdir(self, path: Path | str, pattern: str = "*") -> list[Path]:
        """Sorted entries matching pattern, WITHOUT test-split files in a dev run."""
        p = Path(path)
        p = p if p.is_absolute() else self.root / p
        if not p.exists():
            return []
        out = sorted(p.glob(pattern))
        if self.split == "dev":
            out = [q for q in out if not self.is_test_path(q)]
        return out


def require_test_access(root: Path, env: Mapping[str, str], git_hash: str) -> None:
    """Refuse the TEST path unless ALLOW_TEST=1, PURPOSE and a logged row for git_hash."""
    if env.get("ALLOW_TEST") != "1":
        raise TestSplitRefusedError(
            "eval-test REFUSED: the TEST split is frozen; ALLOW_TEST=1 is required (set only "
            "for the single pre-registered run via `make eval-test`)."
        )
    if not env.get("PURPOSE", "").strip():
        raise TestSplitRefusedError("eval-test REFUSED: set PURPOSE='<why>' (it is logged).")
    log = Path(root) / ACCESS_LOG
    if not log.exists():
        raise TestSplitRefusedError(
            f"eval-test REFUSED: {ACCESS_LOG.as_posix()} has no row yet; run the root "
            "`make eval-test` (infra/scripts/eval_test_guard.py logs the access first)."
        )
    rows = [r for r in log.read_text(encoding="utf-8").splitlines() if r.startswith("|")]
    if not any(f"| {git_hash} |" in r for r in rows):
        raise TestSplitRefusedError(
            f"eval-test REFUSED: no row for commit {git_hash} in {ACCESS_LOG.as_posix()}; the "
            "access must be logged for THIS commit before any test file is opened."
        )


def env_dict() -> dict[str, str]:
    return dict(os.environ)
