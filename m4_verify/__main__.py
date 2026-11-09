"""m4_verify command line.

  uv run python -m m4_verify verify --record R.json --transcript T.json [--second-transcript T2.json]
                                    [--disable C3 ...] [--config cfg.yaml] [--lexicon drugs.csv]
                                    [--encounter-index index.json] [--out verdict.json]
  MODE=mock uv run python -m m4_verify mock [--out-dir results/m4_verify]
  uv run python -m m4_verify e4 [--gold-dir DIR_OR_JSONL] [--lexicon CSV] [--n 200] [--seed N] [--out-dir DIR]
  uv run python -m m4_verify audit --sentences FILE.txt      (prints negation matches per line)
  uv run python -m m4_verify tune-c7 --pairs DEV_PAIRS.jsonl  (DEV only; see tune_c7.py)

Exit codes: 0 ok, 2 usage error (unknown check id, unreadable input).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from m4_verify.config import CHECK_IDS, ROOT, default_config, load_config


def _load(p: str):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _cfg(args):
    cfg = load_config(args.config) if getattr(args, "config", None) else default_config()
    if getattr(args, "disable", None):
        bad = [c for c in args.disable if c.upper() not in CHECK_IDS]
        if bad:
            print(
                f"error: unknown check id(s) {bad}; valid: {', '.join(CHECK_IDS)}", file=sys.stderr
            )
            sys.exit(2)
        cfg = replace(cfg, disabled=cfg.disabled | {c.upper() for c in args.disable})
    if getattr(args, "lexicon", None):
        cfg = replace(cfg, lexicon_path=str(Path(args.lexicon).resolve()))
    return cfg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="m4_verify", description="Deterministic fail-closed verifier (C1..C8)."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="verify one record against its transcript")
    v.add_argument("--record", required=True)
    v.add_argument("--transcript", required=True)
    v.add_argument("--second-transcript")
    v.add_argument("--disable", nargs="*", default=[])
    v.add_argument("--config")
    v.add_argument("--lexicon")
    v.add_argument("--encounter-index", help="JSON object {audio_id: patient_ref}")
    v.add_argument("--out")

    m = sub.add_parser("mock", help="MODE=mock: fixtures only")
    m.add_argument("--out-dir", default=str(ROOT / "results" / "m4_verify"))
    m.add_argument("--n", type=int, default=200)
    m.add_argument("--skip-e4", action="store_true")

    e = sub.add_parser("e4", help="planted-mistake experiment (DEV gold only)")
    e.add_argument("--gold-dir", default=str(ROOT / "fixtures" / "gold" / "valid"))
    e.add_argument("--lexicon")
    e.add_argument("--config")
    e.add_argument("--disable", nargs="*", default=[])
    e.add_argument("--n", type=int, default=200)
    e.add_argument("--seed", type=int, default=20261109)
    e.add_argument("--out-dir", default=str(ROOT / "results" / "m4_verify"))

    a = sub.add_parser("audit", help="print negation analysis for each line of a text file")
    a.add_argument("--sentences", required=True)

    t = sub.add_parser("tune-c7", help="tune the C7 confidence threshold on DEV pairs")
    t.add_argument(
        "--pairs", required=True, help="JSONL rows {asr_transcript: path, gold_transcript: path}"
    )
    t.add_argument("--max-flag-rate", type=float, default=0.2)

    args = ap.parse_args(argv)

    if args.cmd == "verify":
        from m4_verify.verifier import verify

        cfg = _cfg(args)
        try:
            rec, tr = _load(args.record), _load(args.transcript)
            second = _load(args.second_transcript) if args.second_transcript else None
            index = _load(args.encounter_index) if args.encounter_index else None
        except (OSError, json.JSONDecodeError) as ex:
            print(f"error: cannot read input: {ex}", file=sys.stderr)
            return 2
        verdict = verify(rec, tr, config=cfg, second_transcript=second, encounter_index=index)
        txt = json.dumps(verdict, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(txt + "\n", encoding="utf-8")
        else:
            sys.stdout.reconfigure(encoding="utf-8")
            print(txt)
        return 0

    if args.cmd == "mock":
        import os

        os.environ["MODE"] = "mock"
        from m4_verify.evaluate import FIX, run_e4, run_mock
        from m4_verify.lexicon import load_lexicon

        cfg = default_config()
        lex = load_lexicon(FIX / "lexicon" / "drugs_fixture.csv")
        out = Path(args.out_dir)
        res = run_mock(out, lex, cfg)
        print(
            f"mock: {res['verdicts_validated']} fixture verdicts validated, errors={res['validation_errors']}"
        )
        for rid, s in res["records"].items():
            print(f"  {rid}: auto_acceptable={s['auto_acceptable']} flags={s['flags']}")
        if not args.skip_e4:
            s = run_e4(FIX / "gold" / "valid", lex, cfg, out, n_per_type=args.n)
            _print_e4(s)
        return 1 if res["validation_errors"] else 0

    if args.cmd == "e4":
        from m4_verify.evaluate import run_e4
        from m4_verify.lexicon import load_lexicon

        cfg = _cfg(args)
        lex = load_lexicon(cfg.lexicon_path) if cfg.lexicon_path else cfg.lexicon()
        s = run_e4(
            Path(args.gold_dir), lex, cfg, Path(args.out_dir), n_per_type=args.n, seed=args.seed
        )
        _print_e4(s)
        return 1 if s["verdict_validation_errors"] else 0

    if args.cmd == "audit":
        from m4_verify.negation import analyze

        sys.stdout.reconfigure(encoding="utf-8")
        for ln, line in enumerate(Path(args.sentences).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            an = analyze(line)
            cues = [f"{c.token}:{c.rule_id}" for cl in an.clauses for c in cl.cues]
            print(f"{ln}\t{'NEG' if cues else '---'}\t{' '.join(cues)}\t{line}")
        return 0

    if args.cmd == "tune-c7":
        from m4_verify.tune_c7 import main as tune_main

        return tune_main(args.pairs, args.max_flag_rate)
    return 2


def _print_e4(s: dict) -> None:
    print(
        f"e4: {s['n_gold_conversations']} gold conversations from {s['gold_source']}; verdicts validated={s['verdicts_validated']} errors={len(s['verdict_validation_errors'])}"
    )
    for r in s["clean_flag_rate"]:
        print(f"  clean {r['unit']}: {r['flagged']}/{r['n']} flagged")
    for r in s["catch_rates"]:
        print(
            f"  {r['level']:<10} {r['condition']:<22} {r['type']} {r['type_name']:<24} caught {r['caught']}/{r['n']} (unique {r['unique_caught']}/{r['n_unique']})"
        )


if __name__ == "__main__":
    sys.exit(main())
