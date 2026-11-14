"""CLI.

uv run python -m m3_extract mock                      # MODE=mock: fixtures only
uv run python -m m3_extract run-rules [--split dev] [--schema record.v2|record.v1] [--transcripts DIR]
uv run python -m m3_extract score-v2                  # dev_scores_v2.csv (gold.v2, DEV only)
uv run python -m m3_extract run-llm [--subset]        # seeded 40-conversation DEV subset
uv run python -m m3_extract score                     # dev_scores.csv + failures_dev.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from m3_extract import run, splits


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="m3_extract")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("mock")
    r = sub.add_parser("run-rules")
    r.add_argument("--split", default="dev", choices=["dev", "test"])
    r.add_argument(
        "--transcripts", type=Path, default=None, help="dir of transcript.v1 files (default: gold)"
    )
    r.add_argument("--out", type=Path, default=None)
    r.add_argument("--schema", default="record.v2", choices=["record.v1", "record.v2"])
    q = sub.add_parser("run-llm")
    q.add_argument("--all-dev", action="store_true", help="full dev instead of the seeded subset")
    q.add_argument("--transcripts", type=Path, default=None)
    sub.add_parser("score")
    sub.add_parser("score-v2")
    a = ap.parse_args(argv)

    if a.cmd == "mock" or os.environ.get("MODE") == "mock":
        print(json.dumps(run.run_mock(), indent=2))
        return 0
    if a.cmd == "run-rules":
        ids = splits.split_ids(a.split)
        base = "rules" if a.schema == "record.v1" else "rules_v2"
        out = a.out or (
            run.RESULTS / (base if a.transcripts is None else f"{base}_{a.transcripts.name}")
        )
        print(
            json.dumps(
                run.run_rules(ids, out, transcripts_dir=a.transcripts, schema=a.schema), indent=2
            )
        )
        return 0
    if a.cmd == "run-llm":
        ids = splits.dev_ids() if a.all_dev else splits.llm_subset()
        (run.RESULTS / "llm_subset.txt").write_text(
            "\n".join(splits.llm_subset()) + "\n", encoding="utf-8"
        )
        out = run.RESULTS / ("llm" if a.transcripts is None else f"llm_{a.transcripts.name}")
        print(json.dumps(run.run_llm(ids, out, transcripts_dir=a.transcripts), indent=2))
        return 0
    if a.cmd == "score-v2":
        print(json.dumps(run.score_dev_v2(), indent=2, ensure_ascii=False))
        return 0
    if a.cmd == "score":
        print(json.dumps(run.score_dev(), indent=2, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
