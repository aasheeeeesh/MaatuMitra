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

## From m1_data (merged 20261109T222420Z)

- [ ] (m1, native Kannada) Review all 59 templates in `data/templates/*.yaml` and the 164 unattested words in `results/m1_data/unattested_tokens.json`; mark wrong/unnatural ones. Until then everything is "not native-validated".
- [ ] (m1, native Kannada) Check Kannada drug spellings and variants in `data/lexicon/drugs.csv` (`kn_primary`, `kn_variants`).
- [ ] (m1, pharmacist) Spot-check NLEM 2022 rows against the PDF (https://nppa.gov.in/storage/uploads/pdf/nlem-2022pdf-0cd1d2b28855bf30128875ab19fc5304.pdf), first the JSON-extracted ones: ibuprofen 2.1.3, ondansetron 17.2.3, metformin 18.3.1.6, iron-folic acid 8.1.3; also cefadroxil ("Tablet 100 mg") and levofloxacin ("Tablet 300 mg") odd printed strengths; cephalexin, erythromycin, ORS, amlodipine, omeprazole were NOT found by our queries.
- [ ] (m1, pharmacist) Check each `adult_dose_range_mg` / `max_daily_mg` against the cited openFDA label URL in `source_url`; decide whether US label ranges are acceptable for an Indian setting (paracetamol 1000-1000 mg comes from a US OTC label).
- [ ] (m1, clinician) Decide the gold convention "medicine stopped before finishing = negated: true" (docs/annotation_guide.md section 4).
- [ ] (m1) Verify licences in `m1_data/handoff/licences.md` marked UNVERIFIED (NLEM, WHO AWaRe portal, ISMP list, Wikipedia page licences, news18 and CARE Hospitals pages: only single words used).
- [ ] (m1) Confirm the split interpretation (families inside categories) is acceptable before the first `make eval-test`.

## From m6_ui (merged 20261110T081219Z)

- [ ] **Native Kannada review of the UI strings.** Open `m6_ui/i18n/kn.json`, read every value next to `m6_ui/i18n/en.json`, fix unnatural wording (keep the `{placeholders}`), set `_meta.native_validated` only after a real native speaker signed off, bump `_meta.version`, run `mingw32-make m6-test`.
- [ ] **Check Kannada conjunct rendering by eye (UNVERIFIED on Android/Linux).** Run `mingw32-make m6-mock`, open `results/m6_ui/conjunct_test_page.html` (or the "Letter test" screen in the app) on a cheap Android phone (Chrome) and on Linux (Firefox/Chrome). Each line must show joined letters, no dotted circles, no loose halant; note what the two ZWNJ lines look like. Record device, browser and result in `m6_ui/handoff/decisions.md` as a new entry.
- [ ] **Check the 360 px layout (UNVERIFIED).** Run `M6_DEMO_ROLE=nurse M6_DEMO_PAGE=review M6_DEMO_RECORD=rec-m6-xss M6_DEMO_LANG=kn mingw32-make m6-run`, open http://127.0.0.1:8501 in Chrome DevTools device mode at 360 px width: no horizontal scroll, buttons at least 48 px tall, flagged items at the top in red with "!" and a text label. Repeat with `M6_DEMO_PAGE=record` and tap the microphone to see the recording state.
- [ ] **Decide the "human confirmed a flag" save path (open question).** With m5's current rule, a reviewer's "Yes, this is correct" can never be saved while the verifier still flags. Decide with the architect whether a reviewer override (with reason + audit) is wanted; it needs a contract change.
- [ ] **Run live mode once (UNVERIFIED).** Start m5 (`mingw32-make m5-db-up`, `uv run python -m m5_backend.app.main`), create a record, write `{"<record_id>": "<m5 uuid>"}` to a JSON file, then `MODE=live API_URL=http://127.0.0.1:8000 M6_API_USER=<uuid> M6_API_PASSWORD=<sandbox pw from .env> M6_SERVER_IDS=<file> mingw32-make m6-run`; approve a clean record (expect "Saved") and a flagged one (expect the red refusal).

## From m3_extract (merged 20261110T084736Z)

- [ ] (m3, Kannada review) A native Kannada speaker checks `m3_extract/data/symptoms.yaml` (is each word the usual spoken word for the English name? are common spoken variants missing, e.g. inflected ಜ್ವರವಿದೆ?) and `m3_extract/data/phrases.yaml` (do the English glosses match the Kannada?). Mark each line OK / wrong / missing variant. Nothing in m3 is native-validated.
- [ ] (m3, UNVERIFIED words) Confirm with a grammar reference or speaker: ಬಾರಿ = "times" (Wiktionary has no entry, 404 on 2026-11-10), ಸಾರಿ = "times", ಒಮ್ಮೆ = "once", ದಿನಕ್ಕೆ = "per day", ಚಮಚ -> teaspoon, and the number words 11, 12, 16, 20, 30, 100 in `m3_extract/numbers.py` (marked UNVERIFIED there).
- [ ] (m3, ASR) When m2_asr publishes transcripts, run `uv run python -m m3_extract run-rules --transcripts results/m2_asr/<model_dir>` (files must be named `<conversation_id>__<anything>.json`) and score them; extraction from ASR text has NOT been run yet.
- [ ] (m3, licence) Open the upstream Qwen3-4B-Instruct model card and confirm the Apache-2.0 licence that `ollama show qwen3:4b-instruct` prints (not fetched by us).
- [ ] (m3, clinical) A clinician decides whether "stopped before finishing" (ಮುಗಿಸದೆ ನಿಲ್ಲಿಸಿದೆವು) should be `negated: true` (current convention from the annotation guide) or a separate status.
- [ ] (m3, scores) Read `results/m3_extract/failures_dev.md`; the 0-error dev_tune score is in-sample (rules were written while reading those conversations). Only the dev_holdout row (and later the frozen test split via `make eval-test`) estimates performance on new wording.

## From m5_backend (merged 20261110T160937Z)

- [ ] m5 fix pass: re-read `m5_backend/app/main.py` (`save_record`, `verify_record`), `m5_backend/sql/050_gate.sql` and the new line `attacks.save_gate` in `m5_backend/tests/access_matrix_expected.yaml`; confirm they match D-80 and the brief.
- [ ] m5 integration: wire the real m4 verifier into the API (`create_app(..., verifier=fn)`, fn(record_json) -> verdict.v1) and adapt m6_ui to `/records/{id}/verify` + `/save` with `{verdict_id, resolutions}` (see m5_backend/CONTRACT.md). Until then the default verifier flags every record for manual review.
- [ ] UNVERIFIED: run the Docker path once (`docker compose up`, `POSTGRES_USER=mm_bootstrap`, `OWNER_DB_PASSWORD` set, then `uv run python -m m5_backend.scripts.dbtool all`) and confirm owner_role and the bootstrap superuser have different passwords. Add `OWNER_DB_PASSWORD` to your local `.env` if you move away from `POSTGRES_USER=owner_role`.
- [ ] Decide whether k = 5 (drop small groups) is acceptable for the research export, or ask for merging instead.
- [ ] Optional (audit condition 8): extra step (audio playback or second confirmation) before a critical flag (C3, C4) can be confirmed; not built.
- [ ] Still open from the audit: run gitleaks with a verified checksum on the tree and history; re-run the R-order check with data spanning several months.

## From m1_data (merged 20261110T180301Z)

- [ ] Native Kannada reviewer: check the syrup wording (ಸಿರಪ್ ಐದು ಎಂ.ಎಲ್ ... ಕೊಡಿ), the rewritten twins of h5/e7/h2, ಓ.ಆರ್.ಎಸ್, and the artefact form "ಕೊಡ ಬೇಡಿ" (reviews/human_sheets/kannada_review_sheet.csv). ai_simulated_review only so far.
- [ ] Real pharmacist/doctor: confirm paracetamol 500-1000/4000, ondansetron 4-24, metformin 500-1000, ibuprofen 200-800 and that synthetic syrup volumes 2.5/5/7.5/10 ml are acceptable as non-advice text. Fill NLEM-based rows (metronidazole, cotrimoxazole stay UNVERIFIED).
- [ ] Decide negative-question (-ಲ್ವಾ) gold polarity (table NEG-S07 is not generated).

## From infra (merged 20261110T180301Z)

- [ ] (D-110) Kannada native check: is "ಕೊಡ ಬೇಡಿ" (with a space) acceptable in the data, or should every case be "ಕೊಡಬೇಡಿ"? Only changeable before the first `make eval-test`.
- [ ] (D-110) Paediatric check: child paracetamol syrup volumes in templates e8, h2, h3, i5 (2.5-10 ml) are synthetic and not matched to an age or weight table (UNVERIFIED).

## From m4_verify (merged 20261111T141428Z)

## m4_verify fix pass (2026-11-11)

- [ ] **Kannada (native speaker): check the new negation forms.** Open m4_verify/tests/test_negation_fixpass.py. For every sentence say (a) is it natural spoken Kannada, (b) is the "negated / not negated" reading right. Forms to check: ತಗೋಬೇಡಿ, ಕೊಡ್ಬೇಡಿ, ತಿನ್ಬೇಡ, ತಗೋಬೇಡಾ, ಬೇಡಾ, ಬೇಡವಾ, ಇಲ್ರೀ, ಇಲ್ಲಪ್ಪ, ಕುಡಿಯಲ್ವಾ?, "ಜ್ವರ ಇದೆ ಕೆಮ್ಮು ಇಲ್ಲ", "ಇಲ್ಲ ಅಕ್ಕ", "ಹೌದ್ರೀ", "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 ಎಂ.ಜಿ. ... ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ". Write the answers into reviews/human_sheets/negation_rules_review_sheet.csv (new rows S-LVA, S-BEDI/S-BEDA fused, clause split after predicate, multi-word answers, abbreviation dots).
- [ ] **Kannada: child words.** Confirm or extend the child word list in m4_verify/lexicon.py (CHILD_PREFIXES_KN). Should ಮಗ / ಮಗಳು (son / daughter) count as "child"? Should an age like "ಐದು ವರ್ಷದ" count?
- [ ] **Clinician / pharmacist: allowed units per drug.** Check m4_verify/config/default.yaml (allowed_units_by_drug) and the units derived from data/lexicon/drugs.csv notes: run `uv run python -c "from m4_verify.config import default_config; from m4_verify.lexicon import load_lexicon; L=load_lexicon('data/lexicon/drugs.csv'); c=default_config(); [print(g, c.units_for(g, L), c.units_source(g, L)) for g in L.drugs]"` and mark wrong rows. UNVERIFIED rows: paracetamol ml (syrup strength not fetched), iron-folic acid mg+mcg, every drug on the default (cephalexin, erythromycin, amlodipine, omeprazole).
- [ ] **Clinician: is "flag every dose in a conversation that mentions a child" acceptable** as a fail-closed rule, or is it too broad (it also flags an adult's own dose in a visit about a child)?
- [ ] **Confusable drug pairs.** The E4 drug swaps use data/lexicon/drugs.csv confusable_with, which is mostly AI-proposed. A pharmacist should check the pairs or provide a real list (ISMP or Indian equivalent); paracetamol, ibuprofen, zinc, ORS and others have no pair and are never swapped.
- [ ] **Real second ASR transcript for C7.** When m2 has two ASR outputs for the same DEV audio, run the verifier with `--second-transcript` on DEV records and report the clean-record flag rate; the current E4 C7 row uses a perfect (oracle) transcript and is only an upper bound.
- [ ] **Never set ALLOW_TEST=1 for m4 commands.** If you ever must, also set PURPOSE="..." and check results/m4_verify/test_access_log.md afterwards.

## From m3_extract (merged 20261111T144008Z)

- [ ] UNVERIFIED (native speaker): confirm the ಜ್ವರವಿಲ್ಲ / ಕೆಮ್ಮಿಲ್ಲ / ವಾಂತಿಯಿಲ್ಲ / ನೋವಿಲ್ಲ spelling rule, ಪ್ಯಾಕೆಟ್ (sachet), ಎರಡೂವರೆ (2.5), ಆಗಿದ್ದರೆ (fever follow-up); use reviews/human_sheets.
- [ ] Optional (about 25 min, needs Ollama running with qwen3:4b-instruct): `mingw32-make m3-run-llm-dev` to replace the STALE rules-vs-LLM comparison; read holdout-only rows, not pooled ones.
- [ ] After the first real ASR run: `uv run python -m m3_extract run-rules --transcripts <dir>` and check whether ASR writes the short-vowel ಒ.ಆರ್.ಎಸ್.

## From infra (merged 20261111T145546Z)

- [ ] (m3 clinical review, 2026-11-11) Real clinician: which fields a record needs for child syrup (strength, age, weight); is negated:true acceptable for an unfinished course; which advice items count as CRITICAL; ಚಮಚ = teaspoon or tablespoon; omeprazole "after food" in template e4.
- [ ] (m6 reviews, 2026-11-11) Native Kannada clinic staff read the m6 screens aloud and check the new m6_ rows in reviews/human_sheets/kannada_review_sheet.csv, especially the safety strings.
- [ ] (m6 security, 2026-11-11) Run gitleaks (not installed during the audit) and test m6 live mode against m5 in the final security audit.
