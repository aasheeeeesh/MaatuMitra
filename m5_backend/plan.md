# m5_backend plan (backend-security-engineer, 2026-11-09)

Written BEFORE tests and code. Goal: "nobody can open a record they should not" is
true IN THE DATABASE (Postgres 16 forced row-level security), and an automated matrix
(E5, >= 500 access_case.v1 cases) proves it. All data is synthetic.

## 0. Postgres without Docker (this laptop)

- Checked `pgserver` 0.1.4 (PyPI): bundles PostgreSQL **16.2** (README badge and
  pgbuild/Makefile), Apache-2.0, has a win_amd64 wheel. Rejected: 16.2 predates the fix for
  CVE-2024-10976 (row security + role changes; fixed in 16.5), which hits exactly our
  `SET LOCAL ROLE` + RLS design.
- Chosen: EnterpriseDB "binaries from installer" zip, PostgreSQL **16.15**, Windows x86-64,
  PostgreSQL License. Only `bin/`, `lib/`, `share/` unpacked to
  `%USERPROFILE%/.maatumitra/pg16/pgsql` (101 MB). Data dir `%USERPROFILE%/.maatumitra/pgdata16`.
  Both outside the repo. Port 54329, `listen_addresses=127.0.0.1`, scram-sha-256 auth.
- `m5_backend/scripts/db_up.sh` / `db_down.sh` reproduce this. Tests that need a DB skip
  with a clear message when none is reachable. CI uses a `postgres:16` service.

## 1. Roles (interpretation recorded as a decision)

| role | login | what it is for |
|---|---|---|
| bootstrap superuser (`PG_BOOTSTRAP_USER`) | yes | only creates roles + databases (db_up, test fixture). Never used by requests. |
| `owner_role` | yes | owns schemas/tables, runs migrations. Never used by requests. FORCE RLS binds it too: with no policy it sees 0 rows. |
| `api_login` | yes, NOINHERIT | the API logs in as this. No table privileges of its own. Member of the 5 app roles WITH INHERIT FALSE, SET TRUE. Switches only via `SET LOCAL ROLE` inside one transaction. |
| `asha_role` `nurse_role` `physician_role` `pharmacist_role` `researcher_role` | no | app roles; privileges + policies. |
| `maint_role` | no | seed loader + research export job; reached only from `owner_role` (operator credentials), never from `api_login`. |
| `pharm_view_owner` | no | owns `pharmacist_orders_v`; has one narrow policy (the pharmacist predicate). |
| `audit_writer` | no | owns the SECURITY DEFINER function `app.audit_write(...)`; the only role with INSERT on audit_log. |

None is SUPERUSER or BYPASSRLS (asserted by a test). Brief says `api_login` NOLOGIN; it must log in,
so it is LOGIN with no table privileges (decision entry).

## 2. Schema (schemas `clinic`, `research`, `app`; UUID keys, gen_random_uuid())

clinic.facilities, users(id, role, facility_id), households(id, facility_id, assigned_asha_id),
patients(id, household_id, facility_id, name_synthetic, age_band, sex),
encounters(id, patient_id, author_id, facility_id, encounter_type, created_at),
records(id, encounter_id, json, status, approved_by, approved_at) with
`CHECK (status <> 'saved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))`,
medication_orders(...brief columns...), consents(patient_id, research_ok, updated_at),
audit_log(id, at, user_id, app_role, action, table_name, row_id, outcome) (enums only, no free text).
research.encounters_deid (pseudonym, age_band, sex, encounter_type, encounter_month,
record_status, symptoms_present[], symptoms_absent[], medications jsonb (structured only)).

Every table: ENABLE + FORCE ROW LEVEL SECURITY; no policy = deny; one policy per role and action.

## 3. Rules (from the brief; the hand-written matrix encodes the same rules independently)

- ASHA: SELECT/INSERT households where assigned_asha_id = me; patients/encounters/records reachable
  through those households. No UPDATE/DELETE. No orders, consents, audit, research.
- Nurse: SELECT/INSERT/UPDATE patients, encounters, draft records (status draft|flagged) in her
  facility; SELECT medication_orders in her facility.
- Physician: nurse rights (records of any status) + INSERT/UPDATE medication_orders + approve/save
  records (approved_by = me), her facility.
- Pharmacist: no table grants; SELECT on security_barrier view `clinic.pharmacist_orders_v`:
  facility = mine AND status = 'ready_to_dispense' AND patient_id = app.active_patient_id. The API
  sets the active patient only via POST /pharmacist/active-patient (checks an order exists, audits).
- Researcher: no base-table grants; SELECT on schema research only.
- Nobody: DELETE anywhere, UPDATE/DELETE/TRUNCATE audit_log (REVOKE + trigger), facilities, users, consents.
- Per request: one transaction, `SET LOCAL ROLE`, `set_config('app.user_id'|'app.facility_id'|'app.role', v, true)`.

## 4. API (FastAPI, 127.0.0.1)

PyJWT HS256 mock issuer (POST /auth/token, rate-limited), algorithms pinned, exp/iss/aud verified,
sub+role+fid required, role ONLY from the verified token. pydantic `extra="forbid"`. Parameterised
SQL only (psycopg). Generic errors, no stack traces. Rows hidden by RLS -> 404 (no existence oracle).
Audio: GET /encounters/{id}/audio only after the encounter is visible to the caller under RLS.
Saved gate: POST /records/{id}/save needs a verdict.v1 with no 'flag' check and auto_acceptable=true.

## 5. Matrix (E5)

1. Write `tests/access_matrix_expected.yaml` BY HAND first (before any policy SQL).
2. Generator: 5 roles x 12 resources x 4 actions x 4 ownerships = 960 base cases + attacks
   (id_guess, tampered_jwt, expired_jwt, alg_none, wrong_aud, sqli in every text param,
   mass_assignment, idor_audio, guc_tamper incl. SET app.user_id / RESET ROLE). Each case is
   validated as access_case.v1.
3. Runner: base cases at DB level through the SAME `request_tx` used by the API (rolled back);
   audio + attacks through the API (FastAPI TestClient, real DB).
4. Output `results/m5_backend/access_matrix_results.jsonl` + summary
   "unauthorized successes: X of N; upper bound 3/N" and unexpected denials (availability bugs).
5. Residual limit: raw DB credentials of api_login can SET ROLE to any app role and set GUCs
   (demonstrated by a separate test, not counted as a matrix pass).

## 6. Tests first (order)

no-DB: JWT (none/tampered/expired/wrong aud/iss, missing claims), pydantic forbid, rate limiter,
matrix generation + schema validation, pseudonym function. DB: role attributes, RLS flags on every
table, owner sees 0 rows, audit append-only (update/delete/truncate fail), saved CHECK, pharmacist
flow, research export de-identification + consent withdrawal, no GUC leak across transactions,
API end-to-end, full matrix.

## 7. Mock mode

`MODE=mock mingw32-make m5-mock`: generate + validate cases, run the no-DB auth attack checks,
write results/m5_backend/access_cases.jsonl. No Postgres needed.
