# Rules for every builder and reviewer agent (written by the orchestrator)

Read this file fully before starting. It complements PROJECT_BRIEF.md (sections 0.3, 2, 4, 6, 11) and your agent file in .claude/agents/.

## Environment
- Repo root: the folder containing this `infra/` folder. Use Git Bash with repo-relative paths.
- Before any `uv run`: `export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra` (Windows path-length workaround, D-3). Make is `mingw32-make`.
- The `python` on PATH is NOT ours. Always use `uv run python ...`.
- Free disk is only ~12 GB. Check `df -h /c` before any download > 500 MB. Put model caches in the default HF cache (outside the repo). Never put weights or large audio in tracked paths.
- Hardware: i7-12650H, 16 GB RAM, RTX 3050 Ti 4 GB VRAM, Windows 11. Ollama is installed (qwen3:4b-instruct, nomic-embed-text).

## Dependencies (shared venv; several agents run at once)
- Never run plain `uv sync` (it removes other agents' packages). Use `uv sync --inexact --extra <extra>`.
- To add a package: take the mutex, add, release:
  `until mkdir .uvlock 2>/dev/null; do sleep 5; done; uv add --optional <extra> '<pkg>==<ver>' ; rmdir .uvlock`
  (base dependency: drop `--optional <extra>`). Then confirm your line is still in pyproject.toml.
- Extras: asr, tts, llm, helper (create a new extra only if needed, e.g. `backend`).

## Boundaries
- Write only inside your module folder, `results/<module>/`, and any extra paths your delegation message lists.
- Do not import another module's code. You may import `contracts.validate`.
- Contract change needed? Do NOT edit contracts/. Write the request in `<module>/handoff/open_questions.md` and work around it.
- NEVER run `git commit`, `git push`, `git remote`, or rewrite history. `git status/diff/log` are fine.
- No real patient data. Bind every server to 127.0.0.1. No secrets in files (use .env, which is gitignored).

## Reporting (handoff files, merged by the orchestrator with infra/scripts/merge_handoff.py)
Write into `<module>/handoff/`:
- `decisions.md`: entries `### D-?: <title>   (Phase B / <module> / <agent> / 2026-11-09)` using EXACTLY the section 11 template (all 9 bullets). Plain language for a beginner. One entry per tool/model/dataset choice, safety rule, problem hit, scope cut.
- `glossary.md` (new terms, `- **term**: definition`), `ai_usage.md`, `human_todo.md`, `open_questions.md`, `licences.md` (table rows matching docs/licences.md columns).
Every UNVERIFIED item goes in both human_todo.md and open_questions.md.

## Honesty
Only cite URLs you actually fetched in this session (record fetch date). Never fabricate numbers, licences, model capabilities or test results. Real error text goes in the report when something fails.

## Final report
At most 300 words: what you did, what passed (real command + result), what is UNVERIFIED, what the human should check.
