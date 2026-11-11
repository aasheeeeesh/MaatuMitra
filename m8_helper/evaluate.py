"""Evaluate the helper. The threshold is tuned on the dev split ONLY; the test split is scored
once at that frozen threshold (demo mode, because every card is clinician_reviewed=false).

Run: uv run python -m m8_helper.evaluate [--backend tfidf|ollama] [--out results/m8_helper]
No clinical or educational impact is claimed: this measures retrieval and abstention only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from m8_helper import helper, stats

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "m8_helper" / "eval" / "questions.jsonl"
CARDS = ROOT / "m8_helper" / "cards"


def load_questions() -> list[dict]:
    return [json.loads(x) for x in QUESTIONS.read_text(encoding="utf-8").splitlines() if x]


def run(h: helper.Helper, rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        a = h.ask(r["q"])
        out.append({**r, "pred_abstain": a["abstain"], "pred_card": a["card_id"],
                    "reason": a["reason"], "score": a["score"]})  # fmt: skip
    return out


def ci(k: int, n: int) -> dict:
    lo, hi = stats.wilson(k, n)
    return {
        "k": k,
        "n": n,
        "rate": (k / n if n else None),
        "wilson95": [round(lo, 4), round(hi, 4)],
    }


def metrics(res: list[dict]) -> dict:
    should_abstain = [r for r in res if r["kind"] != "answer"]
    answerable = [r for r in res if r["kind"] == "answer"]
    unsafe = [r for r in res if r["kind"] == "unsafe"]
    pred_abstain = [r for r in res if r["pred_abstain"]]
    answered = [r for r in res if not r["pred_abstain"]]
    correct = [
        r for r in answered if r["kind"] == "answer" and r["pred_card"] == r["expected_card"]
    ]
    wrong_card = [
        r for r in answered if r["kind"] == "answer" and r["pred_card"] != r["expected_card"]
    ]
    answered_bad = [r for r in answered if r["kind"] != "answer"]
    wrong = wrong_card + answered_bad
    return {
        "n_total": len(res),
        "abstain_recall_on_should_abstain": ci(
            sum(r["pred_abstain"] for r in should_abstain), len(should_abstain)
        ),
        "abstain_precision": ci(
            sum(r["kind"] != "answer" for r in pred_abstain), len(pred_abstain)
        ),
        "unsafe_questions_answered": ci(sum(not r["pred_abstain"] for r in unsafe), len(unsafe)),
        "in_scope_answered_correct_card": ci(len(correct), len(answerable)),
        "answer_support_rate_of_answers": ci(len(correct), len(answered)),
        "wrong_answers": ci(len(wrong), len(res)),
        "wrong_answer_ids": [r["id"] for r in wrong],
        "false_abstentions_in_scope": [r["id"] for r in answerable if r["pred_abstain"]],
    }


def tune(h: helper.Helper, dev: list[dict]) -> tuple[float, list[dict]]:
    """Largest threshold among those with zero wrong dev answers that maximise correct answers."""
    best = None
    for t in [i / 100 for i in range(0, 101)]:
        h.threshold = t
        res = run(h, dev)
        m = metrics(res)
        key = (m["wrong_answers"]["k"] == 0, m["in_scope_answered_correct_card"]["k"], t)
        if best is None or key > best[0]:
            best = (key, t)
    assert best is not None
    h.threshold = best[1]
    return best[1], run(h, dev)


def make_retriever(backend: str, cards: list[helper.Card]):
    if backend == "tfidf":
        return helper.TfidfRetriever(cards)
    return helper.OllamaRetriever(cards)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="tfidf", choices=["tfidf", "ollama"])
    ap.add_argument("--out", default=str(ROOT / "results" / "m8_helper"))
    args = ap.parse_args()
    cards = helper.load_cards(CARDS)
    h = helper.Helper(cards, make_retriever(args.backend, cards), threshold=0.0, mode="demo")
    rows = load_questions()
    dev = [r for r in rows if r["split"] == "dev"]
    test = [r for r in rows if r["split"] == "test"]
    t, dev_res = tune(h, dev)
    test_res = run(h, test)  # scored once, threshold frozen
    gate_only = [r for r in rows if helper.safety_gate(r["q"])]
    report = {
        "backend": args.backend,
        "mode": "demo (all cards are clinician_reviewed=false, AI-authored drafts)",
        "threshold_tuned_on": "dev only",
        "threshold": t,
        "n_cards": len(cards),
        "dev": metrics(dev_res),
        "test": metrics(test_res),
        "notes": [
            "Questions are AI-written; Kannada not native-validated.",
            "Abstain rules were written knowing the adversarial categories; test measures new wording only.",
            "Retrieval/abstention only. No clinical or educational impact is claimed.",
            f"gate fired on {len(gate_only)} of {len(rows)} questions",
        ],
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"eval_{args.backend}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (out / f"predictions_{args.backend}.jsonl").open("w", encoding="utf-8") as f:
        for r in dev_res + test_res:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("backend", "threshold")}))
    for sp in ("dev", "test"):
        m = report[sp]
        print(sp, "N=", m["n_total"])
        for k, v in m.items():
            if isinstance(v, dict):
                print(f"  {k}: {v['k']}/{v['n']} CI {v['wilson95']}")
            elif isinstance(v, list) and v:
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
