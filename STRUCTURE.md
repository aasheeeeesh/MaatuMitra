# Repository structure (STUB)

Generated in full in Phase D (full tree + one plain sentence per folder and key file,
with its layer L0-L7). Current top level:

| path | what it is | layer |
|---|---|---|
| contracts/ | JSON Schemas + validator shared by all modules | all |
| fixtures/ | hand-made example files per contract (valid and invalid) | all |
| m1_data/ | data, lexicon, templates, generator, splits | L0 |
| m2_asr/ | speech recognition adapters and benchmarking | L1 |
| m3_extract/ | transcript -> record (rules main, local LLM comparison) | L2 |
| m4_verify/ | fail-closed safety verifier C1..C8 | L3 |
| m6_ui/ | Streamlit review app | L4, L6 |
| m8_helper/ | counselling helper over approved cards | L4b |
| m5_backend/ | Postgres RLS, API, audit, access matrix | L5 |
| m7_eval/ | metrics, experiments, reports | L7 |
| data/ | generated data (large audio git-ignored) | L0 |
| docs/ | decisions, severity, metrics, hypothesis, glossary, licences | L7 |
| integration/ | boundary and end-to-end tests | all |
| reviews/ | simulated reviews and human review sheets | L7 |
| results/ | raw outputs, tables, plots, test access log | L7 |
| infra/ | inventory, cost report, helper scripts | L7 |
| notebooks/ | executed experiment notebooks | L1, L7 |
| tests/ | repo-level tests | all |
| .claude/ | 14 subagents and 5 skills | - |
| .github/workflows/ | CI | - |
