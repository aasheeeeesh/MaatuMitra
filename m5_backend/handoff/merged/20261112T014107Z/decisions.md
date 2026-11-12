### D-?: One verdict per record content, so a second verify no longer breaks the first physician's save   (Phase C / m5_backend / backend-security-engineer / 2026-11-12)
- What we needed to decide: /save used to need the NEWEST verdict. If a second person (or a second browser tab) pressed "verify" on the same unchanged record, the first physician's save failed with 409 "stale", although nothing had changed.
- Options we considered:
  1. Keep "newest wins" and tell users not to verify twice. Pro: no change. Con: a real clinic would hit it constantly.
  2. Accept any earlier verdict whose content fingerprint (hash) matches. Pro: simple. Con: the database trigger looks at "the newest verdict", so API and database could disagree if two verdicts exist for one content.
  3. Allow only ONE verdict per record content (unique index); a second verify returns the existing verdict. Pro: API and trigger cannot disagree; nothing to go stale. Con: a verifier upgrade does not re-check unchanged content until the content changes.
- What we chose: Option 3.
- Why: The rule "a verdict belongs to the exact content it was computed for" is then enforced by the database itself, and the stale check only triggers on a real content change.
- What we actually did: unique index `verdicts_one_per_content` in m5_backend/sql/050_gate.sql; /verify in m5_backend/app/main.py returns the stored verdict for identical content (INSERT ... ON CONFLICT DO NOTHING handles two verifies at the same moment); /save compares content hashes only. Tests: m5_backend/tests/test_phase_c_fixes.py (a_*). Changing content and then changing it back makes the original verdict valid again (same hash), which is correct.
- What could go wrong / weaknesses: Re-verifying after a verifier upgrade needs a content change or an operator step (not built). A verdict made by an ASHA or nurse is reused for the physician's save; the physician still has to resolve every flag herself. Two truly simultaneous verifies were handled in code (ON CONFLICT) but not load-tested (UNVERIFIED).
- What else could be done: a verifier_version column so a newer verifier can supersede old verdicts explicitly.
- How to change this decision later: drop the index in 050_gate.sql and restore the "latest" comparison in save_record.
- Status: done

### D-?: Read-only reopen of a saved record (GET /records/{id}/review)   (Phase C / m5_backend / backend-security-engineer / 2026-11-12)
- What we needed to decide: The review screen got 404 when it reopened a saved record, because /verify only accepts unsaved records.
- Options we considered:
  1. Let /verify run on saved records. Pro: screen unchanged. Con: could add a verdict row or invite changing a finished record.
  2. A new GET that only reads. Pro: cannot change anything; same row-level security as the record. Con: the screen must call a new route.
- What we chose: Option 2.
- Why: A saved record should be viewable but not touchable. A GET with no writes makes that easy to prove.
- What we actually did: GET /records/{id}/review returns status, approver, the stored verdict for the CURRENT content (null if never verified), open flags, and for physicians the resolutions. /verify on a saved record still answers 404. Tests in test_phase_c_fixes.py (b_*) check that no rows are written, that another facility and a nurse get 404, and that no token gets 401.
- What could go wrong / weaknesses: Only physicians can read resolutions (database grant), so other roles see an empty list; m6 must be changed to call the new route (UNVERIFIED with the live screen). The hand-written access matrix YAML was not extended with this route (the tests cover it instead).
- What else could be done: add the route to access_matrix_expected.yaml by hand.
- How to change this decision later: m5_backend/app/main.py (review_record) and m5_backend/CONTRACT.md.
- Status: done

### D-?: The verifier receives the encounter id and transcript that m5 loads from the database   (Phase C / m5_backend / backend-security-engineer / 2026-11-12)
- What we needed to decide: The m4 adapter picked the transcript from `source_transcript_id` inside the record, a field the author can edit.
- Options we considered:
  1. Keep the field and trust m4 to notice mismatches. Pro: no change. Con: the author steers which transcript is checked.
  2. m5 passes `encounter_id` and `transcript` (read from the record's DATABASE encounter, the same file GET /records/{id}/transcript serves). Pro: transcript is bound to the encounter. Con: hook signature changes.
- What we chose: Option 2, backward compatible.
- Why: Same principle as the rest of m5: facts come from the database, not from editable fields.
- What we actually did: hook is `fn(record, *, encounter_id, transcript)`; m5 passes only the keywords the function accepts, so an old `fn(record)` hook keeps working (m5_backend/app/verifier.py, `call_verifier`). A missing or invalid transcript is passed as None. integration/verifier_adapter.py now uses the passed transcript and fails closed on None; the old lookup remains only when it is called without `encounter_id`. m4 itself still flags a record whose source_transcript_id differs from the transcript (tested).
- What could go wrong / weaknesses: The transcript file of an encounter is trusted to belong to that encounter's audio (written by the pipeline, not by users). Not tried with the live m6 screen (UNVERIFIED).
- What else could be done: store the transcript in the database together with a hash.
- How to change this decision later: verifier.py, main.py (verify_record), integration/verifier_adapter.py.
- Status: done

### D-?: The database gate now covers every final status, not only "saved"   (Phase C / m5_backend / backend-security-engineer / 2026-11-12)
- What we needed to decide: The trigger checked only status = 'saved'. A physician with direct SQL could set status 'approved' on her own record without resolving flags.
- Options we considered:
  1. Remove 'approved' from the allowed statuses. Pro: simplest. Con: schema change.
  2. Make the trigger gate both 'approved' and 'saved'. Pro: no schema change; any path to a final status is checked. Con: slightly more complex trigger.
- What we chose: Option 2.
- Why: Defence in depth; the database must not trust that the API is the only door.
- What we actually did: m5_backend/sql/050_gate.sql: the gate runs on INSERT and on any UPDATE that changes status, content or approver of an approved/saved row; an untouched final row passes. Rewriting an approved record's content therefore also needs a verdict for the NEW content. Saved rows were already immutable by RLS. Tests via direct SQL as physician_role: test_phase_c_fixes.py (d_*). One older test (physician approving in someone else's name) now fails earlier with CheckViolation instead of 42501; it accepts either.
- What could go wrong / weaknesses: The verifier's honesty is still assumed (verdict content is written by the API). maint_role (operator seed loader) stays exempt by design.
- What else could be done: forbid status 'approved' entirely if it stays unused.
- How to change this decision later: 050_gate.sql, function app.records_saved_gate.
- Status: done
