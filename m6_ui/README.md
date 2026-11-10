# m6_ui: Kannada-first review app (layers L4 human review + L6 UI)

Built by the `frontend-engineer` agent (AI). All data is SYNTHETIC. Kannada UI strings are
AI-drafted and **not native-validated**. Not a clinical tool.

## Run it (Git Bash, repo root)

```bash
export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra
mingw32-make m6-test   # 105 tests: pure logic + Streamlit AppTest (MODE=mock)
mingw32-make m6-mock   # headless run on fixtures -> results/m6_ui/mock_summary.json + conjunct_test_page.html
mingw32-make m6-run    # app on http://127.0.0.1:8501 (MODE=mock; 127.0.0.1 only)
```

Mock-only demo defaults (environment variables, never URL parameters):
`M6_DEMO_ROLE=nurse M6_DEMO_PAGE=review M6_DEMO_RECORD=rec-m6-xss M6_DEMO_LANG=en`.
`M6_MOCK_GATE_REFUSE=1` makes the mock server refuse every save (also a checkbox on the review screen).

## Screens

1. Role picker: four big buttons (icon + text). Practice login, no password.
2. Record / upload: `st.audio_input` + file upload, status panel ("no audio yet" / "audio received, N s").
   MOCK MODE does not transcribe; it picks a fixture record (said on screen).
3. Review: transcript with evidence highlighted (flagged evidence: red background + thick underline +
   "!" marker); items with FLAGGED ones first, each with colour + icon + text label; the failing
   check's reason in Kannada AND English plus the verifier's raw message; "play this part"
   (cuts `audio_start..audio_end` from a synthetic tone in mock) or "no timing available".
4. Approve: locked until every flag is answered ("Yes, this is correct" or "No, change it").
   An edit re-runs the verifier; new flags must be answered too. Approve calls the server-side
   gate (approve, then save); a refusal is shown in red with icon, title, reason and "NOT saved".
5. Advice cards: placeholder (m8 not built) from `fixtures/card`, big topic buttons, a
   "Not sure / ask a doctor" button that shows a clear ask-a-doctor panel, voice input beside it.
6. Where checks failed: real escaped planted mistakes from `results/m4_verify/e4/catch_rates.csv`
   (plus any `results/*/failure*.md`), else a hand-made fallback list marked "not measured".
Plus a Kannada letter (conjunct) test page.

## Files

`app.py` (screens), `review.py` (rows, flagged-first, Approve rule), `highlight.py` (escape then
highlight), `gate.py` (MockGate / HttpGate), `verifier.py` (mock stand-in / m4 subprocess),
`audio.py` (tone fixture + clip cutting), `data.py` (fixtures + validation), `failures.py`,
`theme.py` + `static/style.css` (palette, contrast maths, CSS), `i18n/{kn,en}.json`,
`conjuncts.json`, `number_words.json`, `.streamlit/config.toml`, `fixtures/` (XSS record,
tone WAV, failure list), `static/fonts/` (Noto Sans Kannada v2.006 variable font + OFL.txt).

## Live mode (UNVERIFIED end to end)

`MODE=live API_URL=http://127.0.0.1:8000 M6_API_USER=<uuid> M6_API_PASSWORD=<sandbox pw>
M6_SERVER_IDS=<json file {record_id: m5 uuid}> mingw32-make m6-run`. Credentials stay in the
server process (never sent to the browser, never in a URL). Edits re-run the real verifier with
`uv run python -m m4_verify verify ...` in a subprocess. Not run against a live m5 database here.

## Known limits

See handoff/decisions.md. Main ones: Kannada strings not native-validated; conjuncts checked by
eye only in headless Edge on Windows (Android/Linux UNVERIFIED); 360 px layout checked only by a
headless screenshot; the mock verifier is a stand-in; with m5's documented rules a human
"confirm" can never lead to "saved" while a flag remains (see handoff/open_questions.md).
