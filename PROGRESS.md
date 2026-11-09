# PROGRESS

NEXT STEP: Phase B wave 1 running in parallel: m1 text-data builder (B1a), m4_verify builder (B4), m5_backend builder (B5). Then reviews for each; then wave 2 (B1b audio, m2, m3, m6).

NOTE: on Windows set `export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra` before `uv run` (path-length limit, D-3). Use `mingw32-make` for make.

Status values: todo / in-progress / done / blocked.

| # | Phase | Task | Status | Date | Commit |
|---|-------|------|--------|------|--------|
| 0 | - | Resume check; save PROJECT_BRIEF.md; git init (branch main); hardware probe | done | 2026-11-09 | (pre-commit) |
| A1 | A | Architect: feasibility, layout, lockfile, contracts+fixtures+validator, CI, docs (severity/metrics/hypothesis), agents+skills | done | 2026-11-09 | ef3a288 |
| A2 | A | Seed PROGRESS/HUMAN_TODO/DECISIONS; commit | done | 2026-11-09 | ef3a288 |
| B1a | B | m1 text data: lexicon, templates, generator, split, lock | in-progress | 2026-11-09 | |
| B1b | B | m1 audio: TTS + public real speech + manifest | todo | | |
| B1r | B | m1 reviews + fixes + gate | todo | | |
| B4 | B | m4_verify build + reviews + gate | in-progress | 2026-11-09 | |
| B2 | B | m2_asr build + reviews + gate | todo | | |
| B3 | B | m3_extract build + reviews + gate | todo | | |
| B5 | B | m5_backend build + reviews + gate | in-progress | 2026-11-09 | |
| B6 | B | m6_ui build + reviews + gate | todo | | |
| B7 | B | m7_eval build + reviews + gate | todo | | |
| B8 | B | m8_helper build + reviews + gate | todo | | |
| C1 | C | Integration boundaries + e2e + fresh-clone make eval | todo | | |
| C2 | C | Final audits (integrity, security) + fixes | todo | | |
| C3 | C | make eval-test once (ALLOW_TEST=1) + log | todo | | |
| C4 | C | docs/final_report_draft.md + demo script | todo | | |
| D1 | D | Package: STRUCTURE.md, gitleaks/pip-audit, fresh-clone repro, tag v1.0-submission | todo | | |
