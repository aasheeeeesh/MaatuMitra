### D-?: PostgreSQL 16 without Docker: EnterpriseDB 16.15 binaries zip   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: How to get a real PostgreSQL 16 on a laptop with no Docker and no admin rights (follows D-4).
- Options we considered:
  1. `pgserver` from PyPI (pip-installable Postgres). Pro: one `uv add`. Con: it ships PostgreSQL **16.2** (README badge and its pgbuild/Makefile, fetched 2026-11-09). 16.2 is older than the fix for CVE-2024-10976 ("row security below e.g. subqueries disregards user ID changes", fixed in 16.5, postgresql.org page fetched 2026-11-09). That bug is about exactly our design (RLS + switching roles), so it is a bad fit.
  2. EnterpriseDB "binaries from installer" zip, PostgreSQL 16.15. Pro: current patch release, no installer, no admin. Con: 373 MB download.
  3. Install Docker Desktop. Con: admin rights, big disk use; the human must do it.
- What we chose: Option 2.
- Why: newest 16.x patch level, works without admin, the PostgreSQL License allows this use. We keep only the server parts to save disk (12 GB free).
- What we actually did: downloaded `https://get.enterprisedb.com/postgresql/postgresql-16.15-5-windows-x64-binaries.zip` (link found on https://www.enterprisedb.com/download-postgresql-binaries, fetched 2026-11-09; 373,254,386 bytes; sha256 `43bb45f173a6f08cf1d29a97a6d8deb119e8e8093a24c00d2d1001a0ccaa8281`, same hash on two downloads). Unpacked `pgsql/bin`, `pgsql/lib`, `pgsql/share` to `%USERPROFILE%/.maatumitra/pg16` (126 MB), deleted the zip. Data dir `%USERPROFILE%/.maatumitra/pgdata16`. `m5_backend/scripts/db_up.sh` runs initdb (scram-sha-256 passwords, superuser name from .env) and starts the server with `listen_addresses=127.0.0.1`, port 54329 (checked with `netstat`: `127.0.0.1:54329 LISTENING` only). `db_down.sh` stops it.
- What could go wrong / weaknesses: EDB does not publish a checksum next to the link, so the sha256 only proves both downloads were identical, not that the file is authentic (UNVERIFIED). The zip also contains pgAdmin/StackBuilder, which we did not unpack or use. Windows only; Linux/CI uses the postgres:16 Docker image instead.
- What else could be done: verify the binaries' Authenticode signatures; use Docker on a machine that has it.
- How to change this decision later: point `PG_BIN` in `.env` to another PostgreSQL 16 `bin/`; nothing else depends on EDB.
- Status: done

### D-?: Database roles: who logs in, who owns, who can do what   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: The brief says `api_login` is "NOLOGIN, privileges only through SET LOCAL ROLE". But the API must log in as *something*.
- Options we considered:
  1. API logs in as `owner_role`. Con: the table owner is the most powerful normal role; forbidden by the brief.
  2. `api_login` = a LOGIN role with **no privileges of its own**, NOINHERIT, member of the five app roles with "SET only" (PG16 `WITH INHERIT FALSE, SET TRUE`). It must run `SET LOCAL ROLE <app role>` to touch anything.
  3. One login role per app role. Con: five passwords in the API; the role choice would move into connection handling.
- What we chose: Option 2, plus three small NOLOGIN helper roles: `maint_role` (seed loader + research export, reachable only from `owner_role`), `pharm_view_owner` (owns the pharmacist view, one narrow policy), `audit_writer` (owns the audit function). A **bootstrap superuser** (name/password in .env) is used only by `dbtool`/tests to create roles and databases.
- Why: nothing a request uses is a superuser, has BYPASSRLS, or owns a table. If the API forgets `SET LOCAL ROLE`, it can do nothing at all (fail closed; tested).
- What we actually did: `m5_backend/scripts/dbtool.py` (`bootstrap_roles` refuses to continue if any of our roles is superuser/BYPASSRLS). Tests: `test_no_role_is_superuser_or_bypassrls`, `test_api_login_memberships_are_set_only`, `test_api_login_has_no_table_privileges_of_its_own`.
- What could go wrong / weaknesses: helper roles are a deviation from the brief's list (recorded here). Whoever has the `owner_role` password can become `maint_role` and read everything; whoever has the `api_login` password can become any app role.
- What else could be done: separate operator login for the export job; a real secrets manager.
- How to change this decision later: `scripts/dbtool.py` (roles), `sql/*.sql` (grants/policies).
- Status: done

### D-?: RLS foundation: FORCE on every table, default deny, one transaction per request   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: How every request tells the database who is asking.
- Options we considered:
  1. Filter rows in Python. Con: one forgotten WHERE leaks data.
  2. RLS policies reading per-transaction settings (**GUCs**) set with `SET LOCAL` / `set_config(..., true)`.
  3. Session-level `SET`. Con: leaks to the next user of a pooled connection.
- What we chose: Option 2. Every one of the 10 tables has ENABLE **and FORCE** row level security; no policy means no rows; no policy is granted to PUBLIC; IDs are UUIDs; composite foreign keys keep patient/encounter/order facilities consistent.
- Why: the database refuses even if the API code has a bug. FORCE makes RLS apply to the table owner too.
- What we actually did: `sql/010_schema.sql`, `sql/020_rls.sql`, `app/db.py` (`request_tx`: BEGIN, `SET LOCAL ROLE` from a fixed allowlist, `set_config('app.user_id'|'app.facility_id'|'app.role'|'app.active_patient_id', v, true)`). Tests: `test_every_table_has_rls_enabled_and_forced`, `test_table_owner_with_no_policy_sees_zero_rows` (owner sees 0 rows of 8 patients), `test_role_with_grants_but_no_policy_sees_zero_rows`, `test_no_role_or_guc_leaks_to_next_transaction_on_pooled_connection`, `test_reset_role_leaves_no_privileges`.
- What could go wrong / weaknesses: anyone who can run raw SQL as `api_login` can set the GUCs to any user (residual limit; `test_residual_raw_api_credentials_can_set_gucs` shows it works). A malformed GUC raises an error (fails closed), it never widens access.
- What else could be done: sign the context (e.g. pass a signed token into the DB and verify it in a SECURITY DEFINER function) so raw credentials alone are not enough.
- How to change this decision later: `app/db.py`, `sql/020_rls.sql`.
- Status: done

### D-?: Access rule: ASHA   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: What an ASHA (community health worker) may see and write.
- Options we considered: 1. Facility-wide access (simpler, but an ASHA would see households she never visits). 2. Only households assigned to her and what hangs off them (the brief).
- What we chose: Option 2: SELECT/INSERT on households with `assigned_asha_id = me` (insert also needs her facility), and on patients/encounters/records reachable through those households. Her encounters must be `asha_household_visit` authored by herself; her records must be draft/flagged with no approver. No UPDATE, no DELETE, no orders, consents, audit, research. Audio follows encounter visibility.
- Why: least privilege, straight from the brief.
- What we actually did: policies `asha_*` in `sql/020_rls.sql`; expected table rows `asha:` in `tests/access_matrix_expected.yaml`; 192 base matrix cases for the ASHA role all pass.
- What could go wrong / weaknesses: an ASHA cannot correct a typo she made (no UPDATE). Reassigning a household to another ASHA needs an operator.
- What else could be done: allow UPDATE of her own draft records for a short time window.
- How to change this decision later: `asha_*` policies + the `asha:` block of the expected table (edit both by hand, separately).
- Status: done

### D-?: Access rule: nurse ("draft records" = draft or flagged)   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: The brief says nurses work on "draft records". record.v1 has statuses draft, flagged, approved, saved.
- Options we considered: 1. `draft` only. 2. `draft` and `flagged` (not yet approved). 3. All statuses.
- What we chose: Option 2. Nurse: SELECT/INSERT/UPDATE patients, encounters and draft|flagged records in her facility; SELECT medication_orders in her facility; she cannot set approved/saved or an approver. UPDATE is limited by **column grants** (patients: name/age band/sex; encounters: type; records: json/status). No households.
- Why: a flagged record is still a draft that needs work; approved/saved records are a physician's.
- What we actually did: `nurse_*` policies and column grants in `sql/020_rls.sql`; tests `test_nurse_cannot_approve_or_see_saved_records`; all nurse matrix cases pass.
- What could go wrong / weaknesses: nurses cannot read approved/saved records at all (possibly too strict clinically: open question). Nurses cannot see households, so they insert patients by household id they get elsewhere.
- What else could be done: read-only access to saved records in her facility if clinicians want it.
- How to change this decision later: `nurse_records_*` policies + `nurse:` block of the expected table.
- Status: done

### D-?: Access rule: physician (approve only in her own name; saved is final)   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: How approval works in the database.
- Options we considered: 1. Physician may write any approved_by value. 2. approved_by must equal the physician's own id; a saved record can never be updated.
- What we chose: Option 2. Physician = nurse rights for any record status in her facility + INSERT/UPDATE medication_orders (patient and facility taken from the encounter) + approve/save with `approved_by = me`. UPDATE policy excludes status 'saved'.
- Why: nobody can approve in a colleague's name; a saved record cannot be changed silently.
- What we actually did: `physician_*` policies; tests `test_physician_cannot_approve_in_someone_elses_name`, `test_saved_record_is_immutable`.
- What could go wrong / weaknesses: correcting a saved record needs a new record (no amendment workflow yet).
- What else could be done: an amendment table that links a correction to the saved original.
- How to change this decision later: `physician_records_update` policy.
- Status: done

### D-?: Access rule: pharmacist only through a security_barrier view and an "active patient"   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: How a pharmacist sees orders without any table grant.
- Options we considered: 1. Grant SELECT on medication_orders with a policy. Con: the brief says no table grants. 2. A `security_invoker` view. Con: needs table grants for the pharmacist. 3. A normal (owner-rights) view with `security_barrier`, owned by a narrow role.
- What we chose: Option 3. `clinic.pharmacist_orders_v` (order id, 8-char patient ref, drug, dose, unit, frequency, duration, status) owned by `pharm_view_owner`, whose only policy is: facility = mine AND status = 'ready_to_dispense' AND patient_id = `app.active_patient_id`. The view's WHERE clause repeats this. The API sets the active patient only via `POST /pharmacist/active-patient`, which checks that a ready order exists for that patient at her facility (through the view) and writes an audit row (allow or deny); the choice is kept server-side for 10 minutes.
- Why: the predicate is enforced twice in the database; the pharmacist can never list all patients.
- What we actually did: `sql/030_views.sql`, `app/main.py`; test `test_pharmacist_active_patient_flow_is_checked_and_audited`; matrix: other facility, non-active patient and non-ready order are all denied even when the DB context is set directly.
- What could go wrong / weaknesses: **the system cannot prove the patient is physically present**; it only narrows scope and audits. A pharmacist could try patient ids one by one; each try is audited (no lockout yet). The 8-character patient ref is part of the UUID (not secret, not a name).
- What else could be done: rate-limit activations; require a code printed on the prescription.
- How to change this decision later: `sql/030_views.sql`, `set_active_patient` in `app/main.py`.
- Status: done

### D-?: Access rule: researcher only sees a de-identified export   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: How researchers get data without seeing patients.
- Options we considered: 1. Views over base tables. Con: easy to leak ids/text. 2. A separate `research` schema filled by an export job (full refresh each time).
- What we chose: Option 2. pseudonym = first 20 hex chars (80 bits) of HMAC-SHA256(key from `.env`, patient_id); age band, sex, encounter type, month (YYYY-MM), record status, symptom names, structured medication fields. No ids, no names, no free text (advice, follow-up and evidence spans dropped). Strings must be in a closed allowlist (symptom list in code, drug names from the lexicon CSV), otherwise dropped. Only `consents.research_ok = true` at export time; withdrawal disappears at the next export.
- Why: researchers cannot reverse the pseudonym without the key; a full refresh makes withdrawal simple.
- What we actually did: `app/export.py`, `sql/010_schema.sql` (research table), `sql/020_rls.sql`. Tests: `test_export_contains_no_ids_names_dates_or_free_text` (scans every id, name, exact date and free-text token: 0 hits), `test_only_consenting_patients_and_withdrawal_removes_at_next_export`.
- What could go wrong / weaknesses: age band + sex + month + rare drug in a tiny facility could still re-identify someone (no k-anonymity check). 80-bit truncation: collisions are negligible at this size but not zero. The free-text scan exempts words that are also allowlisted drug/symptom names.
- What else could be done: k-anonymity / suppression of small cells; rotate the HMAC key per study.
- How to change this decision later: `app/export.py` (`PSEUDONYM_HEX`, vocabularies).
- Status: done

### D-?: Saved-record gate in the database and the API   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: How to make sure nothing is "saved" without approval and with open safety flags.
- Options we considered: 1. Only check in the UI. 2. DB CHECK constraint + API check of the verdict.
- What we chose: Option 2. `CHECK (status <> 'saved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))`. `POST /records/{id}/save` validates the verdict.v1 and refuses (409, audited `save_rejected`) when any check is `flag`, `auto_acceptable` is false, or checks is empty; 422 if the verdict belongs to another record.
- Why: two independent layers (DB + server), both fail closed.
- What we actually did: `sql/010_schema.sql`, `save_record` in `app/main.py`. Tests: `test_saved_check_constraint`, `test_saved_gate_rejects_unresolved_flags_and_accepts_clean_verdict`. Finding: for a physician, the RLS WITH CHECK already refuses an unapproved save before the CHECK runs.
- What could go wrong / weaknesses: there is no way yet to mark a flag as "resolved by a human"; the API trusts the verdict the client sends (it does not re-run the verifier).
- What else could be done: store the verdict server-side from m4_verify output and add explicit flag-resolution records.
- How to change this decision later: `save_record` in `app/main.py`; the CHECK in `sql/010_schema.sql`.
- Status: done

### D-?: Audit log: append-only, written through one SECURITY DEFINER function   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: The brief says "INSERT-only for the api", but pharmacists and researchers must have NO table grants.
- Options we considered: 1. Grant INSERT on audit_log to every app role. Con: breaks "no table grants" for pharmacist/researcher; lets a role forge another user's row. 2. A minimal SECURITY DEFINER function `app.audit_write(action, table, row_id, outcome)` (pinned search_path) owned by `audit_writer`; user and role come from the request GUCs, not from arguments.
- What we chose: Option 2, plus REVOKE UPDATE/DELETE/TRUNCATE from everyone including the owner, and triggers that raise on UPDATE/DELETE/TRUNCATE. Columns are enums/ids only (no free-text column exists).
- Why: no role can write arbitrary audit rows, and nobody can change them.
- What we actually did: `sql/040_audit.sql`. Tests in `tests/test_audit_log.py`: update/delete/truncate fail for all 5 app roles, the owner and even the superuser (trigger).
- What could go wrong / weaknesses: a superuser can disable triggers; the owner can re-grant itself rights. Audit rows written inside a failed request are rolled back, so the API writes the "deny" row in a second transaction; if that also fails, the deny is not logged.
- What else could be done: ship the log to append-only storage outside the database.
- How to change this decision later: `sql/040_audit.sql`.
- Status: done

### D-?: Nobody gets DELETE; facilities, users and consents are closed to app roles (scope cut)   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: The brief lists no rights for deleting, for facilities/users, or for managing consent.
- Options we considered: 1. Give nurses consent management. 2. Default deny (only the operator via `maint_role` changes consents).
- What we chose: Option 2.
- Why: "default deny, then explicit policies" means unlisted rights stay closed.
- What we actually did: no grants/policies for those; all such matrix cells expect and get deny.
- What could go wrong / weaknesses: a real clinic needs a consent workflow (open question).
- What else could be done: a nurse/ASHA consent endpoint with its own audit action.
- How to change this decision later: `sql/020_rls.sql` + expected table.
- Status: done (scope cut)

### D-?: Authentication: PyJWT mock issuer, HS256 pinned   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: How users prove who they are in the sandbox.
- Options we considered: 1. A real identity provider (cost/time). 2. A local mock issuer with strict verification.
- What we chose: Option 2: HS256 only (alg pinned; `none`, HS512 and RS/HS confusion rejected), `exp`, `iat`, `iss`, `aud`, `sub`, `role`, `fid` required, no leeway, expiry 300 s (max 900), signing key >= 32 chars from `.env`, and the token's user/role/facility must match the synthetic directory. Role is taken ONLY from the verified token. Login is rate-limited (5 per minute per IP+user, 30 per IP).
- Why: covers the classic JWT mistakes listed in the brief.
- What we actually did: `app/auth.py`, `app/ratelimit.py`, `seed/synthetic_users.json`; `tests/test_auth_jwt.py` (24 cases) + 143 token-attack matrix cases.
- What could go wrong / weaknesses: one shared mock password; in-memory rate limit (resets on restart, one process only); no token revocation.
- What else could be done: asymmetric keys (RS256/EdDSA) from a real issuer; refresh tokens.
- How to change this decision later: `app/auth.py`.
- Status: done

### D-?: API hygiene: forbid extra fields, generic errors, 404 for hidden rows, audio after authorisation   (Phase B / m5_backend / backend-security-engineer / 2026-11-09)
- What we needed to decide: How the API avoids mass assignment, injection and information leaks.
- Options we considered: (1) default FastAPI behaviour (detailed error bodies echoing input); (2) strict models and generic errors.
- What we chose: (2). Every body model has `extra="forbid"`; server-owned fields (facility, author, approver, assigned ASHA, patient of an order) come from the token or the RLS-visible encounter. Only parameterised SQL (`psycopg`), identifiers via `psycopg.sql.Identifier` from fixed lists. Errors are `{"error": "<generic>"}`, no stack traces, no OpenAPI docs. Rows hidden by RLS return 404. Audio is served only after the encounter is visible to the caller; the file name is built from a parsed UUID.
- Why: OWASP A01/A03/A04/A05.
- What we actually did: `app/models.py`, `app/main.py`; tests `test_models_ratelimit.py`, `test_api.py`; matrix sqli (192), mass_assignment (20), idor_audio (26), id_guess (100) cases all pass.
- What could go wrong / weaknesses: 403 (grant/WITH CHECK) vs 404 (hidden) can still reveal that a row exists when updating a visible row. No TLS (127.0.0.1 only).
- What else could be done: map every 403 on a write to 404; add request size limits.
- How to change this decision later: `app/main.py`.
- Status: done

### D-?: Access matrix E5: 1486 cases, 0 unauthorized successes   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: How to prove the rules hold without the test being circular.
- Options we considered: 1. Generate the expected outcomes from the SQL (circular: rejected). 2. Write the expected table by hand from the brief, before writing any policy.
- What we chose: Option 2. `tests/access_matrix_expected.yaml` was written by hand first. 960 base cases (5 roles x 12 resources x 4 actions x 4 ownerships) run at DB level through the same `request_tx` as the API, each rolled back; 526 attack cases run through the API (tampered/expired/alg-none/wrong-aud tokens, id guessing, SQLi in path ids, query params, login fields, enum/pattern fields and free-text JSON, mass assignment, audio IDOR incl. path traversal, GUC tampering via headers/params/body SQL and at DB level RESET ROLE / SET ROLE owner / SET SESSION AUTHORIZATION / garbage GUCs). Every case validates as access_case.v1.
- Why: rule of three: 0 failures in N trials gives a 95% upper bound of about 3/N.
- What we actually did: `matrix/generate.py`, `matrix/run.py`, `tests/test_access_matrix.py`. Result (2026-11-10, PostgreSQL 16.15 local): **unauthorized successes: 0 of 1385 deny-expected cases (1486 total); 95% upper bound 3/1385 = 0.0022.** Unexpected denials (availability bugs): 0 of 101 allow-expected. Integrity failures: 0 (SQLi text stored and read back byte-identical). Files: `results/m5_backend/access_matrix_results.jsonl`, `access_matrix_summary.json`.
- What could go wrong / weaknesses: the cases are not independent trials (many share one policy), so 3/N is optimistic. The matrix tests the rules we wrote; both the table and the SQL were written by the same AI agent from the same brief, so a shared misreading of the brief would not be caught. **Residual limit: anyone holding raw DB credentials can set GUCs / SET ROLE; credentials must stay out of reach (constraint 3).** CI run: UNVERIFIED.
- What else could be done: an independent human writes a second expected table; property-based fuzzing; run in CI on every push.
- How to change this decision later: edit the YAML by hand; never generate it from SQL.
- Status: done locally; CI pending

### D-?: Problems hit while building m5_backend (and fixes)   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: How to handle five problems found during the build.
- Options we considered: fix each at the root vs. work around it.
- What we chose: fix at the root.
- Why: each one could hide a real failure.
- What we actually did:
  1. `unzip 'pgsql/share/*'` skipped sub-folders, so initdb failed ("could not open directory .../share/timezonesets"); re-downloaded (same sha256) and extracted with `'pgsql/share/**'`.
  2. The server inherited the shell's output pipe, so the setup command never returned and stopping it killed Postgres; `db_up.sh` now redirects pg_ctl's stdin/stdout/stderr.
  3. Migration error "permission denied for function audit_write": EXECUTE was granted after ownership moved to `audit_writer`; the grant now comes first.
  4. First matrix run reported 3 "unauthorized successes": a **test bug**: the physician "role escalation" probe changed the role claim to "physician", i.e. it sent a genuine token. The probe now really changes the claim and asserts it did. Re-run: 0.
  5. After a lint refactor, FastAPI could not resolve a function-local `Annotated` dependency (with `from __future__ import annotations`) and returned 422 everywhere; the dependency is now module-level. The matrix caught this as unexpected denials.
- What could go wrong / weaknesses: none known left from these; problem 4 shows the matrix itself can contain bugs, so a human should read `matrix/run.py`.
- What else could be done: a self-test that every attack probe differs from its control request.
- How to change this decision later: n/a.
- Status: done
