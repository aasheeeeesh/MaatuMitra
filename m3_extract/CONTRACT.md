# m3_extract contract (STUB by architect; the builder keeps it current)

- Layer: L2 structuring (rules = main, local LLM = comparison)
- Schema versions used: transcript.v1 (in), record.v1 (out), gold.v1 (scoring)
- Inputs: transcript.v1 (gold or ASR); data/lexicon/drugs.csv (fixture: fixtures/lexicon/drugs_fixture.csv); `.claude/skills/kannada-nlp/negation_table.yaml`.
- Outputs: results/m3_extract/<pipeline>/*.json (record.v1); field-level accuracy tables.
- May write ONLY: m3_extract/, results/m3_extract/, and `m3_extract/handoff/*` for shared docs.
- May read: contracts/, fixtures/, data/ (read-only unless this is m1), results/<other module>/.
- May import: `contracts.validate` only. Never another module's code.
- MOCK MODE: `MODE=mock make m3-mock` runs purely on fixtures/.
- Every produced artifact is validated with
  `uv run python -m contracts.validate <schema> <path>` in this module's tests.
