"""DEV-only guard for every m4 reader of gold / transcript data (PROJECT_BRIEF 6.5; fix for M4-1).

ALLOW-LIST, not a name heuristic:
  * Under data/ a file is opened ONLY if its conversation id (file stem before "__") is listed in
    data/splits/dev.txt. Test files are skipped without being opened.
  * Everywhere (including copies or renamed folders outside data/) a document is REFUSED if
      - its conversation id (gold `conversation_id`, or transcript `audio_id` before "__") is in
        data/splits/test.txt, or
      - its `template_family_id` is a TEST family in data/splits/split_plan.json, or
      - the sha256 of the file bytes is listed in data/splits/test.lock.
  * The only way past the guard is ALLOW_TEST=1 AND a non-empty PURPOSE=... in the environment.
    Every such access is appended to results/m4_verify/test_access_log.md (date, git hash, user,
    purpose, source, ids). m4 itself never sets ALLOW_TEST; the official test run is `make eval-test`.
  * Missing split lists -> SplitGuardError (fail-closed: membership cannot be checked).

All file reads in this module use the builtin open() on purpose (tests spy on it to prove that no
test file is opened).
"""

from __future__ import annotations

import datetime as _dt
import getpass
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SPLITS = DATA / "splits"
ACCESS_LOG = ROOT / "results" / "m4_verify" / "test_access_log.md"


class SplitGuardError(RuntimeError):
    """The split lists could not be read, so DEV membership cannot be checked (fail-closed)."""


class SplitRefused(ValueError):
    """Input contains TEST-split data and test access was not explicitly allowed."""


@dataclass(frozen=True)
class SplitInfo:
    dev_ids: frozenset[str]
    test_ids: frozenset[str]
    test_families: frozenset[str]
    test_hashes: frozenset[str]
    splits_dir: str


@dataclass
class GoldLoad:
    docs: list[dict[str, Any]]
    source: str
    under_data: bool
    loaded_ids: list[str] = field(default_factory=list)
    skipped_not_allowed: int = 0  # files under data/ not opened because their id is not in dev.txt


def _read_bytes(path: str | Path) -> bytes:
    with open(path, "rb") as fh:  # builtin open (see module docstring)
        return fh.read()


def _ids(path: Path) -> frozenset[str]:
    return frozenset(x.strip() for x in _read_bytes(path).decode("utf-8").split() if x.strip())


@lru_cache(maxsize=8)
def split_info(splits_dir: str = str(SPLITS)) -> SplitInfo:
    d = Path(splits_dir)
    try:
        dev = _ids(d / "dev.txt")
        test = _ids(d / "test.txt")
        plan = json.loads(_read_bytes(d / "split_plan.json").decode("utf-8"))
        fams = frozenset(plan.get("families", {}).get("test", []))
        hashes = frozenset(
            ln.split()[0]
            for ln in _read_bytes(d / "test.lock").decode("utf-8").splitlines()
            if ln.strip() and not ln.startswith("#") and len(ln.split()[0]) == 64
        )
    except (OSError, ValueError) as ex:
        raise SplitGuardError(
            f"cannot read the split lists in '{d}' ({type(ex).__name__}: {ex}); "
            "refusing to load data whose split membership cannot be checked"
        ) from ex
    if not dev or not test:
        raise SplitGuardError(f"empty dev.txt or test.txt in '{d}'")
    return SplitInfo(dev, test, fams, hashes, str(d))


def conv_id(name: str) -> str:
    """'m1-a1-000__gold.json' -> 'm1-a1-000'."""
    n = Path(name).name
    if n.endswith(".json"):
        n = n[:-5]
    return n.split("__")[0]


def is_under_data(path: str | Path) -> bool:
    return Path(path).resolve().is_relative_to(DATA.resolve())


def _purpose() -> str | None:
    if os.environ.get("ALLOW_TEST") != "1":
        return None
    p = (os.environ.get("PURPOSE") or "").strip()
    return p or None


def _git_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _refuse_or_log(reasons: list[str], source: str, log_path: Path | None) -> None:
    why = "; ".join(reasons)
    if os.environ.get("ALLOW_TEST") == "1" and _purpose() is None:
        raise SplitRefused(
            f"REFUSED: {source}: {why}. ALLOW_TEST=1 was set but PURPOSE=... is empty"
        )
    purpose = _purpose()
    if purpose is None:
        raise SplitRefused(
            f"REFUSED: {source}: {why}. m4 tunes and evaluates on DEV only "
            "(PROJECT_BRIEF 6.5); the test split is read only by `make eval-test`"
        )
    log = Path(log_path) if log_path else ACCESS_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    new = not log.exists()
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        if new:
            fh.write(
                "# m4_verify test-split access log (ALLOW_TEST=1 + PURPOSE)\n\n"
                "| date (UTC) | git | user | purpose | source | reason |\n|---|---|---|---|---|---|\n"
            )
        now = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        fh.write(
            f"| {now} | {_git_hash()} | {getpass.getuser()} | {purpose} | {source} | {why} |\n"
        )


def guard_doc(
    doc: dict[str, Any],
    source: str,
    info: SplitInfo | None = None,
    log_path: Path | None = None,
) -> None:
    """Refuse (raise SplitRefused) if one parsed gold/transcript document belongs to TEST."""
    info = info or split_info()
    cid = doc.get("conversation_id") or conv_id(str(doc.get("audio_id") or ""))
    reasons = []
    if cid in info.test_ids:
        reasons.append(f"conversation id '{cid}' is listed in data/splits/test.txt")
    fam = doc.get("template_family_id")
    if fam and fam in info.test_families:
        reasons.append(f"template family '{fam}' is a TEST family (split_plan.json)")
    if reasons:
        _refuse_or_log(reasons, source, log_path)


def guard_bytes(
    raw: bytes, source: str, info: SplitInfo | None = None, log_path: Path | None = None
) -> None:
    info = info or split_info()
    if hashlib.sha256(raw).hexdigest() in info.test_hashes:
        _refuse_or_log(
            ["file bytes match a sha256 in data/splits/test.lock (copy of a TEST file)"],
            source,
            log_path,
        )


def allowed_data_name(path: str | Path, info: SplitInfo | None = None) -> bool:
    """For a file under data/: may it be opened? Only dev ids (or test ids with logged access)."""
    info = info or split_info()
    cid = conv_id(str(path))
    if cid in info.dev_ids:
        return True
    return cid in info.test_ids and _purpose() is not None


def read_guarded_json(
    path: str | Path, info: SplitInfo | None = None, log_path: Path | None = None
) -> dict[str, Any]:
    """Read ONE json document (gold or transcript) through the guard."""
    info = info or split_info()
    p = Path(path)
    if is_under_data(p) and not allowed_data_name(p, info):
        cid = conv_id(str(p))
        why = (
            f"'{cid}' is listed in data/splits/test.txt"
            if cid in info.test_ids
            else f"'{cid}' is not listed in data/splits/dev.txt"
        )
        _refuse_or_log([why], str(p), log_path)
    raw = _read_bytes(p)
    guard_bytes(raw, str(p), info, log_path)
    doc = json.loads(raw.decode("utf-8"))
    guard_doc(doc, str(p), info, log_path)
    return doc


def load_gold(
    path: str | Path,
    ids: set[str] | None = None,
    splits_dir: str | Path | None = None,
    log_path: Path | None = None,
) -> GoldLoad:
    """Load gold.v1 documents from a directory (*.json, *.jsonl) or a .jsonl file, DEV only."""
    info = split_info(str(splits_dir)) if splits_dir else split_info()
    p = Path(path)
    under = is_under_data(p)
    res = GoldLoad(docs=[], source=str(p), under_data=under)
    files = (sorted(p.glob("*.json")) + sorted(p.glob("*.jsonl"))) if p.is_dir() else [p]
    for f in files:
        if f.suffix == ".json":
            if under and not allowed_data_name(f, info):
                res.skipped_not_allowed += 1
                continue  # never opened
            raw = _read_bytes(f)
            guard_bytes(raw, str(f), info, log_path)
            doc = json.loads(raw.decode("utf-8"))
            guard_doc(doc, str(f), info, log_path)
            res.docs.append(doc)
        else:
            raw = _read_bytes(f)
            guard_bytes(raw, str(f), info, log_path)
            for k, line in enumerate(raw.decode("utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                doc = json.loads(line)
                cid = doc.get("conversation_id", "")
                if under and cid not in info.dev_ids:
                    if cid in info.test_ids:
                        guard_doc(doc, f"{f}:{k}", info, log_path)  # refuses unless allowed
                    else:
                        res.skipped_not_allowed += 1
                        continue
                guard_doc(doc, f"{f}:{k}", info, log_path)
                res.docs.append(doc)
    res.docs = [d for d in res.docs if d.get("schema_version") == "gold.v1"]
    if ids is not None:
        res.docs = [d for d in res.docs if d["conversation_id"] in ids]
    res.docs.sort(key=lambda d: d["conversation_id"])
    res.loaded_ids = [d["conversation_id"] for d in res.docs]
    return res
