---
name: secure-backend
description: Database-enforced access control for MaatuMitra (Postgres 16 forced RLS per role, SET LOCAL ROLE + GUCs, JWT pitfalls, audit log, pharmacist view, de-identified research export, OWASP Top-10 checklist, access matrix E5). Use when building or auditing m5_backend or anything that touches auth, SQL, secrets or the API.
---

# Secure backend (PROJECT_BRIEF AGENT 6 design + pitfalls)

The goal: "nobody can open a record they should not" must be true IN THE DATABASE,
and proven by an automated matrix (E5). All data is synthetic. Bind everything to
127.0.0.1. Secrets only in `.env` (git-ignored); `.env.example` has placeholders.

## 1. Roles and RLS (follow exactly; deviations need a decision entry)

- `owner_role`: runs migrations, owns tables. NEVER used for requests (owners bypass RLS
  unless FORCE is set; even with FORCE, keep requests off it).
- `api_login`: the only LOGIN role the API uses; gets app privileges only via
  `SET LOCAL ROLE <app_role>`.
- NOLOGIN app roles: `asha_role`, `nurse_role`, `physician_role`, `pharmacist_role`,
  `researcher_role`. None is SUPERUSER or has BYPASSRLS. Check with
  `SELECT rolname, rolsuper, rolbypassrls FROM pg_roles;`.
- Every table: `ALTER TABLE t ENABLE ROW LEVEL SECURITY; ALTER TABLE t FORCE ROW LEVEL SECURITY;`
  then default deny, then one explicit policy per role and action. Verify with
  `SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relkind='r' ...`.
- UUID primary keys (`gen_random_uuid()`), never sequential ids (id guessing).

## 2. Per-request context (one transaction per request)

```sql
BEGIN;
SET LOCAL ROLE nurse_role;
SELECT set_config('app.user_id', $1, true);      -- true = transaction-local
SELECT set_config('app.facility_id', $2, true);
-- ... queries ...
COMMIT;
```
Policies read `current_setting('app.user_id', true)`. Use SET LOCAL / is_local=true only;
session-level SET leaks through connection pools. Values come from the VERIFIED token,
never from the request body.

## 3. Role rules (summary of AGENT 6)

- ASHA: select/insert only on households where `assigned_asha_id` = her id, and rows
  reachable through those households.
- Nurse: select/insert/update patients, encounters, draft records in her facility;
  read-only medication_orders.
- Physician: nurse rights + insert/update medication_orders + approve records (her facility).
- Pharmacist: NO table grants. SELECT only on `pharmacist_orders_v` (security_barrier),
  rows where facility matches, status = 'ready_to_dispense' AND patient_id =
  `app.active_patient_id`, which the API sets only after checking an order exists, with
  an audit row. Limit: cannot prove the patient is physically present.
- Researcher: NO base-table grants. SELECT only on schema `research`, filled by an export
  job: pseudonym = truncated HMAC-SHA256(key from .env, patient_id), age_band,
  encounter_type, structured fields, NO free text, NO names, dates coarsened to month,
  only `consents.research_ok = true` at export time; withdrawal removes them next export.
- Saved gate: `CHECK (status <> 'saved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))`,
  and the API refuses to save a record whose verdict.v1 has unresolved flags.
  (record.v1 itself has no approver field; the gate lives here.)
- audit_log: INSERT-only for the API; REVOKE UPDATE, DELETE, TRUNCATE; trigger raising on
  UPDATE/DELETE; log user, role, action, table, row id, outcome, time. Never free text.

## 4. Pitfalls checklist

- [ ] FORCE RLS on every table (ENABLE alone does not bind the owner).
- [ ] No request path uses a superuser, the table owner, or a BYPASSRLS role.
- [ ] `SET LOCAL` / `set_config(..., true)` only; test that a second transaction on the same
      connection sees no leftover role/GUC.
- [ ] GUC tampering: a client that can run SQL can `SET app.user_id`. Only the API runs SQL;
      DB credentials stay out of reach (residual risk; state it).
- [ ] `RESET ROLE` / `SET ROLE` attempts from user input are impossible (parameterised SQL only).
- [ ] Views: `security_barrier`; check `security_invoker` semantics on PG16 for every view.
- [ ] SECURITY DEFINER functions: pinned `search_path`, minimal, audited.
- [ ] JWT: `jwt.decode(token, key, algorithms=["HS256"], audience=..., issuer=...,
      options={"require": ["exp", "iss", "aud", "sub", "role"]})`; reject `alg: none`,
      wrong aud/iss, expired; short expiry; role ONLY from the verified token.
- [ ] pydantic models with `model_config = ConfigDict(extra="forbid")` (blocks mass assignment
      of `role`, `assigned_asha_id`, `approved_by`).
- [ ] Generic error messages; no stack traces to clients; rate-limit login.
- [ ] Audio served only after an authorisation check on its encounter (IDOR).
- [ ] No PII or free text in logs.

## 5. OWASP Top-10 (2021 names) quick map

A01 Broken access control -> RLS + matrix. A02 Cryptographic failures -> HMAC key in .env,
no secrets in repo, TLS not needed on 127.0.0.1 (state it). A03 Injection -> parameterised
SQL, sqli strings in every text parameter of the matrix. A04 Insecure design -> fail-closed
gate. A05 Misconfiguration -> 127.0.0.1 binds, no default passwords. A06 Vulnerable
components -> pip-audit in CI. A07 Auth failures -> JWT checks above. A08 Integrity ->
uv.lock pinned, pinned image digest. A09 Logging failures -> append-only audit_log.
A10 SSRF -> the API fetches no user-supplied URLs.

## 6. Access matrix (E5)

- `m5_backend/tests/access_matrix_expected.yaml` is written BY HAND from the rules above,
  never generated from the SQL policies (that would be circular).
- Cases = 5 roles x resources x actions x ownership (>= 500) + attacks (id_guess,
  tampered_jwt, expired_jwt, alg_none, wrong_aud, sqli, mass_assignment, idor_audio,
  guc_tamper). Each case validates as access_case.v1. Auth/GUC attacks always expect deny.
- Report: "unauthorized successes: 0 of N; 95% upper bound 3/N (rule of three)".

## 7. De-identification test

Scan every row of the research export for every original patient id, name, household id,
user id and every free-text token from records; expect zero hits. Withdraw a consent,
re-export, confirm the pseudonym is gone.
