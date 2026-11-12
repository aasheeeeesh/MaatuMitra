"""E4-v2: planted mistakes in the NEW record.v2 fields (a SEPARATE table from the v1 E4).

Types (Phase C):
  j route swap       medications[i].route -> another route (oral <-> iv/im/injection ...)
  k strength drop    medications[i].strength_value + strength_unit -> null (and its evidence removed)
  l status flip      medications[i].status "given" <-> "not given" (prescribed -> advised_against ...)
  m age band flip    patient_age_band child/infant/adolescent <-> adult

Source records: the v1 gold-derived record (planted.gold_to_pair) converted by
contracts/migrate_v1_to_v2.py, then the new fields FILLED from the matching gold.v2 document
(route, strength, formulation, as_needed, food_timing, status, speaker, field evidence, age band,
weight). A gold.v2 document whose v1 fields or text disagree with gold.v1 is not used (counted).
RECORD level only: the record is mutated, the transcript stays the gold text (these are extractor
errors, not ASR errors; no transcript-level v2 table is produced).

DEV ONLY: both gold folders are read through m4_verify/split_guard.py (allow-list on
data/splits/dev.txt; test ids, test families and test.lock hashes refused anywhere).
Unique mutations are counted once (same convention as the v1 E4, D-115).
"""

from __future__ import annotations

import copy
import csv
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contracts.migrate_v1_to_v2 import migrate_record
from contracts.validate import conversation_text, validate_doc
from m4_verify.checks import is_cannot_verify, reason_code, severity_class
from m4_verify.config import Config
from m4_verify.evaluate import unique_outcomes
from m4_verify.lexicon import Lexicon
from m4_verify.planted import SEED, _get, _set, gold_to_pair
from m4_verify.split_guard import load_gold
from m4_verify.stats import wilson
from m4_verify.verifier import verify

TYPES_V2 = {"j": "route swap", "k": "strength drop", "l": "status flip", "m": "age band flip"}
ROUTE_SWAP = {
    "oral": ["iv", "im", "injection_unspecified"],
    "injection_unspecified": ["oral", "iv", "im"],
    "iv": ["im", "sc", "oral"],
    "im": ["iv", "sc", "oral"],
    "sc": ["iv", "im", "oral"],
    "topical": ["oral", "iv"],
    "inhaled": ["oral", "iv"],
    "rectal": ["oral", "iv"],
    "other": ["oral", "iv"],
    "unknown": ["oral", "iv"],
}
# given (prescribed, already_taken, continue_existing) <-> not given (not_taken, advised_against):
# the CR-NEG flip of docs/severity.md. stopped_early has no opposite; it flips to prescribed (MAJOR).
STATUS_FLIP = {
    "prescribed": ["advised_against", "not_taken"],
    "continue_existing": ["advised_against", "not_taken"],
    "already_taken": ["not_taken", "advised_against"],
    "not_taken": ["already_taken", "prescribed"],
    "advised_against": ["prescribed"],
    "stopped_early": ["prescribed"],
}
AGE_FLIP = {
    "infant": "adult",
    "child": "adult",
    "adolescent": "adult",
    "unknown": "adult",
    "adult": "child",
    "older_adult": "child",
}
NEW_MED_FIELDS = (
    "route",
    "strength_value",
    "strength_unit",
    "formulation",
    "as_needed",
    "food_timing",
    "status",
    "speaker",
)
V1_MED_FIELDS = ("drug", "dose_value", "dose_unit", "frequency_per_day", "duration_days", "negated")
V2_FIELD_KINDS = (
    "route",
    "strength_value",
    "formulation",
    "as_needed",
    "food_timing",
    "status",
    "speaker",
)
LOG_KEYS = (
    "id",
    "type",
    "type_name",
    "level",
    "source_id",
    "field_path",
    "before",
    "after",
    "note",
    "unique_key",
)


@dataclass
class Pair:
    cid: str
    transcript: dict[str, Any]
    record: dict[str, Any]


def _ev(gs: dict[str, Any]) -> dict[str, Any]:
    return {
        "span_text": gs["span_text"],
        "char_start": gs["char_start"],
        "char_end": gs["char_end"],
        "audio_start": None,
        "audio_end": None,
    }


def _same_span(ev: dict[str, Any], gs: dict[str, Any]) -> bool:
    return (ev["char_start"], ev["char_end"], ev["span_text"]) == (
        gs["char_start"],
        gs["char_end"],
        gs["span_text"],
    )


def fill_v2(rec: dict[str, Any], g2: dict[str, Any], text: str) -> dict[str, Any]:
    """Fill the new fields of a MIGRATED record from gold.v2. ValueError if they disagree."""
    if conversation_text(g2["turns"]) != text:
        raise ValueError("gold.v2 conversation text differs from gold.v1")
    gr = g2["gold_record"]
    out = copy.deepcopy(rec)
    if len(gr["medications"]) != len(out["medications"]) or len(gr["advice"]) != len(out["advice"]):
        raise ValueError("different number of medications or advice items")
    for m, gm in zip(out["medications"], gr["medications"], strict=True):
        for f in V1_MED_FIELDS:
            if m[f] != gm[f]:
                raise ValueError(f"medication field {f}: v1 {m[f]!r} vs v2 {gm[f]!r}")
        if not _same_span(m["evidence"], gm["gold_span"]):
            raise ValueError("medication evidence span differs")
        for f in NEW_MED_FIELDS:
            m[f] = gm[f]
        m["field_evidence"] = {k: _ev(v) for k, v in gm["gold_field_spans"].items()}
    for a, ga in zip(out["advice"], gr["advice"], strict=True):
        if a["text"] != ga["text"] or not _same_span(a["evidence"], ga["gold_span"]):
            raise ValueError("advice item differs")
        a["speaker"] = ga["speaker"]
    for key, val in (("patient_age_band", "band"), ("weight_kg", "value")):
        obj = gr.get(key)
        out[key] = None if obj is None else {val: obj[val], "evidence": _ev(obj["gold_span"])}
    errs = validate_doc("record.v2", out)
    if errs:
        raise ValueError(f"filled record is not valid record.v2: {errs[:3]}")
    return out


def build_pairs(g1_docs: list[dict], g2_docs: list[dict]) -> tuple[list[Pair], Counter]:
    by1 = {g["conversation_id"]: g for g in g1_docs}
    problems: Counter = Counter({"no_v1_gold": 0, "v1_v2_mismatch": 0})
    pairs = []
    for g2 in sorted(g2_docs, key=lambda d: d["conversation_id"]):
        cid = g2["conversation_id"]
        if cid not in by1:
            problems["no_v1_gold"] += 1
            continue
        tr, rec1 = gold_to_pair(by1[cid])
        try:
            rec = fill_v2(migrate_record(rec1), g2, tr["text"])
        except ValueError:
            problems["v1_v2_mismatch"] += 1
            continue
        pairs.append(Pair(cid, tr, rec))
    return pairs, problems


# --------------------------------------------------------------------------- generator
def candidates(t: str, rec: dict[str, Any]) -> list[str]:
    out = []
    if t == "m":
        return ["/patient_age_band"] if rec.get("patient_age_band") else []
    for i, m in enumerate(rec["medications"]):
        if t == "j" and m["route"] is not None:
            out.append(f"/medications/{i}/route")
        elif t == "k" and m["strength_value"] is not None:
            out.append(f"/medications/{i}/strength_value")
        elif t == "l" and m["status"] in STATUS_FLIP:
            out.append(f"/medications/{i}/status")
    return out


def _mutate(t: str, path: str, rec: dict[str, Any], rng: random.Random):
    new = copy.deepcopy(rec)
    if t == "m":
        before = rec["patient_age_band"]["band"]
        after = AGE_FLIP[before]
        new["patient_age_band"]["band"] = after
        return new, before, after
    before = _get(rec, path)
    med = _get(new, path.rsplit("/", 1)[0])
    if t == "j":
        after = rng.choice(ROUTE_SWAP[before])
        _set(new, path, after)
    elif t == "k":
        before = f"{before} {med['strength_unit']}"
        after = None
        med["strength_value"] = med["strength_unit"] = None
        med["field_evidence"].pop("strength", None)
    elif t == "l":
        after = rng.choice(STATUS_FLIP[before])
        _set(new, path, after)
    else:
        raise ValueError(t)
    return new, before, after


def generate_v2(pairs: list[Pair], n_per_type: int = 200, seed: int = SEED) -> list[dict]:
    out: list[dict] = []
    for t in TYPES_V2:
        rng = random.Random(f"{seed}-record-v2-{t}")  # noqa: S311 (deterministic sampling, not crypto)
        cands = [(k, p) for k, pr in enumerate(pairs) for p in candidates(t, pr.record)]
        if not cands:
            continue
        for made in range(1, n_per_type + 1):
            k, path = cands[(made - 1) % len(cands)]
            pr = pairs[k]
            new, before, after = _mutate(t, path, pr.record, rng)
            out.append(
                {
                    "id": f"E4V2-R-{t}-{made:04d}",
                    "type": t,
                    "type_name": TYPES_V2[t],
                    "level": "record",
                    "source_id": pr.cid,
                    "field_path": path,
                    "before": before,
                    "after": after,
                    "note": "field evidence kept (points at the ORIGINAL words)"
                    if t != "k"
                    else "strength and its evidence removed",
                    "unique_key": f"{pr.cid}|{path}|{after}",
                    "record": new,
                }
            )
    return out


def log_rows(injections: list[dict]) -> list[dict]:
    return [{k: inj[k] for k in LOG_KEYS} for inj in injections]


# --------------------------------------------------------------------------- evaluation
def at_field_v2(flag: dict[str, Any], inj: dict[str, Any]) -> bool:
    fp, path = flag["field_path"], inj["field_path"]
    if inj["type"] == "m":
        return fp == "/patient_age_band"
    item = path.rsplit("/", 1)[0]
    if fp in (path, item):
        return True
    if inj["type"] == "k":
        return fp == f"{item}/strength_unit" or (
            fp == f"{item}/dose_value" and severity_class(flag["reason"]) == "CR-LIQUID-STRENGTH"
        )
    return False


def _key(c: dict) -> tuple[str, str, str]:
    return (c["check_id"], c["field_path"], c["reason"])


def _v2_paths(rec: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    for i, _ in enumerate(rec["medications"]):
        out += [(k, f"/medications/{i}/{k}") for k in V2_FIELD_KINDS]
    for k in ("patient_age_band", "weight_kg"):
        if rec.get(k) is not None:
            out.append((k, f"/{k}"))
    return out


def evaluate(pairs: list[Pair], injections: list[dict], lex: Lexicon, cfg: Config) -> dict:
    errors: list[str] = []
    n_verdicts = 0

    def run(rec, tr, cid):
        nonlocal n_verdicts
        v = verify(rec, tr, lexicon=lex, config=cfg, encounter_index={cid: rec["patient_ref"]})
        n_verdicts += 1
        e = validate_doc("verdict", v)
        if e:
            errors.append(f"{rec['record_id']}: {e[:2]}")
        return [c for c in v["checks"] if c["status"] == "flag"]

    clean_flags: dict[str, set] = {}
    by_cid = {p.cid: p for p in pairs}
    rec_any = rec_real = 0
    field_n: Counter = Counter()
    field_flag: Counter = Counter()
    codes: Counter = Counter()
    clean_rows = []
    for p in pairs:
        flags = run(p.record, p.transcript, p.cid)
        clean_flags[p.cid] = {_key(c) for c in flags}
        rec_any += int(bool(flags))
        rec_real += int(any(not is_cannot_verify(c["reason"]) for c in flags))
        for c in flags:
            codes[f"{c['check_id']}:{reason_code(c['reason']) or 'uncoded'}"] += 1
        for kind, path in _v2_paths(p.record):
            field_n[kind] += 1
            hit = [c for c in flags if c["field_path"] == path]
            if hit:
                field_flag[kind] += 1
                clean_rows.append(
                    {
                        "record_id": p.record["record_id"],
                        "field": path,
                        "flags": [f"{c['check_id']}: {c['reason']}" for c in hit],
                    }
                )
    results = []
    for inj in injections:
        p = by_cid[inj["source_id"]]
        flags = run(inj["record"], p.transcript, p.cid)
        hit = [c for c in flags if at_field_v2(c, inj)]
        new_real = [
            c
            for c in hit
            if not is_cannot_verify(c["reason"]) and _key(c) not in clean_flags[p.cid]
        ]
        results.append(
            {
                "id": inj["id"],
                "type": inj["type"],
                "type_name": inj["type_name"],
                "field_path": inj["field_path"],
                "unique_key": inj["unique_key"],
                "caught_at_field": bool(hit),
                "detected": bool(new_real),
                "to_review": bool(flags),
                "checks_at_field": sorted({c["check_id"] for c in hit}),
                "classes_at_field": sorted({severity_class(c["reason"]) or "uncoded" for c in hit}),
                "reasons_at_field": [f"{c['check_id']}: {c['reason'][:160]}" for c in hit][:4],
            }
        )
    return {
        "results": results,
        "clean": {
            "n_records": len(pairs),
            "records_flagged": rec_any,
            "records_flagged_excl_cannot_verify": rec_real,
            "field_n": dict(field_n),
            "field_flagged": dict(field_flag),
            "codes": dict(codes.most_common()),
            "rows": clean_rows,
        },
        "verdicts": n_verdicts,
        "errors": errors,
    }


def _r(x: float) -> float | str:
    return "nan" if x != x else round(x, 4)


def _ci(k: int, n: int) -> list:
    lo, hi = wilson(k, n)
    return [_r(lo), _r(hi)]


def catch_rates(results: list[dict], pairs: list[Pair], injections: list[dict]) -> list[dict]:
    rows = []
    for t, name in TYPES_V2.items():
        rs = [r for r in results if r["type"] == t]
        n_cand = sum(len(candidates(t, p.record)) for p in pairs)
        row: dict[str, Any] = {
            "type": t,
            "type_name": name,
            "candidate_fields": n_cand,
            "injections": len(rs),
        }
        if not rs:
            row.update(
                n_unique=0,
                note=f"not measurable: 0 candidate fields in the {len(pairs)} source records (no record has this field filled)",
            )
            rows.append(row)
            continue
        kc, n, mixed = unique_outcomes(rs, "caught_at_field")
        kd, _, _ = unique_outcomes(rs, "detected")
        kr, _, _ = unique_outcomes(rs, "to_review")
        checks = Counter(c for r in rs for c in r["checks_at_field"])
        classes = Counter(c for r in rs for c in r["classes_at_field"])
        row.update(
            n_unique=n,
            mixed_repeats=mixed,
            caught=kc,
            caught_ci=_ci(kc, n),
            detected=kd,
            detected_ci=_ci(kd, n),
            to_review=kr,
            to_review_ci=_ci(kr, n),
            checks_at_field=dict(checks.most_common()),
            classes_at_field=dict(classes.most_common()),
            note="" if n >= 30 else f"only {n} unique mutations: wide interval",
        )
        rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _summary_md(s: dict) -> str:
    c = s["clean"]
    n = c["n_records"]
    lo, hi = _ci(c["records_flagged"], n)
    lo2, hi2 = _ci(c["records_flagged_excl_cannot_verify"], n)
    lines = [
        "# E4-v2 planted record.v2 mistakes (m4_verify)",
        "",
        f"Gold sources: `{s['gold_source']}` ({s['gold_loaded']} DEV loaded, {s['gold_skipped']} not in dev.txt, never opened) "
        f"and `{s['gold_v2_source']}` ({s['gold_v2_loaded']} DEV loaded, {s['gold_v2_skipped']} never opened). "
        f"Source records = contracts/migrate_v1_to_v2.py on the v1 gold record + new fields filled from gold.v2: "
        f"{n} built; skipped: {s['problems']}. Lexicon `{s['lexicon']}`. Seed {s['seed']}, up to {s['n_per_type']} "
        f"injections per type (repeats of one mutation counted ONCE). Verdicts validated against verdict.v1: "
        f"{s['verdicts']} (errors: {len(s['verdict_validation_errors'])}).",
        "",
        "PLANTED errors on SYNTHETIC, template-generated text (not native-validated), RECORD level only "
        "(no transcript-level v2 table). This table is SEPARATE from the v1 E4 table "
        "(results/m4_verify/dev/e4/summary.md). Every proportion is k/n over unique mutations with a "
        "Wilson 95% CI in brackets. No clinical claim is made.",
        "",
        "## Review burden on the SAME error-free v2 records",
        "",
        "| unit | n | flagged (any) | Wilson 95% CI | flagged excl. cannot_verify | Wilson 95% CI |",
        "|---|---|---|---|---|---|",
        f"| record | {n} | {c['records_flagged']} | [{lo}, {hi}] | {c['records_flagged_excl_cannot_verify']} | [{lo2}, {hi2}] |",
        "",
        "Flags on the new v2 fields of error-free records (a field = one path; flagged = any flag at exactly that path):",
        "",
        "| v2 field | n | flagged | Wilson 95% CI |",
        "|---|---|---|---|",
    ]
    for kind in (*V2_FIELD_KINDS, "patient_age_band", "weight_kg"):
        fn = c["field_n"].get(kind, 0)
        if fn:
            k = c["field_flagged"].get(kind, 0)
            a, b = _ci(k, fn)
            lines.append(f"| {kind} | {fn} | {k} | [{a}, {b}] |")
    lines += [
        "",
        "Flags on error-free records by check and reason code: "
        + ", ".join(f"`{k}` {v}" for k, v in c["codes"].items()),
        "",
        "## Catch rate per planted v2 type (unique mutations)",
        "",
        "`caught` = a flag on the injected field; `detected` = such a flag that is not cannot_verify and "
        "is new compared with the error-free record; `to review` = any flag anywhere in the record.",
        "",
        "| type | candidate fields | n_unique | caught [CI] | detected [CI] | to review [CI] | injections | checks at field | classes at field | note |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in s["catch_rates"]:
        if not r["n_unique"]:
            lines.append(
                f"| {r['type']} {r['type_name']} | {r['candidate_fields']} | 0 | - | - | - | 0 | - | - | {r['note']} |"
            )
            continue
        lines.append(
            f"| {r['type']} {r['type_name']} | {r['candidate_fields']} | {r['n_unique']} | "
            f"{r['caught']}/{r['n_unique']} {r['caught_ci']} | {r['detected']}/{r['n_unique']} {r['detected_ci']} | "
            f"{r['to_review']}/{r['n_unique']} {r['to_review_ci']} | {r['injections']} | "
            f"{', '.join(f'{k} {v}' for k, v in r['checks_at_field'].items())} | "
            f"{', '.join(f'{k} {v}' for k, v in r['classes_at_field'].items())} | {r['note']} |"
        )
    lines += [
        "",
        "Known limits: field evidence of a planted value still points at the ORIGINAL words, so these "
        "are 'value disagrees with its own span' errors (easy for rules). Speaker cannot be checked "
        "against transcript.v1 (no roles). C7 does not look at the new v2 spans. Every Kannada rule "
        "is AI-written, not native-validated.",
        "",
    ]
    return "\n".join(lines)


def run_e4_v2(
    gold_dir: Path | str,
    gold_v2_dir: Path | str,
    lex: Lexicon,
    cfg: Config,
    out_dir: Path | str,
    n_per_type: int = 200,
    seed: int = SEED,
) -> dict:
    g2 = load_gold(gold_v2_dir, schema="gold.v2")  # DEV allow-list guard; raises on TEST data
    g1 = load_gold(gold_dir)
    pairs, problems = build_pairs(g1.docs, g2.docs)
    injs = generate_v2(pairs, n_per_type, seed)
    ev = evaluate(pairs, injs, lex, cfg)
    rates = catch_rates(ev["results"], pairs, injs)
    out = Path(out_dir) / "e4_v2"
    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "injection_log_record.jsonl", log_rows(injs))
    _write_jsonl(out / "injection_results.jsonl", ev["results"])
    _write_jsonl(out / "clean_flagged_v2_fields.jsonl", ev["clean"]["rows"])
    with open(out / "catch_rates.csv", "w", encoding="utf-8", newline="") as fh:
        keys = [
            "type",
            "type_name",
            "candidate_fields",
            "n_unique",
            "caught",
            "caught_ci",
            "detected",
            "detected_ci",
            "to_review",
            "to_review_ci",
            "injections",
            "note",
        ]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rates:
            w.writerow({k: r.get(k, "") for k in keys})
    c = ev["clean"]
    with open(out / "clean_flag_rate.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["unit", "n", "flagged", "wilson_lo", "wilson_hi"])
        w.writerow(
            [
                "record",
                c["n_records"],
                c["records_flagged"],
                *_ci(c["records_flagged"], c["n_records"]),
            ]
        )
        w.writerow(
            [
                "record_excl_cannot_verify",
                c["n_records"],
                c["records_flagged_excl_cannot_verify"],
                *_ci(c["records_flagged_excl_cannot_verify"], c["n_records"]),
            ]
        )
        for kind, fn in sorted(c["field_n"].items()):
            k = c["field_flagged"].get(kind, 0)
            w.writerow([f"v2_field:{kind}", fn, k, *_ci(k, fn)])
    summary = {
        "gold_source": str(gold_dir),
        "gold_v2_source": str(gold_v2_dir),
        "gold_loaded": len(g1.docs),
        "gold_skipped": g1.skipped_not_allowed,
        "gold_v2_loaded": len(g2.docs),
        "gold_v2_skipped": g2.skipped_not_allowed,
        "problems": dict(problems),
        "lexicon": lex.path,
        "seed": seed,
        "n_per_type": n_per_type,
        "verdicts": ev["verdicts"],
        "verdict_validation_errors": ev["errors"],
        "clean": {k: v for k, v in c.items() if k != "rows"},
        "catch_rates": rates,
        "types": TYPES_V2,
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "summary.md").write_text(_summary_md(summary), encoding="utf-8")
    by_type: dict[str, int] = defaultdict(int)
    for i in injs:
        by_type[i["type"]] += 1
    summary["injections_by_type"] = dict(by_type)
    return summary
