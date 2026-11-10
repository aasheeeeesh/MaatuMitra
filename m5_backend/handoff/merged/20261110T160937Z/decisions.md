### D-?: The server stores every verdict; saving needs one resolution per flag (F1 + D-80 built)   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: How to stop a physician's client from sending a hand-made "all checks pass" verdict (audit attempt SG-1 saved a never-approved draft with HTTP 200), while still letting a reviewer who looked at a flag and confirmed it (or fixed the field) save the record.
- Options we considered:
  1. Sign the client's verdict. Pro: small change. Con: the client still decides what the verifier said; needs key handling.
  2. The server runs the verifier and stores the verdict itself; the save request only names that verdict and answers each flag. Pro: the client cannot invent a verdict; matches the brief and D-80. Con: new tables, endpoints, tests, and a verifier hook.
  3. Only a database trigger. Pro: cannot be bypassed from the API. Con: cannot express "edited and re-verified" easily.
- What we chose: Option 2, plus the database trigger from option 3 as a backstop (both).
- Why: The save gate is the safety heart of the project, so it must not trust the client. The trigger means even someone writing SQL directly cannot mark a record saved without a stored verdict and a confirmation for every flag.
- What we actually did: New tables `clinic.verdicts` and `clinic.record_resolutions` (forced RLS, append-only triggers, no UPDATE/DELETE grants; resolutions have no free-text column). `POST /records/{id}/verify` runs the verifier on the stored record and stores the verdict, with a record hash computed by the database. `POST /records/{id}/save` takes `{verdict_id, resolutions:[{check_id, field_path, action}]}` (extra fields refused, so no "by"). Rules: physician only; resolver = token user; every flag in the stored verdict has exactly one resolution (missing 409, unknown or duplicate 422); stale verdict 409; "edited" needs a changed record, a new stored verdict, and no flag the physician did not confirm; resolutions, status, approver, audit rows in one transaction. Trigger `records_saved_gate` (sql/050_gate.sql). Files: m5_backend/app/main.py, models.py, verifier.py, sql/010, 020, 050, tests/test_save_gate.py (SG-1 replay refused), 13 new matrix cases. Run `uv run pytest m5_backend/tests/test_save_gate.py`.
- What could go wrong / weaknesses: m5 cannot import the m4 verifier, so the real verifier is wired in at integration through `create_app(verifier=...)`. Until then the built-in default flags the whole record and the physician must confirm it: that is a click, not a safety check. A physician holding raw database credentials could insert a forged verdict (RLS lets her write verdicts for her facility); the API never does. Reviewers may still click "confirm" without looking (automation bias). The optional extra step for critical flags (audio playback, second confirmation) is NOT built. Audit condition 6 (a "reason" text) is not built, so there is no new free text. The old red/green order was followed when writing tests, but the red run was only observed for the pool fix (F5); the others were written first and passed after the code.
- What else could be done: Require audio playback for critical checks (C3, C4); add a short reason code list (not free text); let the verifier run as its own database role so even physician SQL cannot insert verdicts.
- How to change this decision later: app/main.py (save_record, verify_record), sql/050_gate.sql, tests/test_save_gate.py; m6_ui must change its save call (see CONTRACT.md).
- Status: done (m6_ui adaptation and real verifier wiring pending at integration)

### D-?: The audit log takes the role from the database session, not from a setting   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: F2: the audit function read `app.role` and `app.user_id`, which any session running SQL can change, so a researcher could write a row saying "physician".
- Options we considered: (1) leave it as documented residual risk. Pro: no work. Con: weakens the audit trail as evidence. (2) Read the role from the session role (`current_setting('role')`) and check that the user id exists with that role. Pro: cheap forgery stops. Con: a session with raw `api_login` credentials can still `SET ROLE` to another app role. (3) One database login per app role. Pro: strongest. Con: contradicts the brief's single api_login design and needs five pools.
- What we chose: Option 2.
- Why: It closes the audit attempt AL-forge with a small change and keeps the brief's design.
- What we actually did: `app.audit_write` in sql/040_audit.sql derives the role from the session role and refuses a user id that does not exist with that role; the `app.role` setting is no longer set or read. Test: tests/test_hardening.py::test_f2_researcher_cannot_write_an_audit_row_as_physician.
- What could go wrong / weaknesses: Raw `api_login` credentials still allow choosing any app role (residual limit, same as the GUC limit). The maint role (operator) may write rows with any existing user id.
- What else could be done: Per-role database logins; sign audit rows.
- How to change this decision later: sql/040_audit.sql, tests/test_hardening.py.
- Status: done

### D-?: Research export drops groups smaller than 5 patients   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: F3: with age band, sex, month, visit type and a pseudonym, almost every patient in the export was unique.
- Options we considered: (1) leave it. Pro: simplest. Con: easy to single people out. (2) Drop every group (age band x sex x month x visit type) with fewer than k = 5 distinct patients. Pro: simple, explainable. Con: loses rare groups, not full anonymity. (3) Merge small groups into wider ones. Pro: keeps more rows. Con: more logic to get wrong.
- What we chose: Option 2 with k = 5, and a `k_min` argument for tests.
- Why: Simple and checkable. We accept data loss over a false sense of privacy.
- What we actually did: `suppress_small_cells` in app/export.py. The seed gets a cohort of 5 consenting patients (C1..C5) in one cell; the other three consenting patients are alone in their cells and are NOT exported. So the synthetic export holds 5 patients (the cohort), nothing else. Tests: tests/test_hardening.py (pure and database), updated tests/test_research_export_db.py; the matrix points research cases at cohort patients.
- What could go wrong / weaknesses: Symptoms and medicines are not part of the cell, and the pseudonym links one patient's visits, so this is NOT proof of anonymity. k = 5 is a convention, not a calculation.
- What else could be done: Merge small groups; add l-diversity or a formal risk estimate; ask a privacy expert.
- How to change this decision later: K_MIN in app/export.py; seed cohort in seed/seed.py.
- Status: done

### D-?: Withdrawing consent removes research rows at once   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: F4: a withdrawal only took effect when someone re-ran the export; nothing guaranteed that would happen.
- Options we considered: (1) schedule the export. Pro: no schema change. Con: still a delay. (2) A database trigger on `clinic.consents` that deletes the patient's research rows in the same transaction. Pro: immediate. Con: needs a way to find the pseudonym without the secret key in the database. (3) A synchronous job called by an API. Pro: no trigger. Con: direct SQL updates would bypass it.
- What we chose: Option 2 with a private map table `research.pseudonym_map` (patient id to pseudonym), filled by the export, readable only by the operator role.
- Why: It cannot be skipped, and the HMAC key stays out of the database.
- What we actually did: sql/050_gate.sql triggers `consents_withdrawn` and `consents_deleted`; app/export.py fills the map. Test: tests/test_hardening.py::test_f4_withdrawal_removes_research_rows_immediately (no re-export in between).
- What could go wrong / weaknesses: The map is a patient-to-pseudonym link inside the database; whoever holds owner credentials and uses `maint_role` can read it. Re-consent needs the next export to bring the patient back.
- What else could be done: Store a keyed hash of the patient id instead of the id.
- How to change this decision later: sql/050_gate.sql, app/export.py.
- Status: done

### D-?: The connection pool wipes session state on every return   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: F5: a session-level `SET ROLE` or `SET app.*` (only possible through an injection) stayed on the pooled connection for the next user (audit attempt G-2).
- Options we considered: (1) check `current_user = session_user` before reuse. Pro: cheap. Con: misses other settings. (2) `DISCARD ALL` when returning a connection. Pro: resets everything; fail closed if it errors. Con: tiny cost per request; also deletes prepared statements.
- What we chose: Option 2, and automatic statement preparation is switched off.
- Why: Everything session-level is forgotten, whatever was set.
- What we actually did: app/db.py `_put` runs `DISCARD ALL`; `prepare_threshold = None`. Problem hit: with auto-prepare on, the matrix failed with "prepared statement does not exist", because the client kept names the server had discarded. Test: tests/test_hardening.py::test_f5_injected_session_level_set_role_does_not_reach_next_request (seen failing when the reset is removed).
- What could go wrong / weaknesses: Not preparing statements costs a little speed.
- What else could be done: Use a real pool library with a reset hook.
- How to change this decision later: app/db.py.
- Status: done

### D-?: The API refuses to start with a dangerous database login   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: F6: nothing stopped the API from running as a superuser, a BYPASSRLS role or the table owner if `API_DB_USER` was set wrongly.
- Options we considered: (1) document it. Con: one wrong line in .env removes all protection. (2) Check at startup and exit. Pro: fails closed. Con: one extra query.
- What we chose: Option 2.
- Why: A silent misconfiguration is the worst failure here.
- What we actually did: `Database.verify_login()` (app/db.py) is called in `create_app`; it refuses superuser, BYPASSRLS, CREATEROLE, CREATEDB, REPLICATION, owning tables or functions in clinic/research/app, or a session role different from the login. Test: tests/test_hardening.py::test_f6_api_refuses_to_start_with_unsafe_login (bootstrap, owner, a BYPASSRLS login refused; api_login accepted).
- What could go wrong / weaknesses: The check runs once at startup; a role changed later is not noticed until restart.
- What else could be done: Re-check periodically.
- How to change this decision later: app/db.py, `check_login` argument of `create_app`.
- Status: done

### D-?: Separate password for owner_role; Docker bootstrap user is mm_bootstrap   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: F7: `.env.example` told Docker users to use `POSTGRES_USER=owner_role`, which would make the image's superuser and owner_role share a name and password.
- Options we considered: (1) only fix the comment. Con: the code still reused one password. (2) New `OWNER_DB_PASSWORD`, `POSTGRES_USER=mm_bootstrap`. Pro: clean separation. Con: existing local .env files keep working only through a legacy rule.
- What we chose: Option 2, with a legacy rule: if `POSTGRES_USER` is still `owner_role`, `POSTGRES_PASSWORD` is used for owner_role (so the existing local setup works).
- Why: One credential per purpose.
- What we actually did: .env.example, docker-compose.yml comments, app/config.py; tests in tests/test_hardening.py (F7). 
- What could go wrong / weaknesses: The Docker path is UNVERIFIED (no Docker here).
- What else could be done: Run the Docker path once; drop the legacy rule.
- How to change this decision later: app/config.py, .env.example.
- Status: partly done (Docker run UNVERIFIED)

### D-?: Pharmacist patient reference is random; the catalog row-count leak is accepted   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: F8: `patient_ref` was the first 8 characters of the patient UUID; and any role can read table statistics and see "Rows Removed by Filter" in EXPLAIN.
- Options we considered: (1) a keyed hash per facility. Con: the database would need a secret. (2) A random per-patient reference stored in `clinic.patients.ref`. Pro: unrelated to the id, no secret. Con: one more column. For the row-count leak: block catalog reads (Con: breaks PostgreSQL tools) or accept.
- What we chose: Option 2 for the reference; ACCEPT the row-count leak as a documented residual limit.
- Why: The leak needs raw SQL, which the API never runs; hiding statistics would break normal PostgreSQL behaviour.
- What we actually did: sql/010 (`ref` column), sql/030 (view joins patients through one narrow policy). Test: tests/test_hardening.py::test_f8_patient_ref_is_not_a_uuid_prefix. README "Limits".
- What could go wrong / weaknesses: Anyone with raw SQL can still learn approximate table sizes.
- What else could be done: Per-facility keyed references; revoke `pg_stat` views from app roles.
- How to change this decision later: sql/010, sql/030.
- Status: done (row-count leak accepted)

### D-?: Tests no longer rewrite tracked result files; one foreign-key snag   (Phase B / m5_backend / backend-security-engineer / 2026-11-10)
- What we needed to decide: The audit noted that running the tests rewrote `results/m5_backend/access_matrix_summary.json`. Also: revoking UPDATE from owner_role on `verdicts` broke the foreign key from resolutions.
- Options we considered: tests write results (con: noisy diffs) or only the CLI does; for the snag, keep UPDATE for the owner on verdicts (the trigger still refuses) or add a special column grant.
- What we chose: `test_access_matrix` runs with `write=False`; `make m5-matrix` writes the three results files. owner_role keeps UPDATE on `verdicts` only (PostgreSQL's foreign-key check needs it); the append-only trigger still blocks every update.
- Why: Clean diffs; the trigger is the real guard.
- What we actually did: tests/test_access_matrix.py, sql/050_gate.sql. Results regenerated once: 1499 cases, 0 unauthorized successes of 1398 deny-expected, 3/1398 = 0.0021, 0 unexpected denials.
- What could go wrong / weaknesses: A superuser or owner can disable triggers (same residual as the audit log). The expected-access YAML gained one hand-written line (`attacks.save_gate: deny`); the same AI wrote it, so a human should re-read it. access_case.v1 has no `save_gate` attack value, so those cases use `mass_assignment` / `id_guess` (contract request in open_questions.md).
- What else could be done: Ask for a `save_gate` attack value in access_case.v1.
- How to change this decision later: tests/test_access_matrix.py, sql/050_gate.sql, matrix/generate.py.
- Status: done
