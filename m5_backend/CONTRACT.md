# m5_backend contract

- Layer: L5 access control + audit (PostgreSQL 16 forced RLS).
- Schema versions used: record.v1 and verdict.v1 (inputs, validated with `contracts.validate`
  on every write/save), access_case.v1 (output; every generated case is validated).
- Inputs:
  - `POST /records`, `PATCH /records/{id}`: a record.v1 document with status draft|flagged.
  - `POST /records/{id}/verify` (body `{}`): the SERVER runs its verifier on the stored record and
    stores the verdict.v1 (table `clinic.verdicts`). Returns `verdict_id`, `record_hash`, `verdict`,
    `unresolved` (list of `{check_id, field_path}`).
  - `POST /records/{id}/save` (CHANGED 2026-11-10, D-80 / F1): body
    `{"verdict_id": uuid, "resolutions": [{"check_id": "C1".."C8", "field_path": "/...",
    "action": "confirmed"|"edited"}]}`. NO verdict content, NO resolver field (extra fields -> 422).
    Physician only; resolver = token user. 200 `{id, status: "saved", resolved: n}`. 409: missing
    resolution / stale verdict / empty or unacceptable verdict / edited record not re-verified or new
    flags; 422: unknown or duplicate resolution, bad body; 403 non-physician; 404 other facility.
    The DB CHECK `saved_requires_approval` and the trigger `records_saved_gate` also apply.
  - `GET /verdicts/{id}`: a stored verdict (visible when its record is).
  - `POST /records/{id}/verify` (CHANGED, Phase C fix a): one verdict per record CONTENT. A second
    verify of identical content returns the existing verdict (same `verdict_id`, no new row), so
    it cannot make an earlier verdict stale; changed content gets a new verdict and the old one is
    refused at /save (409). DB: unique index `verdicts_one_per_content (record_id, record_hash)`.
  - `GET /records/{id}/review` (NEW, Phase C fix b): read-only reopen of ANY visible record
    (also saved): `{record_id, status, approved_by, approved_at, verdict_id, record_hash, verdict,
    unresolved, resolutions}`. `verdict` is null when the current content was never verified.
    `resolutions` is filled for physicians only (only they hold SELECT on resolutions). Never runs
    the verifier, never writes. Same RLS as GET /records/{id} (other facility / hidden -> 404).
- Outputs:
  - FastAPI app bound to 127.0.0.1 (`m5_backend.app.main:create_app`). Endpoints:
    `POST /auth/token` (sandbox mock issuer), `GET|POST /households`, `GET|POST /patients`,
    `GET|PATCH /patients/{id}`, `POST /encounters`, `GET|PATCH /encounters/{id}`,
    `GET /encounters/{id}/audio`, `GET /records` (list), `GET /records/{id}/transcript`, `POST /records`, `GET|PATCH /records/{id}`,
    `POST /records/{id}/verify`, `POST /records/{id}/save`, `GET /verdicts/{id}`, `POST /medication-orders`,
    `GET|PATCH /medication-orders/{id}`, `POST /pharmacist/active-patient`,
    `GET /pharmacist/orders`, `GET /research/encounters`. Errors are `{"error": "<generic>"}`.
  - SQL migrations `m5_backend/sql/*.sql`.
  - `results/m5_backend/access_cases.jsonl` (access_case.v1, one per line),
    `access_matrix_results.jsonl` (each line: `{"case": <access_case.v1>, "layer", "observed",
    "outcome", "detail"}`), `access_matrix_summary.json`.
- Writes ONLY: m5_backend/, results/m5_backend/, .env (local, git-ignored), .env.example
  (placeholder keys only).
- Imports: `contracts.validate` only. Verifier hook: `create_app(..., verifier=fn)` with
  `fn(record_json, *, encounter_id, transcript) -> verdict.v1 dict` (CHANGED, Phase C fix c;
  m5 loads both from the DATABASE encounter; transcript is None if missing; legacy one-argument
  `fn(record_json)` still works because m5 only passes the keywords the function accepts).
  Integration passes the m4 adapter; default = manual review.
- Contract request (not applied; contracts/ is not ours): access_case.v1 `attack` has no `save_gate`
  value, so the save-gate cases use `mass_assignment` / `id_guess`.
- Env (changed, F7): `POSTGRES_USER=mm_bootstrap` for Docker; `OWNER_DB_PASSWORD` for owner_role.
- m6_ui must change: stop sending `{"verdict": ...}` to `/save`; call `/verify`, show `unresolved`,
  send `{verdict_id, resolutions}`.
- MOCK MODE: `MODE=mock mingw32-make m5-mock` needs no database (case generation +
  validation, JWT / model / pseudonym tests).
- Token claims (for m6_ui): HS256, `iss`, `aud`, `sub` (user uuid), `role`
  (asha|nurse|physician|pharmacist|researcher), `fid` (facility uuid), `iat`, `exp` (<= 900 s),
  `jti`. Send `Authorization: Bearer <token>`.
