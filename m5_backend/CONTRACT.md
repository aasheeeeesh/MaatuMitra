# m5_backend contract

- Layer: L5 access control + audit (PostgreSQL 16 forced RLS).
- Schema versions used: record.v1 and verdict.v1 (inputs, validated with `contracts.validate`
  on every write/save), access_case.v1 (output; every generated case is validated).
- Inputs:
  - `POST /records`, `PATCH /records/{id}`: a record.v1 document with status draft|flagged.
  - `POST /records/{id}/save`: a verdict.v1 document. Refused (409) if any check has status
    `flag`, if `auto_acceptable` is false, or if checks is empty; 422 if its `record_id`
    differs from the stored record's `record_id`. The DB CHECK `saved_requires_approval`
    also requires approved_by + approved_at for status 'saved'.
- Outputs:
  - FastAPI app bound to 127.0.0.1 (`m5_backend.app.main:create_app`). Endpoints:
    `POST /auth/token` (sandbox mock issuer), `GET|POST /households`, `GET|POST /patients`,
    `GET|PATCH /patients/{id}`, `POST /encounters`, `GET|PATCH /encounters/{id}`,
    `GET /encounters/{id}/audio`, `POST /records`, `GET|PATCH /records/{id}`,
    `POST /records/{id}/approve`, `POST /records/{id}/save`, `POST /medication-orders`,
    `GET|PATCH /medication-orders/{id}`, `POST /pharmacist/active-patient`,
    `GET /pharmacist/orders`, `GET /research/encounters`. Errors are `{"error": "<generic>"}`.
  - SQL migrations `m5_backend/sql/*.sql`.
  - `results/m5_backend/access_cases.jsonl` (access_case.v1, one per line),
    `access_matrix_results.jsonl` (each line: `{"case": <access_case.v1>, "layer", "observed",
    "outcome", "detail"}`), `access_matrix_summary.json`.
- Writes ONLY: m5_backend/, results/m5_backend/, .env (local, git-ignored), .env.example
  (placeholder keys only).
- Imports: `contracts.validate` only.
- MOCK MODE: `MODE=mock mingw32-make m5-mock` needs no database (case generation +
  validation, JWT / model / pseudonym tests).
- Token claims (for m6_ui): HS256, `iss`, `aud`, `sub` (user uuid), `role`
  (asha|nurse|physician|pharmacist|researcher), `fid` (facility uuid), `iat`, `exp` (<= 900 s),
  `jti`. Send `Authorization: Bearer <token>`.
