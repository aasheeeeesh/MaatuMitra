"""m7_eval command line.

uv run python -m m7_eval run            # DEV (default): results/m7_eval/dev/
MODE=mock uv run python -m m7_eval mock # fake tree from fixtures/: results/m7_eval/mock/
uv run python -m m7_eval eval-test      # GUARDED: refuses unless ALLOW_TEST=1, PURPOSE and
                                        # a results/test_access_log.md row for this commit
uv run python -m m7_eval repro-check    # two DEV runs, compare every output sha256
uv run python -m m7_eval e7-analyse <record_sheet.csv> [--out DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from m7_eval import report
from m7_eval.guard import TestSplitRefusedError

ROOT = Path(__file__).resolve().parents[1]


def _print_result(res: dict, out: Path) -> None:
    print(
        f"wrote {out.as_posix()}: {len(res['tables'])} tables, {len(res['plots'])} plots, "
        f"{len(res['gallery'])} gallery items, {len(res['manifest']['inputs'])} inputs hashed, "
        f"test files opened: {len(res['manifest']['test_files_opened'])}"
    )
    for n in res["notes"]:
        print(f"  note: {n}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="m7_eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--split", default="dev", choices=["dev"])
    r.add_argument("--out", type=Path, default=ROOT / "results/m7_eval/dev")
    m = sub.add_parser("mock")
    m.add_argument("--out", type=Path, default=ROOT / "results/m7_eval/mock")
    t = sub.add_parser("eval-test")
    t.add_argument("--out", type=Path, default=ROOT / "results/m7_eval/test")
    sub.add_parser("repro-check")
    a = sub.add_parser("e7-analyse")
    a.add_argument("sheet", type=Path)
    a.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.cmd == "run":
        res = report.run(ROOT, "dev", args.out)
        _print_result(res, args.out)
        return 0
    if args.cmd == "mock":
        from m7_eval import mock

        with tempfile.TemporaryDirectory() as td:
            tree = mock.build_mock_root(ROOT, Path(td))
            res = report.run(tree, "dev", args.out, gh="mock")
        _print_result(res, args.out)
        return 0
    if args.cmd == "eval-test":
        try:
            res = report.run(ROOT, "test", args.out, env=dict(os.environ))
        except TestSplitRefusedError as e:
            print(str(e), file=sys.stderr)
            return 3
        _print_result(res, args.out)
        return 0
    if args.cmd == "repro-check":
        with tempfile.TemporaryDirectory() as td:
            gh = report.git_hash(ROOT)
            m1 = report.run(ROOT, "dev", Path(td) / "a", gh=gh)["manifest"]["outputs"]
            m2 = report.run(ROOT, "dev", Path(td) / "b", gh=gh)["manifest"]["outputs"]
        same = m1 == m2
        print(f"repro-check: {len(m1)} output files, identical across two runs: {same}")
        return 0 if same else 1
    if args.cmd == "e7-analyse":
        from m7_eval.e7_kit import analyse

        out = analyse.main(args.sheet, args.out)
        print(out)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
