# m7_eval contract (kept current by research-scientist-eval, 2026-11-12)

- Layer: L7 evaluation, cost log, governance.
- Reads (only through `m7_eval/guard.py`): data/splits (membership only), data/gold and
  data/transcripts/gold (DEV ids only), data/templates (template text, for the frame marker),
  data/lexicon/drugs.csv, data/public_real/fleurs_kn_in_test_subset.jsonl (only its split rows),
  .claude/skills/kannada-nlp/negation_table.yaml, results/m2_asr, results/m3_extract,
  results/m4_verify/dev/e4, results/m5_backend, results/m8_helper.
- Input contract DEFINED HERE for m2 (not built yet): `results/m2_asr/<run>/<split>/transcripts.jsonl`,
  one transcript.v1 per line; `audio_id` = `<conversation>__<voice>__<variant>` (m1 audio_build
  naming) for TTS, or the FLEURS file stem for `source: public_real`; optional
  `results/m2_asr/<run>/run.json` with `hardware`. TEST transcripts go under `<run>/test/`.
- Test-run outputs expected for eval-test (Phase C): results/m3_extract/test/{rules,llm}/,
  results/m4_verify/test/e4/ (see configs/eval.yaml `inputs.test`).
- Writes: results/m7_eval/{dev,mock,test}/, m7_eval/e7_kit/ (kit files), m7_eval/handoff/.
- Imports: `contracts.validate` (tests only). No other module's code.
- Schema versions: transcript.v1, record.v1/v2, gold.v1/v2 (read), verdict-derived E4 rows.
- MOCK MODE: `MODE=mock mingw32-make m7-mock` (fake tree from fixtures/).
