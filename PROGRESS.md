# PROGRESS

NEXT STEP (2026-11-12): m5 Phase C fixes DONE (verdict per content, GET /records/{id}/review, hook gets DB encounter+transcript, trigger gates approved+saved). RUNNING: m2 ASR on dev. Next: (1) after m2: record.v2 migration of m3 (Sonnet) + m4 (Opus) + adapter; m6 to use /review for saved records; integration test hygiene (timestamps); (2) m7 refresh: E1 from m2, LLM comparison rerun; (3) C2 final audits (integrity Opus, security Opus incl. gitleaks); (4) C3 make eval-test ONCE; (5) C4 report + demo; Phase D. Max 2 agents.

NOTE: on Windows set `export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra` before `uv run` (path-length limit, D-3). Use `mingw32-make` for make.
MODEL POLICY (D-65, user request 2026-11-10): Sonnet for kannada-language-reviewer, clinical-reviewer and fix passes (except m4); Opus for m4_verify work, scientific-integrity-auditor, security-auditor.


Status values: todo / in-progress / done / blocked.

| # | Phase | Task | Status | Date | Commit |
|---|-------|------|--------|------|--------|
| 0 | - | Resume check; save PROJECT_BRIEF.md; git init (branch main); hardware probe | done | 2026-11-09 | (pre-commit) |
| A1 | A | Architect: feasibility, layout, lockfile, contracts+fixtures+validator, CI, docs (severity/metrics/hypothesis), agents+skills | done | 2026-11-09 | ef3a288 |
| A2 | A | Seed PROGRESS/HUMAN_TODO/DECISIONS; commit | done | 2026-11-09 | ef3a288 |
| B1a | B | m1 text data: lexicon, templates, generator, split, lock | done (test split frozen; REFREEZE-1 D-109) | 2026-11-10 | 9a3faf8 |
| B1b | B | m1 audio: TTS + public real speech + manifest | done (344 convs MMS + pitch-shifted test voice; clean on disk, variants on demand; FLEURS 250) | 2026-11-12 | a7ba312 |
| B1r | B | m1 reviews + fixes + gate | done (3 reviews D-90,D-91,D-93; fix pass + REFREEZE-1 D-104..D-110) | 2026-11-10 | 66ff51a |
| B4 | B | m4_verify build + reviews + gate | done (fix pass D-111..D-116; M4-1 guard fixed; E4 dev rerun) | 2026-11-11 | 36d203a |
| B2 | B | m2_asr build + reviews + gate | todo | | |
| B3 | B | m3_extract build + reviews + gate | done (fix pass D-117..D-121; clinical review D-122 -> record.v2 in Phase C) | 2026-11-11 | 18bb537 |
| B5 | B | m5_backend build + reviews + gate | done (fix pass verified D-103; open: m4 wiring + m6 adapt in Phase C) | 2026-11-10 | 4f3c5ad |
| B6 | B | m6_ui build + reviews + gate | done (reviews D-123 security, D-124 kannada; fixes in the Phase C m6 pass) | 2026-11-11 | 6440bbd |
| B7 | B | m7_eval build + reviews + gate | built (make eval on dev; E1 waits for m2; LLM comparison stale) reviews in C2 | 2026-11-12 | 38e4034 |
| B8 | B | m8_helper build + reviews + gate | built (H4 not met; D-138..) reviews pending | 2026-11-12 | c7d1cba |
| C1 | C | Integration boundaries + e2e + fresh-clone make eval | in-progress (m4 wired into m5, 10/10 dev e2e, 0 contract mismatches; m5 fix + v2 migration pending; fresh clone pending) | 2026-11-12 | 4ae68f9 |
| C2 | C | Final audits (integrity, security) + fixes | todo | | |
| C3 | C | make eval-test once (ALLOW_TEST=1) + log | todo | | |
| C4 | C | docs/final_report_draft.md + demo script | todo | | |
| D1 | D | Package: STRUCTURE.md, gitleaks/pip-audit, fresh-clone repro, tag v1.0-submission | todo | | |
