# m2_asr contract (STUB by architect; the builder keeps it current)

- Layer: L1 speech (ASR)
- Schema versions used: manifest.v1 (in), transcript.v1 (out)
- Inputs: data/manifest.jsonl (manifest.v1) + audio files; gold transcripts for scoring.
- Outputs: results/m2_asr/<model>/*.jsonl (one transcript.v1 per line); results/m2_asr/summary.csv; results/m2_asr/common_subset.txt; executed notebooks in notebooks/.
- May write ONLY: m2_asr/, notebooks/m2_*, results/m2_asr/, infra/inventory.md (append a compute section), and `m2_asr/handoff/*` for shared docs.
- May read: contracts/, fixtures/, data/ (read-only unless this is m1), results/<other module>/.
- May import: `contracts.validate` only. Never another module's code.
- MOCK MODE: `MODE=mock make m2-mock` runs purely on fixtures/.
- Every produced artifact is validated with
  `uv run python -m contracts.validate <schema> <path>` in this module's tests.
