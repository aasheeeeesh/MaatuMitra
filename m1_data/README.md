# m1_data (layer L0: data and content)

Built by the `data-scientist` agent. Pass B1a = text data only (audio is a later pass).
Everything is synthetic; all Kannada is AI-composed and **not native-validated**.

## Run

| what | command (Git Bash, `export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra`) |
|---|---|
| tests | `mingw32-make m1-test` (= `uv run pytest m1_data/tests`) |
| mock (fixtures only) | `mingw32-make m1-mock` -> `results/m1_data/mock/` (git-ignored) |
| regenerate everything | `mingw32-make data` (lexicon -> generator -> coverage) |
| generator only | `uv run python data/generate.py` or `uv run python -m m1_data generate` |
| coverage report | `uv run python -m m1_data coverage` -> `results/m1_data/coverage.json` |
| frozen test split | `mingw32-make split-lock` (infra script) or `mingw32-make m1-split-lock` |

The lexicon build needs the optional extra `data` (`indic-transliteration==2.3.82`):
`uv run --extra data python -m m1_data build-lexicon`.

## Files

- `lexicon_source.py` curated, cited facts per drug -> `lexicon.py` builds `data/lexicon/drugs.csv`
- `templates.py` loads `data/templates/*.yaml`; `render.py` is the template mini-language
- `negation.py` matcher for the shared negation table (self-check + coverage only)
- `generate.py` the deterministic generator; `split.py` split plan + lock; `coverage.py`
- `cli.py` / `__main__.py` command line; `../data/generate.py` thin wrapper
- `config.py` VERSION (`m1-data-1.1.0`) and SEED (`20261109`)

## Current output (generator m1-data-1.1.0)

592 conversations (dev 328 / test 264), 760 medication entries (test 352), 417 twins.
Numbers: `results/m1_data/coverage.json`.
