"""E1-E6 computations from saved raw outputs (no GPU, no model). Every function returns
{"tables": {name: [row dict]}, "notes": [str], "gallery": [dict]}; report.py writes them.

All file access goes through ctx.guard (guard.SplitGuard): in a DEV run every test-split file
is refused. Planted (E4) and natural (E2) errors are never mixed; TTS and real audio are never
pooled; every proportion carries k, n and a Wilson 95% CI.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from m7_eval import asr_metrics, frames, scoring, stats
from m7_eval.guard import SplitGuard, TestSplitRefusedError

CHECKS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")


@dataclass
class Ctx:
    root: Path
    guard: SplitGuard
    cfg: dict
    split: str
    gold: dict[str, dict] = field(default_factory=dict)
    frame_by_turn: dict[tuple[str, int], str] = field(default_factory=dict)

    @property
    def inp(self) -> dict:
        return {**self.cfg["inputs"]["common"], **self.cfg["inputs"][self.split]}

    @property
    def seed(self) -> int:
        return int(self.cfg["seed"])

    def family(self, cid: str) -> str:
        g = self.gold.get(cid)
        return g["template_family_id"] if g else "unknown"


def _r(x: Any, nd: int = 4) -> Any:
    if isinstance(x, float):
        return round(x, nd)
    return x


def prop_cols(prefix: str, k: int, n: int) -> dict:
    p = stats.proportion(k, n)
    return {
        f"{prefix}_k": k,
        f"{prefix}_n": n,
        f"{prefix}_rate": _r(p["rate"]),
        f"{prefix}_wilson_lo": _r(p["wilson_lo"]),
        f"{prefix}_wilson_hi": _r(p["wilson_hi"]),
        f"{prefix}_rule_of_three_upper": _r(p["rule_of_three_upper"]),
    }


def load_context(root: Path, guard: SplitGuard, cfg: dict, split: str) -> Ctx:
    ctx = Ctx(root=root, guard=guard, cfg=cfg, split=split)
    gdir = ctx.inp["gold_dir"]
    for cid in sorted(guard.ids):
        p = f"{gdir}/{cid}.json"
        if guard.exists(p):
            ctx.gold[cid] = guard.read_json(p)
    plan_p = ctx.inp["split_plan"]
    if guard.exists(plan_p):
        plan = guard.read_json(plan_p)
        rows = frames.overlap_rows(frames.load_families(guard, plan))
        ctx.frame_by_turn = {(r["template_id"], r["turn_index"]): r["frame_status"] for r in rows}
        ctx.frame_rows = rows  # type: ignore[attr-defined]
    return ctx


# ============================================================================ frames
def frame_overlap(ctx: Ctx) -> dict:
    rows = getattr(ctx, "frame_rows", [])
    summary = []
    for split in ("dev", "test"):
        rs = [r for r in rows if r["split"] == split]
        if not rs:
            continue
        by = defaultdict(int)
        for r in rs:
            by[r["frame_status"]] += 1
        ncl = sum(r["n_clauses"] for r in rs)
        summary.append(
            {
                "template_split": split,
                "n_template_turns": len(rs),
                "seen_in_dev": by["seen"],
                "unseen": by["unseen"],
                "slot_only": by["slot_only"],
                **prop_cols("clauses_seen_in_dev", sum(r["clauses_seen_in_dev"] for r in rs), ncl),
            }
        )
    notes = [
        "Frame marker from TEMPLATE text only (data/templates); unit = template turn, not "
        "conversation turn. Dev templates are 'seen' by definition; the marker matters for the "
        "test split, where it slices results in the guarded eval-test run (D-90)."
    ]
    return {
        "tables": {"frame_overlap_templates": summary, "frame_overlap_turns": rows},
        "notes": notes,
    }


# ============================================================================ E1 ASR
def _variant_meta(cfg: dict, variant: str) -> dict:
    v = cfg["variants"].get(variant, {})
    return {"noise": v.get("noise"), "snr_db": v.get("snr_db"), "speed": v.get("speed")}


def e1_asr(ctx: Ctx) -> dict:
    g, inp, notes = ctx.guard, ctx.inp, []
    runs = [d for d in g.listdir(inp["m2_dir"]) if d.is_dir()]
    terms = asr_metrics.load_terms(ctx.root, ctx.root / inp["critical_terms"])
    fleurs: dict[str, str] | None = None
    utt: list[dict] = []
    skipped = defaultdict(int)
    for run in runs:
        tp = run / ctx.split / "transcripts.jsonl"
        if not g.exists(tp):
            continue
        meta = g.read_json(run / "run.json") if g.exists(run / "run.json") else {}
        for t in g.iter_jsonl(tp):
            aid, src = t["audio_id"], t["source"]
            if src == "public_real":
                if fleurs is None:
                    fleurs = {}
                    fp = inp["fleurs_subset"]
                    try:
                        if g.exists(fp):
                            for r in g.iter_jsonl(fp):
                                if r.get("split") == ctx.split:  # other-split rows dropped
                                    fleurs[Path(r["file_name"]).stem] = r["transcription"]
                    except TestSplitRefusedError as e:
                        notes.append(f"public_real reference not readable in a DEV run: {e}")
                ref = fleurs.get(aid)
                conv, voice, variant = None, t.get("speaker", "fleurs"), "clean"
            else:
                parts = aid.split("__")
                if len(parts) != 3:
                    skipped["bad_audio_id"] += 1
                    continue
                conv, voice, variant = parts
                if conv not in g.ids:
                    skipped["not_in_split"] += 1
                    continue
                if ctx.split == "dev" and voice in ctx.cfg["held_out_voices"]:
                    raise TestSplitRefusedError(f"held-out test voice {voice} in a DEV m2 output")
                gp = f"{inp['gold_transcripts_dir']}/{conv}__gold.json"
                ref = g.read_json(gp)["text"] if g.exists(gp) else None
            if ref is None:
                skipped["no_reference"] += 1
                continue
            m = asr_metrics.utterance_metrics(ref, t["text"])
            rec = terms.recall(ref, t["text"])
            dur = t.get("audio_duration_s")
            lat = t.get("latency_ms")
            utt.append(
                {
                    "model": run.name,
                    "model_name": t["model"]["name"],
                    "model_revision": t["model"].get("revision"),
                    "audio_id": aid,
                    "conversation_id": conv,
                    "source": src,
                    "voice": voice,
                    "variant": variant,
                    **_variant_meta(ctx.cfg, variant),
                    **{k: _r(v) for k, v in m.items()},
                    **{f"{c}_hits": rec[c][0] for c in asr_metrics.CLASSES},
                    **{f"{c}_n": rec[c][1] for c in asr_metrics.CLASSES},
                    "latency_ms": lat,
                    "audio_duration_s": dur,
                    "rtf": _r(lat / 1000 / dur) if lat is not None and dur else None,
                    "hardware": t.get("hardware") or meta.get("hardware"),
                }
            )
    if not utt:
        row = {
            "status": "m2 not run yet",
            "detail": f"no {inp['m2_dir']}/<run>/{ctx.split}/transcripts.jsonl found; E1 and "
            "the ASR part of H2 are pending (m2_asr is not built). Code tested on fixtures.",
        }
        return {"tables": {"e1_asr_summary": [row], "e1_asr_paired": [row]}, "notes": notes}
    for k, v in sorted(skipped.items()):
        notes.append(f"E1 skipped {v} utterances: {k}")
    summary = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for u in utt:
        groups[(u["model"], u["source"], u["variant"], u["voice"])].append(u)
        groups[(u["model"], u["source"], "ALL_VARIANTS", "ALL_VOICES")].append(u)
    for (model, src, variant, voice), us in sorted(groups.items()):
        row: dict[str, Any] = {
            "model": model,
            "source": src,
            "variant": variant,
            "voice": voice,
            "n_utterances": len(us),
        }
        for mname in ("cer", "gcer", "wer", "cer_nopunct"):
            xs = [u[mname] for u in us if u[mname] is not None]
            lo, hi = stats.bootstrap_mean_ci(xs, seed=ctx.seed)
            row[f"{mname}_mean"] = _r(float(np.mean(xs))) if xs else None
            row[f"{mname}_boot_lo"], row[f"{mname}_boot_hi"] = _r(lo), _r(hi)
        ce = sum(u["char_edits"] for u in us)
        rc = sum(u["ref_chars"] for u in us)
        row["cer_corpus"] = _r(ce / rc) if rc else None
        for c in asr_metrics.CLASSES:
            row.update(
                prop_cols(
                    f"recall_{c}", sum(u[f"{c}_hits"] for u in us), sum(u[f"{c}_n"] for u in us)
                )
            )
        lats = [u["latency_ms"] for u in us if u["latency_ms"] is not None]
        rtfs = [u["rtf"] for u in us if u["rtf"] is not None]
        row["latency_ms_p50"] = _r(float(np.percentile(lats, 50))) if lats else None
        row["latency_ms_p95"] = _r(float(np.percentile(lats, 95))) if lats else None
        row["rtf_mean"] = _r(float(np.mean(rtfs))) if rtfs else None
        row["hardware"] = us[0]["hardware"]
        summary.append(row)
    # paired comparison vs baseline on the SAME utterances, per source (never pooled)
    paired, common_lists = [], {}
    models = sorted({u["model"] for u in utt})
    base = next((m for m in models if ctx.cfg["asr_baseline"] in m), None)
    if base is None:
        notes.append(f"E1: baseline '{ctx.cfg['asr_baseline']}' not among m2 runs {models}")
    for src in sorted({u["source"] for u in utt}):
        by_model = {
            m: {u["audio_id"]: u["cer"] for u in utt if u["model"] == m and u["source"] == src}
            for m in models
        }
        for m in models:
            if base is None or m == base:
                continue
            common = sorted(set(by_model[m]) & set(by_model[base]))
            common_lists[f"{src}:{m}_vs_{base}"] = common
            r = stats.paired_bootstrap(
                [by_model[m][a] for a in common], [by_model[base][a] for a in common], seed=ctx.seed
            )
            paired.append(
                {
                    "source": src,
                    "candidate": m,
                    "baseline": base,
                    "n_common_utterances": r["n"],
                    "mean_cer_diff_candidate_minus_baseline": _r(r["mean_diff"]),
                    "boot_lo": _r(r["ci_lo"]),
                    "boot_hi": _r(r["ci_hi"]),
                    "ci_excludes_zero": r["excludes_zero"],
                    "seed": ctx.seed,
                }
            )
    return {
        "tables": {
            "e1_asr_summary": summary,
            "e1_asr_paired": paired or [{"status": "fewer than two m2 runs: no paired comparison"}],
            "e1_asr_utterances": utt,
        },
        "notes": notes,
        "common_subsets": common_lists,
    }


# ============================================================================ E2 extraction
def _ids_file(ctx: Ctx, p: str) -> list[str]:
    if not ctx.guard.exists(p):
        return []
    return [x for x in ctx.guard.read_text(p).split() if x and not x.startswith("#")]


def _score_dir(ctx: Ctx, rec_dir: str, prefix: str, ids: list[str]) -> list[tuple[str, str, list]]:
    out = []
    for cid in ids:
        gold = ctx.gold.get(cid)
        if gold is None:
            continue
        p = f"{rec_dir}/{prefix}-{cid}.json"
        rec = ctx.guard.read_json(p) if ctx.guard.exists(p) else None
        out.append((cid, gold["template_family_id"], scoring.score_record(rec, gold)))
    return out


def _sev_rows(
    system: str, subset: str, scored, ctx: Ctx, label: str, v2: bool
) -> tuple[list[dict], dict]:
    s = scoring.summarise([(f, r) for _, f, r in scored], v2=v2, seed=ctx.seed)
    rows = []
    for sev, v in s["severity"].items():
        rows.append(
            {
                "system": system,
                "subset": subset,
                "severity": sev,
                "n_records": s["n_records"],
                "errors": v["errors"],
                "n_fields": v["n_fields"],
                "per_1000": _r(v["per_1000"], 2),
                "cluster_lo_per_1000": _r(v["cluster_lo_per_1000"], 2),
                "cluster_hi_per_1000": _r(v["cluster_hi_per_1000"], 2),
                "n_clusters_template_family": v["n_clusters"],
                "wilson_lo_per_1000": _r(v["wilson_lo_per_1000"], 2),
                "wilson_hi_per_1000": _r(v["wilson_hi_per_1000"], 2),
                "rule_of_three_per_1000": _r(v["rule_of_three_per_1000"], 2),
                "not_measurable": ";".join(s["not_measurable"]),
                "label": label,
            }
        )
    return rows, s


def e2_extraction(ctx: Ctx) -> dict:
    inp, notes = ctx.inp, []
    label = ctx.cfg["in_sample_label"].strip() if ctx.split == "dev" else "TEST (out-of-sample)"
    ids = sorted(ctx.gold)
    systems: list[tuple[str, str, list]] = []
    if ctx.guard.exists(inp["m3_rules_dir"]):
        systems.append(
            ("rules", f"full_{ctx.split}", _score_dir(ctx, inp["m3_rules_dir"], "rules", ids))
        )
    subset = [c for c in _ids_file(ctx, inp["m3_llm_subset"]) if c in ctx.gold]
    if subset and systems:
        systems.append(("rules", "llm_subset", [x for x in systems[0][2] if x[0] in set(subset)]))
    llm_fresh = ctx.guard.exists(inp["m3_llm_dir"])
    if llm_fresh and subset:
        systems.append(("llm", "llm_subset", _score_dir(ctx, inp["m3_llm_dir"], "llm", subset)))
    stale = (not llm_fresh) and ctx.guard.exists(inp["m3_llm_stale_dir"])
    if not systems:
        row = {"status": "m3 outputs not found", "detail": inp["m3_rules_dir"]}
        return {"tables": {"e2_extraction_severity": [row]}, "notes": notes}
    sev, items, codes, slices = [], [], [], []
    v2_any = False
    for system, sub, scored in systems:
        recs_v2 = []
        for cid, _, _ in scored:
            p = f"{inp['m3_rules_dir' if system == 'rules' else 'm3_llm_dir']}/{system}-{cid}.json"
            recs_v2.append(ctx.guard.exists(p) and scoring.is_v2(ctx.guard.read_json(p)))
        v2 = (
            bool(recs_v2) and all(recs_v2) and all(scoring.is_v2(ctx.gold[c]) for c, _, _ in scored)
        )
        v2_any |= v2
        rows, s = _sev_rows(system, sub, scored, ctx, label, v2)
        sev += rows
        for kind, v in s["items"].items():
            items.append(
                {
                    "system": system,
                    "subset": sub,
                    "item_kind": kind,
                    "tp": v["tp"],
                    "fp": v["fp"],
                    "fn": v["fn"],
                    "precision": _r(v["precision"]),
                    "precision_cluster_lo": _r(v["precision_cluster_lo"]),
                    "precision_cluster_hi": _r(v["precision_cluster_hi"]),
                    "precision_wilson_lo": _r(v["precision_wilson"][0]),
                    "precision_wilson_hi": _r(v["precision_wilson"][1]),
                    "recall": _r(v["recall"]),
                    "recall_cluster_lo": _r(v["recall_cluster_lo"]),
                    "recall_cluster_hi": _r(v["recall_cluster_hi"]),
                    "recall_wilson_lo": _r(v["recall_wilson"][0]),
                    "recall_wilson_hi": _r(v["recall_wilson"][1]),
                    "f1": _r(v["f1"]),
                    "label": label,
                }
            )
        n_fields = s["severity"]["any"]["n_fields"]
        for code, k in s["codes"].items():
            codes.append(
                {
                    "system": system,
                    "subset": sub,
                    "code": code,
                    "severity": scoring.SEVERITY[code[:2]],
                    **{k2: _r(v2_) for k2, v2_ in stats.per_1000(k, n_fields).items()},
                    "label": label,
                }
            )
        if sub.startswith("full_"):
            slices += _e2_slices(ctx, system, scored, label)
    if stale:
        sev.append(
            {
                "system": "llm",
                "subset": "llm_subset",
                "severity": "-",
                "label": "STALE: LLM outputs were made on pre-REFREEZE-1 data (D-120); NOT scored "
                "against current gold. Refresh: mingw32-make m7-e2-llm-refresh (~25 min, Ollama).",
            }
        )
    paired = (
        _e2_paired(ctx, systems)
        if llm_fresh
        else [
            {"status": "no fresh LLM outputs: paired rules-vs-LLM comparison not computed (STALE)"}
        ]
    )
    if not v2_any:
        notes.append(
            "E2: inputs are record.v1 / gold.v1, so CR-ROUTE, CR-PAEDIATRIC and CR-LIQUID-STRENGTH "
            "are NOT MEASURABLE (not zero). They appear once m1 writes gold.v2 and m3 record.v2."
        )
    gallery = _e2_gallery(ctx, systems[0][2])
    return {
        "tables": {
            "e2_extraction_severity": sev,
            "e2_extraction_items": items,
            "e2_extraction_codes": codes,
            "e2_extraction_slices": slices,
            "e2_rules_vs_llm_paired": paired,
        },
        "notes": notes,
        "gallery": gallery,
        "natural_critical": next(
            (r for r in sev if r.get("severity") == "critical" and r["subset"].startswith("full_")),
            None,
        ),
    }


def _e2_slices(ctx: Ctx, system: str, scored, label: str) -> list[dict]:
    keys: dict[tuple[str, str], list] = defaultdict(list)
    for cid, fam, res in scored:
        tags = ctx.gold[cid].get("tags", {})
        keys[("template_family", fam)].append(res)
        for t in ("code_switched", "has_negation", "cross_turn_negation"):
            keys[(t, str(tags.get(t)))].append(res)
        if ctx.split == "test":
            req = fam if fam in ctx.cfg["required_test_slices"] else "other_test_families"
            keys[("required_test_slice", req)].append(res)
            tpl = frames.template_of(cid)
            by_status: dict[str, list] = defaultdict(list)
            for r in res:
                st = (
                    "extra_item"
                    if r.turn is None
                    else ctx.frame_by_turn.get((tpl, r.turn), "unknown")
                )
                by_status[st].append(r)
            for st, rs in by_status.items():
                keys[("frame_status", st)].append(rs)
    rows = []
    for (stype, sval), groups in sorted(keys.items()):
        allr = [r for rs in groups for r in rs]
        n = len(allr)
        for sev in ("critical", "major"):
            k = sum(1 for r in allr if r.severity == sev)
            rows.append(
                {
                    "system": system,
                    "slice": stype,
                    "value": sval,
                    "severity": sev,
                    "n_records": len(groups),
                    **prop_cols("errors_per_field", k, n),
                    "label": label,
                }
            )
    return rows


def _e2_paired(ctx: Ctx, systems) -> list[dict]:
    rules = {c: r for c, _, r in next(s for s in systems if s[:2] == ("rules", "llm_subset"))[2]}
    llm = {c: r for c, _, r in next(s for s in systems if s[0] == "llm")[2]}
    common = sorted(set(rules) & set(llm))
    out = []
    for sev in ("critical", "any"):

        def rate(res, sev=sev):
            k = sum(1 for r in res if r.code and (sev == "any" or r.severity == sev))
            return k / len(res) if res else 0.0

        r = stats.paired_bootstrap(
            [rate(llm[c]) for c in common], [rate(rules[c]) for c in common], seed=ctx.seed
        )
        out.append(
            {
                "comparison": "llm_minus_rules",
                "severity": sev,
                "n_common_conversations": r["n"],
                "mean_diff_errors_per_field": _r(r["mean_diff"], 5),
                "boot_lo": _r(r["ci_lo"], 5),
                "boot_hi": _r(r["ci_hi"], 5),
                "ci_excludes_zero": r["excludes_zero"],
                "seed": ctx.seed,
                "label": "rules are IN-SAMPLE on 32 of 40 subset conversations (D-121)",
            }
        )
    return out


CAUSE = {
    "MA-MISSED-ADVICE": "advice sentence not extracted (no advice pattern matched this wording)",
    "MA-MISSED-FOLLOWUP": "follow-up instruction not extracted (pattern gap)",
    "MA-MISSED-SYMPTOM": "symptom word not in the extractor's list or negation clause mis-split",
    "MA-EXTRA-SYMPTOM": "symptom recorded without spoken support (e.g. a question read as a report)",
    "MA-MISSED-DRUG": "drug name spelling/transliteration not in the lexicon",
    "CR-NEG": "negation cue missed or applied to the wrong clause",
    "CR-DOSE": "number or unit parsed wrongly",
    "CR-DRUG": "confusable drug name",
    "CR-UNSUPPORTED": "drug recorded that was not spoken",
}


def _e2_gallery(ctx: Ctx, scored) -> list[dict]:
    """Up to 3 natural errors per code, one per distinct input sentence (diverse examples)."""
    out, seen_codes, seen_inputs = [], defaultdict(int), set()
    for cid, fam, res in scored:
        for r in res:
            if not r.code or seen_codes[r.code] >= 3:
                continue
            g = ctx.gold[cid]
            turn = g["turns"][r.turn]["text"] if r.turn is not None else "(extra item)"
            if (r.code, turn) in seen_inputs:
                continue
            seen_inputs.add((r.code, turn))
            seen_codes[r.code] += 1
            out.append(
                {
                    "kind": "natural extraction error (m3 rules, DEV, in-sample)",
                    "id": cid,
                    "family": fam,
                    "input": turn,
                    "system_output": f"{r.field} = {r.pred!r}",
                    "correct": f"{r.field} = {r.gold!r}",
                    "code": r.code,
                    "dangerous": r.code.startswith("CR"),
                    "slipped_through": "n/a (m4 not yet run on m3 output)",
                    "cause": CAUSE.get(r.code, "see code")
                    + " (auto-suggested cause; a human should confirm)",
                }
            )
    return out


# ============================================================================ E3 + E4 (m4)
def _m4_inputs(ctx: Ctx) -> dict | None:
    d = ctx.inp["m4_e4_dir"]
    g = ctx.guard
    if not g.exists(f"{d}/injection_results.jsonl"):
        return None
    logs = {}
    for lv in ("record", "transcript"):
        p = f"{d}/injection_log_{lv}.jsonl"
        if g.exists(p):
            logs.update({r["id"]: r for r in g.iter_jsonl(p)})
    clean_rate = list(csv.DictReader(io.StringIO(g.read_text(f"{d}/clean_flag_rate.csv"))))
    return {
        "results": list(g.iter_jsonl(f"{d}/injection_results.jsonl")),
        "logs": logs,
        "clean_flagged": list(g.iter_jsonl(f"{d}/clean_flagged_fields.jsonl")),
        "clean_rate": {r["unit"]: r for r in clean_rate},
        "summary_md": g.read_text(f"{d}/summary.md") if g.exists(f"{d}/summary.md") else "",
    }


def _unique(rows: list[dict], pred) -> tuple[int, int]:
    """(k, n) over UNIQUE mutations; repeats that disagree count as NOT caught (as m4)."""
    seen: dict[str, set[bool]] = defaultdict(set)
    for r in rows:
        seen[r["unique_key"]].add(bool(pred(r)))
    return sum(1 for v in seen.values() if v == {True}), len(seen)


ROW_LABEL = {
    ("transcript", "text_only"): "HEADLINE: error in the transcript itself, text-only checks",
    ("record", "with_encounter_index"): "record-level: record mutated, transcript correct (easier)",
    ("record", "no_encounter_index"): "record-level wrong patient, no encounter index (blind spot)",
    (
        "transcript",
        "oracle_second_transcript_upper_bound",
    ): "UPPER BOUND: oracle (perfect) second transcript",
}


def _clean_field_flags(m4: dict, removed: str | None, excl_cv: bool) -> int:
    k = 0
    for f in m4["clean_flagged"]:
        fl = [x for x in f["flags"] if removed is None or not x.startswith(f"{removed}:")]
        if excl_cv:
            fl = [x for x in fl if "cannot_verify" not in x]
        k += bool(fl)
    return k


def e3_e4_verifier(ctx: Ctx, natural_critical: dict | None) -> dict:
    m4 = _m4_inputs(ctx)
    if m4 is None:
        row = {"status": f"m4 E4 outputs not found in {ctx.inp['m4_e4_dir']}"}
        return {"tables": {"e4_planted_by_type": [row], "e3_ablation": [row]}, "notes": []}
    label = ctx.cfg["in_sample_label"].strip() if ctx.split == "dev" else "TEST (out-of-sample)"
    res, logs = m4["results"], m4["logs"]
    n_fields = int(m4["clean_rate"]["field"]["n"])
    n_recs = int(m4["clean_rate"]["record"]["n"])
    burden_any = _clean_field_flags(m4, None, False)
    burden_real = _clean_field_flags(m4, None, True)
    notes = []
    if burden_any != int(m4["clean_rate"]["field"]["flagged"]):
        notes.append(
            f"WARNING: recomputed clean-field flags {burden_any} != m4 table "
            f"{m4['clean_rate']['field']['flagged']}"
        )
    burden_cols = {
        **prop_cols("review_burden_fields_any_flag", burden_any, n_fields),
        **prop_cols("review_burden_fields_excl_cannot_verify", burden_real, n_fields),
    }
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in res:
        lg = logs.get(r["id"], {})
        r["_type_name"] = lg.get("type_name", r["type"])
        groups[(r["level"], r["condition"], r["type"], r["_type_name"])].append(r)
    by_type = []
    for (lv, cond, typ, tname), rs in sorted(groups.items()):
        row = {
            "level": lv,
            "condition": cond,
            "row_label": ROW_LABEL.get((lv, cond), ""),
            "type": typ,
            "type_name": tname,
            "n_injections": len(rs),
        }
        for col, key in (
            ("caught_at_field", "caught_at_field"),
            ("detected", "detected_at_field"),
            ("sent_to_review", "sent_to_review"),
        ):
            k, n = _unique(rs, lambda r, key=key: r[key])
            row.update(prop_cols(col, k, n))
        if (lv, cond) == ("transcript", "text_only"):
            row.update(burden_cols)
        row["label"] = label + " PLANTED errors (not natural)."
        by_type.append(row)
    headline = [r for r in by_type if r["condition"] == "text_only"]
    # per field
    fgroups: dict[tuple, list[dict]] = defaultdict(list)
    for r in res:
        fgroups[(r["level"], r["condition"], r["field"])].append(r)
    by_field = []
    for (lv, cond, fld), rs in sorted(fgroups.items()):
        row = {
            "level": lv,
            "condition": cond,
            "row_label": ROW_LABEL.get((lv, cond), ""),
            "field": fld,
        }
        for col, key in (("caught_at_field", "caught_at_field"), ("detected", "detected_at_field")):
            row.update(prop_cols(col, *_unique(rs, lambda r, key=key: r[key])))
        by_field.append(row)
    # per template family (text-only headline), plus cluster bootstrap over families
    fam_rows, clusters = [], {}
    tx = [r for r in res if r["condition"] == "text_only"]
    by_fam: dict[str, list[dict]] = defaultdict(list)
    for r in tx:
        by_fam[ctx.family(logs.get(r["id"], {}).get("source_id", ""))].append(r)
    for fam, rs in sorted(by_fam.items()):
        k, n = _unique(rs, lambda r: r["caught_at_field"])
        clusters[fam] = (k, n)
        fam_rows.append(
            {"condition": "text_only", "template_family": fam, **prop_cols("caught_at_field", k, n)}
        )
    k_all, n_all = _unique(tx, lambda r: r["caught_at_field"])
    lo, hi = stats.cluster_bootstrap_rate(clusters, seed=ctx.seed)
    fam_rows.append(
        {
            "condition": "text_only",
            "template_family": "ALL (pooled over types)",
            **prop_cols("caught_at_field", k_all, n_all),
            "cluster_boot_lo": _r(lo),
            "cluster_boot_hi": _r(hi),
            "n_clusters": len(clusters),
        }
    )
    if ctx.split == "test":
        fam_rows += _e4_test_slices(ctx, tx, logs)
    # E3 ablation: remove one check at a time (derived from stored per-check outputs)
    abl = []
    for lv, cond in (
        ("record", "with_encounter_index"),
        ("transcript", "text_only"),
        ("transcript", "oracle_second_transcript_upper_bound"),
    ):
        rs = [r for r in res if r["level"] == lv and r["condition"] == cond]
        if not rs:
            continue
        for removed in (None, *CHECKS):

            def caught(r, removed=removed):
                return bool(set(r.get("at_field_checks") or []) - {removed})

            def detected(r, removed=removed):
                return bool(set(r.get("detected_checks") or []) - {removed})

            k, n = _unique(rs, caught)
            kd, _ = _unique(rs, detected)
            abl.append(
                {
                    "level": lv,
                    "condition": cond,
                    "row_label": ROW_LABEL.get((lv, cond), ""),
                    "removed_check": removed or "none (all C1..C8)",
                    **prop_cols("critical_caught_at_field", k, n),
                    **prop_cols("critical_escaped", n - k, n),
                    **prop_cols("critical_detected", kd, n),
                    **prop_cols(
                        "flag_rate_error_free_fields",
                        _clean_field_flags(m4, removed, False),
                        n_fields,
                    ),
                    **prop_cols(
                        "flag_rate_error_free_fields_excl_cannot_verify",
                        _clean_field_flags(m4, removed, True),
                        n_fields,
                    ),
                    "label": label
                    + " PLANTED errors; derived by removing one check's stored flags "
                    "(assumes checks do not read each other's results; UNVERIFIED until m4 re-runs "
                    "with the check disabled in its registry).",
                }
            )
    natural = [
        {
            "errors": "natural (m3 rules output vs gold)",
            "status": "verifier NOT yet run on m3 output (Phase C integration m3->m4)",
            **(
                {
                    k: natural_critical.get(k)
                    for k in ("errors", "n_fields", "wilson_hi_per_1000", "rule_of_three_per_1000")
                }
                if natural_critical
                else {}
            ),
            "note": "0 natural critical errors on dev means verifier recall on natural errors is "
            "NOT MEASURABLE here (0/0), not 100%.",
        }
    ]
    # H1 status on DEV (H1 itself is judged on test)
    h1 = []
    for lv, cond in (("transcript", "text_only"), ("record", "with_encounter_index")):
        rs = [r for r in res if r["level"] == lv and r["condition"] == cond]
        k, n = _unique(rs, lambda r: r["caught_at_field"])
        p = stats.proportion(k, n)
        h1.append(
            {
                "hypothesis": "H1 (dev preview, planted errors)",
                "level": lv,
                "condition": cond,
                "row_label": ROW_LABEL[(lv, cond)],
                **prop_cols("critical_caught_at_field", k, n),
                "threshold_recall": 0.95,
                "point_meets_recall": bool(p["rate"] is not None and p["rate"] >= 0.95),
                "lower_bound_meets_recall": bool(
                    p["wilson_lo"] is not None and p["wilson_lo"] >= 0.95
                ),
                **burden_cols,
                "threshold_flag_rate": 0.20,
                "meets_flag_rate": burden_any / n_fields <= 0.20 if n_fields else None,
                "label": label + " Not the pre-registered test result.",
            }
        )
    h1.append(
        {
            "hypothesis": "H1 records",
            **prop_cols(
                "error_free_records_flagged", int(m4["clean_rate"]["record"]["flagged"]), n_recs
            ),
        }
    )
    gallery = _e4_gallery(ctx, res, logs, m4)
    return {
        "tables": {
            "e4_planted_by_type": by_type,
            "e4_headline_text_only": headline,
            "e4_planted_by_field": by_field,
            "e4_planted_by_family": fam_rows,
            "e3_ablation": abl,
            "e3_natural_errors": natural,
            "h1_dev_preview": h1,
        },
        "notes": notes,
        "gallery": gallery,
    }


def _e4_test_slices(ctx: Ctx, tx: list[dict], logs: dict) -> list[dict]:
    rows, by = [], defaultdict(list)
    for r in tx:
        cid = logs.get(r["id"], {}).get("source_id", "")
        fam = ctx.family(cid)
        by[
            ("required_test_slice", fam if fam in ctx.cfg["required_test_slices"] else "other")
        ].append(r)
        g = ctx.gold.get(cid)
        st = "unknown"
        if g:
            parts = r["field_path"].strip("/").split("/")
            try:
                item = g["gold_record"][parts[0]][int(parts[1])]
                st = ctx.frame_by_turn.get(
                    (frames.template_of(cid), item["gold_span"]["turn_index"]), "unknown"
                )
            except (KeyError, IndexError, ValueError):
                pass
        by[("frame_status", st)].append(r)
    for (s, v), rs in sorted(by.items()):
        rows.append(
            {
                "condition": "text_only",
                "template_family": f"{s}={v}",
                **prop_cols("caught_at_field", *_unique(rs, lambda r: r["caught_at_field"])),
            }
        )
    return rows


def _e4_gallery(ctx: Ctx, res, logs, m4) -> list[dict]:
    out, per_type = [], defaultdict(int)
    for r in res:
        if r["condition"] != "text_only" or r["caught_at_field"] or per_type[r["type"]] >= 1:
            continue
        lg = logs.get(r["id"], {})
        cid = lg.get("source_id", "")
        g = ctx.gold.get(cid)
        per_type[r["type"]] += 1
        out.append(
            {
                "kind": "PLANTED transcript error that slipped through (m4 text-only, DEV)",
                "id": r["id"],
                "family": ctx.family(cid),
                "input": f"conversation {cid}: {lg.get('note', '')}"
                + (
                    f" | original turns: {' / '.join(t['text'] for t in g['turns'])[:300]}"
                    if g
                    else ""
                ),
                "system_output": f"no flag on {r['field_path']} (flags elsewhere: {', '.join(r.get('flagged_checks') or []) or 'none'})",
                "correct": f"{r['field_path']}: spoken value {lg.get('before')!r}; record (from corrupted transcript) {lg.get('after')!r} must be flagged",
                "code": lg.get("type_name", r["type"]),
                "dangerous": True,
                "slipped_through": True,
                "cause": "text-only checks compare the record with the SAME corrupted transcript, so they agree; "
                "only a second, independent transcript or audio check (C7) can see this",
            }
        )
    real_alarms = [
        x for x in m4["clean_flagged"] if any("cannot_verify" not in y for y in x["flags"])
    ]
    for f in real_alarms[:2]:
        out.append(
            {
                "kind": "false alarm on an ERROR-FREE record (review burden, m4, DEV)",
                "id": f["record_id"],
                "family": ctx.family(f["record_id"].removeprefix("rec-")),
                "input": f"error-free record field {f['field']}",
                "system_output": "; ".join(f["flags"]),
                "correct": "no flag (field matches gold)",
                "code": "false alarm",
                "dangerous": False,
                "slipped_through": False,
                "cause": "verifier vocabulary gap (word not in m4's own list), so it cannot confirm support",
            }
        )
    return out


# ============================================================================ E5 access
def e5_access(ctx: Ctx) -> dict:
    p = ctx.inp["m5_results"]
    if not ctx.guard.exists(p):
        return {"tables": {"e5_access": [{"status": "m5 results not found"}]}, "notes": []}
    rows = list(ctx.guard.iter_jsonl(p))
    out = []
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for r in rows:
        groups[("ALL", "ALL")].append(r)
        groups[("layer", r["layer"])].append(r)
        groups[("attack", str(r["case"]["attack"]))].append(r)
        groups[("role", r["case"]["role"])].append(r)
    for (s, v), rs in sorted(groups.items(), key=lambda x: (x[0][0] != "ALL", x[0])):
        deny = [r for r in rs if r["case"]["expected"] == "deny"]
        allow = [r for r in rs if r["case"]["expected"] == "allow"]
        unauth = sum(1 for r in deny if r["observed"] != "deny")
        wrong_deny = sum(1 for r in allow if r["observed"] != "allow")
        out.append(
            {
                "slice": s,
                "value": v,
                "n_cases": len(rs),
                **prop_cols("unauthorized_success", unauth, len(deny)),
                **prop_cols("unexpected_denial", wrong_deny, len(allow)),
            }
        )
    tot = out[0]
    h3 = {
        "hypothesis": "H3",
        "threshold": "0 unauthorized successes in N >= 500",
        "n_deny_cases": tot["unauthorized_success_n"],
        "unauthorized": tot["unauthorized_success_k"],
        "rule_of_three_upper": tot["unauthorized_success_rule_of_three_upper"],
        "met_on_this_run": tot["unauthorized_success_k"] == 0
        and tot["unauthorized_success_n"] >= 500,
        "note": "access matrix written and run by the same AI that wrote the rules (D-103); "
        "synthetic users; sandbox DB on 127.0.0.1",
    }
    return {"tables": {"e5_access": out, "h3_status": [h3]}, "notes": []}


# ============================================================================ E6 helper
def e6_helper(ctx: Ctx) -> dict:
    out, gallery, dropped = [], [], 0
    for name, p in ctx.inp["m8_predictions"].items():
        if not ctx.guard.exists(p):
            continue
        rows = []
        for r in ctx.guard.iter_jsonl(p):
            if r.get("split") == ctx.split:
                rows.append(r)
            else:
                dropped += 1
        ans = [r for r in rows if r["kind"] == "answer"]
        oos = [r for r in rows if r["kind"] == "oos"]
        unsafe = [r for r in rows if r["kind"] == "unsafe"]
        answered = [r for r in rows if not r["pred_abstain"]]
        good = sum(1 for r in ans if not r["pred_abstain"] and r["pred_card"] == r["expected_card"])
        wrong = sum(
            1 for r in ans if not r["pred_abstain"] and r["pred_card"] != r["expected_card"]
        )
        out.append(
            {
                "retriever": name,
                "split": ctx.split,
                **prop_cols("in_scope_answered_from_correct_card", good, len(ans)),
                **prop_cols("in_scope_wrong_card", wrong, len(ans)),
                **prop_cols("out_of_scope_refused", sum(r["pred_abstain"] for r in oos), len(oos)),
                **prop_cols(
                    "dosing_diagnosis_refused", sum(r["pred_abstain"] for r in unsafe), len(unsafe)
                ),
                **prop_cols(
                    "answers_citing_card_id",
                    sum(1 for r in answered if r.get("pred_card")),
                    len(answered),
                ),
                "label": "IN-SAMPLE: the similarity threshold was tuned on these dev questions (D-139)"
                if ctx.split == "dev"
                else "TEST",
            }
        )
        for r in ans + oos + unsafe:
            bad = (r["kind"] == "answer" and r["pred_card"] != r["expected_card"]) or (
                r["kind"] != "answer" and not r["pred_abstain"]
            )
            if bad and sum(1 for x in gallery if x["id"].startswith(name)) < 2:
                gallery.append(
                    {
                        "kind": f"helper failure (m8 {name}, {ctx.split})",
                        "id": f"{name}:{r['id']}",
                        "family": r["topic"],
                        "input": r["q"],
                        "system_output": "abstained"
                        if r["pred_abstain"]
                        else f"answered with card {r['pred_card']}",
                        "correct": f"card {r['expected_card']}"
                        if r["kind"] == "answer"
                        else "refuse",
                        "code": f"{r['kind']} / {r['reason']} (score {r['score']:.2f})",
                        "dangerous": r["kind"] == "unsafe" and not r["pred_abstain"],
                        "slipped_through": r["kind"] == "unsafe" and not r["pred_abstain"],
                        "cause": "similarity below the dev-tuned threshold (lexical/embedding mismatch)"
                        if r["pred_abstain"]
                        else "retrieval matched the wrong card",
                    }
                )
    notes = (
        [f"E6: {dropped} m8 rows of the other split were dropped without scoring"]
        if dropped
        else []
    )
    return {
        "tables": {"e6_helper": out or [{"status": "m8 predictions not found"}]},
        "notes": notes,
        "gallery": gallery,
    }


# ============================================================================ cost / latency
def cost_latency(ctx: Ctx) -> dict:
    rows = []
    stale = ctx.inp["m3_llm_stale_dir"] + "/run_summary.json"
    fresh = ctx.inp["m3_llm_dir"] + "/run_summary.json"
    for p, lab in ((fresh, "current"), (stale, "STALE pre-REFREEZE-1")):
        if ctx.guard.exists(p):
            s = ctx.guard.read_json(p)
            rows.append(
                {
                    "component": f"m3 LLM extraction ({s.get('model')})",
                    "status": lab,
                    "n": s.get("n"),
                    "latency_ms_p50": _r(s.get("latency_ms_p50"), 1),
                    "latency_ms_p95": _r(s.get("latency_ms_p95"), 1),
                    "hardware": s.get("hardware"),
                    "cloud_cost_usd": 0,
                    "source_file": p,
                }
            )
    rows.append({"component": "m2 ASR", "status": "m2 not run yet", "cloud_cost_usd": 0})
    rows.append(
        {
            "component": "m7 evaluation (this run)",
            "status": "local CPU, no GPU, no network",
            "hardware": ctx.cfg["hardware"],
            "cloud_cost_usd": 0,
        }
    )
    return {"tables": {"cost_latency": rows}, "notes": []}


def dump_json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)
