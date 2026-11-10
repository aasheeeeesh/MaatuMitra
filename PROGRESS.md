# PROGRESS

NEXT STEP (2026-11-10): m1 fix pass + REFREEZE-1 DONE (D-104..D-110; one commit). DO NOT run m4 `e4`/`tune-c7` on data/ until M4-1 is fixed. Max 2 agents at a time. Next fix passes: (1) m4 Opus: M4-1 guard (filter by dev.txt), field-level catch attribution, C4 child doses 'not checkable' + separate cannot-verify reason, units per drug, max_daily, confusable swaps from lexicon, negation gaps (D-93), README numbers; then E4 on DEV gold; (2) m3 Sonnet: remove test-only words, ಆಗಿದ್ದರೆ/ಜ್ವರವಿಲ್ಲ/ಪ್ಯಾಕೆಟ್, accept ORS short+long vowel and un-xfail test_multi_token_names_longest_match, re-score dev on regenerated data, honest labels. Then remaining reviews (m3 clinical; m6 kannada+security); B1b audio; m2; m7; m8; Phase C.

NOTE: on Windows set `export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra` before `uv run` (path-length limit, D-3). Use `mingw32-make` for make.
MODEL POLICY (D-65, user request 2026-11-10): Sonnet for kannada-language-reviewer, clinical-reviewer and fix passes (except m4); Opus for m4_verify work, scientific-integrity-auditor, security-auditor.


Status values: todo / in-progress / done / blocked.

| # | Phase | Task | Status | Date | Commit |
|---|-------|------|--------|------|--------|
| 0 | - | Resume check; save PROJECT_BRIEF.md; git init (branch main); hardware probe | done | 2026-11-09 | (pre-commit) |
| A1 | A | Architect: feasibility, layout, lockfile, contracts+fixtures+validator, CI, docs (severity/metrics/hypothesis), agents+skills | done | 2026-11-09 | ef3a288 |
| A2 | A | Seed PROGRESS/HUMAN_TODO/DECISIONS; commit | done | 2026-11-09 | ef3a288 |
| B1a | B | m1 text data: lexicon, templates, generator, split, lock | done (test split frozen; REFREEZE-1 D-109) | 2026-11-10 | 9a3faf8 |
| B1b | B | m1 audio: TTS + public real speech + manifest | todo | | |
| B1r | B | m1 reviews + fixes + gate | done (3 reviews D-90,D-91,D-93; fix pass + REFREEZE-1 D-104..D-110) | 2026-11-10 | 66ff51a |
| B4 | B | m4_verify build + reviews + gate | in-progress (built c6fdf72; reviews running) | 2026-11-10 | c6fdf72 |
| B2 | B | m2_asr build + reviews + gate | todo | | |
| B3 | B | m3_extract build + reviews + gate | in-progress (built; reviews pending: clinical, integrity) | 2026-11-10 | ce46096 |
| B5 | B | m5_backend build + reviews + gate | done (fix pass verified D-103; open: m4 wiring + m6 adapt in Phase C) | 2026-11-10 | 4f3c5ad |
| B6 | B | m6_ui build + reviews + gate | in-progress (built; reviews pending: kannada, security) | 2026-11-10 | 67b2234 |
| B7 | B | m7_eval build + reviews + gate | todo | | |
| B8 | B | m8_helper build + reviews + gate | todo | | |
| C1 | C | Integration boundaries + e2e + fresh-clone make eval | todo | | |
| C2 | C | Final audits (integrity, security) + fixes | todo | | |
| C3 | C | make eval-test once (ALLOW_TEST=1) + log | todo | | |
| C4 | C | docs/final_report_draft.md + demo script | todo | | |
| D1 | D | Package: STRUCTURE.md, gitleaks/pip-audit, fresh-clone repro, tag v1.0-submission | todo | | |
