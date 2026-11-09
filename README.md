# MaatuMitra

A Kannada voice scribe built as a **class sandbox experiment** for an antimicrobial
resistance (AMR) course. Not a clinical tool. All data is synthetic, TTS-generated or
public-licensed; no patient data, ever. Kannada content is not native-validated unless
stated otherwise.

Pipeline: audio -> transcript -> structured record (every field quotes the words actually
spoken) -> deterministic fail-closed safety checks -> mandatory human approval -> saved.

**Start here:** docs/DECISIONS_EXPLAINED.md (plain-language log of every decision).

## Quick start (STUB: the full reproduction steps are written in Phase C/D)

Requirements: [uv](https://docs.astral.sh/uv/) and GNU make. On Windows use **Git Bash**
and type `mingw32-make` instead of `make`.

```bash
make setup               # uv sync --locked: base dependencies only (small)
make test                # all tests (repo + every module)
make lint                # ruff
make validate-fixtures   # every valid fixture passes, every invalid one fails
make split-lock          # frozen test split unchanged
make audit               # pip-audit on the locked dependencies
make m4                  # one module alone: tests + mock run (m1 .. m8)
```

Heavy, optional dependencies: `uv sync --locked --extra asr` (also `tts`, `llm`, `helper`).

Direct `uv run` commands also work, for example:

```bash
uv run pytest m1_data/tests
uv run python -m contracts.validate record fixtures/record/valid
uv run python -m contracts.validate --check-fixtures fixtures
```

On Windows with a long repo path, first run
`export UV_PROJECT_ENVIRONMENT="$USERPROFILE/.venvs/maatumitra"` (the Makefile does this
automatically; see DECISIONS D-3).

The test split is frozen: `make eval-test` refuses unless `ALLOW_TEST=1 PURPOSE="..."` is
given and docs/hypothesis.md is committed; every run is logged in results/test_access_log.md.
