# m5_backend contract (STUB by architect; the builder keeps it current)

- Layer: L5 access control + audit (Postgres RLS)
- Schema versions used: record.v1, verdict.v1 (in), access_case.v1 (out)
- Inputs: record.v1, verdict.v1 (to enforce the saved-record gate).
- Outputs: FastAPI app bound to 127.0.0.1; SQL migrations; access matrix cases (access_case.v1) and results in results/m5_backend/.
- May write ONLY: m5_backend/, results/m5_backend/, docker-compose.yml, .env.example (placeholders only), and `m5_backend/handoff/*` for shared docs.
- May read: contracts/, fixtures/, data/ (read-only unless this is m1), results/<other module>/.
- May import: `contracts.validate` only. Never another module's code.
- MOCK MODE: `MODE=mock make m5-mock` runs purely on fixtures/.
- Every produced artifact is validated with
  `uv run python -m contracts.validate <schema> <path>` in this module's tests.
