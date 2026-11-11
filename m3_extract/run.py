"""Runners: extract -> evidence check -> save (or reject) -> score -> CSV / failure report.

Layout under results/m3_extract/:
  <pipeline>/<record_id>.json            valid record.v1 (evidence check passed)
  <pipeline>/rejected/<record_id>.json   {"reasons": [...], "record": <candidate>, ...} (counted as errors)
  <pipeline>/logs/<record_id>.json       extraction log (rules events / LLM raw output, latency)
  llm_subset.txt, dev_scores.csv, error_codes_dev.csv, evidence_overlap_dev.csv, failures_dev.md
"""

from __future__ import annotations

import csv
import json
import platform
import shutil
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from contracts.validate import validate_doc
from m3_extract import splits
from m3_extract.evidence import check_evidence
from m3_extract.lexicon import DrugLexicon, load_lexicon
from m3_extract.rules import DEFAULT_LEXICON, extract
from m3_extract.scoring import FieldResult, aggregate, score_record

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "m3_extract"
FIX = ROOT / "fixtures"
FAILURE_NOTES = Path(__file__).resolve().parent / "failure_analysis.md"
HARDWARE = "i7-12650H, 16 GB RAM, RTX 3050 Ti 4 GB VRAM, Windows 11 (builder_rules.md)"


def _dump(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_record(
    record: dict[str, Any],
    transcript: dict[str, Any],
    out_dir: Path,
    *,
    log: dict[str, Any] | None = None,
    extra_reasons: list[str] | None = None,
) -> Path:
    """Write a record if it passes the evidence check AND record.v1; otherwise keep it in
    rejected/ with the reasons. Nothing is silently dropped."""
    reasons = list(extra_reasons or [])
    if not reasons:
        reasons += [f"record.v1: {e}" for e in validate_doc("record.v1", record)]
        reasons += check_evidence(record, transcript["text"])
    rid = record["record_id"]
    if log is not None:
        _dump(log, out_dir / "logs" / f"{rid}.json")
    if reasons:
        path = out_dir / "rejected" / f"{rid}.json"
        _dump(
            {
                "record_id": rid,
                "source_transcript_id": transcript["audio_id"],
                "reasons": reasons,
                "record": record,
            },
            path,
        )
        return path
    path = out_dir / f"{rid}.json"
    _dump(record, path)
    return path


def _transcript_path(cid: str, transcripts_dir: Path | None) -> Path:
    if transcripts_dir is None:
        return splits.gold_transcript_path(cid)
    splits.assert_allowed(cid)
    hits = sorted(transcripts_dir.glob(f"{cid}__*.json"))
    if not hits:
        raise FileNotFoundError(f"no transcript for {cid} in {transcripts_dir}")
    return hits[0]


def _reset(out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)


def run_rules(
    ids: list[str],
    out_dir: Path,
    *,
    transcripts_dir: Path | None = None,
    lexicon: DrugLexicon | None = None,
) -> dict[str, Any]:
    lexicon = lexicon or load_lexicon(DEFAULT_LEXICON)
    _reset(out_dir)
    n_rej = 0
    for cid in ids:
        gold = splits.load_gold(cid)
        tr = splits.load_transcript(_transcript_path(cid, transcripts_dir))
        rec, log = extract(tr, splits.encounter_context(gold), lexicon=lexicon)
        n_rej += save_record(rec, tr, out_dir, log=log).parent.name == "rejected"
    return {"pipeline": "rules", "n": len(ids), "n_rejected": n_rej}


def run_llm(
    ids: list[str], out_dir: Path, *, transcripts_dir: Path | None = None
) -> dict[str, Any]:
    from m3_extract import llm

    digest = llm.model_digest()
    if digest is None:
        raise RuntimeError(f"Ollama model {llm.MODEL} not reachable at {llm.OLLAMA_URL}")
    lexicon = load_lexicon(DEFAULT_LEXICON)
    _reset(out_dir)
    rows = []
    for cid in ids:
        gold = splits.load_gold(cid)
        tr = splits.load_transcript(_transcript_path(cid, transcripts_dir))
        res = llm.extract_llm(tr, splits.encounter_context(gold), lexicon=lexicon, digest=digest)
        log = {
            "record_id": res.record["record_id"],
            "latency_ms": res.latency_ms,
            "meta": res.meta,
            "raw_output": res.raw,
            "model": llm.MODEL,
            "digest": digest,
        }
        path = save_record(res.record, tr, out_dir, log=log, extra_reasons=res.rejected_reasons)
        rows.append(
            {
                "conversation_id": cid,
                "latency_ms": round(res.latency_ms, 1),
                "rejected": path.parent.name == "rejected",
                "eval_count": res.meta.get("eval_count"),
                "prompt_eval_count": res.meta.get("prompt_eval_count"),
            }
        )
        print(
            f"[llm] {cid} {res.latency_ms / 1000:.1f}s rejected={rows[-1]['rejected']}", flush=True
        )
    lat = [r["latency_ms"] for r in rows]
    with (out_dir / "latency.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    q = statistics.quantiles(lat, n=20) if len(lat) >= 2 else [lat[0]] * 19
    summary = {
        "pipeline": "llm",
        "model": llm.MODEL,
        "digest": digest,
        "seed": llm.SEED,
        "prompt_version": llm.PROMPT_VERSION,
        "hardware": HARDWARE,
        "n": len(ids),
        "n_rejected": sum(r["rejected"] for r in rows),
        "latency_ms_p50": statistics.median(lat),
        "latency_ms_p95": q[18],
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
    }
    _dump(summary, out_dir / "run_summary.json")
    return summary


# ----------------------------------------------------------------------------- scoring


def load_outputs(out_dir: Path, pipeline: str, cid: str) -> tuple[dict | None, list[str] | None]:
    """Find the output for conversation cid (record id = <pipeline>-<audio_id>, audio_id = cid
    for gold transcripts, cid__<variant> for ASR transcripts)."""
    for pat in (f"{pipeline}-{cid}.json", f"{pipeline}-{cid}__*.json"):
        hits = sorted(out_dir.glob(pat))
        if hits:
            return json.loads(hits[0].read_text(encoding="utf-8")), None
        hits = sorted((out_dir / "rejected").glob(pat))
        if hits:
            return None, json.loads(hits[0].read_text(encoding="utf-8"))["reasons"]
    return None, ["no output file (pipeline did not run on this id)"]


def score_ids(
    pipeline: str,
    ids: list[str],
    out_dir: Path,
    *,
    gold_loader=splits.load_gold,
    gold_text: bool = True,
) -> tuple[list[FieldResult], dict[str, list[str]], dict[str, dict]]:
    results: list[FieldResult] = []
    rejected: dict[str, list[str]] = {}
    golds: dict[str, dict] = {}
    for cid in ids:
        gold = gold_loader(cid)
        golds[cid] = gold
        rec, reasons = load_outputs(out_dir, pipeline, cid)
        if reasons:
            rejected[cid] = reasons
        results += score_record(rec, gold, offsets_comparable=gold_text)
    return results, rejected, golds


SLICES = (
    "all",
    "dev_part",
    "category",
    "code_switched",
    "has_negation",
    "cross_turn_negation",
    "field",
)


def _slice_value(sl: str, cid: str, gold: dict) -> str:
    if sl == "all":
        return "all"
    if sl == "dev_part":
        return splits.dev_part_of(cid) if cid.startswith("m1-") else "fixture"
    if sl == "category":
        return gold["template_family_id"][0]
    return str(gold["tags"][sl]).lower()


def score_rows(
    pipeline: str, subset: str, results: list[FieldResult], rejected: dict, golds: dict
) -> list[dict]:
    rows = []
    for sl in SLICES:
        groups: dict[str, list[FieldResult]] = {}
        for r in results:
            val = (
                f"{r.kind}.{r.field}"  # per-field slice: medication.dose_value, advice.text, ...
                if sl == "field"
                else _slice_value(sl, r.conversation_id, golds[r.conversation_id])
            )
            groups.setdefault(val, []).append(r)
        for val in sorted(groups):
            cids = {r.conversation_id for r in groups[val]}
            for row in aggregate(groups[val]):
                rows.append(
                    {
                        "pipeline": pipeline,
                        "subset": subset,
                        "slice": sl,
                        "slice_value": val,
                        "n_rejected_records": sum(1 for c in cids if c in rejected),
                        **row,
                    }
                )
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.2f}" if isinstance(v, float) else v) for k, v in r.items()})


def code_rows(pipeline: str, subset: str, results: list[FieldResult]) -> list[dict]:
    c = Counter(r.code for r in results if r.code)
    return [
        {
            "pipeline": pipeline,
            "subset": subset,
            "code": k,
            "severity": k and {"CR": "critical", "MA": "major", "MI": "minor"}[k[:2]],
            "errors": v,
            "n_fields": len(results),
        }
        for k, v in sorted(c.items())
    ]


def overlap_rows(pipeline: str, subset: str, results: list[FieldResult]) -> list[dict]:
    rows = []
    for kind in ("medication", "symptom", "advice", "follow_up"):
        xs = [
            r.evidence_overlap for r in results if r.kind == kind and r.evidence_overlap is not None
        ]
        rows.append(
            {
                "pipeline": pipeline,
                "subset": subset,
                "kind": kind,
                "matched_items": len(xs),
                "evidence_overlaps_gold_span": sum(xs),
            }
        )
    return rows


def _fmt(v: Any) -> str:
    return "null" if v is None else json.dumps(v, ensure_ascii=False)


def failure_section(
    pipeline: str,
    subset: str,
    results: list[FieldResult],
    rejected: dict,
    golds: dict,
    out_dir: Path,
    max_per_code: int = 4,
) -> str:
    lines = [f"## {pipeline} on {subset}", ""]
    errs = [r for r in results if r.code]
    c = Counter(r.code for r in errs)
    lines.append(f"Fields: {len(results)}; errors: {len(errs)}; rejected records: {len(rejected)}.")
    lines.append("")
    lines.append("| code | count |")
    lines.append("|---|---|")
    lines += [
        f"| {k} | {v} |" for k, v in sorted(c.items(), key=lambda kv: (kv[0][:2] != "CR", -kv[1]))
    ]
    lines.append("")
    for code in sorted(c, key=lambda k: (k[:2] != "CR", k)):
        lines.append(f"### {code} (showing up to {max_per_code} of {c[code]})")
        lines.append("")
        for r in [r for r in errs if r.code == code][:max_per_code]:
            g = golds[r.conversation_id]
            turns = " / ".join(t["text"] for t in g["turns"])
            part = (
                splits.dev_part_of(r.conversation_id)
                if r.conversation_id.startswith("m1-")
                else "fixture"
            )
            lines.append(
                f"- `{r.conversation_id}` ({part}, family {g['template_family_id']}), {r.kind} `{r.item}` field `{r.field}`"
            )
            lines.append(f"  - input: {turns}")
            lines.append(
                f"  - output: {_fmt(r.pred)}; gold: {_fmt(r.gold)}"
                + (f"; note: {r.detail}" if r.detail else "")
            )
            if r.conversation_id in rejected:
                lines.append(
                    f"  - cause: record REJECTED by the evidence check: {rejected[r.conversation_id][0]}"
                )
            else:
                lines.append(f"  - cause (automatic hint): {_hint(r, out_dir, pipeline)}")
        lines.append("")
    if rejected:
        lines.append("### Rejected records (evidence check / schema), reasons")
        lines.append("")
        for cid, rs in sorted(rejected.items()):
            lines.append(f"- `{cid}`: " + "; ".join(rs[:3]))
        lines.append("")
    return "\n".join(lines)


def _hint(r: FieldResult, out_dir: Path, pipeline: str) -> str:
    if pipeline != "rules":
        return "LLM output differs from gold (see logs/ raw_output)"
    p = out_dir / "logs" / f"rules-{r.conversation_id}.json"
    if not p.exists():
        return "no log"
    ev = [
        e
        for e in json.loads(p.read_text(encoding="utf-8"))["events"]
        if e.get("item") in (r.item, r.pred) or e.get("drug") in (r.item, r.pred)
    ]
    if r.code in ("MA-MISSED-DRUG", "MA-MISSED-SYMPTOM"):
        return "no lexicon/symptom-list match for the spoken form" + (
            f"; events: {ev}" if ev else ""
        )
    if r.code in ("MA-MISSED-ADVICE", "MA-MISSED-FOLLOWUP"):
        return "no phrase pattern in m3_extract/data/phrases.yaml matches this wording"
    if r.code == "MA-WORDING-UNJUDGED":
        return "phrase pattern / fallback produced a different gloss"
    return f"rule events: {ev}" if ev else "see rules.py decision order"


# ----------------------------------------------------------------------------- mock mode


def run_mock(out_root: Path = RESULTS / "mock") -> dict[str, Any]:
    """MODE=mock: rules pipeline on hand-made fixtures only (fixture lexicon), scored vs fixture gold."""
    lexicon = load_lexicon(FIX / "lexicon" / "drugs_fixture.csv")
    out_dir = out_root / "rules"
    _reset(out_dir)
    golds = {}
    for gp in sorted((FIX / "gold" / "valid").glob("*.json")):
        g = json.loads(gp.read_text(encoding="utf-8"))
        golds[g["conversation_id"]] = g
    n_rej = 0
    for cid, g in golds.items():
        tr = json.loads(
            (FIX / "transcript" / "valid" / f"{cid}__gold.json").read_text(encoding="utf-8")
        )
        rec, log = extract(tr, splits.encounter_context(g), lexicon=lexicon)
        n_rej += save_record(rec, tr, out_dir, log=log).parent.name == "rejected"
    results, rejected, _ = score_ids("rules", list(golds), out_dir, gold_loader=golds.__getitem__)
    rows = score_rows("rules", "fixtures", results, rejected, golds)
    write_csv(rows, out_root / "mock_scores.csv")
    crit = next(r for r in rows if r["slice"] == "all" and r["severity"] == "critical")
    return {
        "n_records": len(list(out_dir.glob("*.json"))),
        "n_rejected": n_rej,
        "critical_errors": crit["errors"],
        "n_fields": crit["n_fields"],
    }


# ----------------------------------------------------------------------------- dev scoring


def score_dev(out_root: Path = RESULTS) -> dict[str, Any]:
    """Score whatever pipeline outputs exist: rules on full dev and on the LLM subset; LLM on
    the subset. Writes dev_scores.csv, error_codes_dev.csv, evidence_overlap_dev.csv, failures_dev.md."""
    subset = splits.llm_subset()
    (out_root / "llm_subset.txt").write_text("\n".join(subset) + "\n", encoding="utf-8")
    plans = [("rules", "full_dev", splits.dev_ids()), ("rules", "llm_subset", subset)]
    if (out_root / "llm").exists():
        plans.append(("llm", "llm_subset", subset))
    rows, codes, overl, sections, summary = [], [], [], [], {}
    for pipeline, name, ids in plans:
        out_dir = out_root / pipeline
        results, rejected, golds = score_ids(pipeline, ids, out_dir)
        rows += score_rows(pipeline, name, results, rejected, golds)
        codes += code_rows(pipeline, name, results)
        overl += overlap_rows(pipeline, name, results)
        if name == "full_dev" or pipeline == "llm":
            sections.append(failure_section(pipeline, name, results, rejected, golds, out_dir))
        summary[f"{pipeline}/{name}"] = {
            r["severity"]: (
                r["errors"],
                r["n_fields"],
                round(r["per_1000"], 1),
                round(r["ci_low_per_1000"], 1),
                round(r["ci_high_per_1000"], 1),
            )
            for r in rows
            if r["pipeline"] == pipeline and r["subset"] == name and r["slice"] == "all"
        }
        summary[f"{pipeline}/{name}"]["rejected"] = len(rejected)
    write_csv(rows, out_root / "dev_scores.csv")
    write_csv(codes, out_root / "error_codes_dev.csv")
    write_csv(overl, out_root / "evidence_overlap_dev.csv")
    notes = FAILURE_NOTES.read_text(encoding="utf-8") if FAILURE_NOTES.exists() else ""
    head = (
        "# m3_extract failures on DEV (generated by `python -m m3_extract score`)\n\n"
        "DEV split only (test never read). Synthetic template text, gold transcripts (no ASR yet). "
        "Kannada not native-validated. dev_tune = templates read while writing rules; dev_holdout = "
        "templates never read (a3 b4 c5 d2 e6 f3 g5 h6 i3) but looked at later while fixing v2/v3. "
        "ALL rows are in-sample: DEV is where the rules were written. rules/llm_subset rows are 80% "
        "dev_tune (32 of 40). LLM rows appear only if results/m3_extract/llm exists (the old "
        "comparison is STALE, pre-REFREEZE).\n\n"
    )
    (out_root / "failures_dev.md").write_text(
        head + notes + "\n\n" + "\n\n".join(sections) + "\n", encoding="utf-8"
    )
    _dump(summary, out_root / "dev_summary.json")
    return summary
