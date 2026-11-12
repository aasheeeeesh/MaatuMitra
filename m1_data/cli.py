"""m1_data command line.

python -m m1_data build-lexicon          (needs: uv run --extra data)
python -m m1_data generate [--refreeze]  (writes data/)
python -m m1_data coverage               (prints + writes results/m1_data/coverage.json)
python -m m1_data verify-lock            (frozen test split unchanged?)
python -m m1_data audio-plan             (counts + size estimate, no disk use)
python -m m1_data audio-build [--limit-convs N] [--min-free-gb 4]   (MMS-TTS audio, resumable)
python -m m1_data fleurs [--min-free-gb 4]                          (public real speech subset)
python -m m1_data audio-verify [--materialise-sample N]  (manifest sha256 vs files present)
python -m m1_data audio-materialise --ids <file|all> --split dev|test --variants <list|all> --out DIR
                                         (variants re-made from the stored clean file; sha256 checked;
                                          --split test needs ALLOW_TEST=1)
MODE=mock python -m m1_data mock         (fixtures only -> results/m1_data/mock/)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from m1_data.config import ROOT, VERSION


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m m1_data", description=f"m1_data {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build-lexicon")
    g = sub.add_parser("generate")
    g.add_argument("--out", type=Path, default=ROOT)
    g.add_argument("--refreeze", action="store_true", help="allow the TEST split to change")
    sub.add_parser("coverage")
    sub.add_parser("verify-lock")
    sub.add_parser("audio-plan")
    v = sub.add_parser("audio-verify")
    v.add_argument("--materialise-sample", type=int, default=0)
    m = sub.add_parser("audio-materialise")
    m.add_argument("--ids", default="all", help="a file of conversation ids, or 'all'")
    m.add_argument("--split", choices=["dev", "test"], required=True)
    m.add_argument("--variants", default="all", help="comma list, e.g. white_snr10,speed1.1")
    m.add_argument("--out", type=Path, required=True)
    for name in ("audio-build", "fleurs"):
        q = sub.add_parser(name)
        q.add_argument("--min-free-gb", type=float, default=4.0)
        if name == "audio-build":
            q.add_argument("--limit-convs", type=int, default=None)
            q.add_argument("--threads", type=int, default=4)
    sub.add_parser("mock")
    a = ap.parse_args(argv)

    if a.cmd == "build-lexicon":
        from m1_data.lexicon import write_lexicon

        print(f"wrote {write_lexicon().relative_to(ROOT).as_posix()}")
    elif a.cmd == "generate":
        from m1_data.generate import generate

        print(json.dumps(generate(out_root=a.out, refreeze=a.refreeze), indent=2))
    elif a.cmd == "coverage":
        from m1_data.coverage import write_reports

        print(json.dumps(write_reports(), ensure_ascii=False, indent=2))
    elif a.cmd in ("audio-plan", "audio-verify", "audio-materialise", "audio-build", "fleurs"):
        from m1_data import audio_run as ar

        if a.cmd == "audio-plan":
            res = ar.estimate(ROOT)
        elif a.cmd == "audio-verify":
            res = ar.verify(ROOT, a.materialise_sample)
        elif a.cmd == "audio-materialise":
            try:
                res = ar.materialise(ROOT, a.ids, a.split, a.variants, a.out)
            except (PermissionError, ValueError) as e:
                print(f"ERROR: {e}")
                return 1
        elif a.cmd == "audio-build":
            res = ar.run_tts(ROOT, a.limit_convs, a.min_free_gb, a.threads)
        else:
            res = ar.run_fleurs(ROOT, a.min_free_gb)
        print(json.dumps(res, indent=2))
        return 1 if res.get("bad") else 0
    elif a.cmd == "verify-lock":
        from m1_data.split import LOCK_PATH, verify_lock

        problems = verify_lock(LOCK_PATH, ROOT)
        for p in problems:
            print(f"ERROR: {p}")
        print("split-lock:", "FAIL" if problems else "OK")
        return 1 if problems else 0
    elif a.cmd == "mock":
        if os.environ.get("MODE") != "mock":
            print("note: MODE is not 'mock'; running the fixture-only mock anyway")
        from m1_data.generate import generate

        out = ROOT / "results" / "m1_data" / "mock"
        res = generate(
            out_root=out,
            lexicon_path=ROOT / "fixtures" / "lexicon" / "drugs_fixture.csv",
            per_template=2,
            mock=True,
            refreeze=True,
        )
        print(json.dumps({k: v for k, v in res.items() if k != "skipped"}, indent=2))
        print(f"skipped templates (no fixture drug fits): {len(res['skipped'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
