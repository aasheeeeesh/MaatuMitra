# m7_eval plan (research-scientist-eval, 2026-11-12)

Goal: ONE command (`mingw32-make eval`) recomputes every E1-E7 number from saved raw outputs
under `results/<module>/` on the DEV split, with no GPU, and writes `results/m7_eval/`.
`mingw32-make eval-test` is guarded (ALLOW_TEST=1, PURPOSE, committed hypothesis.md, log row).

## Order of work (tests first)
1. `stats.py` + tests: Wilson (0/50, 3/50 hand values), rule of three, bootstrap,
   paired bootstrap, cluster bootstrap (seed reproducibility).
2. `textnorm.py`, `asr_metrics.py` + tests: comparison normalisation, CER, grapheme CER,
   WER, critical-term recall (drug / number / unit / negation).
3. `guard.py` + tests: split membership (dev.txt, test.txt, test.lock), a guarded reader that
   refuses test files, the eval-test refusal, the "log row for this commit" requirement.
4. `frames.py` + tests: seen-frame vs unseen-frame marker from TEMPLATE text only.
5. `scoring.py` + tests: field-level record vs gold scoring, v1 and v2 (CR-ROUTE,
   CR-PAEDIATRIC, CR-LIQUID-STRENGTH, MA-STATUS); "not measurable" for v1.
6. `experiments.py`: E1 ASR (m2, "not run yet" when absent), E2 rules vs LLM (m3; STALE
   label), E3 ablation (derived from m4 per-check raw rows), E4 planted (m4, unique N,
   headline = text-only row next to review burden), E5 access (m5, rule of three),
   E6 helper (m8, dev rows only), cost/latency.
7. `report.py`: CSV tables, small PNG plots with CIs (English labels only), failure gallery,
   input manifest (sha256 + git hash). `__main__.py` CLI; MODE=mock on a fake tree built
   from fixtures/.
8. E7 user-study kit in `m7_eval/e7_kit/` (protocol, consent EN/KN, 20 synthetic records,
   record sheet, SUS questionnaire, analysis script with Wilson CIs, no significance tests).
9. module.mk targets: m7-test, m7-mock, m7-eval (EVAL_TARGETS), m7-eval-test
   (EVAL_TEST_TARGETS), m7-e2-llm-refresh (delegates to m3's own target; not run by m7).

## Rules kept
- Only DEV files are opened in the default run (proved by a test that patches `open`).
- Every proportion: k, n, Wilson 95% CI; zero counts also get 3/n.
- Extraction rates: cluster bootstrap by template family is the PRIMARY CI (D-121).
- Never pool TTS and real audio, or planted and natural errors.
- Dev numbers about m3/m4 rules carry the "in-sample (dev used to write the rules)" label.
