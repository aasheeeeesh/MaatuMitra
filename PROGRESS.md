# PROGRESS

NEXT STEP (2026-11-11): fix passes DONE for m1 (66ff51a, REFREEZE-1), m4 (36d203a), m3 (D-117..D-121). Max 2 agents at a time. Next: (1) remaining reviews: m3 clinical (Sonnet); m6 kannada (Sonnet) + security (Opus); (2) B1b audio (TTS + public real speech; may only ADD to test.lock); (3) m2 ASR; (4) m7 eval (incl. rerun m3 LLM comparison, cluster bootstrap); (5) m8 helper (first to cut); Phase C (wire m4 into m5, adapt m6 to new /save, e2e, final audits, make eval-test once, report); Phase D.

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
| B4 | B | m4_verify build + reviews + gate | done (fix pass D-111..D-116; M4-1 guard fixed; E4 dev rerun) | 2026-11-11 | 36d203a |
| B2 | B | m2_asr build + reviews + gate | todo | | |
| B3 | B | m3_extract build + reviews + gate | in-progress (fix pass done D-117..D-121; clinical review pending) | 2026-11-11 | (this commit) |
| B5 | B | m5_backend build + reviews + gate | done (fix pass verified D-103; open: m4 wiring + m6 adapt in Phase C) | 2026-11-10 | 4f3c5ad |
| B6 | B | m6_ui build + reviews + gate | in-progress (built; reviews pending: kannada, security) | 2026-11-10 | 67b2234 |
| B7 | B | m7_eval build + reviews + gate | todo | | |
| B8 | B | m8_helper build + reviews + gate | todo | | |
| C1 | C | Integration boundaries + e2e + fresh-clone make eval | todo | | |
| C2 | C | Final audits (integrity, security) + fixes | todo | | |
| C3 | C | make eval-test once (ALLOW_TEST=1) + log | todo | | |
| C4 | C | docs/final_report_draft.md + demo script | todo | | |
| D1 | D | Package: STRUCTURE.md, gitleaks/pip-audit, fresh-clone repro, tag v1.0-submission | todo | | |
