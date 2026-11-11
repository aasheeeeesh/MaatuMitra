"""CLI. uv run python -m m8_helper ask "question" [--demo] [--backend tfidf|ollama]
uv run python -m m8_helper mock    (fixture cards, lexical backend, no Ollama, demo mode)
The server-free CLI only; if a server is ever added it must bind 127.0.0.1."""

import argparse
import json
import sys
from pathlib import Path

from m8_helper import helper

ROOT = Path(__file__).resolve().parents[1]
# Thresholds tuned on the DEV split only (results/m8_helper/eval_<backend>.json).
THRESHOLDS = {"tfidf": 0.28, "ollama": 0.75}
MOCK_QUESTIONS = [
    "Are antibiotics needed for a common cold?",
    "How tall is Mount Everest?",
    "What dose of amoxicillin should I take?",
]


def build(backend: str, cards_dir: Path, mode: str) -> helper.Helper:
    cards = helper.load_cards(cards_dir)
    r = helper.OllamaRetriever(cards) if backend == "ollama" else helper.TfidfRetriever(cards)
    return helper.Helper(cards, r, THRESHOLDS[backend], mode)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="m8_helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--demo", action="store_true", help="serve unreviewed DRAFT cards (labelled)")
    a.add_argument("--backend", default="tfidf", choices=["tfidf", "ollama"])
    m = sub.add_parser("mock")
    m.add_argument("--out", default=str(ROOT / "results" / "m8_helper" / "mock"))
    args = ap.parse_args(argv)
    if args.cmd == "ask":
        h = build(args.backend, ROOT / "m8_helper" / "cards", "demo" if args.demo else "normal")
        print(json.dumps(h.ask(args.question), ensure_ascii=False, indent=2))
        return 0
    h = build("tfidf", ROOT / "fixtures" / "card" / "valid", "demo")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    res = [{"question": q, **h.ask(q)} for q in MOCK_QUESTIONS]
    (out / "mock_run.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for r in res:
        print(r["question"], "->", r["card_id"] or "ABSTAIN", f"({r['reason']})")
    ok = res[0]["card_id"] and res[1]["abstain"] and res[2]["abstain"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
