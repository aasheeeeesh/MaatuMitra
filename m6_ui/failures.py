"""Screen 6 ("where it failed") data, in this order of preference:

1. any results/*/failure*.md file (published by another module);
2. escaped planted mistakes in results/m4_verify/e4/catch_rates.csv (rows with caught < n),
   plus up to 2 example injections per row from injection_results/injection_log files;
3. the hand-made fallback list m6_ui/fixtures/failure_cases.json (marked NOT measured).
Only published result files are read; no other module's code is imported.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

M6 = Path(__file__).resolve().parent
MAX_MD_CHARS = 4000


@dataclass
class FailureRow:
    type_name: str
    condition: str
    n: int
    caught: int
    n_unique: int | None
    unique_caught: int | None
    measured: bool
    source: str
    examples: list[str] = field(default_factory=list)
    text: str = ""  # markdown files: raw text (shown escaped)


def _md_rows(root: Path) -> list[FailureRow]:
    rows = []
    for p in sorted((root / "results").glob("*/failure*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")[:MAX_MD_CHARS]
        rows.append(
            FailureRow(
                p.stem,
                p.parent.name,
                0,
                0,
                None,
                None,
                True,
                p.relative_to(root).as_posix(),
                text=text,
            )
        )
    return rows


def _examples(e4: Path, level: str, type_code: str, condition: str, k: int = 2) -> list[str]:
    res = e4 / "injection_results.jsonl"
    log = e4 / f"injection_log_{level}.jsonl"
    if not res.exists() or not log.exists():
        return []
    ids = []
    with res.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if (
                d.get("caught") is False
                and d.get("type") == type_code
                and d.get("condition") == condition
                and d.get("level") == level
            ):
                ids.append(d["id"])
                if len(ids) >= k:
                    break
    want, out = set(ids), []
    with log.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("id") in want:
                note = d.get("note") or ""
                out.append(
                    f"{d['source_id']} {d['field_path']}: {d.get('before')!r} -> {d.get('after')!r} {note}".strip()
                )
    return out


def _e4_rows(root: Path) -> list[FailureRow]:
    e4 = root / "results" / "m4_verify" / "e4"
    p = e4 / "catch_rates.csv"
    if not p.exists():
        return []
    rows = []
    with p.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            n, caught = int(r["n"]), int(r["caught"])
            if caught >= n:
                continue
            rows.append(
                FailureRow(
                    type_name=f"{r['level']}: {r['type_name']}",
                    condition=r["condition"],
                    n=n,
                    caught=caught,
                    n_unique=int(r["n_unique"]) if r.get("n_unique") else None,
                    unique_caught=int(r["unique_caught"]) if r.get("unique_caught") else None,
                    measured=True,
                    source=p.relative_to(root).as_posix(),
                    examples=_examples(e4, r["level"], r["type"], r["condition"]),
                )
            )
    return rows


def _fixture_rows() -> list[FailureRow]:
    doc = json.loads((M6 / "fixtures" / "failure_cases.json").read_text(encoding="utf-8"))
    return [
        FailureRow(
            c["type_name"],
            c["condition"],
            0,
            0,
            None,
            None,
            False,
            "m6_ui/fixtures/failure_cases.json",
            examples=[c["example"], c["why"]],
        )
        for c in doc["cases"]
    ]


def load_failures(root: Path) -> list[FailureRow]:
    root = Path(root)
    rows = _md_rows(root) + _e4_rows(root)
    return rows or _fixture_rows()
