# PROGRESS

NEXT STEP (2026-11-10): reviews DONE: integrity (D-90), clinical (D-91, plans REFREEZE-1). RUNNING: m5 security audit, Kannada review (m4+m1+m3, Sonnet). DO NOT run m4 `e4`/`tune-c7` on data/ until M4-1 is fixed. Max 2 agents at a time. Then fix passes in this order: (1) m1 Sonnet: REFREEZE-1 (child-dose templates a3,e8,h2,h3,i5 + e2 + lexicon fixes + Kannada fixes + annotation_guide test-only words) in ONE commit; (2) m4 Opus: M4-1 guard, field-level catch attribution, C4 child + cannot-verify reason, units per drug, confusable swaps, README numbers; then E4 on DEV gold; (3) m3 Sonnet: remove test-only words, rerun dev, honest labels; (4) m5: security findings + D-80. Then m3/m6 remaining reviews; B1b audio; m2.

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
| B3 | B | m3_extract build + reviews + gate | in-progress (built; reviews pending: clinical, integrity) | 2026-11-10 | ce46096 |
| B5 | B | m5_backend build + reviews + gate | in-progress (security audit done D-92; fix pass pending) | 2026-11-10 | c6fdf72 |
| B6 | B | m6_ui build + reviews + gate | in-progress (built; reviews pending: kannada, security) | 2026-11-10 | 67b2234 |
| B7 | B | m7_eval build + reviews + gate | todo | | |
| B8 | B | m8_helper build + reviews + gate | todo | | |
| C1 | C | Integration boundaries + e2e + fresh-clone make eval | todo | | |
| C2 | C | Final audits (integrity, security) + fixes | todo | | |
| C3 | C | make eval-test once (ALLOW_TEST=1) + log | todo | | |
| C4 | C | docs/final_report_draft.md + demo script | todo | | |
| D1 | D | Package: STRUCTURE.md, gitleaks/pip-audit, fresh-clone repro, tag v1.0-submission | todo | | |
