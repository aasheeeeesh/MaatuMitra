# m6_ui plan (frontend-engineer, 2026-11-10)

Written BEFORE tests and code. Kannada UI strings are AI-drafted and **not native-validated**.

## Goal

A Streamlit review app (layers L4 human review + L6 UI) that makes a dangerous extraction
error hard to miss before a human approves a record. Runs fully on fixtures (`MODE=mock`).

## Files

| file | job |
|---|---|
| `app.py` | Streamlit entry script (thin: wires screens together) |
| `i18n.py`, `i18n/en.json`, `i18n/kn.json` | every UI string; versioned (`_meta.version`); identical keys |
| `theme.py`, `static/style.css` | palette (single source of colours) + CSS; contrast is computed in tests |
| `static/fonts/NotoSansKannada-VF.ttf`, `static/fonts/OFL.txt` | bundled font (notofonts release NotoSansKannada-v2.006, SIL OFL 1.1) |
| `.streamlit/config.toml` | 127.0.0.1, static serving, theme, minimal toolbar, no usage stats |
| `data.py` | load + validate record/verdict/transcript/card fixtures (`contracts.validate` only) |
| `review.py` | pure logic: record -> field rows, verdict flags -> rows, flagged-first order, resolution state, `approve_enabled` |
| `highlight.py` | escape ALL transcript text, then wrap evidence spans in markup |
| `audio.py` | synthetic tone WAV fixture (stdlib `wave`), cut `audio_start..audio_end` |
| `gate.py` | server-side save gate client: `MockGate` (mirrors m5 rules, can be forced to refuse), `HttpGate` (m5 API, live) |
| `verifier.py` | re-run the verifier after an edit: `MockVerifier` (stand-in on fixtures), `SubprocessVerifier` (live: `uv run python -m m4_verify verify ...`, no import) |
| `failures.py` | screen 6 data: `results/*/failure*.md`, else escaped errors in `results/m4_verify/e4/`, else `fixtures/failure_cases.json` |
| `conjuncts.json` | tricky Kannada conjunct list (test data, not UI text) |
| `mock_run.py` | `make m6-mock`: builds every fixture review model, writes `results/m6_ui/mock_summary.json` and the conjunct HTML test page |
| `fixtures/` | m6-only fixtures: XSS transcript/record/verdict, `tone.wav`, failure-case list |

## Screens

1. Role picker: 4 big buttons (Material icons + text): ASHA, nurse, physician, pharmacist. Mock login only (no token in URL, nothing secret in the browser).
2. Record / upload: `st.audio_input` + `st.file_uploader`; a status panel with icon + text ("no audio yet" / "audio received, N s"). Streamlit's own widget shows the live "recording" state; MOCK MODE then picks a fixture record (no ASR is run, said on screen).
3. Review: transcript with evidence highlighted (flagged evidence: colour + thick underline + "!" marker); field rows FLAGGED FIRST, each with colour + icon + text label; per flag: failing check reason in Kannada + English (check-id template from i18n + verifier's raw reason), "play this part" (or "no timing available"), big Yes (confirm) / No (edit) buttons.
4. Approve: disabled until every flag (keyed by check id + field path + reason) is confirmed or edited. Edits re-run the verifier; new flags must be resolved too. Approve calls `gate.approve` then `gate.save`; a refusal is shown with icon + label + reason, status stays "not saved".
5. Counselling tab: placeholder (m8 not built) reading `fixtures/card`; big topic buttons; "not sure, ask a doctor" panel; card status + clinician_reviewed shown.
6. "Where it failed" tab: real escaped errors from m4 E4 results (rate < 1), with examples.
Plus a "Kannada rendering test" tab listing tricky conjuncts.

## Rules mapped to tests (written before code)

| rule | test |
|---|---|
| flagged-first ordering | `test_review.py` (logic) + `test_app.py` (rendered order) |
| Approve disabled until every flag individually resolved | `test_app.py` |
| server refusal handled | `test_app.py` (MockGate forced refusal + real "unresolved flags" refusal), `test_gate.py` (HttpGate via httpx.MockTransport) |
| language toggle | `test_app.py` |
| escaped HTML (XSS) | `test_highlight.py` + `test_app.py` on the XSS fixture |
| no hard-coded Kannada in `.py` | `test_i18n.py` greps `m6_ui/**/*.py` for U+0C80..U+0CFF |
| identical i18n keys, every `t("key")` exists | `test_i18n.py` |
| font >= 18 px, targets >= 48 px, contrast >= 4.5:1 | `test_design.py` (parses config/CSS, computes WCAG ratios) |
| 127.0.0.1 | `test_design.py` parses `.streamlit/config.toml`; `module.mk` passes `--server.address 127.0.0.1` too |
| font file + licence | `test_design.py` (sha256, `OFL-1.1` text, Kannada glyphs in cmap via fontTools if present) |
| play this part | `test_audio.py` (cut length = end - start; null -> no timing) |
| verifier re-run | `test_verifier.py` (edit clears C4/C7 on that field; unsupported value raises C2; subprocess failure -> fail-closed flag) |

## Changes made during the build

- Row granularity: one row per symptom (name + present), per advice item (text + negated), per
  follow-up, and one row per medication attribute (drug, dose value+unit, times per day, days,
  negated). Flags on sub-paths land on the item's row; unmatched flags land on a "whole record" row.
- Confirm is per ROW (all current flags on that row), keyed by check id + path + reason.
- Mock-only start defaults via env (`M6_DEMO_ROLE`, `M6_DEMO_PAGE`, `M6_DEMO_RECORD`, `M6_DEMO_LANG`) for demos/screenshots.
- Headless Edge screenshots of the live app came out blank; layout stays UNVERIFIED (see handoff).

## Not possible to verify here (UNVERIFIED)

Visual conjunct shaping on Android/Linux, real 360 px phone layout, Streamlit audio widget
behaviour on phones, live m5/m4 end-to-end (needs Postgres + .env).
