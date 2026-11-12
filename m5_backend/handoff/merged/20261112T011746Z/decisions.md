### D-?: Remove POST /records/{id}/approve; /save is the only approval   (Phase C / m5_backend / backend-security-engineer / 2026-11-12)
- What we needed to decide: The old /approve route set a record to "approved" with the physician's name and no flag check (review finding D-123 F3). Fix it or remove it?
- Options we considered:
  1. Gate /approve like /save. Pro: keeps an "approved but not saved" step. Con: two routes to maintain and to get wrong; nobody needs the middle state (m6 no longer calls it).
  2. Remove /approve. Pro: one door, one set of rules. Con: a client that still calls it gets 404.
- What we chose: Option 2.
- Why: Every extra path to "approved" is a place to forget the flag check. /save already stores the verdict on the server and needs one answer per open flag, and the database trigger still checks the saved state.
- What we actually did: deleted the route in m5_backend/app/main.py. Test `test_handcrafted_approve_with_unresolved_flags_is_refused` in m5_backend/tests/test_followups.py FAILED on the old code (HTTP 200, record became "approved") and passes now (404/405, record stays draft). Run `uv run pytest m5_backend/tests/test_followups.py`.
- What could go wrong / weaknesses: The database still lets a physician set status "approved" by direct SQL (RLS: only in her own name); the trigger gates only "saved". The status stays in the schema for old data.
- What else could be done: forbid "approved" in the CHECK constraint and RLS too (needs a migration).
- How to change this decision later: re-add a route in app/main.py with the same code as save_record; write the tests first.
- Status: done

### D-?: Add GET /records (list) and GET /records/{id}/transcript   (Phase C / m5_backend / backend-security-engineer / 2026-11-12)
- What we needed to decide: m6 had no way to list records or fetch a transcript from the server. How to add both without opening new holes?
- Options we considered:
  1. List and filter in Python after reading everything. Con: one bug leaks rows.
  2. Let the database do it: run the query as the caller's role so forced RLS hides the rest. Transcript: files named by the encounter id read from the database.
  3. Store transcripts in a new table. Pro: RLS on the text itself. Con: new table, new policies, bigger change.
- What we chose: Option 2 for both.
- Why: Same pattern as audio, which already passed the matrix. The transcript file name comes from the database row, so a record that claims another record's transcript id reads nothing (tested).
- What we actually did: app/main.py (`list_records`, `get_transcript`), setting `M5_TRANSCRIPT_DIR`, seed writes synthetic transcripts. The list returns id, record_id, encounter_id, patient_id, status, flagged_count; limit 1..100, offset >= 0 (else 422). ASHA sees only her patients' records; pharmacist and researcher get 403. Matrix: 160 new endpoint cases, 20 id-guess cases and token attacks, all pass (results/m5_backend/access_matrix_summary.json).
- What could go wrong / weaknesses: Transcript files sit on disk outside the database: whoever can read the folder can read them (disk permissions are not tested). Pages use OFFSET, so rows added while paging can shift. access_case.v1 has a fixed resource list, so the new cases use resource "records" (contract request in open_questions.md).
- What else could be done: a transcripts table with RLS; cursor pagination.
- How to change this decision later: app/main.py, matrix/generate.py, tests/access_matrix_expected.yaml (`endpoints` section).
- Status: done

### D-?: Load the verifier by import path (MAATUMITRA_VERIFIER)   (Phase C / m5_backend / backend-security-engineer / 2026-11-12)
- What we needed to decide: How integration plugs the real checker (m4) into m5 without m5 importing m4.
- Options we considered:
  1. Integration code calls create_app(verifier=fn). Pro: simple. Con: needs a custom launcher script.
  2. Also read a setting `module:function` from .env at startup. Pro: no launcher; one line to document. Con: the operator controls which code runs, so a bad value must fail loudly.
  3. Fall back to the default if loading fails. Con: silently runs a different checker than intended.
- What we chose: Options 1 and 2; a bad value stops startup (no fallback).
- Why: A silent downgrade of a safety check is worse than a failed start. The value comes from .env, never from a request. The default stays "flag everything for manual review".
- What we actually did: app/verifier.py `load_verifier`, setting `verifier_spec`, `.env.example`. Tests use a tiny fake module m5_backend/tests/fake_verifier_mod.py (10 bad specs rejected; a verdict is stored with the fake's version).
- What could go wrong / weaknesses: Anyone who can edit .env can run any importable function as the verifier. Only works for a function record_json -> verdict.v1 dict. Not run with the real m4 (UNVERIFIED).
- What else could be done: an allow-list of module names.
- How to change this decision later: app/verifier.py and `create_app` in app/main.py.
- Status: done (real m4 wiring UNVERIFIED until Phase C integration)

### D-?: Accept record.v2 bodies next to record.v1   (Phase C / m5_backend / backend-security-engineer / 2026-11-12)
- What we needed to decide: m3 will emit record.v2 (route, strength, status, evidence). Should POST/PATCH /records take it now?
- Options we considered:
  1. Wait and add new columns. Con: big migration; the contract note asked for JSONB.
  2. Validate v1 or v2 with contracts.validate and store the whole document in the existing JSONB column.
- What we chose: Option 2.
- Why: Small and safe: the document was already stored as JSON. We also refuse bidi control characters (text-direction tricks) on both versions.
- What we actually did: `_check_record` in app/main.py. Tests: a v2 fixture is stored unchanged, verified and updated; a bad route, a bidi character, an unknown version and status "saved" all give 422.
- What could go wrong / weaknesses: The research export reads only v1-style fields, so v2-only data is not exported (safe, but less useful). The built-in default verifier knows nothing about v2.
- What else could be done: export route and status after a privacy review.
- How to change this decision later: `_check_record` in app/main.py and app/export.py.
- Status: done
