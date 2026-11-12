"""Score saved transcripts against references and write results/m2_asr/summary.csv.

One row per model x source x slice. TTS and public_real are never pooled. CIs: percentile
bootstrap (1000, seed 20261109) for per-utterance means; Wilson 95% for recall proportions.
Everything is recomputed from the per-file JSONs under results/m2_asr/dev/<model>/.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import yaml

from . import metrics as M
from .models import MODELS, NOT_RUN
from .runner import out_name


def load_terms(root: Path) -> M.CriticalTerms:
    """Critical-term lists: data files only (m7's yaml and the drug lexicon are read as data)."""
    cfg = yaml.safe_load((root / "m7_eval/configs/critical_terms.yaml").read_text(encoding="utf-8"))
    drugs: list[tuple[str, list[str]]] = []
    with (root / "data/lexicon/drugs.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            names = [row["generic_en"], row["kn_primary"]]
            names += row["kn_variants"].split("|") + row["roman_variants"].split("|")
            for nm in names:
                if nm.strip() and not nm.strip().isdigit():
                    drugs.append((row["generic_en"], M.tokens(nm)))
    neg: list[str] = []
    tbl = root / ".claude/skills/kannada-nlp/negation_table.yaml"
    if tbl.exists():
        t = yaml.safe_load(tbl.read_text(encoding="utf-8"))
        neg = [e["pattern"] for e in t["entries"] if e["type"] in ("strong_whole_token", "suffix")]
    return M.CriticalTerms(drugs, cfg["number_words"], cfg["units"], neg)


def reference_text(root: Path, e: dict) -> str | None:
    if e["source"] == "public_real":
        return e.get("reference")
    gp = root / "data/transcripts/gold" / f"{e['conv']}__gold.json"
    return json.loads(gp.read_text(encoding="utf-8"))["text"] if gp.exists() else None


def _variant_parts(v: str) -> dict:
    if v == "clean":
        return {"noise_type": "none", "snr_db": "none", "speed": "1.0"}
    if v.startswith("speed"):
        return {"noise_type": "none", "snr_db": "none", "speed": v.removeprefix("speed")}
    n, s = v.split("_snr")
    return {"noise_type": n, "snr_db": s, "speed": "1.0"}


def utterance_rows(
    root: Path, model: str, entries: list[dict], terms: M.CriticalTerms
) -> list[dict]:
    d = root / "results/m2_asr/dev" / model
    rows = []
    for e in entries:
        f = d / out_name(e["audio_id"])
        if not f.exists():
            continue
        t = json.loads(f.read_text(encoding="utf-8"))
        ref = reference_text(root, e)
        if ref is None:
            continue
        m = M.utterance_metrics(ref, t["text"])
        rec = terms.recall(ref, t["text"])
        rows.append(
            {
                **e,
                **m,
                **{f"{c}_hits": rec[c][0] for c in M.CLASSES},
                **{f"{c}_n": rec[c][1] for c in M.CLASSES},
                "latency_ms": t["latency_ms"],
                "audio_duration_s": t["audio_duration_s"],
                "rtf": M.rtf(t["latency_ms"], t["audio_duration_s"]),
                "hardware": t["hardware"],
                "revision": t["model"]["revision"],
                "code_switched": M.is_code_switched(ref),
                "hyp_empty": not t["text"].strip(),
                "runaway": len(M.compare_norm(t["text"])) > 3 * max(1, m["ref_chars"]),
                **_variant_parts(e["variant"]),
            }
        )
    return rows


SLICE_KINDS = ("all", "variant", "noise_type", "snr_db", "speed", "voice", "code_switched")


def _stat_row(model: str, source: str, kind: str, value: str, us: list[dict]) -> dict:
    row: dict = {
        "model": model,
        "status": "ran",
        "source": source,
        "slice": kind,
        "value": value,
        "n_utterances": len(us),
    }
    for k in ("cer", "gcer", "wer", "cer_nopunct"):
        xs = [u[k] for u in us if u[k] is not None]
        lo, hi = M.bootstrap_ci(xs)
        row[f"{k}_mean"] = round(sum(xs) / len(xs), 4) if xs else ""
        row[f"{k}_ci_lo"], row[f"{k}_ci_hi"] = round(lo, 4), round(hi, 4)
    ce, rc = sum(u["char_edits"] for u in us), sum(u["ref_chars"] for u in us)
    row["cer_corpus"] = round(ce / rc, 4) if rc else ""
    for c in M.CLASSES:
        k, n = sum(u[f"{c}_hits"] for u in us), sum(u[f"{c}_n"] for u in us)
        lo, hi = M.wilson(k, n)
        row.update(
            {
                f"recall_{c}_k": k,
                f"recall_{c}_n": n,
                f"recall_{c}": round(k / n, 4) if n else "",
                f"recall_{c}_wilson_lo": "" if lo is None else round(lo, 4),
                f"recall_{c}_wilson_hi": "" if hi is None else round(hi, 4),
            }
        )
    lats = [u["latency_ms"] for u in us if u["latency_ms"] is not None]
    rtfs = [u["rtf"] for u in us if u["rtf"] is not None]
    row["latency_ms_p50"] = round(M.percentile(lats, 50), 1) if lats else ""
    row["latency_ms_p95"] = round(M.percentile(lats, 95), 1) if lats else ""
    row["rtf_mean"] = round(sum(rtfs) / len(rtfs), 3) if rtfs else ""
    row["empty_outputs"] = sum(u["hyp_empty"] for u in us)
    row["runaway_outputs_gt3x_ref_len"] = sum(u["runaway"] for u in us)
    row["hardware"], row["revision"], row["note"] = us[0]["hardware"], us[0]["revision"], ""
    return row


def summarise(root: Path, models_ran: list[str], entries: list[dict], out_csv: Path) -> list[dict]:
    terms = load_terms(root)
    out: list[dict] = []
    for model in models_ran:
        urows = utterance_rows(root, model, entries, terms)
        by_source = defaultdict(list)
        for u in urows:
            by_source[u["source"]].append(u)
        for source, us in sorted(by_source.items()):
            for kind in SLICE_KINDS:
                groups = defaultdict(list)
                for u in us:
                    groups["ALL" if kind == "all" else str(u[kind])].append(u)
                if kind in ("noise_type", "snr_db", "speed", "variant") and source != "tts":
                    continue  # public_real has only clean audio
                for val, g in sorted(groups.items()):
                    out.append(_stat_row(model, source, kind, val, g))
        n_expected = len(entries)
        for r in out:
            if r["model"] == model and r["slice"] == "all":
                r["note"] = f"{len(urows)} of {n_expected} common-subset files scored"
    for name, info in NOT_RUN.items():
        out.append(
            {
                "model": name,
                "status": info["status"],
                "source": "",
                "slice": "",
                "value": "",
                "note": info["reason"],
                "revision": info["repo"],
            }
        )
    cols: list[str] = []
    for r in out:
        for k in r:
            if k not in cols:
                cols.append(k)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    return out


def paired(root: Path, a: str, b: str, entries: list[dict], out_csv: Path) -> list[dict]:
    """Paired bootstrap of per-utterance CER difference (a - b) on the SAME files, per source."""
    terms = load_terms(root)
    ra = {u["audio_id"]: u for u in utterance_rows(root, a, entries, terms)}
    rb = {u["audio_id"]: u for u in utterance_rows(root, b, entries, terms)}
    rows = []
    for source in ("tts", "public_real"):
        ids = sorted(i for i in ra if i in rb and ra[i]["source"] == source)
        d = [
            ra[i]["cer"] - rb[i]["cer"]
            for i in ids
            if ra[i]["cer"] is not None and rb[i]["cer"] is not None
        ]
        lo, hi = M.bootstrap_ci(d)
        rows.append(
            {
                "model_a": a,
                "model_b": b,
                "source": source,
                "n_paired": len(d),
                "mean_cer_a_minus_b": round(sum(d) / len(d), 4) if d else "",
                "ci_lo": round(lo, 4),
                "ci_hi": round(hi, 4),
                "a_better": bool(d) and hi < 0,
                "b_better": bool(d) and lo > 0,
            }
        )
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows


def all_model_names() -> list[str]:
    return list(MODELS)
