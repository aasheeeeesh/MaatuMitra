# m3_extract: transcript -> structured record with evidence

Layer L2. Built by the `nlp-engineer` agent (AI). Synthetic data only; Kannada rules and word lists
are **not native-validated**. See `plan.md` (design), `CONTRACT.md` (inputs/outputs) and
`handoff/decisions.md` (why).

Two pipelines produce `record.v1`:

| pipeline | what | speed (dev laptop) |
|---|---|---|
| `rules` (MAIN) | normaliser, lexicon drug finder (exact / variant / edit-distance 1 on Latin, logged), Kannada + ASCII number parser, unit / frequency / duration parsers, symptom list, negation flag from the shared table ONLY, cross-turn answers, phrase list for advice / follow-up | ~1 s for all 328 dev conversations |
| `llm` (E2 comparison) | Ollama `qwen3:4b-instruct` (digest `0edcdef34593...`), temperature 0, seed 20261110, JSON-schema-constrained output; the model returns quotes, our code finds them and runs the same evidence check | ~30-60 s per conversation |

Every evidence span satisfies `transcript.text[char_start:char_end] == span_text` (NFC); a record
with any failing span is rejected and kept in `results/m3_extract/<pipeline>/rejected/`.

## Run (Git Bash, repo root)

```bash
export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra
mingw32-make m3-test          # unit tests (fixtures only)
mingw32-make m3-mock          # MODE=mock on fixtures -> results/m3_extract/mock/
mingw32-make m3-run-dev       # rules on all DEV gold transcripts + scoring
mingw32-make m3-run-llm-dev   # LLM on the seeded 40-conversation DEV subset + scoring (needs Ollama)
mingw32-make m3-score         # recompute scores from saved outputs
```

ASR input (when m2 publishes transcripts): `uv run python -m m3_extract run-rules --transcripts <dir>`.

## Dev results (read the honesty labels first)

See `results/m3_extract/dev_scores.csv` (all slices incl. per-field, Wilson 95% CIs, N) and
`results/m3_extract/failures_dev.md`; hand-written analysis in `m3_extract/failure_analysis.md`.

- **Everything here is in-sample.** DEV is where the rules were written. dev_tune (240 records) was
  read while writing; dev_holdout (88) is contaminated (looked at while fixing v2 and v3). No number
  is an estimate of accuracy on new data. The frozen TEST split has not been touched.
- Rules v3 (`results/m3_extract/rules_v3_frozen/`, REFREEZE-1 data): dev_tune critical 0/2704
  [0, 1.4] per 1000, major 0/2704; dev_holdout critical 0/920 [0, 4.2], major 48/920 = 52.2 per 1000
  [39.6, 68.5] (all missed advice / follow-up wording). The pooled "0 critical on full dev" line is
  NOT quoted as a result. Per-field rows: `failure_analysis.md`.
- The only unseen-wording figure is historical: rules v1 on the holdout before REFREEZE-1, critical
  7/920 = 7.6 per 1000 [3.7, 15.6] (`results/m3_extract/rules_v1_frozen/`).
- **Rules vs LLM comparison: STALE.** It was run on pre-REFREEZE data and not rerun (about 25 min for
  40 conversations, over the 15-minute limit). 32 of its 40 conversations are in-sample for the rules
  (seen during rule writing), so it never showed that the rules beat the LLM. Old outputs:
  `results/m3_extract/llm_STALE_pre_refreeze/`. To refresh: `mingw32-make m3-run-llm-dev` (writes
  `results/m3_extract/llm/`).
- No ASR output has been scored yet.
