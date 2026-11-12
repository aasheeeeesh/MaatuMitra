### D-?: One adapter function wires m4 into m5   (Phase C / integration / integration-qa / 2026-11-12)
- What we needed to decide: m5 calls `fn(record)` and must not import m4. m4 needs the record AND the transcript. Where does the glue live, and what happens when it cannot run m4?
- Options we considered:
  1. Make m5 import m4. Pro: simple. Con: breaks the rule that modules do not import each other.
  2. An adapter in integration/ that m5 loads by name (`MAATUMITRA_VERIFIER=integration.verifier_adapter:verify_record`). Pro: allowed place, no m5 change. Con: it finds the transcript from a field inside the record.
  3. Change the m5 hook to also receive the encounter id. Pro: transcript bound to the encounter. Con: needs an m5 change (not ours to make).
- What we chose: Option 2, failing closed: no transcript, record.v2, a crash or an invalid verdict returns a valid verdict with ONE C1 flag, never a pass.
- Why: it works today without touching modules, and a physician must resolve anything m4 could not really check.
- What we actually did: integration/verifier_adapter.py; tests in integration/tests/test_verifier_adapter.py. The tests were written after the code, not before (a process slip).
- What could go wrong / weaknesses: whoever edits a draft record can change `source_transcript_id` (only an id whitelist and m4's span check guard it). m4 has no record.v2 support yet, so v2 records always get the one fail-closed flag.
- What else could be done: option 3; teach m4 v2.
- How to change this decision later: edit integration/verifier_adapter.py; unset the env variable to go back to "flag everything".
- Status: done

### D-?: End to end through the real HTTP API on 10 seeded DEV conversations   (Phase C / integration / integration-qa / 2026-11-12)
- What we needed to decide: how to prove the chain works from text to saved record, without touching test data.
- Options we considered:
  1. Call module functions directly. Pro: fast, no DB. Con: skips the save gate and database security.
  2. Start the real API as a subprocess and talk HTTP, with a user per role. Pro: tests the gate, row-level security and the adapter for real. Con: needs the local database.
- What we chose: Option 2. Mock ASR (the gold text through m2's transcript builder, because m2 has no real dev output for these ids), m3 rules, m4 via the adapter, asha creates, physician resolves and saves, 11 users read back, m6's own HttpGate loads the draft. Planted-error records (a flipped negation) are in a separate table and are fixed by an `edited` resolution.
- Why: the safety claim lives in the gate; only an HTTP run exercises it.
- What we actually did: integration/e2e.py, integration/tests/test_e2e.py (skips cleanly if the DB is down), results/integration/e2e_dev.md. Seed 20261112, ids from data/splits/dev.txt only.
- What could go wrong / weaknesses: ASR is mocked (gold text), so ASR errors are not tested here. The "reviewer" confirms every flag; that is a test policy, not clinical review. Ten conversations prove wiring, not accuracy.
- What else could be done: run with m2's real transcripts for template ids once they exist; use record.v2.
- How to change this decision later: integration/e2e.py (`select_ids`, `AUTHOR`, reviewer rule in `run_one`).
- Status: done

### D-?: Integration findings to fix in the modules   (Phase C / integration / integration-qa / 2026-11-12)
- What we needed to decide: which mismatches found while wiring belong to which module (we do not fix modules).
- Options we considered: fix here (not allowed), or report to the orchestrator.
- What we chose: report.
- Why: modules are owned by other agents.
- What we actually did: contract checks found 0 mismatches in 16 boundary samples (results/integration/boundary_checks.md). Behaviour findings: (1) m5 `/verify` stores a new verdict on every call and `/save` demands the NEWEST verdict id, so a second person opening the record in m6 (which verifies on load) makes the first physician's save fail with 409; fix in m5 or m6 (reuse the latest verdict for an unchanged record). (2) m6 live cannot reopen a SAVED record: load always calls /verify and m5 refuses saved rows (404). (3) m5's verifier hook gets no encounter id (see adapter weakness). (4) m3 and m4 still speak record.v1 only. (5) After save the nurse can no longer read the record (policy shows only draft/flagged); expected by the policy, but m6 nurse screens should not promise it.
- What could go wrong / weaknesses: samples are capped at 400 per boundary; m7 outputs were not validated (no schema covers them).
- What else could be done: a CI job that runs this folder with the DB up.
- How to change this decision later: not applicable (reports only).
- Status: needs human (orchestrator routes to m5/m6)
