"""E7 analysis: DESCRIPTIVE results only (few participants: no significance tests, no p-values).

    uv run python -m m7_eval e7-analyse m7_eval/e7_kit/record_sheet_filled.csv

Per condition (flags_shown / flags_hidden): review time (median, mean with bootstrap 95% CI over
reviews), catch rate on records with a planted error (k/n, Wilson 95% CI), false-alarm rate on
clean records (k/n, Wilson), and the automation-bias view: catch rate on planted errors whose
simulated flag was WITHHELD, shown vs hidden.
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

from m7_eval import stats

KIT = Path(__file__).resolve().parent


def _rows(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def analyse(
    sheet: Path, key_path: Path = KIT / "answer_key.csv", seed: int = 20261109
) -> list[dict]:
    key = {r["record_id"]: r for r in _rows(key_path)}
    rows = [r for r in _rows(sheet) if r.get("marked_error", "").strip()]
    out = []
    for cond in ("flags_shown", "flags_hidden"):
        rs = [r for r in rows if r["condition"] == cond]
        err = [r for r in rs if key[r["record_id"]]["has_planted_error"] == "yes"]
        clean = [r for r in rs if key[r["record_id"]]["has_planted_error"] == "no"]
        unflagged_err = [r for r in err if key[r["record_id"]]["simulated_flag"] == "no"]
        secs = [float(r["review_seconds"]) for r in rs if r.get("review_seconds", "").strip()]
        caught = sum(r["marked_error"].strip().lower() == "yes" for r in err)
        fa = sum(r["marked_error"].strip().lower() == "yes" for r in clean)
        cu = sum(r["marked_error"].strip().lower() == "yes" for r in unflagged_err)
        lo, hi = stats.bootstrap_mean_ci(secs, seed=seed)
        row = {
            "condition": cond,
            "n_participants": len({r["participant_id"] for r in rs}),
            "n_reviews": len(rs),
            "review_seconds_median": statistics.median(secs) if secs else None,
            "review_seconds_mean": statistics.fmean(secs) if secs else None,
            "review_seconds_boot_lo": lo,
            "review_seconds_boot_hi": hi,
        }
        for name, k, n in (
            ("catch", caught, len(err)),
            ("false_alarm", fa, len(clean)),
            ("catch_when_no_flag", cu, len(unflagged_err)),
        ):
            p = stats.proportion(k, n)
            row.update(
                {
                    f"{name}_k": k,
                    f"{name}_n": n,
                    f"{name}_rate": p["rate"],
                    f"{name}_wilson_lo": p["wilson_lo"],
                    f"{name}_wilson_hi": p["wilson_hi"],
                }
            )
        out.append(row)
    return out


def report(rows: list[dict]) -> str:
    s = (
        "# E7 user study: descriptive results\n\n"
        "With so few participants we make NO significance claims and report no p-values; "
        "intervals are Wilson 95% (proportions) and bootstrap 95% (mean time).\n\n"
        "| condition | participants | reviews | median s | mean s [CI] | catch | false alarms | "
        "catch when the flag was withheld |\n|---|---|---|---|---|---|---|---|\n"
    )
    for r in rows:

        def p(n, r=r):
            if not r[f"{n}_n"]:
                return "n/a (n=0)"
            return f"{r[f'{n}_k']}/{r[f'{n}_n']} [{r[f'{n}_wilson_lo']:.2f}, {r[f'{n}_wilson_hi']:.2f}]"

        mean = (
            "n/a"
            if r["review_seconds_mean"] is None
            else (
                f"{r['review_seconds_mean']:.1f} [{r['review_seconds_boot_lo']:.1f}, {r['review_seconds_boot_hi']:.1f}]"
            )
        )
        s += (
            f"| {r['condition']} | {r['n_participants']} | {r['n_reviews']} | "
            f"{r['review_seconds_median']} | {mean} | {p('catch')} | {p('false_alarm')} | "
            f"{p('catch_when_no_flag')} |\n"
        )
    return s


def main(sheet: Path, out: Path | None = None) -> str:
    text = report(analyse(sheet))
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "e7_results.md").write_text(text, encoding="utf-8", newline="\n")
    return text
