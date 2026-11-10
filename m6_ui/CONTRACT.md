# m6_ui contract

- Layer: L4 human review + L6 UI (Streamlit 1.67, bound to 127.0.0.1).
- Schema versions used (inputs, all validated with `contracts.validate` on load):
  `record.v1`, `verdict.v1`, `transcript.v1`, `card.v1`. Invalid documents are skipped, a missing
  verdict/transcript is shown as a load error and treated fail-closed.
- Inputs (MOCK MODE): `fixtures/{record,verdict,transcript,card}/valid/*.json`,
  `m6_ui/fixtures/{record,verdict,transcript}/*.json` (XSS security fixture),
  `m6_ui/fixtures/audio/tone_fx.wav` (synthetic tone, not speech),
  `results/*/failure*.md` and `results/m4_verify/e4/{catch_rates.csv,injection_results.jsonl,injection_log_*.jsonl}`
  (read-only, for screen 6).
- Inputs (MODE=live, UNVERIFIED end to end): m5 API (`POST /auth/token`, `POST /records/{uuid}/approve`,
  `POST /records/{uuid}/save` with body `{"verdict": <verdict.v1>}`; 409 = unresolved flags,
  422 = mismatch/invalid, 401/403 = auth); m4 CLI `uv run python -m m4_verify verify --record R
  --transcript T --out O` (subprocess only).
- Outputs: the Streamlit app; `results/m6_ui/mock_summary.json` (per fixture: rows, flagged rows,
  flagged-first check, Approve state, mock gate answer, markup inert); `results/m6_ui/conjunct_test_page.html`;
  screenshots `results/m6_ui/*.png` (headless Edge, Windows).
- Approval rule (UI side): Approve is disabled until every flag (check id + field path + reason)
  is confirmed or edited; the callback re-checks before calling the gate. The UI never marks a
  record saved itself; only a gate `saved` answer does.
- May write ONLY: m6_ui/, results/m6_ui/, `m6_ui/handoff/*`.
- Imports: `contracts.validate` only. Never m4/m5/m8 code.
- MOCK MODE: `MODE=mock mingw32-make m6-mock` (headless) and `mingw32-make m6-run` (app).
