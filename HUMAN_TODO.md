# HUMAN TODO

Things only a human can do. Agents add items through `<module>/handoff/human_todo.md`
(merged by `make merge-handoff MODULE=<module>`). Seeded by the architect on 2026-11-09
with the required items (a)-(g) from PROJECT_BRIEF section 13 as placeholders.

## (a) Pending or failed model runs

- [ ] PLACEHOLDER: m2_asr lists here every model marked pending/failed, with the real error
      text, the notebook path, which cells to run on Colab/Kaggle or a GPU machine, and where
      to put the outputs (results/m2_asr/<model>/).

## (b) Real reviewers

- [ ] Send reviews/human_sheets/*.csv (Kannada review sheet, negation rules sheet) to real
      Kannada speakers, and the clinical sheet to a real pharmacist or doctor; import their
      corrections. Until then all Kannada is "not native-validated" and all AI reviews are
      "ai_simulated_review". (Sheets are created by the reviewer agents in Phase B.)

## (c) User study

- [ ] Run the E7 user study with informed consent using the kit from m7_eval (Phase B/C).

## (d) Verify every UNVERIFIED item

- [ ] Licences of every dataset, model, font and tool in docs/licences.md.
- [ ] Parrotlet's Kannada support (m2), dose ranges in data/lexicon/drugs.csv (m1),
      TTS terms of use (m1), dataset availability (m1).
- [ ] The architect's fixture lexicon doses (fixtures/lexicon/drugs_fixture.csv) are
      FIXTURE ONLY; never use them outside tests.
- [ ] pgserver / portable PostgreSQL 16 choice (m5), docker-compose image digest.
- [ ] Optional: enable Windows long paths, or clone the repo to a short path (for example
      C:\mm), so a `.venv` inside the repo works (see DECISIONS D-3).

## (e) Secrets check before pushing

- [ ] Install gitleaks and run `gitleaks detect --source . --log-opts="--all"` on the whole
      history before the first push (CI also runs it).

## (f) Licence

- [ ] Choose a LICENSE for this repository and replace LICENSE_PLACEHOLDER.md.

## (g) Push (agents never push)

- [ ] `git remote add origin <url>`
- [ ] `git push -u origin main`
- [ ] `git push origin --tags`

## From m5_backend (merged 20261109T222036Z)

- [ ] **Add the m5 database job to CI** (UNVERIFIED until it runs on GitHub; the architect owns `.github/workflows/ci.yml`). Add this job:
  ```yaml
    m5-db:
      runs-on: ubuntu-24.04
      services:
        postgres:
          image: postgres:16.15@sha256:f9a7b9ebf6f56201f949db745e47bc423c0f0f8294bafe991cc10bf74b029657  # same pin as docker-compose.yml
          env:
            POSTGRES_USER: mm_bootstrap
            POSTGRES_PASSWORD: ci-bootstrap-throwaway
            POSTGRES_DB: postgres
          ports:
            - 127.0.0.1:54329:5432
          options: >-
            --health-cmd "pg_isready -U mm_bootstrap -d postgres"
            --health-interval 5s --health-timeout 5s --health-retries 20
      env:
        POSTGRES_HOST: 127.0.0.1
        POSTGRES_PORT: "54329"
        PG_BOOTSTRAP_USER: mm_bootstrap
        PG_BOOTSTRAP_PASSWORD: ci-bootstrap-throwaway
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3
        - name: Throw-away secrets for this run only
          run: |
            for k in POSTGRES_PASSWORD API_DB_PASSWORD JWT_SIGNING_KEY RESEARCH_PSEUDONYM_HMAC_KEY MOCK_LOGIN_PASSWORD; do
              echo "$k=$(openssl rand -hex 32)" >> "$GITHUB_ENV"
            done
        - run: uv python install && make setup
        - name: m5 DB tests incl. the E5 access matrix against real PostgreSQL 16
          run: uv run pytest m5_backend/tests -m needs_db -rs
  ```
  After the first run check: no `needs_db ... SKIPPED` lines, 60 DB tests passed, and the log line `unauthorized successes: 0 of 1385 ...`. If GitHub rejects the `127.0.0.1:` prefix in `ports`, use `54329:5432` (the runner is a throw-away VM). Optionally upload `results/m5_backend/` as an artifact (pin the action to a SHA).
- [ ] Review the hand-written expected table `m5_backend/tests/access_matrix_expected.yaml` against your own reading of PROJECT_BRIEF AGENT 6 (the same AI wrote the table and the SQL).
- [ ] UNVERIFIED: authenticity of the EnterpriseDB zip (no vendor checksum found; sha256 `43bb45f173a6f08cf1d29a97a6d8deb119e8e8093a24c00d2d1001a0ccaa8281`). Optional: check the digital signature of `%USERPROFILE%\.maatumitra\pg16\pgsql\bin\postgres.exe` (right-click > Properties > Digital Signatures).
- [ ] UNVERIFIED: EDB third-party licence notices (`pgsql/commandlinetools_3rd_party_licenses.txt` in the zip) were not reviewed.
- [ ] Decide (clinical/product): may nurses read approved/saved records? Who records research consent (today only the operator via maint_role)?
- [ ] Docker users: set `POSTGRES_USER`/`POSTGRES_PASSWORD` in `.env` equal to `PG_BOOTSTRAP_USER`/`PG_BOOTSTRAP_PASSWORD` (NOT `owner_role`), or owner_role would be the image's superuser (`dbtool` refuses to continue then).
- [ ] Local DB: start `bash m5_backend/scripts/db_up.sh` (resets the `maatumitra` DB; `--no-reset` only starts), stop `bash m5_backend/scripts/db_down.sh`. Data: `%USERPROFILE%\.maatumitra\pgdata16` (outside the repo).

## From m4_verify (merged 20261109T222036Z)

- [ ] (m4) Native Kannada review of `m4_verify/negation.py` rule tables and the test sentences in `m4_verify/tests/test_negation.py` (UNVERIFIED): for each cue confirm the positive is a negation, the twin is not, the trap is not.
- [ ] (m4) Re-check the audit judgements in `m4_verify/negation_audit.md` (lines marked false positive / missed), and audit one NEW, unseen Kannada article: save sentences to a text file and run `uv run python -m m4_verify audit --sentences <file>`.
- [ ] (m4) Review Kannada number words (`m4_verify/numbers.py`), units/frequency/duration phrases and symptom names (`m4_verify/lexicon.py`) (UNVERIFIED).
- [ ] (m4) Tune the C7 threshold on DEV ASR output when m2 has it: write DEV pairs JSONL `{"asr_transcript": ..., "gold_transcript": ...}`, run `uv run python -m m4_verify tune-c7 --pairs <file>`, copy the chosen value into `m4_verify/config/default.yaml` and set `c7_threshold_status`.
- [ ] (m4) Re-run E4 on m1 DEV gold when it exists: `uv run python -m m4_verify e4 --gold-dir <DEV gold dir> --lexicon data/lexicon/drugs.csv --out-dir results/m4_verify/dev` (never point it at test data; it refuses paths containing "test").
- [ ] (m1/m4) Paracetamol in `data/lexicon/drugs.csv` has `adult_dose_range_mg = 1000-1000`, so the verifier flags a normal 500 mg tablet dose (fixture rec-fx-trap-006 becomes flagged). Check the source and correct the range (UNVERIFIED which value is right).
- [ ] (m4) 12 of 34 rows in `data/lexicon/drugs.csv` have a blank dose range: every dosed record for those drugs will be flagged "no verified range" (fail-closed). Decide whether that review burden is acceptable.
