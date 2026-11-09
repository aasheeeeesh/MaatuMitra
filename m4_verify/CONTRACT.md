# m4_verify contract (STUB by architect; the builder keeps it current)

- Layer: L3 safety verifier (plain code, fail-closed)
- Schema versions used: record.v1 + transcript.v1 (in), verdict.v1 (out)
- Inputs: record.v1 + its transcript.v1; lexicon. Its OWN negation rules (must not import m3 code or the m3 table logic).
- Outputs: results/m4_verify/ verdicts (verdict.v1); per-check table; planted-mistake logs (E4); m4_verify/negation_audit.md.
- May write ONLY: m4_verify/, results/m4_verify/, and `m4_verify/handoff/*` for shared docs.
- May read: contracts/, fixtures/, data/ (read-only unless this is m1), results/<other module>/.
- May import: `contracts.validate` only. Never another module's code.
- MOCK MODE: `MODE=mock make m4-mock` runs purely on fixtures/.
- Every produced artifact is validated with
  `uv run python -m contracts.validate <schema> <path>` in this module's tests.
