# m6_ui contract (STUB by architect; the builder keeps it current)

- Layer: L4 human review + L6 UI (Streamlit)
- Schema versions used: transcript.v1, record.v1, verdict.v1, card.v1 (in)
- Inputs: transcript.v1, record.v1, verdict.v1, card.v1; m5 API (mock in MODE=mock).
- Outputs: Streamlit app bound to 127.0.0.1; i18n/kn.json, i18n/en.json; AppTest tests.
- May write ONLY: m6_ui/, results/m6_ui/, and `m6_ui/handoff/*` for shared docs.
- May read: contracts/, fixtures/, data/ (read-only unless this is m1), results/<other module>/.
- May import: `contracts.validate` only. Never another module's code.
- MOCK MODE: `MODE=mock make m6-mock` runs purely on fixtures/.
- Every produced artifact is validated with
  `uv run python -m contracts.validate <schema> <path>` in this module's tests.
