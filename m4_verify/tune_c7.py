"""Tune the C7 confidence threshold on DEV ASR output only (PROJECT_BRIEF 6.5).

Input: JSONL rows {"asr_transcript": path, "gold_transcript": path} for DEV audio.
A critical ASR word (drug / number / unit / negation cue) is "wrong" if its comparison form does
not occur among the gold transcript's tokens. For each candidate threshold we compute
recall (wrong critical words below threshold) and flag rate (correct critical words below
threshold), and pick the HIGHEST recall whose flag rate <= max_flag_rate. Paths containing a
"test" component are refused. Copy the printed value into the config by hand (with a decision entry).
"""

from __future__ import annotations

import json
from pathlib import Path

from m4_verify.config import default_config
from m4_verify.lexicon import UNIT_TOKENS
from m4_verify.negation import classify_token
from m4_verify.numbers import word_value
from m4_verify.planted import refuse_test_split
from m4_verify.textnorm import comparison, token_texts


def _critical(word: str, drug_tokens: set[str]) -> bool:
    w = comparison(word)
    return (
        w.isdigit()
        or word_value(w) is not None
        or w in UNIT_TOKENS
        or w in drug_tokens
        or classify_token(w) is not None
    )


def tune(pairs: list[tuple[dict, dict]], max_flag_rate: float = 0.2) -> dict:
    drug_tokens = default_config().lexicon().entity_tokens()
    obs: list[tuple[float, bool]] = []  # (conf, wrong)
    for asr, gold in pairs:
        gold_toks = set(token_texts(gold["text"]))
        for w in asr["words"]:
            if w.get("conf") is None or not _critical(w["w"], drug_tokens):
                continue
            obs.append((float(w["conf"]), comparison(w["w"]) not in gold_toks))
    wrong = [c for c, bad in obs if bad]
    right = [c for c, bad in obs if not bad]
    best = None
    grid = []
    for k in range(5, 100, 5):
        thr = k / 100
        rec = sum(c < thr for c in wrong) / len(wrong) if wrong else float("nan")
        fr = sum(c < thr for c in right) / len(right) if right else float("nan")
        grid.append({"threshold": thr, "recall": rec, "flag_rate": fr})
        if fr == fr and fr <= max_flag_rate and (best is None or rec > best["recall"]):
            best = grid[-1]
    return {
        "n_critical": len(obs),
        "n_wrong": len(wrong),
        "grid": grid,
        "chosen": best,
        "max_flag_rate": max_flag_rate,
    }


def main(pairs_path: str, max_flag_rate: float) -> int:
    refuse_test_split(pairs_path)
    pairs = []
    for line in Path(pairs_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        for k in ("asr_transcript", "gold_transcript"):
            refuse_test_split(row[k])
        pairs.append(
            tuple(
                json.loads(Path(row[k]).read_text(encoding="utf-8"))
                for k in ("asr_transcript", "gold_transcript")
            )
        )
    print(json.dumps(tune(pairs, max_flag_rate), indent=2))
    return 0
