"""Run the verifier on fixtures (mock) and the E4 planted-mistake experiment; write results.

Outputs (out_dir, default results/m4_verify/):
  verdicts/<record_id>.json            verdict.v1 for every fixture record (mock run)
  fixture_per_check.csv                per-check status counts on the fixture records
  e4/clean_verdicts/*.json             verdict.v1 for every clean gold record
  e4/injection_log_{record,transcript}.jsonl   exactly what was injected (id, type, field_path, before, after)
  e4/injection_results.jsonl           per injection and condition: caught?, which checks flagged
  e4/sample_verdicts.jsonl             2 full verdicts per type and condition (all others validated in memory)
  e4/catch_rates.csv                   per level/condition/type: n, unique, caught, rate, Wilson 95% CI
  e4/per_check.csv                     per scope and check: flagged count, rate, caught ONLY by this check
  e4/clean_flag_rate.csv               review burden on error-free records and fields
  e4/summary.json, e4/summary.md
Every verdict produced is validated with contracts.validate; the count is reported.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from contracts.validate import validate_doc
from m4_verify.config import CHECK_IDS, ROOT, Config, default_config
from m4_verify.lexicon import Lexicon, load_lexicon
from m4_verify.planted import (
    SEED,
    TYPES,
    generate_record_level,
    generate_transcript_level,
    gold_to_pair,
    load_gold_dir,
    log_rows,
)
from m4_verify.stats import rule_of_three, wilson
from m4_verify.verifier import verify

FIX = ROOT / "fixtures"
FIXTURE_PAIRS = {
    "rec-fx-asha-001": "fx-asha-001__gold",
    "rec-fx-asha-002": "fx-asha-002__gold",
    "rec-fx-pharm-003": "fx-pharm-003__gold",
    "rec-fx-phys-004": "fx-phys-004__gold",
    "rec-fx-nurse-005": "fx-nurse-005__gold",
    "rec-fx-trap-006": "fx-trap-006__gold",
    "rec-fx-pharm-003-asr": "fx-pharm-003__asr_digit_error",
}


class Validated:
    def __init__(self) -> None:
        self.n = 0
        self.errors: list[str] = []

    def __call__(self, v: dict) -> dict:
        errs = validate_doc("verdict", v)
        self.n += 1
        if errs:
            self.errors.append(f"{v.get('record_id')}: {errs[:2]}")
        return v


def _dump(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def _csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _touches(fp: str, field: str) -> bool:
    """Does a flag at field_path fp concern the record field `field`?"""
    return fp == "/" or fp == field or field.startswith(fp + "/") or fp.startswith(field + "/")


def _r(x: float) -> float | str:
    return "" if x != x else round(x, 4)


# --------------------------------------------------------------------------- mock (fixtures)
def run_mock(out_dir: Path, lex: Lexicon, cfg: Config) -> dict:
    val = Validated()
    counts: dict[str, dict[str, int]] = {c: defaultdict(int) for c in CHECK_IDS}
    summary = {}
    for rid, tid in sorted(FIXTURE_PAIRS.items()):
        rec = json.loads((FIX / "record" / "valid" / f"{rid}.json").read_text(encoding="utf-8"))
        tr = json.loads((FIX / "transcript" / "valid" / f"{tid}.json").read_text(encoding="utf-8"))
        v = val(verify(rec, tr, lexicon=lex, config=cfg))
        _dump(out_dir / "verdicts" / f"{rid}.json", v)
        for c in v["checks"]:
            counts[c["check_id"]][c["status"]] += 1
        summary[rid] = {
            "auto_acceptable": v["auto_acceptable"],
            "flags": [
                f"{c['check_id']} {c['field_path']}" for c in v["checks"] if c["status"] == "flag"
            ],
        }
    rows = [
        {
            "check_id": c,
            "pass": counts[c]["pass"],
            "flag": counts[c]["flag"],
            "n/a": counts[c]["n/a"],
        }
        for c in CHECK_IDS
    ]
    _csv(out_dir / "fixture_per_check.csv", rows)
    return {"verdicts_validated": val.n, "validation_errors": val.errors, "records": summary}


# --------------------------------------------------------------------------- E4
def _item_path(field_path: str) -> str:
    parts = field_path.strip("/").split("/")
    return (
        "/" + "/".join(parts[:2])
        if parts[0] in ("symptoms", "medications", "advice")
        else "/" + parts[0]
    )


def _record_fields(rec: dict) -> list[str]:
    f = ["/patient_ref"]
    for kind in ("symptoms", "medications", "advice"):
        f += [f"/{kind}/{i}" for i in range(len(rec[kind]))]
    if rec.get("follow_up"):
        f.append("/follow_up")
    return f


def run_e4(
    gold_dir: Path,
    lex: Lexicon,
    cfg: Config,
    out_dir: Path,
    n_per_type: int = 200,
    seed: int = SEED,
) -> dict:
    golds = load_gold_dir(gold_dir)
    e4 = out_dir / "e4"
    val = Validated()

    # ---- clean (error-free) records: review burden
    clean_rows = []
    rec_flagged = fields_total = fields_flagged = 0
    per_check_clean_rec: dict[str, int] = defaultdict(int)
    per_check_clean_field: dict[str, int] = defaultdict(int)
    for g in golds:
        tr, rec = gold_to_pair(g)
        v = val(
            verify(
                rec,
                tr,
                lexicon=lex,
                config=cfg,
                encounter_index={tr["audio_id"]: rec["patient_ref"]},
            )
        )
        _dump(e4 / "clean_verdicts" / f"{rec['record_id']}.json", v)
        flags = [c for c in v["checks"] if c["status"] == "flag"]
        rec_flagged += int(not v["auto_acceptable"])
        for cid in {c["check_id"] for c in flags}:
            per_check_clean_rec[cid] += 1
        for fld in _record_fields(rec):
            fields_total += 1
            hit = [c for c in flags if _touches(c["field_path"], fld)]
            fields_flagged += int(bool(hit))
            for cid in {c["check_id"] for c in hit}:
                per_check_clean_field[cid] += 1
            if hit:
                clean_rows.append(
                    {
                        "record_id": rec["record_id"],
                        "field": fld,
                        "flags": [f"{c['check_id']}: {c['reason']}" for c in hit],
                    }
                )
    n_rec = len(golds)
    lo_r, hi_r = wilson(rec_flagged, n_rec)
    lo_f, hi_f = wilson(fields_flagged, fields_total)
    clean = [
        {
            "unit": "record",
            "n": n_rec,
            "flagged": rec_flagged,
            "rate": _r(rec_flagged / n_rec if n_rec else float("nan")),
            "wilson_lo": _r(lo_r),
            "wilson_hi": _r(hi_r),
        },
        {
            "unit": "field",
            "n": fields_total,
            "flagged": fields_flagged,
            "rate": _r(fields_flagged / fields_total if fields_total else float("nan")),
            "wilson_lo": _r(lo_f),
            "wilson_hi": _r(hi_f),
        },
    ]
    _csv(e4 / "clean_flag_rate.csv", clean)
    _jsonl(e4 / "clean_flagged_fields.jsonl", clean_rows)

    # ---- injections
    rec_inj = generate_record_level(golds, lex, n_per_type, seed)
    tr_inj = generate_transcript_level(golds, lex, n_per_type, seed)
    _jsonl(e4 / "injection_log_record.jsonl", log_rows(rec_inj))
    _jsonl(e4 / "injection_log_transcript.jsonl", log_rows(tr_inj))

    conditions = [
        ("record", "with_encounter_index", rec_inj, False, True),
        ("record", "no_encounter_index", [i for i in rec_inj if i["type"] == "i"], False, False),
        ("transcript", "text_only", tr_inj, False, True),
        ("transcript", "with_second_transcript", tr_inj, True, True),
    ]
    results = []
    samples = []
    agg: dict[tuple, dict] = {}
    for level, cond, injs, second, index in conditions:
        seen_samples: dict[str, int] = defaultdict(int)
        for inj in injs:
            tr = inj["transcript"]
            v = val(
                verify(
                    inj["record"],
                    tr,
                    lexicon=lex,
                    config=cfg,
                    second_transcript=inj["clean_transcript"] if second else None,
                    encounter_index={tr["audio_id"]: inj["true_patient_ref"]} if index else None,
                )
            )
            flags = [c for c in v["checks"] if c["status"] == "flag"]
            item = _item_path(inj["field_path"])
            caught = not v["auto_acceptable"]
            at_field = any(
                c["field_path"] != "/" and _touches(c["field_path"], item) for c in flags
            )
            checks = sorted({c["check_id"] for c in flags})
            results.append(
                {
                    "id": inj["id"],
                    "level": level,
                    "condition": cond,
                    "type": inj["type"],
                    "caught": caught,
                    "caught_at_field": at_field,
                    "flagged_checks": checks,
                    "unique_key": inj["unique_key"],
                }
            )
            if seen_samples[inj["type"]] < 2:
                seen_samples[inj["type"]] += 1
                samples.append({"injection_id": inj["id"], "condition": cond, "verdict": v})
            a = agg.setdefault(
                (level, cond, inj["type"]),
                {
                    "n": 0,
                    "caught": 0,
                    "at_field": 0,
                    "uniq": set(),
                    "uniq_caught": set(),
                    "uniq_missed": set(),
                    "checks": defaultdict(int),
                    "only": defaultdict(int),
                },
            )
            a["n"] += 1
            a["caught"] += int(caught)
            a["at_field"] += int(at_field)
            a["uniq"].add(inj["unique_key"])
            (a["uniq_caught"] if caught else a["uniq_missed"]).add(inj["unique_key"])
            for cid in checks:
                a["checks"][cid] += 1
            if len(checks) == 1:
                a["only"][checks[0]] += 1
    _jsonl(e4 / "injection_results.jsonl", results)
    _jsonl(e4 / "sample_verdicts.jsonl", samples)

    catch_rows = []
    per_check_rows = []
    for (level, cond, t), a in sorted(agg.items()):
        lo, hi = wilson(a["caught"], a["n"])
        nu = len(a["uniq"])
        ulo, uhi = wilson(len(a["uniq_caught"]), nu)
        catch_rows.append(
            {
                "level": level,
                "condition": cond,
                "type": t,
                "type_name": TYPES[t],
                "n": a["n"],
                "caught": a["caught"],
                "rate": _r(a["caught"] / a["n"]),
                "wilson_lo": _r(lo),
                "wilson_hi": _r(hi),
                "caught_at_field": a["at_field"],
                "n_unique": nu,
                "unique_caught": len(a["uniq_caught"]),
                "unique_rate": _r(len(a["uniq_caught"]) / nu),
                "unique_wilson_lo": _r(ulo),
                "unique_wilson_hi": _r(uhi),
                "rule_of_three_upper_if_zero_missed_unique": _r(rule_of_three(nu))
                if not a["uniq_missed"]
                else "",
            }
        )
        for cid in CHECK_IDS:
            per_check_rows.append(
                {
                    "scope": f"{level}:{cond}:{t}",
                    "check_id": cid,
                    "n": a["n"],
                    "flagged": a["checks"][cid],
                    "rate": _r(a["checks"][cid] / a["n"]),
                    "caught_only_by_this_check": a["only"][cid],
                }
            )
    for cid in CHECK_IDS:
        per_check_rows.append(
            {
                "scope": "clean:records",
                "check_id": cid,
                "n": n_rec,
                "flagged": per_check_clean_rec[cid],
                "rate": _r(per_check_clean_rec[cid] / n_rec if n_rec else float("nan")),
                "caught_only_by_this_check": "",
            }
        )
        per_check_rows.append(
            {
                "scope": "clean:fields",
                "check_id": cid,
                "n": fields_total,
                "flagged": per_check_clean_field[cid],
                "rate": _r(
                    per_check_clean_field[cid] / fields_total if fields_total else float("nan")
                ),
                "caught_only_by_this_check": "",
            }
        )
    _csv(e4 / "catch_rates.csv", catch_rows)
    _csv(e4 / "per_check.csv", per_check_rows)

    summary = {
        "gold_source": str(Path(gold_dir).resolve().relative_to(ROOT))
        if Path(gold_dir).resolve().is_relative_to(ROOT)
        else str(gold_dir),
        "n_gold_conversations": n_rec,
        "lexicon": str(Path(lex.path).resolve().relative_to(ROOT))
        if Path(lex.path).resolve().is_relative_to(ROOT)
        else lex.path,
        "seed": seed,
        "n_per_type": n_per_type,
        "c7_threshold": cfg.c7_conf_threshold,
        "c7_threshold_status": cfg.c7_threshold_status,
        "disabled_checks": sorted(cfg.disabled),
        "verdicts_validated": val.n,
        "verdict_validation_errors": val.errors[:20],
        "clean_flag_rate": clean,
        "catch_rates": catch_rows,
        "note": "Planted errors, synthetic fixture gold (not native-validated). Duplicated mutations are not independent: use n_unique for confidence intervals. Never pool with natural errors.",
    }
    _dump(e4 / "summary.json", summary)
    (e4 / "summary.md").write_text(_summary_md(summary), encoding="utf-8")
    return summary


def _summary_md(s: dict) -> str:
    L = [
        "# E4 planted-mistake results (m4_verify)",
        "",
        f"Gold source: `{s['gold_source']}` ({s['n_gold_conversations']} conversations). Lexicon: `{s['lexicon']}`. "
        f"Seed {s['seed']}, {s['n_per_type']} injections per type. C7 threshold {s['c7_threshold']} ({s['c7_threshold_status']}). "
        f"Verdicts produced and validated against verdict.v1: {s['verdicts_validated']} (errors: {len(s['verdict_validation_errors'])}).",
        "",
        "PLANTED errors on SYNTHETIC fixture text (not native-validated). Many injections repeat the same mutation, "
        "so the honest sample size is `n_unique`; CIs on `n` overstate certainty.",
        "",
        "## Review burden on error-free gold",
        "",
        "| unit | n | flagged | rate | Wilson 95% CI |",
        "|---|---|---|---|---|",
    ]
    for r in s["clean_flag_rate"]:
        L.append(
            f"| {r['unit']} | {r['n']} | {r['flagged']} | {r['rate']} | {r['wilson_lo']}-{r['wilson_hi']} |"
        )
    L += [
        "",
        "## Catch rate (critical-error recall) per type",
        "",
        "| level | condition | type | n | caught | rate | n_unique | unique caught | unique Wilson 95% CI |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in s["catch_rates"]:
        L.append(
            f"| {r['level']} | {r['condition']} | {r['type']} {r['type_name']} | {r['n']} | {r['caught']} | {r['rate']} | {r['n_unique']} | {r['unique_caught']} | {r['unique_wilson_lo']}-{r['unique_wilson_hi']} |"
        )
    L += [
        "",
        "Transcript level: `text_only` = what text-only checks can see when the ASR error is consistent with the record; "
        "`with_second_transcript` = C7 compares against a second, correct transcript (an ASR cross-check). "
        "Anything caught only in the second condition NEEDS an audio/ASR cross-check. C7 word-confidence was not "
        "evaluated here: synthetic injections have no real confidences and inventing them would be circular.",
        "",
    ]
    return "\n".join(L)


def run_all(
    out_dir: Path,
    gold_dir: Path | None = None,
    lexicon_path: Path | None = None,
    n_per_type: int = 200,
    seed: int = SEED,
    cfg: Config | None = None,
) -> dict:
    cfg = cfg or default_config()
    lex = load_lexicon(lexicon_path or cfg.lexicon_path or (FIX / "lexicon" / "drugs_fixture.csv"))
    mock = run_mock(out_dir, lex, cfg)
    e4 = run_e4(gold_dir or (FIX / "gold" / "valid"), lex, cfg, out_dir, n_per_type, seed)
    return {"mock": mock, "e4": e4}
