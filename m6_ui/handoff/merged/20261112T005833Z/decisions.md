### D-?: Save with one call: the server's verdict id plus one answer per flag (no separate approve call)   (Phase C / m6_ui / frontend-engineer / 2026-11-12)
- What we needed to decide: m5 changed /save (D-80, D-94) to take {verdict_id, resolutions}. Security finding F3 said the old approve-then-save order left a record marked approved when the save was refused.
- Options we considered:
  1. Keep calling /approve first. Pro: no change. Con: a refused save leaves the record stamped approved.
  2. Call /approve only after a successful save. Pro: no stale approval. Con: pointless, because m5 /save already means approve.
  3. Call only /save. Pro: one gated step. Con: m5's /approve endpoint still exists and has no flag check.
- What we chose: Option 3. The UI never calls /approve.
- Why: Save = approve in m5. One call means there is no half-approved state. A physician's per-flag answer becomes one resolution per (check id, field path), the same key m5 uses, so two reasons on one field do not make a duplicate.
- What we actually did: m6_ui/gate.py (MockGate mirrors the m5 rules; HttpGate talks to m5), m6_ui/review.py build_resolutions, m6_ui/app.py _approve. After an edit the save uses the FIRST verdict id (the one that held the flags), as m5 requires. Each m5 refusal (stale, not re-verified, forbidden, conflict, bad request, not found...) has Kannada and English text. Tests: m6_ui/tests/test_gate.py, test_security.py. Real m5 check: m6_ui/tests/test_live_m5.py (passed with the DB and API up).
- What could go wrong / weaknesses: m5's /approve endpoint still has no flag check (see open_questions.md). An edit that makes the checker raise a NEW kind of flag cannot be saved under m5's rules; the UI shows the refusal and the physician must edit again. The mock gate is a copy of the m5 rules written from reading main.py, not m5 code.
- What else could be done: Ask m5 to remove or gate /approve. Show the physician which flag blocks an edited save before pressing Approve.
- How to change this decision later: m6_ui/gate.py, m6_ui/app.py (_approve), m6_ui/review.py.
- Status: done

### D-?: Each person logs in as their own m5 user; the role comes from the token   (Phase C / m6_ui / frontend-engineer / 2026-11-12)
- What we needed to decide: Security finding F1: the role was a button click and live mode used one shared server credential, so every user acted as that one identity.
- Options we considered:
  1. Keep the role picker. Pro: easy demo. Con: any role can approve; the audit log names the wrong person.
  2. One shared service user. Pro: simple. Con: loses who clicked.
  3. A login screen per person (m5 mock issuer), token kept in the server-side session object, role read from the token. Pro: m5 sees the real user and row-level security filters lists. Con: the user must know their user id.
- What we chose: Option 3 in live mode. The practice role picker stays in mock mode only, labelled as practice; mock roles see only their own record types and only a doctor can approve.
- Why: The server is the authority. The page reads the role claim only to decide what to show; m5 checks the signed token on every call, so a forged display role cannot change what m5 allows.
- What we actually did: m6_ui/gate.py HttpGate.login/logout/role; login screen in m6_ui/app.py; ASHA patient list from GET /patients (m5 row-level security). M6_API_USER, M6_API_PASSWORD and M6_SERVER_IDS are gone. Tests: test_security.py test_f1_*.
- What could go wrong / weaknesses: The role claim is decoded without checking the signature on this page (display only). m5 has no 'list records' endpoint, so the record id is typed. Token lifetime is at most 15 minutes; after that the person is sent back to the login screen. The sandbox password is shared by all test users (an m5 limit). Not tried in a real browser.
- What else could be done: A user picker from m5's seed list; a 'my records' endpoint in m5; a real identity provider.
- How to change this decision later: m6_ui/gate.py, m6_ui/app.py (_login_page, _role).
- Status: done

### D-?: Live mode shows the record that m5 holds, loaded by the same id it saves   (Phase C / m6_ui / frontend-engineer / 2026-11-12)
- What we needed to decide: Security finding F2: live mode showed a local fixture but saved a different server row through an id-mapping file.
- Options we considered:
  1. Keep the mapping file. Pro: none. Con: a human can approve something they never saw.
  2. Load the record and verdict from m5 by id. Pro: what you see is what is saved. Con: needs the verify call and a typed record id.
- What we chose: Option 2.
- Why: This is the 'record attached to the wrong patient' class of error.
- What we actually did: HttpGate.load_record = GET /records/{id} then POST /records/{id}/verify; an edit = PATCH then verify; the transcript is still looked up locally by source_transcript_id (m5 has no transcript endpoint). Tests: test_f2_f3_live_*, test_live_edit_goes_to_the_server_*.
- What could go wrong / weaknesses: If the transcript is not in the local fixtures, highlights are missing and a load error is shown. Record ids must be UUIDs and are checked before use, so a typed '../' never becomes a request path.
- What else could be done: A transcript endpoint in m5.
- How to change this decision later: m6_ui/gate.py, m6_ui/app.py (_work).
- Status: done

### D-?: Hidden text-direction characters are shown as [U+XXXX] and refused in edits   (Phase C / m6_ui / frontend-engineer / 2026-11-12)
- What we needed to decide: Security finding F6: Unicode direction controls (U+202A-202E, U+2066-2069) can reorder digits on screen so a number looks different.
- Options we considered:
  1. Strip them silently. Pro: clean. Con: hides that the text was tampered with.
  2. Replace with a visible marker and warn; refuse them in edits. Pro: the reviewer sees it. Con: slightly noisy.
- What we chose: Option 2. Zero-width joiner and non-joiner stay (Kannada needs them).
- Why: A reviewer should see that something odd is in the text, not have it removed.
- What we actually did: m6_ui/highlight.py neutralise()/esc(); data.bidi_problems() uses contracts.validate.bidi_errors; banner review.bidi_found; edits refused with resolve.bidi. Tests: test_highlight.py, test_security.py (test_f6_*).
- What could go wrong / weaknesses: Browser rendering is UNVERIFIED (no real browser run).
- What else could be done: Reject these characters at m5 on input (m5 job).
- How to change this decision later: m6_ui/highlight.py.
- Status: done

### D-?: Small security fixes F4, F5, F7 and a documented limit for F8   (Phase C / m6_ui / frontend-engineer / 2026-11-12)
- What we needed to decide: Remaining findings: records stayed editable after a save (F4), the env refusal switch could be unticked (F5), the mock verifier accepted a one-letter drug (F7), no anti-framing header (F8).
- Options we considered:
  1. Fix all in code. Pro: done. Con: F8 is not possible in Streamlit config.
  2. Fix F4-F7 and document F8. Pro: honest. Con: F8 stays open.
- What we chose: Option 2.
- Why: Streamlit 1.67 has no setting for X-Frame-Options or frame-ancestors; a proxy is out of scope for a one-laptop class project.
- What we actually did: F4: after a save, answer/edit buttons are not drawn and Approve is disabled; a repeat save shows green 'already saved'. F5: MockGate(locked=True) ignores 'off' and the checkbox is disabled. F7: the mock verifier needs a whole-token match and at least 3 letters for a drug. F8: README section. Tests: test_security.py.
- What could go wrong / weaknesses: F8 is open (clickjacking from another page in the same browser). F7 is still a stand-in for the real m4 lexicon check.
- What else could be done: A reverse proxy adding X-Frame-Options: DENY.
- How to change this decision later: m6_ui/app.py, gate.py, verifier.py, README.md.
- Status: partly done

### D-?: Kannada wording fixes from the review (D-124) and new text for the safety reason codes   (Phase C / m6_ui / frontend-engineer / 2026-11-12)
- What we needed to decide: The simulated Kannada reviewer found 12 major wording problems and the app had no text for child-dose, cannot-verify, route, liquid-strength or max-daily flags.
- Options we considered:
  1. Accept all majors and add keys now. Pro: closes the gap. Con: model knowledge only, no native speaker.
  2. Wait for a native speaker. Pro: better wording. Con: misleading text stays in the app.
- What we chose: Option 1, with everything marked 'not native-validated' and sent to native review.
- Why: Texts like 'checker: correct' read as a guarantee; a negation warning that does not say the meaning may be reversed under-warns.
- What we actually did: m6_ui/i18n/kn.json + en.json (version 1.1.0, same keys, NFC): reason.C3 (meaning may be reversed), reason.C4 (has a subject), badge.ok 'checker saw nothing', one word each for red-marked / coloured words / speech recognition, approve.ready word order, fail.blind_spot (ಇಲ್ಲ and ಬೇಡ), mock banner (do not use for treatment), refusal text without the 'open flag' calque, a loud 'no doctor has checked this' box with icon, error.load without English. New: reason.code.* (out_of_range, exceeds_max_daily, unit_not_allowed, route, cannot_verify and 5 sub-reasons, shown with a 'could not check' note), gate.code.* for every m5 refusal, login/approve texts, record.v2 labels (v2.*, v2val.*). record.v2 records show route, strength, formulation, status, as-needed, food timing, age band and weight read-only. Tests: test_i18n.py, test_security.py.
- What could go wrong / weaknesses: All Kannada is AI-drafted and not native-validated; the clinical sentences (child dose, liquid strength, route) need a clinician and a native speaker. Minor review items were not all changed.
- What else could be done: A read-aloud session with two native-speaking clinic staff.
- How to change this decision later: m6_ui/i18n/kn.json and en.json (keep keys in sync; test_i18n.py checks).
- Status: needs human
