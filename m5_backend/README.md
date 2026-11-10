# m5_backend: access control + audit (layer L5)

Goal: "nobody can open a record they should not" is enforced **inside PostgreSQL 16** with
forced row-level security (RLS), and an automated matrix (E5) checks it. All data is SYNTHETIC.
Built by the `backend-security-engineer` agent (AI); see handoff/ai_usage.md for what a human
must still check.

## Run it

```bash
# Git Bash, repo root. One-time: copy .env.example to .env and fill every REPLACE_ME value
# (uv run python -c "import secrets; print(secrets.token_hex(32))").
mingw32-make m5-mock      # NO database: generate + validate 1486 access_case.v1 cases, no-DB tests
mingw32-make m5-db-up     # local Postgres 16 on 127.0.0.1:54329 + roles + migrations + seed + export
mingw32-make m5-test      # all tests (DB tests skip with a message if Postgres is not reachable)
mingw32-make m5-matrix    # E5 matrix -> results/m5_backend/access_matrix_{results.jsonl,summary.json}
mingw32-make m5-db-down
uv run python -m m5_backend.app.main   # API on 127.0.0.1:8000 (refuses any other host)
```

### PostgreSQL without Docker (this laptop)

EnterpriseDB "binaries from installer" zip, PostgreSQL **16.15** for Windows x86-64
(`https://get.enterprisedb.com/postgresql/postgresql-16.15-5-windows-x64-binaries.zip`,
373,254,386 bytes, sha256 `43bb45f1...0ccaa8281`, PostgreSQL License). Only `pgsql/bin`,
`pgsql/lib`, `pgsql/share` are unpacked, to `%USERPROFILE%/.maatumitra/pg16` (126 MB).
Data dir `%USERPROFILE%/.maatumitra/pgdata16`. Both are outside the repo. `.env` sets
`PG_BIN` and `PGDATA_DIR`. `pgserver` (PyPI) was rejected: it ships PostgreSQL 16.2, which
predates the fix for CVE-2024-10976 (row security + role changes).

Docker users: `docker-compose.yml` (127.0.0.1 only). Set `POSTGRES_USER`/`POSTGRES_PASSWORD`
to the bootstrap superuser values (`PG_BOOTSTRAP_USER`/`PG_BOOTSTRAP_PASSWORD`, `.env.example`
uses `mm_bootstrap`), **not** to `owner_role`. `owner_role` has its own password,
`OWNER_DB_PASSWORD` (F7). Then `uv run python -m m5_backend.scripts.dbtool all`. The Docker path
is UNVERIFIED (never run on this laptop).

## Design in one page

| piece | where |
|---|---|
| roles (bootstrap superuser only creates roles/DBs; `owner_role` owns; `api_login` LOGIN, NOINHERIT, no privileges, member of 5 app roles WITH SET only) | scripts/dbtool.py |
| schema, UUID keys, composite FKs keep facility consistent, saved CHECK | sql/010_schema.sql |
| ENABLE + FORCE RLS on all 13 tables, grants, one policy per role/action | sql/020_rls.sql |
| pharmacist `security_barrier` view owned by `pharm_view_owner` | sql/030_views.sql |
| append-only audit log (SECURITY DEFINER writer; role from the session role, F2; REVOKE, triggers) | sql/040_audit.sql |
| saved-record gate in the DB (trigger), append-only `verdicts` + `record_resolutions`, consent-withdrawal trigger | sql/050_gate.sql |
| server-stored verdicts, `/verify`, `/save` with per-flag resolutions, pluggable verifier | app/main.py, app/verifier.py |
| one transaction per request: `SET LOCAL ROLE` + `set_config(..., true)`; pool runs `DISCARD ALL` on return (F5); startup refuses a superuser / BYPASSRLS / owner login (F6) | app/db.py |
| PyJWT HS256 mock issuer + verifier | app/auth.py |
| FastAPI app, generic errors, rate-limited login, audio after authorisation | app/main.py |
| pydantic `extra="forbid"` bodies | app/models.py |
| research export (HMAC pseudonym, month dates, consent filter, allowlist, k >= 5 small-cell suppression) | app/export.py |
| hand-written expected table | tests/access_matrix_expected.yaml |
| case generator / runner | matrix/generate.py, matrix/run.py |

## Saving a record (D-80 / F1): the server owns the verdict

1. `POST /records/{id}/verify` (body `{}`; asha, nurse or physician). The SERVER loads the stored
   record, runs its verifier, validates the result as verdict.v1 and stores it (append-only
   `clinic.verdicts`, bound to a database-computed hash of the record content). Response:
   `{verdict_id, record_id, record_hash, verdict, unresolved: [{check_id, field_path}]}`.
2. `POST /records/{id}/save` (physician only) with
   `{"verdict_id": "<uuid>", "resolutions": [{"check_id": "C3", "field_path": "/advice/0/negated", "action": "confirmed"|"edited"}]}`.
   No verdict content and no "by" field are accepted (422). The server saves only if every flag
   of the stored verdict has exactly one resolution (409 missing, 422 unknown/duplicate), the
   verdict is not stale (409), and for `edited` the record was really changed, re-verified, and the
   NEW verdict has no flag the physician did not confirm. Resolutions, status, `approved_by`,
   `approved_at` and audit rows commit in one transaction. The trigger `records_saved_gate`
   repeats the core rule inside the database, so direct SQL cannot skip it either.
3. Verifier: m5 never imports m4. `create_app(..., verifier=fn)` takes `fn(record_json) ->
   verdict dict` (integration wires m4 here). The built-in default flags the whole record
   (`manual_review_verifier`), so a physician must confirm explicitly. It is NOT a safety check.

## Result (2026-11-10, local PostgreSQL 16.15, after the fix pass)

`unauthorized successes: 0 of 1398 deny-expected cases (1499 cases total); 95% upper bound
(rule of three) 3/1398 = 0.0021`. Unexpected denials (availability bugs): 0. Integrity
failures: 0. `uv run pytest m5_backend/tests`: 146 passed with the DB up. 13 new save-gate cases
(forged verdict, unknown / duplicate / missing resolution, resolver named in the body, stale
verdict, other-facility record, non-physician resolver, wrong verdict id) are in the matrix; the
tests no longer rewrite tracked result files (`make m5-matrix` does).

## Limits (read these)

- **Raw DB credentials defeat the GUC model.** Anyone holding the `api_login` password can
  `SET ROLE` to any app role and set `app.user_id`/`app.facility_id` to anything
  (demonstrated by `test_residual_raw_api_credentials_can_set_gucs`). Only the API process
  may hold it (`.env`, git-ignored, 127.0.0.1). Owner and bootstrap credentials likewise.
- The pharmacist "active patient" cannot prove the patient is physically present; it only
  narrows scope to one patient with a ready order at her facility, and every attempt is audited.
- The superuser can disable the audit triggers; the owner can re-grant itself privileges.
- The mock issuer (`POST /auth/token`, shared sandbox password) is NOT real authentication.
- The matrix covers the rules we wrote down; a rule nobody thought of is not tested.
- **Audit role (F2)**: the audit function takes the role from the session role, and the user id must
  exist with that role. A session holding raw `api_login` credentials can still `SET ROLE` to any app
  role, so this stops cheap forgery, not a full-SQL attacker.
- **Verdicts are only as good as the verifier.** A physician with raw SQL could insert a forged
  verdict (RLS lets her insert verdicts for her own facility). The API never does this; same raw-credential limit.
- **Small cells (F3)**: cells = age band x sex x month x encounter type with fewer than 5 patients are
  dropped. With the tiny synthetic seed only the 5-patient cohort C1..C5 survives (the three other
  consenting patients are suppressed). This is not a proof of anonymity: symptoms and medicines are
  not part of the cell, and the pseudonym links one patient's visits.
- **Research map (F4)**: `research.pseudonym_map` (patient id to pseudonym) lets a consent withdrawal
  delete rows at once. Only `maint_role` (operator) reads it; the researcher cannot.
- **Catalog / EXPLAIN leak (F8, accepted)**: any app role can read `pg_class.reltuples`, `pg_stat_*` and
  `EXPLAIN ANALYZE` shows "Rows Removed by Filter" for the pharmacist view, i.e. row counts of tables
  it cannot read. It needs raw SQL (the API never runs EXPLAIN). Not fixed.
