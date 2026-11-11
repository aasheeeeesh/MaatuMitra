"""Run the verifier on fixtures (mock) and the E4 planted-mistake experiment; write results.

Outputs (out_dir, default results/m4_verify/):
  verdicts/<record_id>.json            verdict.v1 for every fixture record (mock run)
  fixture_per_check.csv                per-check status counts on the fixture records
  e4/clean_verdicts/*.json             verdict.v1 for every clean gold record
  e4/injection_log_{record,transcript}.jsonl   exactly what was injected (id, type, field_path, before, after)
  e4/injection_results.jsonl           per injection and condition: caught at the field? detected? which checks
  e4/sample_verdicts.jsonl             2 full verdicts per type and condition (all others validated in memory)
  e4/catch_rates.csv                   per level/condition/type, UNIQUE mutations: caught at field, detected,
                                       sent to review, each k/n with a Wilson 95% CI
  e4/per_field.csv                     the same per injected field (dose_value, negated, patient_ref, ...)
  e4/per_check.csv                     per scope and check: unique mutations flagged at the field / detected / only
  e4/clean_flag_rate.csv               review burden on the SAME error-free records (any flag; excl. cannot_verify)
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
from m4_verify.checks import is_cannot_verify, reason_code
from m4_verify.config import CHECK_IDS, ROOT, Config, default_config
from m4_verify.lexicon import Lexicon, load_lexicon
from m4_verify.planted import (
    SEED,
    TYPES,
    confusables,
    generate_record_level,
    generate_transcript_level,
    gold_to_pair,
    log_rows,
)
from m4_verify.split_guard import load_gold
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
# Integrity review D-90 (fix pass 2026-11-11):
#  * a planted error counts as CAUGHT only when a flag lands on the injected field (at_field);
#  * DETECTED is stricter: the flag at the field is not cannot_verify and was not already raised
#    on the error-free version of the same record (so it is caused by the mutation);
#  * all headline numbers use UNIQUE mutations (repeats of one mutation are not new trials);
#  * the second-transcript condition uses the uncorrupted gold text: an ORACLE upper bound.
ORACLE = "oracle_second_transcript_upper_bound"
CONDITION_NOTE = {
    "with_encounter_index": "record-level mutation, encounter index given (patient link checkable)",
    "no_encounter_index": "record-level wrong patient_ref, no encounter index (known blind spot)",
    "text_only": "ASR-like transcript edit; record agrees with the corrupted text; text-only checks",
    ORACLE: "same, plus C7 against the UNCORRUPTED gold text as second transcript: an UPPER BOUND "
    "(a real second ASR output has its own errors)",
}
DOSE_PAIR = {"dose_value", "dose_unit"}


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


def at_field(flag: dict, inj_path: str) -> bool:
    """Does this flag concern the injected field? Exact field, the item itself (item-level C7/C8
    flags), the other half of the dose pair, or a max-daily flag for a dose/frequency error.
    Record-level '/' flags and flags on OTHER items never count."""
    fp = flag["field_path"]
    if inj_path == "/patient_ref":
        return fp == "/patient_ref"
    item = _item_path(inj_path)
    fld = inj_path.rsplit("/", 1)[1]
    if fp in (inj_path, item):
        return True
    if not fp.startswith(item + "/"):
        return False
    ffld = fp[len(item) + 1 :].split("/")[0]
    if fld in DOSE_PAIR and ffld in DOSE_PAIR:
        return True
    return fld in ("dose_value", "dose_unit", "frequency_per_day") and (
        reason_code(flag["reason"]) == "exceeds_max_daily"
    )


def unique_outcomes(rows: list[dict], key: str) -> tuple[int, int, int]:
    """(k unique mutations with outcome True, n unique mutations, n unique with MIXED outcomes).
    A mutation whose repeats disagree is counted as NOT caught (conservative)."""
    seen: dict[str, set[bool]] = defaultdict(set)
    for r in rows:
        seen[r["unique_key"]].add(bool(r[key]))
    k = sum(1 for v in seen.values() if v == {True})
    mixed = sum(1 for v in seen.values() if len(v) > 1)
    return k, len(seen), mixed


def _ci(k: int, n: int) -> tuple[float | str, float | str]:
    lo, hi = wilson(k, n)
    return _r(lo), _r(hi)


def _flag_key(c: dict) -> tuple[str, str, str]:
    return (c["check_id"], c["field_path"], c["reason"])


def run_e4(
    gold_dir: Path,
    lex: Lexicon,
    cfg: Config,
    out_dir: Path,
    n_per_type: int = 200,
    seed: int = SEED,
) -> dict:
    gl = load_gold(gold_dir)  # DEV allow-list guard (m4_verify/split_guard.py); raises on TEST data
    golds = gl.docs
    e4 = out_dir / "e4"
    val = Validated()

    # ---- clean (error-free) records: review burden, measured on the SAME source records
    clean_rows = []
    clean_flags: dict[str, set] = {}
    n_rec = len(golds)
    rec_any = rec_real = fields_total = f_any = f_real = 0
    per_check_clean_rec: dict[str, int] = defaultdict(int)
    per_check_clean_field: dict[str, int] = defaultdict(int)
    clean_codes: dict[str, int] = defaultdict(int)
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
        clean_flags[g["conversation_id"]] = {_flag_key(c) for c in flags}
        real = [c for c in flags if not is_cannot_verify(c["reason"])]
        rec_any += int(bool(flags))
        rec_real += int(bool(real))
        for c in flags:
            clean_codes[f"{c['check_id']}:{reason_code(c['reason']) or 'uncoded'}"] += 1
        for cid in {c["check_id"] for c in flags}:
            per_check_clean_rec[cid] += 1
        for fld in _record_fields(rec):
            fields_total += 1
            hit = [c for c in flags if _touches(c["field_path"], fld)]
            hit_real = [c for c in hit if not is_cannot_verify(c["reason"])]
            f_any += int(bool(hit))
            f_real += int(bool(hit_real))
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

    def _burden(unit, n, k_any, k_real):
        lo, hi = _ci(k_any, n)
        lo2, hi2 = _ci(k_real, n)
        return {
            "unit": unit,
            "n": n,
            "flagged": k_any,
            "rate": _r(k_any / n if n else float("nan")),
            "wilson_lo": lo,
            "wilson_hi": hi,
            "flagged_excl_cannot_verify": k_real,
            "rate_excl_cannot_verify": _r(k_real / n if n else float("nan")),
            "excl_wilson_lo": lo2,
            "excl_wilson_hi": hi2,
        }

    clean = [
        _burden("record", n_rec, rec_any, rec_real),
        _burden("field", fields_total, f_any, f_real),
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
        ("transcript", ORACLE, tr_inj, True, True),
    ]
    results = []
    samples = []
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
            fpath = inj["field_path"]
            hit = [c for c in flags if at_field(c, fpath)]
            before = clean_flags.get(inj["source_id"], set())
            new_real = [
                c for c in hit if not is_cannot_verify(c["reason"]) and _flag_key(c) not in before
            ]
            results.append(
                {
                    "id": inj["id"],
                    "level": level,
                    "condition": cond,
                    "type": inj["type"],
                    "field": fpath.rsplit("/", 1)[1],
                    "field_path": fpath,
                    "unique_key": inj["unique_key"],
                    "sent_to_review": not v["auto_acceptable"],
                    "caught_at_field": bool(hit),
                    "caught": bool(hit),  # = caught_at_field (key read by m6_ui)
                    "detected_at_field": bool(new_real),
                    "flagged_checks": sorted({c["check_id"] for c in flags}),
                    "at_field_checks": sorted({c["check_id"] for c in hit}),
                    "detected_checks": sorted({c["check_id"] for c in new_real}),
                    "at_field_reasons": [f"{c['check_id']}: {c['reason'][:160]}" for c in hit][:4],
                }
            )
            if seen_samples[inj["type"]] < 2:
                seen_samples[inj["type"]] += 1
                samples.append({"injection_id": inj["id"], "condition": cond, "verdict": v})
    _jsonl(e4 / "injection_results.jsonl", results)
    _jsonl(e4 / "sample_verdicts.jsonl", samples)

    def _row(rows, extra):
        k_f, n, mixed = unique_outcomes(rows, "caught_at_field")
        k_d, _, mixed_d = unique_outcomes(rows, "detected_at_field")
        k_s, _, _ = unique_outcomes(rows, "sent_to_review")
        lo, hi = _ci(k_f, n)
        dlo, dhi = _ci(k_d, n)
        slo, shi = _ci(k_s, n)
        return {
            **extra,
            "n_unique": n,
            "caught_at_field_unique": k_f,
            "caught_at_field_rate": _r(k_f / n if n else float("nan")),
            "caught_at_field_wilson_lo": lo,
            "caught_at_field_wilson_hi": hi,
            "detected_unique": k_d,
            "detected_rate": _r(k_d / n if n else float("nan")),
            "detected_wilson_lo": dlo,
            "detected_wilson_hi": dhi,
            "sent_to_review_unique": k_s,
            "sent_to_review_wilson_lo": slo,
            "sent_to_review_wilson_hi": shi,
            "rule_of_three_upper_if_none_missed": _r(rule_of_three(n)) if k_f == n else "",
            "unique_with_mixed_outcomes": max(mixed, mixed_d),
            "n_injections": len(rows),
            # backward-compatible columns read by m6_ui/failures.py (since the fix pass they hold
            # the HONEST numbers: unique mutations, caught = flag on the injected field)
            "n": n,
            "caught": k_f,
            "unique_caught": k_f,
        }

    groups: dict[tuple, list[dict]] = defaultdict(list)
    fgroups: dict[tuple, list[dict]] = defaultdict(list)
    for r in results:
        groups[(r["level"], r["condition"], r["type"])].append(r)
        fgroups[(r["level"], r["condition"], r["field"])].append(r)
    catch_rows = [
        _row(rows, {"level": lv, "condition": c, "type": t, "type_name": TYPES[t]})
        for (lv, c, t), rows in sorted(groups.items())
    ]
    field_rows = [
        _row(rows, {"level": lv, "condition": c, "field": f})
        for (lv, c, f), rows in sorted(fgroups.items())
    ]

    per_check_rows = []
    for (lv, c, t), rows in sorted(groups.items()):
        n = len({r["unique_key"] for r in rows})
        for cid in CHECK_IDS:
            at = {r["unique_key"] for r in rows if cid in r["at_field_checks"]}
            det = {r["unique_key"] for r in rows if cid in r["detected_checks"]}
            only = {r["unique_key"] for r in rows if r["detected_checks"] == [cid]}
            per_check_rows.append(
                {
                    "scope": f"{lv}:{c}:{t}",
                    "check_id": cid,
                    "n_unique": n,
                    "flag_at_field_unique": len(at),
                    "detected_unique": len(det),
                    "detected_only_by_this_check_unique": len(only),
                }
            )
    for cid in CHECK_IDS:
        per_check_rows.append(
            {
                "scope": "clean:records",
                "check_id": cid,
                "n_unique": n_rec,
                "flag_at_field_unique": per_check_clean_rec[cid],
                "detected_unique": "",
                "detected_only_by_this_check_unique": "",
            }
        )
        per_check_rows.append(
            {
                "scope": "clean:fields",
                "check_id": cid,
                "n_unique": fields_total,
                "flag_at_field_unique": per_check_clean_field[cid],
                "detected_unique": "",
                "detected_only_by_this_check_unique": "",
            }
        )
    if catch_rows:
        _csv(e4 / "catch_rates.csv", catch_rows)
        _csv(e4 / "per_field.csv", field_rows)
    _csv(e4 / "per_check.csv", per_check_rows)
    no_conf = sum(
        1
        for g in golds
        for m in g["gold_record"]["medications"]
        if not confusables(m["drug"].casefold(), lex)
    )
    n_meds = sum(len(g["gold_record"]["medications"]) for g in golds)

    def _rel(p):
        p = Path(p).resolve()
        return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)

    summary = {
        "gold_source": _rel(gold_dir),
        "gold_load": {
            "n_loaded": len(golds),
            "skipped_not_in_dev_txt_never_opened": gl.skipped_not_allowed,
            "under_data": gl.under_data,
            "rule": "under data/: only ids in data/splits/dev.txt are opened; test ids, test families "
            "and test.lock hashes are refused everywhere (m4_verify/split_guard.py)",
        },
        "n_gold_conversations": n_rec,
        "lexicon": _rel(lex.path),
        "seed": seed,
        "n_per_type": n_per_type,
        "c7_threshold": cfg.c7_conf_threshold,
        "c7_threshold_status": cfg.c7_threshold_status,
        "disabled_checks": sorted(cfg.disabled),
        "verdicts_validated": val.n,
        "verdict_validation_errors": val.errors[:20],
        "clean_flag_rate": clean,
        "clean_flag_codes": dict(sorted(clean_codes.items())),
        "catch_rates": catch_rows,
        "per_field": field_rows,
        "drug_swap_coverage": {
            "medication_items": n_meds,
            "items_whose_drug_has_no_lexicon_confusable_(never_swapped)": no_conf,
        },
        "conditions": CONDITION_NOTE,
        "definitions": {
            "caught_at_field": "a flag lands on the injected field, its item (item-level flag), "
            "the other half of the dose pair, or a max-daily flag; '/' flags and other items do not count",
            "detected": "caught_at_field by a flag that is NOT cannot_verify and was NOT already raised "
            "on the error-free version of the same record",
            "sent_to_review": "the record is not auto_acceptable (any flag anywhere)",
            "unique": "one mutation = (conversation, field, new value[, edit]); repeats are not new trials",
        },
        "note": "PLANTED errors only (never pool with natural errors). Synthetic Kannada text, not "
        "native-validated. Report detected/caught next to the clean-field flag rate on the SAME records.",
    }
    _dump(e4 / "summary.json", summary)
    (e4 / "summary.md").write_text(_summary_md(summary), encoding="utf-8")
    return summary


def _ci_txt(r: dict, k: str, lo: str, hi: str) -> str:
    return f"{r[k]}/{r['n_unique']} [{r[lo]}, {r[hi]}]"


def _summary_md(s: dict) -> str:
    gl = s["gold_load"]
    L = [
        "# E4 planted-mistake results (m4_verify)",
        "",
        f"Gold source: `{s['gold_source']}`: {gl['n_loaded']} conversations loaded "
        f"({gl['skipped_not_in_dev_txt_never_opened']} files not in dev.txt, never opened). "
        f"Lexicon: `{s['lexicon']}`. Seed {s['seed']}, up to {s['n_per_type']} injections per type "
        f"(repeats of the same mutation are counted ONCE). C7 threshold {s['c7_threshold']} "
        f"({s['c7_threshold_status']}). Verdicts validated against verdict.v1: {s['verdicts_validated']} "
        f"(errors: {len(s['verdict_validation_errors'])}).",
        "",
        "PLANTED errors on SYNTHETIC text (not native-validated). Every proportion is k/n over UNIQUE "
        "mutations with a Wilson 95% CI in brackets. No clinical claim is made.",
        "",
        "## Review burden on the SAME error-free records (read this next to every recall number)",
        "",
        "| unit | n | flagged (any) | Wilson 95% CI | flagged excl. cannot_verify | Wilson 95% CI |",
        "|---|---|---|---|---|---|",
    ]
    for r in s["clean_flag_rate"]:
        L.append(
            f"| {r['unit']} | {r['n']} | {r['flagged']} ({r['rate']}) | [{r['wilson_lo']}, {r['wilson_hi']}] "
            f"| {r['flagged_excl_cannot_verify']} ({r['rate_excl_cannot_verify']}) | "
            f"[{r['excl_wilson_lo']}, {r['excl_wilson_hi']}] |"
        )
    L += [
        "",
        "Flags on error-free records by check and reason code (cannot_verify = the rules cannot check "
        "this value; it is not evidence of an error):",
        "",
        ", ".join(f"`{k}` {v}" for k, v in s["clean_flag_codes"].items()) or "(none)",
        "",
        "## Catch rate per planted type (unique mutations)",
        "",
        "`caught` = a flag on the injected field; `detected` = such a flag that is not cannot_verify and "
        "is new compared with the error-free record; `to review` = any flag anywhere in the record.",
        "",
        "| level | condition | type | n_unique | caught at field [CI] | detected [CI] | to review [CI] | injections |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in s["catch_rates"]:
        L.append(
            f"| {r['level']} | {r['condition']} | {r['type']} {r['type_name']} | {r['n_unique']} | "
            f"{_ci_txt(r, 'caught_at_field_unique', 'caught_at_field_wilson_lo', 'caught_at_field_wilson_hi')} | "
            f"{_ci_txt(r, 'detected_unique', 'detected_wilson_lo', 'detected_wilson_hi')} | "
            f"{_ci_txt(r, 'sent_to_review_unique', 'sent_to_review_wilson_lo', 'sent_to_review_wilson_hi')} | "
            f"{r['n_injections']} |"
        )
    L += [
        "",
        "## Per field (unique mutations)",
        "",
        "| level | condition | field | n_unique | caught at field [CI] | detected [CI] |",
        "|---|---|---|---|---|---|",
    ]
    for r in s["per_field"]:
        L.append(
            f"| {r['level']} | {r['condition']} | {r['field']} | {r['n_unique']} | "
            f"{_ci_txt(r, 'caught_at_field_unique', 'caught_at_field_wilson_lo', 'caught_at_field_wilson_hi')} | "
            f"{_ci_txt(r, 'detected_unique', 'detected_wilson_lo', 'detected_wilson_hi')} |"
        )
    cov = s["drug_swap_coverage"]
    L += [
        "",
        "## Conditions",
        "",
        *[f"- `{k}`: {v}" for k, v in s["conditions"].items()],
        "",
        f"Transcript level: `text_only` = detectable by text-only checks; anything caught only under `{ORACLE}` "
        "NEEDS an audio/ASR cross-check, and that row is an UPPER BOUND (the second transcript is the "
        "uncorrupted gold text). C7 word confidence was not evaluated: synthetic injections have no real "
        "confidences and inventing them would be circular.",
        "",
        f"Drug swaps (type f) use only lexicon confusable pairs: {cov['items_whose_drug_has_no_lexicon_confusable_(never_swapped)']} "
        f"of {cov['medication_items']} medication items have a drug with no listed confusable and are never swapped.",
        "",
        "Per check: `per_check.csv` (unique mutations where the check flagged at the field / detected / was "
        "the only detector). Raw rows: `injection_results.jsonl`; logs: `injection_log_*.jsonl`.",
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
