# AI usage log (constraint 9)

Every piece of AI-assisted work: which agent, which module, what it generated, and what a
human must still check. Builders add entries through `<module>/handoff/ai_usage.md`.

## architect agent (Claude, via Claude Code), Phase A, 2026-11-09

- **Module**: repo skeleton (no module logic).
- **Generated**: pyproject.toml and uv.lock (resolved by uv), Makefile and 8 module.mk
  stubs, all folder READMEs and module stubs (CONTRACT.md, plan.md, placeholder tests,
  handoff/README.md), 8 JSON Schemas, contracts/validate.py, contracts/CHANGELOG.md,
  fixtures/build_fixtures.py and the 79 fixture files it writes,
  fixtures/lexicon/drugs_fixture.csv, the Kannada negation table YAML,
  infra/scripts/{merge_handoff,check_split_lock,eval_test_guard}.py, tests/ (74 tests),
  CI workflow, .gitignore, .gitattributes, .env.example, docker-compose.yml,
  .pre-commit-config.yaml, LICENSE_PLACEHOLDER.md, docs (this file, DECISIONS_EXPLAINED.md,
  glossary, severity, metrics, hypothesis, licences, open questions, stubs),
  HUMAN_TODO.md, README.md, STRUCTURE.md stub, infra/inventory.md, 14 agent files and
  5 skills.
- **How it was checked**: `mingw32-make test` (74 passed, 9 placeholders skipped), `lint`,
  `validate-fixtures` (79 files OK), `split-lock` (warning: no lock yet), `audit`
  (pip-audit: no known vulnerabilities), `eval-test` (refuses), plus a fresh-copy run.
- **What a human must still check**:
  - ALL Kannada text (fixtures, negation table examples, skill phrase lists, card
    fixtures) is AI-written and NOT native-validated.
  - The negation rules and the architect's additions to them (marked
    `architect_addition`) are linguistic hypotheses.
  - Fixture drug doses and AWaRe classes come from model memory, not a fetched source.
  - Whether the pre-registration thresholds in docs/hypothesis.md are what the course wants.
  - CI has never run on GitHub.
  - The Kannada codepoint table was generated from Python's Unicode 14.0 database; newer
    Unicode additions are not covered.
