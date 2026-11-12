"""Run every experiment and write results/m7_eval/<split>/: tables/*.csv, plots/*.png,
summary.md, failure_gallery.md, cost_report.md, manifest.json (inputs + outputs with sha256 and
the git hash) and run_log.json (runtime; the ONLY file that changes between identical runs).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from m7_eval import experiments as ex
from m7_eval import guard as guard_mod

CONFIG = Path("m7_eval/configs/eval.yaml")


def git_hash(root: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout.strip() if r.returncode == 0 else "NO-GIT"


def _csv(rows: list[dict]) -> str:
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    return buf.getvalue()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _md_table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "_no rows_\n"
    out = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows:
        out += "| " + " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols) + " |\n"
    return out


def _ci(r: dict, p: str) -> str:
    if r.get(f"{p}_n") in (None, 0):
        return "not measurable (n=0)"
    s = f"{r[f'{p}_k']}/{r[f'{p}_n']} [{r[f'{p}_wilson_lo']:.3f}, {r[f'{p}_wilson_hi']:.3f}]"
    if r.get(f"{p}_rule_of_three_upper"):
        s += f" (0 of {r[f'{p}_n']}; upper ~3/N = {r[f'{p}_rule_of_three_upper']:.4f})"
    return s


# ------------------------------------------------------------------ plots
def _plots(tables: dict[str, list[dict]], out: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    made = []

    def save(fig, name):
        p = out / "plots" / f"{name}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(p, dpi=72, metadata={"Software": None})
        plt.close(fig)
        made.append(name)

    def bars(ax, labels, rows, p, color):
        xs = range(len(rows))
        rates = [r[f"{p}_rate"] or 0 for r in rows]
        lo = [max(0.0, (r[f"{p}_rate"] or 0) - (r[f"{p}_wilson_lo"] or 0)) for r in rows]
        hi = [max(0.0, (r[f"{p}_wilson_hi"] or 0) - (r[f"{p}_rate"] or 0)) for r in rows]
        ax.bar(xs, rates, yerr=[lo, hi], color=color, capsize=3)
        ax.set_xticks(list(xs), labels, rotation=30, ha="right", fontsize=7)
        ax.set_ylim(0, 1.05)

    head = [r for r in tables.get("e4_headline_text_only", []) if "caught_at_field_rate" in r]
    if head:
        fig, ax = plt.subplots(figsize=(6, 3.2))
        bars(ax, [r["type_name"] for r in head], head, "caught_at_field", "#4477aa")
        b = head[0].get("review_burden_fields_any_flag_rate")
        if b is not None:
            ax.axhline(
                b, color="#cc3311", ls="--", lw=1, label=f"flag rate on error-free fields {b:.2f}"
            )
            ax.legend(fontsize=7)
        ax.set_ylabel("caught at field (Wilson 95% CI)", fontsize=8)
        ax.set_title("E4 planted transcript errors, text-only checks (DEV, unique N)", fontsize=8)
        save(fig, "e4_text_only_catch_rate")
    abl = [r for r in tables.get("e3_ablation", []) if r.get("condition") == "text_only"]
    abl_r = [
        r for r in tables.get("e3_ablation", []) if r.get("condition") == "with_encounter_index"
    ]
    if abl and abl_r:
        fig, axs = plt.subplots(1, 2, figsize=(7, 3.2), sharey=True)
        for ax, rows, t in ((axs[0], abl_r, "record-level"), (axs[1], abl, "transcript text-only")):
            lab = [r["removed_check"].split(" ")[0] for r in rows]
            bars(ax, lab, rows, "critical_caught_at_field", "#4477aa")
            ax.plot(
                range(len(rows)),
                [r["flag_rate_error_free_fields_rate"] for r in rows],
                "o",
                color="#cc3311",
                ms=3,
                label="flag rate, error-free fields",
            )
            ax.set_title(f"E3 ablation, {t} (remove one check)", fontsize=8)
            ax.legend(fontsize=6)
        axs[0].set_ylabel("rate (Wilson 95% CI)", fontsize=8)
        save(fig, "e3_ablation")
    sev = [
        r
        for r in tables.get("e2_extraction_severity", [])
        if r.get("severity") in ("critical", "major") and r.get("n_fields")
    ]
    if sev:
        fig, ax = plt.subplots(figsize=(6, 3.2))
        xs = range(len(sev))
        v = [r["per_1000"] for r in sev]
        lo = [r["per_1000"] - (r["cluster_lo_per_1000"] or 0) for r in sev]
        hi = [(r["cluster_hi_per_1000"] or 0) - r["per_1000"] for r in sev]
        hi = [
            max(h, (r["rule_of_three_per_1000"] or 0) if r["errors"] == 0 else h)
            for h, r in zip(hi, sev, strict=True)
        ]
        ax.bar(xs, v, yerr=[[max(0, x) for x in lo], hi], color="#228833", capsize=3)
        ax.set_xticks(
            list(xs),
            [f"{r['system']}/{r['subset']}/{r['severity']}" for r in sev],
            rotation=30,
            ha="right",
            fontsize=7,
        )
        ax.set_ylabel("errors per 1,000 fields", fontsize=8)
        ax.set_title(
            "E2 extraction errors (DEV, in-sample; CI: cluster bootstrap by family; 0: rule of three)",
            fontsize=7,
        )
        save(fig, "e2_extraction_errors")
    helper = [
        r for r in tables.get("e6_helper", []) if "in_scope_answered_from_correct_card_rate" in r
    ]
    if helper:
        fig, ax = plt.subplots(figsize=(6, 3.2))
        cols = [
            "in_scope_answered_from_correct_card",
            "out_of_scope_refused",
            "dosing_diagnosis_refused",
        ]
        rows = [
            {**{f"x_{k2}": r[f"{c}_{k2}"] for k2 in ("rate", "wilson_lo", "wilson_hi")}}
            for r in helper
            for c in cols
        ]
        bars(
            ax,
            [f"{r['retriever']}:{c.split('_')[0]}" for r in helper for c in cols],
            rows,
            "x",
            "#aa3377",
        )
        ax.set_title("E6 helper on DEV questions (in-sample threshold)", fontsize=8)
        save(fig, "e6_helper")
    cer = [
        r
        for r in tables.get("e1_asr_summary", [])
        if r.get("cer_mean") is not None and r.get("voice") != "ALL_VOICES"
    ]
    if cer:
        fig, ax = plt.subplots(figsize=(6, 3.2))
        xs = range(len(cer))
        v = [r["cer_mean"] for r in cer]
        ax.bar(
            xs,
            v,
            yerr=[
                [x - r["cer_boot_lo"] for x, r in zip(v, cer, strict=True)],
                [r["cer_boot_hi"] - x for x, r in zip(v, cer, strict=True)],
            ],
            capsize=3,
        )
        ax.set_xticks(
            list(xs),
            [f"{r['model'][:12]}/{r['source']}/{r['variant']}" for r in cer],
            rotation=30,
            ha="right",
            fontsize=6,
        )
        ax.set_ylabel("CER (bootstrap 95% CI)", fontsize=8)
        ax.set_title(
            "E1 ASR CER by model, source and variant (never pooled across sources)", fontsize=8
        )
        save(fig, "e1_cer")
    return made


# ------------------------------------------------------------------ markdown
def _gallery_md(items: list[dict], split: str) -> str:
    dangerous = [g for g in items if g.get("dangerous") and g.get("slipped_through")]
    nat_crit = [g for g in items if g["kind"].startswith("natural") and g.get("dangerous")]
    s = f"# Failure gallery ({split.upper()} only; no test-split example)\n\n"
    s += (
        f"{len(items)} real failures from saved module outputs. {len(dangerous)} are DANGEROUS "
        "errors that slipped through the verifier. All are on synthetic, template-generated, "
        "not native-validated text. Causes are auto-suggested by m7 and must be confirmed by a "
        "human.\n\n"
    )
    if not nat_crit:
        s += (
            "**Natural dangerous errors:** the m3 rules made 0 critical errors on dev (in-sample: the "
            "rules were fixed on dev), so every dangerous slip-through below is a PLANTED error "
            "(E4). Fewer than 3 natural dangerous failures exist on dev; we say so instead of "
            "inventing any.\n\n"
        )
    for i, g in enumerate(items, 1):
        s += f"## {i}. {g['kind']}\n\n"
        s += f"- id: `{g['id']}` (family/topic: {g.get('family')})\n"
        s += f"- input: {g['input']}\n- system output: {g['system_output']}\n"
        s += f"- correct answer: {g['correct']}\n- class: {g['code']}; dangerous: {g['dangerous']}"
        s += f"; slipped through: {g['slipped_through']}\n- cause: {g['cause']}\n\n"
    return s


def _summary_md(split: str, gh: str, tables: dict, notes: list[str], cfg: dict) -> str:
    s = f"# m7_eval results ({split.upper()} split)\n\n"
    s += f"git {gh}; seed {cfg['seed']}; {cfg['n_resamples']} bootstrap resamples. "
    s += "Every proportion: k/n [Wilson 95% CI]; zero counts also give the rule-of-three bound.\n\n"
    if split == "dev":
        s += f"**{cfg['in_sample_label'].strip()}**\n\n"
    s += "## E4 headline: planted errors in the TRANSCRIPT, text-only checks (next to review burden)\n\n"
    head = tables.get("e4_headline_text_only", [])
    if head and "caught_at_field_k" in head[0]:
        s += _md_table(
            [
                {
                    "type": r["type_name"],
                    "caught at field": _ci(r, "caught_at_field"),
                    "flag rate on error-free fields": _ci(r, "review_burden_fields_any_flag"),
                }
                for r in head
            ],
            ["type", "caught at field", "flag rate on error-free fields"],
        )
        s += "\nRecord-level and oracle (upper bound) rows: tables/e4_planted_by_type.csv, labelled.\n\n"
    s += "## H1 dev preview (pre-registered thresholds; NOT the test result)\n\n"
    s += _md_table(
        [
            {
                "row": r.get("row_label", r["hypothesis"]),
                "critical caught": _ci(r, "critical_caught_at_field")
                if "critical_caught_at_field_n" in r
                else _ci(r, "error_free_records_flagged"),
                "flag rate error-free fields": _ci(r, "review_burden_fields_any_flag")
                if "review_burden_fields_any_flag_n" in r
                else "",
            }
            for r in tables.get("h1_dev_preview", [])
        ],
        ["row", "critical caught", "flag rate error-free fields"],
    )
    s += "\n## E3 ablation (transcript text-only; remove one check)\n\n"
    s += _md_table(
        [
            {
                "removed": r["removed_check"],
                "escaped": _ci(r, "critical_escaped"),
                "flag rate error-free": _ci(r, "flag_rate_error_free_fields"),
            }
            for r in tables.get("e3_ablation", [])
            if r.get("condition") == "text_only"
        ],
        ["removed", "escaped", "flag rate error-free"],
    )
    s += "\n## E2 extraction (natural errors; per 1,000 fields; primary CI = cluster bootstrap by template family)\n\n"
    s += _md_table(
        [
            {
                "system": r["system"],
                "subset": r["subset"],
                "severity": r["severity"],
                "errors/fields": f"{r.get('errors')}/{r.get('n_fields')}",
                "per 1000": r.get("per_1000"),
                "cluster CI": f"[{r.get('cluster_lo_per_1000')}, {r.get('cluster_hi_per_1000')}]",
                "Wilson CI": f"[{r.get('wilson_lo_per_1000')}, {r.get('wilson_hi_per_1000')}]",
                "rule of 3": r.get("rule_of_three_per_1000"),
                "label": r.get("label", "")[:60],
            }
            for r in tables.get("e2_extraction_severity", [])
        ],
        [
            "system",
            "subset",
            "severity",
            "errors/fields",
            "per 1000",
            "cluster CI",
            "Wilson CI",
            "rule of 3",
            "label",
        ],
    )
    s += "\n## E1 ASR\n\n"
    e1 = tables.get("e1_asr_summary", [])
    if e1 and "status" in e1[0]:
        s += f"**{e1[0]['status']}**: {e1[0]['detail']}\n"
    else:
        s += _md_table(
            [
                {
                    "model": r["model"],
                    "source": r["source"],
                    "variant": r["variant"],
                    "voice": r["voice"],
                    "n": r["n_utterances"],
                    "CER [boot CI]": f"{r['cer_mean']} [{r['cer_boot_lo']}, {r['cer_boot_hi']}]",
                    "negation recall": _ci(r, "recall_negation"),
                }
                for r in e1
            ],
            ["model", "source", "variant", "voice", "n", "CER [boot CI]", "negation recall"],
        )
    s += "\n## E5 access matrix (m5)\n\n"
    s += _md_table(
        [
            {
                "slice": f"{r['slice']}={r['value']}",
                "n": r.get("n_cases"),
                "unauthorized successes": _ci(r, "unauthorized_success"),
                "unexpected denials": _ci(r, "unexpected_denial"),
            }
            for r in tables.get("e5_access", [])
            if r.get("slice") in ("ALL", "layer")
        ],
        ["slice", "n", "unauthorized successes", "unexpected denials"],
    )
    s += "\n## E6 helper (m8, dev questions only)\n\n"
    s += _md_table(
        [
            {
                "retriever": r["retriever"],
                "in-scope correct card": _ci(r, "in_scope_answered_from_correct_card"),
                "out-of-scope refused": _ci(r, "out_of_scope_refused"),
                "dosing/diagnosis refused": _ci(r, "dosing_diagnosis_refused"),
                "answers cite card": _ci(r, "answers_citing_card_id"),
            }
            for r in tables.get("e6_helper", [])
            if "retriever" in r
        ],
        [
            "retriever",
            "in-scope correct card",
            "out-of-scope refused",
            "dosing/diagnosis refused",
            "answers cite card",
        ],
    )
    s += "\n## Frame overlap (D-90), from template text only\n\n"
    s += _md_table(
        tables.get("frame_overlap_templates", []),
        ["template_split", "n_template_turns", "seen_in_dev", "unseen", "slot_only"],
    )
    s += "\n## Notes\n\n" + "".join(f"- {n}\n" for n in notes)
    return s


COST_MD = """# Cost report (m7_eval)

**$0 cloud spend.** Every number in results/m7_eval/ was computed on the local laptop
({hardware}) from files already in the repository. m7 uses no GPU, no network, no paid API and
no cloud account. Evidence: m7_eval has no network client code and no credentials; `make eval`
only reads files listed in manifest.json.

Runtime of the latest `make eval`: see run_log.json (kept out of the reproducible outputs).

| component | status | n | latency p50 (ms) | latency p95 (ms) | hardware | cloud cost (USD) |
|---|---|---|---|---|---|---|
{rows}
UNVERIFIED: the other modules' own cost claims (their inventory entries) are not re-checked here.
"""


def run(
    root: Path,
    split: str,
    out_dir: Path,
    env: Mapping[str, str] | None = None,
    gh: str | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    root = Path(root).resolve()
    gh = gh or git_hash(root)
    if split == "test":
        guard_mod.require_test_access(root, env or {}, gh)  # refuses before ANY test file is read
    g = guard_mod.SplitGuard(root, split)
    cfg = yaml.safe_load(g.read_text(root / CONFIG))
    ctx = ex.load_context(root, g, cfg, split)
    parts = {
        "frames": ex.frame_overlap(ctx),
        "e1": ex.e1_asr(ctx),
        "e2": ex.e2_extraction(ctx),
    }
    parts["e34"] = ex.e3_e4_verifier(ctx, parts["e2"].get("natural_critical"))
    parts["e5"] = ex.e5_access(ctx)
    parts["e6"] = ex.e6_helper(ctx)
    parts["cost"] = ex.cost_latency(ctx)
    tables: dict[str, list[dict]] = {}
    notes: list[str] = []
    gallery: list[dict] = []
    for p in parts.values():
        tables.update(p["tables"])
        notes += p.get("notes", [])
        gallery += p.get("gallery", [])
    out = Path(out_dir)
    for name, rows in sorted(tables.items()):
        _write(out / "tables" / f"{name}.csv", _csv(rows))
    for k, ids in sorted(parts["e1"].get("common_subsets", {}).items()):
        _write(
            out / "tables" / f"e1_common_subset__{k.replace(':', '__')}.txt", "\n".join(ids) + "\n"
        )
    plots = _plots(tables, out)
    _write(out / "failure_gallery.md", _gallery_md(gallery, split))
    _write(out / "summary.md", _summary_md(split, gh, tables, notes, cfg))
    cost_rows = "".join(
        "| {} | {} | {} | {} | {} | {} | {} |\n".format(
            r.get("component"),
            r.get("status"),
            r.get("n", ""),
            r.get("latency_ms_p50", ""),
            r.get("latency_ms_p95", ""),
            r.get("hardware", ""),
            r.get("cloud_cost_usd"),
        )
        for r in tables["cost_latency"]
    )
    _write(out / "cost_report.md", COST_MD.format(hardware=cfg["hardware"], rows=cost_rows))
    outputs = sorted(
        p for p in out.rglob("*") if p.is_file() and p.name not in ("manifest.json", "run_log.json")
    )
    manifest = {
        "git_hash": gh,
        "split": split,
        "seed": cfg["seed"],
        "n_resamples": cfg["n_resamples"],
        "inputs": [{"path": p, "sha256": g.hashes[p]} for p in sorted(g.hashes)],
        "outputs": [
            {
                "path": p.relative_to(out).as_posix(),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in outputs
        ],
        "test_files_opened": [p for p in g.opened if g.is_test_path(p)],
    }
    _write(out / "manifest.json", json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    runtime = time.perf_counter() - t0
    _write(
        out / "run_log.json",
        json.dumps(
            {
                "runtime_s": round(runtime, 2),
                "hardware": cfg["hardware"],
                "finished_unix": int(time.time()),
            },
            indent=1,
        )
        + "\n",
    )
    return {
        "tables": tables,
        "notes": notes,
        "gallery": gallery,
        "plots": plots,
        "manifest": manifest,
        "runtime_s": runtime,
    }
