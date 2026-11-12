# m7_eval (L7: evaluation, statistics, failure gallery, user-study kit)

Built by `research-scientist-eval` (2026-11-12). One command recomputes every number from the
saved raw outputs of the other modules, on the DEV split, with no GPU and no network:

```
mingw32-make eval        # root: m3-score, m4-mock, then m7-eval -> results/m7_eval/dev/
mingw32-make m7-repro    # two DEV runs into temp folders; every output sha256 must match
mingw32-make m7-test     # unit + pipeline tests
mingw32-make m7-mock     # fake tree from fixtures/ -> results/m7_eval/mock/
```

Outputs (`results/m7_eval/dev/`): `tables/*.csv`, `plots/*.png` (English labels only, CIs
shown), `summary.md` (headline tables), `failure_gallery.md` (dev only), `cost_report.md`,
`manifest.json` (git hash + sha256 of every input and output), `run_log.json` (runtime; the
only file that differs between identical runs).

## Experiments
| id | source | what m7 computes |
|---|---|---|
| E1 ASR | `results/m2_asr/<run>/<split>/transcripts.jsonl` (transcript.v1 per line; contract defined here because m2 is not built) | CER (primary), grapheme CER, WER, CER without punctuation; critical-term recall per class (drug / number / unit / negation); latency p50/p95, RTF + hardware; per model x source x variant x voice; paired bootstrap vs the baseline on the common subset. Today: "m2 not run yet". |
| E2 extraction | `results/m3_extract/rules/`, `llm/` (or `llm_STALE_pre_refreeze/`) vs `data/gold` | field-level errors per 1,000 fields by severity and code; item P/R/F1; slices by family and tags; paired bootstrap rules vs LLM (only for fresh LLM outputs). |
| E3 ablation | `results/m4_verify/dev/e4/` raw rows | remove each check C1..C8: critical errors caught/escaped AND flag rate on error-free fields. |
| E4 planted | same | catch rate per type and per field over UNIQUE mutations; headline = text-only transcript row next to the review burden; record-level and oracle rows labelled. |
| E5 access | `results/m5_backend/access_matrix_results.jsonl` | unauthorized successes (rule of three), unexpected denials, by layer / attack / role. |
| E6 helper | `results/m8_helper/predictions_*.jsonl` (dev rows only) | in-scope answered from the right card, out-of-scope and dosing/diagnosis refusals, card citation. |
| E7 kit | `m7_eval/e7_kit/` | protocol, consent EN/KN, 20 synthetic records (10 planted), design, sheet, analysis. Not run. |

## Statistics (`stats.py`)
Wilson 95% (z = 1.959964) for every proportion with k and n; rule of three for zero counts;
percentile bootstrap (1000 resamples, seed 20261109); paired bootstrap for system comparisons;
CLUSTER bootstrap by template family = PRIMARY CI for extraction error rates (errors cluster by
template, D-121). Wilson is shown next to it, labelled as assuming independence.

## Test-split discipline
Every read goes through `guard.SplitGuard`. In a DEV run it refuses files listed in
`data/splits/test.lock`, files whose name holds a test conversation id, files in a `test` folder
and the held-out test voice. `make eval-test` (root) runs `infra/scripts/eval_test_guard.py`
(ALLOW_TEST=1, PURPOSE, committed hypothesis.md, appends to `results/test_access_log.md`) and
only then `m7-eval-test`, which itself refuses unless ALLOW_TEST=1, PURPOSE and a log row for the
current commit exist. Tests patch `open` to prove a DEV run opens no test file.

## Labels
Every dev number about the m3 rules and m4 checks is IN-SAMPLE (dev was used to write them).
With record.v1 / gold.v1 inputs the classes CR-ROUTE, CR-PAEDIATRIC and CR-LIQUID-STRENGTH are
"not measurable" (never zero); the scorer already handles record.v2 / gold.v2.
