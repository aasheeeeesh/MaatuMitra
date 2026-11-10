# m3_extract contract (nlp-engineer, 2026-11-10)

- Layer: L2 structuring (rules = MAIN, local LLM = comparison E2).
- Schema versions: transcript.v1 (in), record.v1 (out), gold.v1 (scoring only).
- Inputs:
  - transcript.v1: `data/transcripts/gold/<cid>__gold.json` (default) or any directory of
    transcript.v1 files named `<cid>__*.json` (`--transcripts DIR`, for ASR outputs later).
    Text must already be NFC with no BOM / zero-width space (refused otherwise: fail closed).
  - Encounter context `{patient_ref, encounter_type}`: not spoken, so not extracted. For dev runs it
    is read from the gold record (only these two fields); in the app it comes from the session.
  - `data/lexicon/drugs.csv` (mock: `fixtures/lexicon/drugs_fixture.csv`).
  - `.claude/skills/kannada-nlp/negation_table.yaml` (the ONLY negation source of the rules pipeline).
  - `m3_extract/data/symptoms.yaml`, `m3_extract/data/phrases.yaml` (this module's own lists).
- Outputs (`results/m3_extract/`):
  - `rules/<record_id>.json`, `llm/<record_id>.json`: record.v1, validated, evidence-checked.
    `record_id` = `<pipeline>-<audio_id>`; `status` is always `draft` (m4/m5 decide the rest).
  - `<pipeline>/rejected/<record_id>.json`: `{record_id, source_transcript_id, reasons[], record}`
    for records that failed the evidence check or record.v1. Scored as errors, never dropped.
  - `<pipeline>/logs/<record_id>.json`: extraction log (rules: events with drug match type
    exact/variant/edit1, cross-turn, soft cue, coordination; LLM: raw output, latency, digest).
  - `llm/latency.csv`, `llm/run_summary.json`, `llm_subset.txt`.
  - `dev_scores.csv`, `error_codes_dev.csv`, `evidence_overlap_dev.csv`, `dev_summary.json`,
    `failures_dev.md`; `rules_v1_frozen/` (scores of rules v1, before the holdout-informed fix).
- Evidence guarantee: for every evidence object, `transcript.text[char_start:char_end] ==
  span_text` (NFC) and audio times are taken from word timestamps when every word in the span has
  them, else null. `m3_extract.evidence.check_evidence(record, text)` is the check.
- May write ONLY: `m3_extract/`, `results/m3_extract/`.
- May import: `contracts.validate` only. Never m4_verify or any other module.
- TEST split: `m3_extract.splits` refuses ids in `data/splits/test.txt` unless `ALLOW_TEST=1`.
- MOCK MODE: `MODE=mock mingw32-make m3-mock` runs purely on `fixtures/`.
