# m1_data contract (STUB by architect; the builder keeps it current)

- Layer: L0 data and content
- Schema versions used: gold.v1, transcript.v1, manifest.v1
- Inputs: Fetched public sources (cited), the negation table `.claude/skills/kannada-nlp/negation_table.yaml`.
- Outputs: data/lexicon/drugs.csv; data/templates/*.yaml; data/gold/*.json (gold.v1); gold transcripts (transcript.v1, model=gold); data/manifest.jsonl (manifest.v1); data/splits/{dev,test}.txt; data/splits/test.lock (format: `<sha256>  <path>` per line, see infra/scripts/check_split_lock.py); minimal-pair twins file.
- May write ONLY: m1_data/, data/, results/m1_data/, docs/annotation_guide.md, and `m1_data/handoff/*` for shared docs.
- May read: contracts/, fixtures/, data/ (read-only unless this is m1), results/<other module>/.
- May import: `contracts.validate` only. Never another module's code.
- MOCK MODE: `MODE=mock make m1-mock` runs purely on fixtures/.
- Every produced artifact is validated with
  `uv run python -m contracts.validate <schema> <path>` in this module's tests.
