# MaatuMitra — start here

Snapshot packaged on 2026-11-13. The project is **not finished**: Phase B is done, Phase C
(integration) is about half done, and Phase D (packaging) has not started. Details are in
"Where the project stands" below.

## 1. What this is

MaatuMitra is a **Kannada voice scribe** for a clinic, built as a **class sandbox experiment**
for an antimicrobial-resistance (AMR) course. It is **not a clinical tool** and makes no
clinical or educational claim.

The pipeline:

1. **Audio** of a doctor–patient conversation (Kannada, with some English words)
2. → **transcript** (speech recognition, module m2)
3. → **structured medication record**, where every field quotes the words actually spoken
   (module m3)
4. → **safety verifier** that is deterministic and *fail-closed*: when it cannot check
   something it raises a flag instead of passing it (module m4)
5. → **mandatory human approval**: a physician must resolve every flag before saving
   (modules m5 + m6)
6. → saved in a database where each role (physician, nurse, pharmacist, ASHA worker,
   researcher) can see only what it is allowed to (row-level security, module m5)

Plus a small **counselling helper** (m8) that answers antibiotic-use questions only by
quoting an approved card, or declines.

**All data is synthetic or public.** Conversations are generated from templates, the audio
is synthetic speech (TTS), and the only real speech is public FLEURS Kannada clips.
**There is no patient data anywhere.** All Kannada text and every "reviewer" so far is
AI-made (`ai_simulated_review`); nothing has been checked by a native speaker or a
clinician yet.

## 2. What is in this zip

| Folder / file | What it is |
|---|---|
| `START_HERE.md` | This guide |
| `PROGRESS.md` | Task table and the exact next step (line 3) |
| `PROJECT_BRIEF.md` | The full original specification (the source of truth) |
| `README.md`, `STRUCTURE.md` | Short project readme and folder map |
| `HUMAN_TODO.md` | Things only a human can do (clinician, native speaker, licences) |
| `docs/DECISIONS_EXPLAINED.md` | **Plain-language log of every decision (D-1 … D-200)** — the best place to understand *why* |
| `docs/` | Severity classes, metrics, pre-registered hypotheses, glossary, licences, open questions, annotation guide |
| `contracts/` | JSON Schemas shared by all modules (record v1/v2, transcript, gold, verdict, …) + validator |
| `fixtures/` | Small valid/invalid example files for each contract |
| `data/` | Lexicon (34 drugs), 59 templates, 592 conversations (transcripts, gold labels v1 + v2, twins), dev/test split + **frozen test lock**, manifest, **synthetic audio** (`data/audio/`, ~520 MB) and FLEURS clips (`data/audio/public_real/`) |
| `m1_data/` | Data generator (text, gold labels, audio) |
| `m2_asr/` | Speech recognition adapters + dev benchmark |
| `m3_extract/` | Transcript → record (rules = main pipeline; local LLM = comparison) |
| `m4_verify/` | Safety verifier C1–C8 and the planted-mistake experiment (E4) |
| `m5_backend/` | PostgreSQL 16 with row-level security, FastAPI on 127.0.0.1, audit log, access matrix |
| `m6_ui/` | Streamlit review app, Kannada first |
| `m7_eval/` | `make eval`: all experiment tables, plots, failure gallery, cost report |
| `m8_helper/` | Counselling helper (quote-a-card or abstain) |
| `integration/` | Verifier adapter (m4 → m5), boundary checks, end-to-end test |
| `results/` | All outputs so far (dev only) |
| `reviews/` | Simulated reviews (integrity, clinical, Kannada, security) + sheets for real human reviewers |
| `notebooks/` | Executed m2 notebook |
| `.claude/` | The agent and skill definitions used to build this |
| `.env.example` | Settings template (placeholders only) |

**Not included, on purpose:** `.env` (your local passwords and keys — make your own from
`.env.example`), the Python environment, model weights, and the PostgreSQL program and
database (all can be re-created; see below).

**Uncommitted work inside this zip:** the files under `m3_extract/` and
`results/m3_extract/` include an **unfinished, unchecked** migration of m3 to record format
version 2. It was stopped mid-run. Run `git status` to see it; check it or discard it with
`git checkout -- m3_extract results/m3_extract` and `git clean -fd m3_extract results/m3_extract`.

## 3. How to set it up (fresh Windows machine)

You need: **Git for Windows** (Git Bash), **uv** (https://docs.astral.sh/uv/), and
**GNU make** (on Windows the command is `mingw32-make`). Python 3.11 is installed by uv.

```bash
# In Git Bash, inside the unzipped folder
export UV_PROJECT_ENVIRONMENT="$USERPROFILE/.venvs/maatumitra"   # avoids Windows path-length errors
uv sync --locked                                                 # base dependencies
mingw32-make test                                                # all tests (database tests skip if no database)
```

Optional extras, only when you need them (some are large):

```bash
uv sync --inexact --extra data      # m1 lexicon rebuild
uv sync --inexact --extra tts       # re-generating audio (installs torch, ~1 GB)
uv sync --inexact --extra asr       # speech recognition
uv sync --inexact --extra llm       # m3 local-LLM comparison
uv sync --inexact --extra helper    # m8 helper
```

**Settings:** copy `.env.example` to `.env` and replace every `REPLACE_ME` value
(for example with `uv run python -c "import secrets; print(secrets.token_hex(32))"`).
Never commit `.env`.

**Database (only for m5, m6 live mode and the end-to-end test):** PostgreSQL 16, either
Docker (`docker-compose.yml`, bound to 127.0.0.1) or the portable Windows zip described in
`m5_backend/README.md` (unpacked to `%USERPROFILE%\.maatumitra\pg16`).

**Local models (optional):** Ollama with `qwen3:4b-instruct` (m3 comparison) and
`nomic-embed-text` (m8). Speech-recognition models are downloaded by m2 when run (pinned
revisions; see `m2_asr/README.md`).

## 4. How to use it

```bash
mingw32-make help                 # every command
mingw32-make test                 # all tests
mingw32-make lint                 # code style
mingw32-make split-lock           # proves the frozen test split is unchanged
mingw32-make validate-fixtures    # contract examples
mingw32-make m1 … m8              # one module: its tests + a mock run that needs no models
mingw32-make eval                 # m7: all experiment tables on DEV data -> results/m7_eval/dev/
mingw32-make m4-e4-dev            # planted-mistake experiment on dev
mingw32-make m5-db-up             # start the local database (then m5-db-down to stop)
uv run python -m m5_backend.app.main   # API on http://127.0.0.1:8000
mingw32-make m6-run               # review app on http://127.0.0.1:8501
uv run python -m m1_data audio-materialise --ids all --split dev --variants all --out <folder>
                                  # rebuild noisy/speed audio copies (checksum-verified)
```

**The test split is frozen and has never been evaluated.** `make eval-test` refuses unless
`ALLOW_TEST=1 PURPOSE="..."` is set, and every run is logged in
`results/test_access_log.md` (that file does not exist yet = no test run so far). Run it
**once**, at the end, never for tuning.

## 5. Where the project stands

| Part | State |
|---|---|
| Phase A (architecture, contracts, docs) | done |
| m1 data (text, gold v1 + v2, audio, FLEURS) | done |
| m2 speech recognition (dev) | done; test-run command not written yet |
| m3 extraction | v1 done and reviewed; **v2 migration unfinished (uncommitted)** |
| m4 verifier (v1 + v2 checks) | done |
| m5 backend | done, plus Phase C fixes |
| m6 review app | done, plus Phase C fixes |
| m7 evaluation (dev) | built; needs a small fix (`file` vs `file_name`) and a refresh |
| m8 helper | built; misses its 90% coverage target (H4) |
| Integration (m4 inside m5, 10-conversation end to end) | done for v1; v2 boundary check pending |
| Final audits, single test run, final report | not started |
| Phase D (packaging, tag `v1.0-submission`) | not started |

The exact next step is always line 3 of `PROGRESS.md`.

**Headline dev results so far** (dev only, synthetic data, not clinical evidence):

- Speech recognition (Kannada-tuned Whisper small): character error 15.5% on real FLEURS
  speech (may be optimistic) and 24.9% on synthetic speech; drug names recognised exactly
  only 18/351 times.
- Safety verifier, text only, when the transcript itself is wrong: caught 14/193 dropped
  negations and 0/183 drug swaps — the verifier cannot see errors that are already in the
  transcript. More than half of error-free records are sent for review.
- Access control: 0 unauthorized successes in 1,642 attack cases (95% upper bound 0.18%).
- Helper: 0 unsafe answers, but answers only about half of in-scope questions.

## 6. Important limits (read before using any number)

- Dev numbers are **in-sample**: the rules were written and adjusted on dev data.
- Synthetic speech has one real voice; the test-only "second voice" is a pitch-shifted copy.
- The test split has no injection or as-needed cases, so those checks cannot be measured on test.
- Nothing is native-validated or clinician-reviewed; see `HUMAN_TODO.md` and `reviews/human_sheets/`.
- Licences marked UNVERIFIED in `docs/licences.md` must be checked by a human.

## 7. How it was built

By an orchestrator plus 14 specialised AI agents (definitions in `.claude/agents/`), each
working only in its own module and reporting through `*/handoff/` files, merged into
`docs/DECISIONS_EXPLAINED.md`. Every commit was checked by the orchestrator before it was
made. Full history: `git log` (the `.git` folder is included).
