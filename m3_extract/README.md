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

## Dev results

See `results/m3_extract/dev_scores.csv` (all slices, Wilson 95% CIs) and
`results/m3_extract/failures_dev.md` (examples with input, output, gold and cause). Summary table:
`m3_extract/failure_analysis.md`. The dev_tune score is in-sample (rules were written while reading
those conversations); dev_holdout is the honest estimate for unseen wording; the frozen TEST split
is only touched by `make eval-test`.
