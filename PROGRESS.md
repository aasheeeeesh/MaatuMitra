# PROGRESS

NEXT STEP (2026-11-10): m3_extract (B3) and m6_ui (B6) builders RESUMED; the user asked for only these two now. Still stopped, resume later from on-disk state: m5 security audit (re-check results/m5_backend/access_matrix_summary.json, rewritten by its rerun); m4 Kannada review; m1+m4 clinical review; m1+m4 integrity audit (it had found a dosing-instruction sentence frame shared by dev and test: possible leak). After that: m1/m4 fixes, m4 E4 on DEV gold, B1b audio, m2. At most 3 agents at a time.

NOTE: on Windows set `export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra` before `uv run` (path-length limit, D-3). Use `mingw32-make` for make.
MODEL POLICY (D-65, user request 2026-11-10): Sonnet for kannada-language-reviewer, clinical-reviewer and fix passes (except m4); Opus for m4_verify work, scientific-integrity-auditor, security-auditor.


Status values: todo / in-progress / done / blocked.

| # | Phase | Task | Status | Date | Commit |
|---|-------|------|--------|------|--------|
| 0 | - | Resume check; save PROJECT_BRIEF.md; git init (branch main); hardware probe | done | 2026-11-09 | (pre-commit) |
| A1 | A | Architect: feasibility, layout, lockfile, contracts+fixtures+validator, CI, docs (severity/metrics/hypothesis), agents+skills | done | 2026-11-09 | ef3a288 |
| A2 | A | Seed PROGRESS/HUMAN_TODO/DECISIONS; commit | done | 2026-11-09 | ef3a288 |
| B1a | B | m1 text data: lexicon, templates, generator, split, lock | done (test split frozen) | 2026-11-10 | 9a3faf8 |
| B1b | B | m1 audio: TTS + public real speech + manifest | todo | | |
| B1r | B | m1 reviews + fixes + gate | in-progress (clinical + integrity running) | 2026-11-10 | |
| B4 | B | m4_verify build + reviews + gate | in-progress (built c6fdf72; reviews running) | 2026-11-10 | c6fdf72 |
| B2 | B | m2_asr build + reviews + gate | todo | | |
| B3 | B | m3_extract build + reviews + gate | in-progress | 2026-11-10 | |
| B5 | B | m5_backend build + reviews + gate | in-progress (built c6fdf72; security audit running) | 2026-11-10 | c6fdf72 |
| B6 | B | m6_ui build + reviews + gate | in-progress | 2026-11-10 | |
| B7 | B | m7_eval build + reviews + gate | todo | | |
| B8 | B | m8_helper build + reviews + gate | todo | | |
| C1 | C | Integration boundaries + e2e + fresh-clone make eval | todo | | |
| C2 | C | Final audits (integrity, security) + fixes | todo | | |
| C3 | C | make eval-test once (ALLOW_TEST=1) + log | todo | | |
| C4 | C | docs/final_report_draft.md + demo script | todo | | |
| D1 | D | Package: STRUCTURE.md, gitleaks/pip-audit, fresh-clone repro, tag v1.0-submission | todo | | |
