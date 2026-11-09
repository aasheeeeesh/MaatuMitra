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
to the bootstrap superuser values (`PG_BOOTSTRAP_USER`/`PG_BOOTSTRAP_PASSWORD`), **not** to
`owner_role`, then `uv run python -m m5_backend.scripts.dbtool all`.

## Design in one page

| piece | where |
|---|---|
| roles (bootstrap superuser only creates roles/DBs; `owner_role` owns; `api_login` LOGIN, NOINHERIT, no privileges, member of 5 app roles WITH SET only) | scripts/dbtool.py |
| schema, UUID keys, composite FKs keep facility consistent, saved CHECK | sql/010_schema.sql |
| ENABLE + FORCE RLS on all 10 tables, grants, one policy per role/action | sql/020_rls.sql |
| pharmacist `security_barrier` view owned by `pharm_view_owner` | sql/030_views.sql |
| append-only audit log (SECURITY DEFINER writer, REVOKE, triggers) | sql/040_audit.sql |
| one transaction per request: `SET LOCAL ROLE` + `set_config(..., true)` | app/db.py |
| PyJWT HS256 mock issuer + verifier | app/auth.py |
| FastAPI app, generic errors, rate-limited login, audio after authorisation | app/main.py |
| pydantic `extra="forbid"` bodies | app/models.py |
| research export (HMAC pseudonym, month dates, consent filter, allowlist) | app/export.py |
| hand-written expected table | tests/access_matrix_expected.yaml |
| case generator / runner | matrix/generate.py, matrix/run.py |

## Result (2026-11-10, local PostgreSQL 16.15)

`unauthorized successes: 0 of 1385 deny-expected cases (1486 cases total); 95% upper bound
(rule of three) 3/1385 = 0.0022`. Unexpected denials (availability bugs): 0. Integrity
failures: 0. `uv run pytest m5_backend/tests`: 116 passed.

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
