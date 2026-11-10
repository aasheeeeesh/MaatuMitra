### D-?: Build the review app in Streamlit with our own palette, CSS and bundled font   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: Which tool to build the review screens with, and how to stop it looking like a default template.
- Options we considered:
  1. Streamlit with custom CSS (the brief's default). Pro: already a base dependency, pure Python, has a built-in test tool (AppTest). Con: limited control over layout; some styling depends on Streamlit's internal HTML names, which can change.
  2. Gradio. Pro: quick demos. Con: not the default, weaker page structure for a multi-screen app, no reason found that Streamlit cannot do the job.
  3. A hand-written web page (HTML + JavaScript) on FastAPI. Pro: full control. Con: much more code, more security work, slower to build and test.
- What we chose: Option 1, Streamlit 1.67 with a theme in `m6_ui/.streamlit/config.toml` plus a small CSS file.
- Why: It runs today with no new packages and AppTest lets us test the important behaviours automatically. We accepted that the CSS hooks into Streamlit's internal class names and may need fixing after an upgrade.
- What we actually did: `m6_ui/app.py`, `m6_ui/theme.py` (palette = single source of colours, WCAG contrast maths), `m6_ui/static/style.css`, `m6_ui/.streamlit/config.toml` (baseFontSize 18, minimal toolbar, no usage stats). Run `mingw32-make m6-run`.
- What could go wrong / weaknesses: CSS selectors such as `.stButton button` are not a public API. The look at 360 px was NOT confirmed on a real phone (headless screenshots of the live app came out blank; see the screenshot entry).
- What else could be done: pin the Streamlit version in uv.lock and add a visual regression test with a real browser (Playwright) when one is available.
- How to change this decision later: replace `app.py`; the logic in `review.py`, `highlight.py`, `gate.py`, `verifier.py` has no Streamlit code and can be reused.
- Status: done

### D-?: Flagged items first, never colour alone, reasons always visible   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: How to show the verifier's flags so a busy health worker cannot miss them.
- Options we considered:
  1. One list in record order with a red mark on flagged items. Pro: simple. Con: a flag at the bottom can be missed; colour alone fails for colour-blind users and in sunlight.
  2. Flagged items first, each with red colour AND a "!" icon AND a text label ("CHECK THIS"), and the reason shown directly (not behind a click). Pro: hard to miss. Con: longer screen.
  3. A separate "problems" tab. Pro: tidy. Con: hides flags behind a click (forbidden by the brief).
- What we chose: Option 2. Rows: one per symptom, per advice item, per follow-up, and one per medication attribute (drug, dose, times per day, days, take/do-not-take). A flag that does not fit any row goes on a "Whole record" row at the very top, so it is never dropped. A missing verdict or an empty check list becomes a fail-closed flag.
- Why: The app's one job is to make a dangerous extraction error impossible to miss. Each flag shows the check's plain reason in BOTH Kannada and English plus the verifier's raw English message.
- What we actually did: `m6_ui/review.py` (`build_rows`, `flags_from_verdict`), `_row_head` in `app.py`; tests `test_review.py`, `test_app.py::test_flagged_fields_are_rendered_first_with_colour_icon_and_label`, `::test_flag_reasons_are_visible_without_a_click_in_both_languages`.
- What could go wrong / weaknesses: The plain-language reasons per check id (C1..C8) are our own wording, not native-validated, and the Kannada wording may be unclear to ASHA workers.
- What else could be done: test the wording with real users; add a short spoken explanation (TTS) for low-literacy users.
- How to change this decision later: `review.py` (row granularity), `i18n/*.json` (`reason.C1`..`reason.C8`).
- Status: done

### D-?: Approve stays locked until every flag is answered; the server decides "saved"   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: When the Approve button is allowed, and who decides that a record is saved.
- Options we considered:
  1. Allow Approve any time and rely on the server. Pro: simple. Con: invites click-through; the brief forbids it.
  2. Lock Approve until every flag is individually answered ("Yes, this is correct" or "No, change it"), then call the server gate and show its answer. Pro: matches the brief; the server stays the authority. Con: more taps.
- What we chose: Option 2. A flag is identified by check id + field path + reason, so a NEW flag created by a re-check after an edit is not counted as answered. The approve callback checks the rule again (it does not trust the disabled button). Approve calls `approve` then `save` on the gate; any refusal is shown in red with icon, title, reason, the server's own message and "Record status: NOT saved". Records with no flags still need a human click (never auto-approved).
- Why: Nothing may be saved without a human decision, and the server, not the browser, enforces the final rule.
- What we actually did: `review.approve_enabled`, `review.mark_row`, `app._approve`, `app._gate_result`; tests `test_app.py::test_approve_disabled_until_every_flag_is_individually_resolved`, `::test_server_refusal_is_shown_and_record_is_not_saved`, `::test_forced_server_refusal_is_handled`, `::test_clean_record_saves_only_after_click`.
- What could go wrong / weaknesses: With m5's documented rule (save refused while any check flags), a human "Yes, this is correct" can NEVER lead to "saved" while the verifier still flags. The UI shows this refusal honestly, but the workflow has no "human override with reason" yet (open question).
- What else could be done: a contract change (for example a `review.v1` document with the reviewer's answer per flag) so m5 can accept a confirmed flag with an audit entry.
- How to change this decision later: `review.py`, `gate.py`, and (with the architect) contracts/m5.
- Status: partly done (needs a human/architect decision on override)

### D-?: Server-side gate client: mock that mirrors m5's rules, HTTP client for live mode   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: How the UI talks to the save gate without importing m5 code and while m5 may not be running.
- Options we considered:
  1. Import m5's FastAPI app. Con: forbidden (no cross-module imports).
  2. A `MockGate` that copies the rules written in m5_backend/CONTRACT.md, plus an `HttpGate` for the real API. Pro: works alone; same interface. Con: the mock can drift from the real server.
- What we chose: Option 2. MockGate refuses: no approval, invalid verdict, record_id mismatch (422), empty checks / auto_acceptable false / any flag (409); `force_refuse` (env `M6_MOCK_GATE_REFUSE=1` or a checkbox in mock mode) refuses every save for tests and demos. HttpGate logs in with `POST /auth/token`, keeps the token in server-side memory and sends it only in the `Authorization` header; it accepts only loopback URLs; it maps 409/422/401/403/404/network errors to labelled refusals.
- Why: The UI must be testable alone and must handle refusal visibly.
- What we actually did: `m6_ui/gate.py`; `test_gate.py` (HttpGate tested with `httpx.MockTransport`; asserts the token never appears in a URL).
- What could go wrong / weaknesses: Live mode was NOT run against a real m5 + PostgreSQL (UNVERIFIED). Live mode also needs a map from record.v1 `record_id` to m5's database UUID (`M6_SERVER_IDS` JSON file), which is a stop-gap.
- What else could be done: an integration test in Phase C with m5's database running.
- How to change this decision later: `m6_ui/gate.py` (`make_gate`, status mapping).
- Status: partly done (live UNVERIFIED)

### D-?: Edits re-run the verifier: mock stand-in in mock mode, m4 command line in live mode   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: How "edits re-run the verifier" works without importing m4.
- Options we considered:
  1. Import m4_verify. Con: forbidden.
  2. Live: run `uv run python -m m4_verify verify --record R --transcript T --out O` as a subprocess (fixed argument list, no shell, timeout). Mock: a small stand-in. Pro: keeps modules independent. Con: subprocess is slow (seconds); the stand-in is not the real logic.
  3. Do not re-check at all. Con: violates the brief.
- What we chose: Option 2. The stand-in clears the original flags only on the exact field the reviewer edited, then re-checks the new value against its evidence span (digits, Kannada digits converted to ASCII, a starter list of Kannada number words from `m6_ui/number_words.json`; units; text), re-checks every span against the transcript, and ALWAYS flags a yes/no (negation) edit for confirmation. Any subprocess failure, timeout or invalid output gives a fail-closed verdict with a `check_error` flag.
- Why: The reviewer sees immediately whether the new value is supported by what was said, and a broken verifier can never silently pass a record.
- What we actually did: `m6_ui/verifier.py`; `test_verifier.py`; `test_app.py::test_edit_reruns_verifier_and_new_flag_must_be_resolved` (editing 50 mg to 500 mg on the ASR-error fixture clears C4/C7 but raises a new C2 flag, because the ASR transcript says 50; the reviewer must confirm it).
- What could go wrong / weaknesses: The stand-in is NOT m4's logic and the number words are not native-validated. The live subprocess path was tested only with a fake command, not with real m4 (UNVERIFIED).
- What else could be done: run m4 in live mode in Phase C integration; cache a long-running verifier process instead of starting `uv` per edit.
- How to change this decision later: `m6_ui/verifier.py` (`make_verifier`, `SubprocessVerifier.cmd_prefix`).
- Status: done (live path UNVERIFIED)

### D-?: Escape all transcript text before adding highlight markup (XSS)   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: How to highlight evidence spans safely, since transcripts and records are untrusted text.
- Options we considered:
  1. Insert `<mark>` tags into the raw text, then render as HTML. Con: any `<script>` or `<img onerror>` in the text becomes live code (cross-site scripting, XSS).
  2. Cut the text at span boundaries, escape EVERY piece with `html.escape(quote=True)`, then add our own fixed tags. Pro: data can never become markup. Con: slightly more code.
- What we chose: Option 2, and every other data value (field values, reasons, card text, file contents) also goes through `esc()` before it touches HTML. Data is never passed to `st.markdown`.
- Why: The brief requires it, and Streamlit's own HTML sanitising is a second layer, not the first.
- What we actually did: `m6_ui/highlight.py`; security fixture `m6_ui/fixtures/{transcript,record,verdict}/` with `<script>`, `<img onerror>`, `<b onmouseover>` payloads in the transcript, drug name, advice, patient_ref and verdict reasons; tests `test_highlight.py`, `test_app.py::test_xss_payload_in_transcript_and_fields_renders_inert`.
- What could go wrong / weaknesses: A future developer could add an unescaped f-string. The test covers the screens that exist today only.
- What else could be done: a lint rule or test that every `st.html` call receives output of an escaping helper.
- How to change this decision later: `m6_ui/highlight.py`, `esc()` calls in `app.py`.
- Status: done

### D-?: Every UI string in versioned i18n files; Kannada is the default language   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: Where UI text lives and how the Kannada/English toggle works.
- Options we considered:
  1. Strings in the Python code. Con: forbidden; impossible to review.
  2. `m6_ui/i18n/kn.json` and `en.json` with identical keys and a `_meta.version`; a missing key raises an error (no silent English fallback). Two big language buttons at the top of every screen.
- What we chose: Option 2, Kannada first.
- Why: Users read Kannada more easily; reviewers can check one file.
- What we actually did: `m6_ui/i18n.py`, `i18n/{kn,en}.json` (version 1.0.0, `native_validated: false`); `test_i18n.py` greps every `m6_ui/**/*.py` for Kannada characters U+0C80..U+0CFF, checks identical keys, identical `{placeholders}`, and that every `t("...")` key used in code exists; `test_app.py::test_role_picker_is_first_and_language_toggle_switches_every_label`.
- What could go wrong / weaknesses: ALL Kannada strings are AI-drafted and NOT native-validated; some words (for example the transliterated "ಆ್ಯಪ್", "ಸರ್ವರ್") may be unnatural. Data text (drug names, card topics, verifier messages) is shown as it is and may be English.
- What else could be done: a native speaker reviews `kn.json` (HUMAN_TODO).
- How to change this decision later: edit both JSON files together and bump `_meta.version`.
- Status: needs human

### D-?: Bundle Noto Sans Kannada v2.006 (slim variable font, SIL OFL 1.1) locally   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: Which Kannada font to ship and how to load it without a CDN.
- Options we considered:
  1. Rely on the phone's system font. Con: older/cheap phones may lack good Kannada shaping; inconsistent look.
  2. Load from Google Fonts at runtime. Con: needs internet, leaks usage to a third party, brief says local.
  3. Bundle the official notofonts release. Pro: offline, consistent. Con: ~210 KB to download.
- What we chose: Option 3: `NotoSansKannada[wght].ttf` from the "full/slim-variable-ttf" folder of release NotoSansKannada-v2.006 (one file, weights 100-900, 210,928 bytes), renamed `m6_ui/static/fonts/NotoSansKannada-VF.ttf`, served by Streamlit static serving and declared both in `config.toml` (`theme.fontFaces`) and by `@font-face` in the CSS.
- Why: One small file covers every weight; the licence allows bundling.
- What we actually did: fetched on 2026-11-10 `https://api.github.com/repos/notofonts/kannada/releases` and `https://github.com/notofonts/kannada/releases/download/NotoSansKannada-v2.006/NotoSansKannada-v2.006.zip` (sha256 `902b1b92018f7c96862d68d0a39ef03b978203cd4c3f55d6760f597657b51c44`); font sha256 `b062c3ec551cee95b88cbbc470036c81b69c788516fd8910ba6ae6e3c70d9bb2`; licence text `https://raw.githubusercontent.com/notofonts/kannada/main/OFL.txt` (SIL Open Font License 1.1, copy in `static/fonts/OFL.txt`); GitHub licence API reports `OFL-1.1`. `test_design.py` checks the hash, the licence text and (with fontTools) that every Kannada character in `kn.json` and `conjuncts.json` is in the font.
- What could go wrong / weaknesses: Variable fonts are widely supported but very old Android WebViews may not support them (UNVERIFIED).
- What else could be done: also ship static Regular + Bold as a fallback.
- How to change this decision later: replace the file in `m6_ui/static/fonts/`, update `FONT_SHA256` in `test_design.py`, `config.toml` and the licence row.
- Status: done

### D-?: Conjunct rendering test page, checked by eye only in headless Edge on Windows   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: How to check that Kannada conjuncts (joined consonants) draw correctly.
- Options we considered:
  1. Automated tests only. Con: tests can check strings and font coverage, not how letters are drawn.
  2. A test page plus a real screenshot looked at by eye. Pro: catches dotted circles and broken joins. Con: needs a browser per platform.
- What we chose: Both: a "Letter test" screen in the app and a standalone `results/m6_ui/conjunct_test_page.html` (written by `make m6-mock`) listing 17 items (ಕ್ಷ, ಜ್ಞ, ತ್ರ, ಶ್ರೀ, ಸ್ತ್ರೀ, ರ್ಕ, ಕ್ಕೆ, ಳ್ಳ, ದ್ವ, drug words, two ZWNJ cases, Kannada digits) with their code points.
- Why: Rendering is a real risk for Kannada and cannot be proven by unit tests.
- What we actually did: headless Microsoft Edge 157 on Windows 11 screenshot `results/m6_ui/screenshot_conjuncts_edge.png`; looked at by the AI agent: the conjuncts appear joined, no dotted circles, ರ್ಕ shows the raised repha form. We could not prove the bundled font (not the Windows system font) was the one used.
- What could go wrong / weaknesses: Android and Linux rendering is UNVERIFIED; the AI agent is not a native reader; the expected look of the ZWNJ cases is UNVERIFIED.
- What else could be done: a native reader checks the page on a cheap Android phone and on Linux (HUMAN_TODO).
- How to change this decision later: edit `m6_ui/conjuncts.json`.
- Status: needs human

### D-?: Synthetic tone WAV for "play this part"; real recording state is Streamlit's own widget   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: How to test "play this part" when fixtures have no real audio, and how to show the recording state.
- Options we considered:
  1. Real Kannada speech audio. Con: we have none in fixtures; data rules.
  2. A synthetic 12 s, 8 kHz tone with a beep every second (stdlib `wave`, deterministic), cut to `audio_start..audio_end`. Pro: tiny (192 KB), reproducible, testable (clip length is checked). Con: not speech.
- What we chose: Option 2; "No timing available for this part" when either time is null. For recording we use `st.audio_input` (its own red recording indicator) plus our status panel ("No audio yet" / "Audio received (N seconds)") and a file upload.
- Why: Lets the cut logic be tested without any speech data.
- What we actually did: `m6_ui/audio.py` (`make_tone_wav`, `cut_wav`), `m6_ui/fixtures/audio/tone_fx.wav`; tests `test_audio.py`, `test_app.py::test_play_this_part_cuts_audio_or_says_no_timing`.
- What could go wrong / weaknesses: Our app cannot see the "recording in progress" moment (it happens in the browser widget); how that widget behaves on cheap Android phones is UNVERIFIED. In mock mode, recorded audio is not transcribed (said on screen).
- What else could be done: connect m2_asr in live mode in Phase C.
- How to change this decision later: `m6_ui/audio.py`, `_page_record` and `_player` in `app.py`.
- Status: done

### D-?: Counselling tab is a placeholder on fixture cards with a clear "ask a doctor" state   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: What screen 5 shows while m8_helper does not exist.
- Options we considered:
  1. Hide the tab. Con: the "ask a doctor" state would not be designed or tested.
  2. Show fixture cards as big topic buttons, a big "Not sure / my question is not here" button that opens a red ask-a-doctor panel, and a voice input next to them that says voice needs m8.
- What we chose: Option 2. Each card shows its Kannada and English text, its status ("machine-drafted, not checked by a native speaker") and "Not checked by a doctor".
- Why: The safe fallback ("ask a doctor") must be obvious; we do not answer questions ourselves.
- What we actually did: `_page_help` in `app.py`; tests `test_app.py::test_counselling_placeholder_and_ask_a_doctor_state`, `::test_counselling_card_shows_not_validated_status`.
- What could go wrong / weaknesses: Card topics are English data; not a real helper.
- What else could be done: call m8 when it publishes an interface.
- How to change this decision later: `_page_help` in `app.py`.
- Status: partly done (waits for m8)

### D-?: "Where checks failed" panel reads real E4 misses from m4's published results   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: Which failure cases screen 6 shows.
- Options we considered:
  1. A hand-made list. Con: not real.
  2. Read published result files: any `results/*/failure*.md`, and the rows of `results/m4_verify/e4/catch_rates.csv` where caught < n, with up to 2 example injections each; fall back to a hand-made list marked "Example only (not measured)".
- What we chose: Option 2. Today it shows real misses such as "transcript: negation drop, text_only, caught 0 of 200" and "record: wrong patient_ref, no_encounter_index", plus the known blind spot sentence.
- Why: Users should see where the green badge can be wrong.
- What we actually did: `m6_ui/failures.py`; `test_failures.py`, `test_app.py::test_failure_panel_lists_cases`.
- What could go wrong / weaknesses: These are planted mistakes on synthetic fixture text, not real-world error rates; the numbers are m4's, not re-checked here.
- What else could be done: read m7_eval's failure report when it exists.
- How to change this decision later: `m6_ui/failures.py`.
- Status: done

### D-?: Bind to 127.0.0.1 only; no tokens in URLs; Streamlit chrome hidden   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: How to keep the app private and simple.
- Options we considered:
  1. Defaults. Con: Streamlit may listen on all network interfaces and shows developer menus.
  2. `server.address = "127.0.0.1"` in `m6_ui/.streamlit/config.toml` AND `--server.address 127.0.0.1` in `make m6-run`; the app refuses to run if started with another address; XSRF protection on; usage statistics off; toolbar "minimal"; error details hidden.
- What we chose: Option 2. Demo start settings are environment variables (`M6_DEMO_*`, mock only), never URL parameters.
- Why: Brief section 2.4 and AGENT 7 security rules.
- What we actually did: started the server on 2026-11-10: `netstat` showed `LISTENING 127.0.0.1:8517` only; `/_stcore/health` 200; the bundled font served at `/app/static/fonts/NotoSansKannada-VF.ttf` (200, 210,928 bytes). `test_design.py::test_server_binds_to_loopback_and_hides_chrome`.
- What could go wrong / weaknesses: Streamlit reads `m6_ui/.streamlit/config.toml` only when started from inside `m6_ui/` (the make target does this; the command-line flag covers the address either way).
- What else could be done: a reverse proxy with authentication if this ever leaves the laptop (out of scope).
- How to change this decision later: `m6_ui/.streamlit/config.toml`, `m6_ui/module.mk`.
- Status: done

### D-?: Headless screenshots of the live Streamlit app came out blank   (Phase B / m6_ui / frontend-engineer / 2026-11-10)
- What we needed to decide: How to show proof of the 360 px layout.
- Options we considered:
  1. Headless Microsoft Edge `--screenshot` at 360 px width. Pro: no new tools. Con: Streamlit draws its page with JavaScript over a websocket; headless capture may happen before that.
  2. Playwright. Con: a new dependency plus a browser download (disk is short).
  3. Check the layout by hand on a phone.
- What we chose: Tried option 1; the screenshot showed only the page background (the theme colour), so the layout is UNVERIFIED. Option 3 goes to HUMAN_TODO.
- Why: We do not claim what we could not see.
- What we actually did: `results/m6_ui/screenshot_app_360px_review_xss.png` (blank apart from background, kept as evidence of the attempt). Layout rules are tested only as CSS rules in `test_design.py` (font sizes >= 18 px, min-height >= 48 px, max-width 100%).
- What could go wrong / weaknesses: real overflow at 360 px may exist.
- What else could be done: Playwright with a waiting step, or Chrome DevTools device mode by a human.
- How to change this decision later: add a screenshot script under `m6_ui/`.
- Status: needs human
