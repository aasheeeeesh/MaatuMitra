"""Boundary checks: every module output that crosses a boundary is validated against its contract.

Read-only. DEV data only: any file or row that belongs to the test split is skipped (never opened
for content). Each check returns a `Check` with N items checked and a list of (file, error).
Nothing here fixes a module; mismatches are reported.

CLI:  uv run python -m integration.boundary   -> results/integration/boundary_checks.md
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contracts.validate import conversation_text, validate_doc

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "integration"
CAP = 400  # at most this many items per boundary (sorted order, deterministic)


@dataclass
class Check:
    name: str
    boundary: str
    schema: str
    n: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.n > 0 and not self.errors

    def add(self, where: str, errs: Iterable[str]) -> None:
        self.n += 1
        for e in errs:
            self.errors.append((where, e))


def _split_ids(name: str) -> set[str]:
    p = REPO / "data" / "splits" / name
    return {x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()}


def _load(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def _dev_only(ids: Iterable[str], test: set[str]) -> list[str]:
    return [i for i in sorted(ids) if i not in test]


def b_m1_manifest(test: set[str]) -> Check:
    c = Check("m1 manifest -> m2/m3", "m1 -> m2", "manifest.v1")
    path = REPO / "data" / "manifest.jsonl"
    seen = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("split") != "dev":
            continue  # only dev rows are examined
        seen += 1
        if seen > CAP:
            break
        c.add(f"manifest.jsonl:{row.get('file')}", validate_doc("manifest", row))
    c.note = f"dev rows only, first {CAP}"
    return c


def b_m1_gold_transcripts(test: set[str]) -> list[Check]:
    g = Check("m1 gold records", "m1 -> m3 (scoring) / m4 (E4)", "gold.v1")
    t = Check("m1 gold transcripts", "m1 -> m2/m3/m4", "transcript.v1")
    x = Check("gold text == transcript text", "m1 internal consistency", "(rule)")
    ids = _dev_only((p.stem for p in (REPO / "data" / "gold").glob("m1-*.json")), test)[:CAP]
    for i in ids:
        gp = REPO / "data" / "gold" / f"{i}.json"
        tp = REPO / "data" / "transcripts" / "gold" / f"{i}__gold.json"
        gold = _load(gp)
        g.add(_rel(gp), validate_doc("gold", gold))
        if tp.exists():
            tr = _load(tp)
            t.add(_rel(tp), validate_doc("transcript", tr))
            same = conversation_text(gold["turns"]) == tr["text"]
            x.add(_rel(tp), [] if same else ["transcript text differs from joined gold turns"])
        else:
            t.add(_rel(tp), ["missing transcript for gold"])
    return [g, t, x]


def b_m2(test: set[str]) -> list[Check]:
    a = Check("m2 dev transcripts (per-file)", "m2 -> m3", "transcript.v1")
    d = REPO / "results" / "m2_asr" / "dev" / "faster-whisper-small"
    for p in sorted(d.glob("*.json"))[:CAP]:
        a.add(_rel(p), validate_doc("transcript", _load(p)))
    b = Check("m2 transcripts.jsonl (m7 input layout)", "m2 -> m7", "transcript.v1")
    for p in sorted((REPO / "results" / "m2_asr").glob("*/dev/transcripts.jsonl")):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines()[:CAP]):
            b.add(f"{_rel(p)}:{n + 1}", validate_doc("transcript", json.loads(line)))
    c = Check("m2 mock adapter output", "m2 -> m3", "transcript.v1")
    from m2_asr.asr.base import build_transcript

    c.add("m2 build_transcript", validate_doc("transcript", build_transcript(
        "m1-a1-000", "template_text", "mock", "mock-1", "ಜ್ವರ ಇದೆ", None, None, "none")))  # fmt: skip
    return [a, b, c]


def b_m2_to_m3() -> Check:
    """m3 must accept m2's real dev transcripts or refuse them cleanly (never crash)."""
    c = Check("m2 real transcript -> m3 extract (no crash)", "m2 -> m3", "(behaviour)")
    from m3_extract.rules import extract

    d = REPO / "results" / "m2_asr" / "dev" / "faster-whisper-small"
    ctx = {"patient_ref": "pt-integration", "encounter_type": "asha_household_visit"}
    for p in sorted(d.glob("*.json"))[:20]:
        tr = _load(p)
        try:
            rec, _ = extract(tr, ctx)
            errs = validate_doc("record", rec, transcript_text=tr["text"])
        except ValueError as exc:  # m3 refuses bad text on purpose (fail closed)
            errs = []
            c.note = f"some refused cleanly: {type(exc).__name__}"
        except Exception as exc:
            errs = [f"crash {type(exc).__name__}: {exc}"]
        c.add(_rel(p), errs)
    return c


def b_m3_records(test: set[str]) -> list[Check]:
    r = Check("m3 rules records (with spans vs transcript)", "m3 -> m4", "record.v1")
    m = Check(
        "m3 records through the m4 adapter: no input-contract flag", "m3 -> m4", "(behaviour)"
    )
    from integration.verifier_adapter import find_transcript, verify_record

    files = sorted((REPO / "results" / "m3_extract" / "rules").glob("rules-m1-*.json"))
    files = [p for p in files if p.stem.removeprefix("rules-") not in test][:CAP]
    for p in files:
        rec = _load(p)
        tr = find_transcript(rec["source_transcript_id"])
        if tr is None:
            r.add(_rel(p), ["no transcript for source_transcript_id"])
            continue
        r.add(_rel(p), validate_doc("record", rec, transcript_text=tr["text"], reject_bidi=True))
        v = verify_record(rec)
        bad = [
            f"{c_['check_id']} {c_['reason'][:120]}"
            for c_ in v["checks"]
            if c_["status"] == "flag" and "input fails its contract" in c_["reason"]
        ]
        m.add(_rel(p), bad)
    return [r, m]


def b_m4_verdicts() -> list[Check]:
    out = []
    for name, pattern in (
        ("m4 fixture verdicts", "results/m4_verify/verdicts/*.json"),
        ("m4 E4 clean verdicts", "results/m4_verify/e4/clean_verdicts/*.json"),
    ):
        c = Check(name, "m4 -> m5/m6", "verdict.v1")
        for p in sorted(REPO.glob(pattern))[:CAP]:
            c.add(_rel(p), validate_doc("verdict", _load(p)))
        out.append(c)
    s = Check("m4 E4 sample verdicts (jsonl)", "m4 -> m6/m7", "verdict.v1")
    p = REPO / "results" / "m4_verify" / "e4" / "sample_verdicts.jsonl"
    if p.exists():
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines()[:CAP]):
            s.add(f"{_rel(p)}:{n + 1}", validate_doc("verdict", json.loads(line)["verdict"]))
    out.append(s)
    return out


def b_m5() -> list[Check]:
    c = Check("m5 access cases", "m5 -> m7 (E5)", "access_case.v1")
    p = REPO / "results" / "m5_backend" / "access_cases.jsonl"
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            c.add(f"{_rel(p)}:{n + 1}", validate_doc("access_case", json.loads(line)))
    c.note = "all lines"
    return [c]


def b_m8() -> Check:
    c = Check("m8 helper cards", "m8 -> m6/m7", "card.v1")
    for p in sorted((REPO / "m8_helper" / "cards").glob("*.json")):
        c.add(_rel(p), validate_doc("card", _load(p)))
    return c


def b_reviews() -> Check:
    c = Check("review reports", "reviewers -> orchestrator", "review_report.v1")
    for p in sorted((REPO / "reviews").glob("*/*.json")):
        doc = _load(p)
        if isinstance(doc, dict) and doc.get("schema_version") == "review_report.v1":
            c.add(_rel(p), validate_doc("review_report", doc))
        else:
            c.add(_rel(p), ["no schema_version review_report.v1 in a reviews/*/*.json file"])
    return c


def run_all() -> list[Check]:
    test = _split_ids("test.txt")
    checks: list[Check] = [b_m1_manifest(test)]
    steps: list[Callable[[], Any]] = [
        lambda: b_m1_gold_transcripts(test),
        lambda: b_m2(test),
        b_m2_to_m3,
        lambda: b_m3_records(test),
        b_m4_verdicts,
        b_m5,
        b_m8,
        b_reviews,
    ]
    for step in steps:
        try:
            out = step()
        except Exception as exc:
            out = Check(step.__name__ if hasattr(step, "__name__") else "step", "?", "?")
            out.add("integration.boundary", [f"step crashed: {type(exc).__name__}: {exc}"])
        checks += out if isinstance(out, list) else [out]
    return checks


def render_md(checks: list[Check]) -> str:
    lines = [
        "# Boundary checks (integration-qa, Phase C1)",
        "",
        "Every sampled module output is validated with `contracts.validate`. DEV only; "
        f"caps at {CAP} items per boundary (sorted order).",
        "",
        "| boundary | check | schema | N | mismatches | result |",
        "|---|---|---|---|---|---|",
    ]
    for c in checks:
        res = "OK" if c.ok else ("NO DATA" if c.n == 0 else "MISMATCH")
        lines.append(f"| {c.boundary} | {c.name} | {c.schema} | {c.n} | {len(c.errors)} | {res} |")
    bad = [c for c in checks if c.errors]
    if bad:
        lines += ["", "## Mismatches (first 5 per check)", ""]
        for c in bad:
            lines.append(f"### {c.name} ({len(c.errors)} total)")
            lines += [f"- `{w}`: {e[:300]}" for w, e in c.errors[:5]]
            lines.append("")
    notes = [f"- {c.name}: {c.note}" for c in checks if c.note]
    if notes:
        lines += ["", "## Notes", "", *notes]
    return "\n".join(lines) + "\n"


def main() -> int:
    checks = run_all()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "boundary_checks.md").write_text(render_md(checks), encoding="utf-8")
    print(render_md(checks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
