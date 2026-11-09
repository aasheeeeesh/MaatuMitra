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
