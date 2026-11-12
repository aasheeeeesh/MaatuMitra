### D-?: How m7 scores extraction errors: its own scorer, the same "field" unit as m3, plus precision and recall per item   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: How the evaluation module counts errors in the records that m3 extracts, so the numbers can be checked independently of m3's own scoring.
- Options we considered:
  1. Copy m3's scores (results/m3_extract/dev_scores.csv). Pro: no work. Con: m7 would just repeat m3's claims; the brief says every number must be recomputed from raw outputs; m7 may not import m3 code.
  2. Write m7's own scorer with a NEW field definition. Pro: fully independent. Con: numbers not comparable with m3's tables; readers get confused.
  3. Write m7's own scorer but use the SAME documented field unit as m3 (medication 6 fields, symptom 2, advice 2, follow-up 1), and add item-level precision, recall and F1. Pro: independent code, comparable numbers, a built-in cross-check. Con: the m7 author read m3's scoring code, so a shared misunderstanding is possible.
- What we chose: Option 3.
- Why: Two separate programs that agree are stronger evidence than one. They do agree on dev: 3624 fields, 0 critical and 48 major errors (40 missed advice, 8 missed follow-up) for the m3 rules; a test fails if they ever disagree.
- What we actually did: m7_eval/scoring.py (score_record, summarise); tests in m7_eval/tests/test_scoring.py (hand-made records for every class) and test_pipeline.py (agreement with m3). The scorer already handles record.v2 + gold.v2: CR-ROUTE, CR-LIQUID-STRENGTH, CR-PAEDIATRIC, status flips as CR-NEG, other status changes as MA-STATUS, other new fields as MA-MED-ATTRIBUTE (docs/severity.md v2 note). With v1 inputs those three classes are reported as "not measurable", never as zero. Tables: results/m7_eval/dev/tables/e2_extraction_*.csv. Run: `mingw32-make eval`.
- What could go wrong / weaknesses: Advice and follow-up wording differences are not judged (code MA-WORDING-UNJUDGED; a human must decide MI-WORDING). The extra codes MA-MISSED-ADVICE, MA-EXTRA-ADVICE, MA-MISSED-FOLLOWUP, MA-EXTRA-FOLLOWUP are not in docs/severity.md yet (D-122 accepted them in principle). All dev numbers are in-sample: the m3 rules were fixed on dev.
- What else could be done: A third, blind scorer written from docs/severity.md only, by someone who never read m3's code.
- How to change this decision later: m7_eval/scoring.py and its tests; re-run `mingw32-make eval`.
- Status: done

### D-?: Confidence intervals: Wilson for proportions, cluster bootstrap by template family for extraction rates, paired bootstrap for comparisons, unique mutations for planted errors   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: Which uncertainty ranges (confidence intervals, "CI": a range that would contain the true value in about 95% of repeated experiments) m7 prints next to every number.
- Options we considered:
  1. Wilson interval for everything. Pro: simple, standard, works at 0 and 100%. Con: assumes every field is independent; our errors come in groups (one template that the rules miss produces the same miss in all its conversations), so the range is too narrow (D-120, D-121).
  2. Cluster bootstrap: resample whole template families (12 on dev) with replacement and recompute the error rate 1000 times. Pro: respects the grouping. Con: with only 12 clusters the range is rough, and with 0 errors it collapses to [0, 0].
  3. Show both: cluster bootstrap as the PRIMARY range for extraction error rates, Wilson next to it labelled "assumes independence", and the rule of three (95% upper bound about 3/N) whenever the count is 0.
- What we chose: Option 3. Plus: paired bootstrap (resample the per-item differences between two systems on the SAME items) for model comparisons, and planted-mistake (E4) counts over UNIQUE mutations, as m4 decided in D-115.
- Why: Honest ranges must be wide when the data are clumpy. Example on dev: the 48 major m3 errors give 13.2 per 1,000 fields; Wilson says [10.0, 17.5] but the cluster bootstrap says [4.8, 23.3]. A zero is never shown without "0 of N, upper bound about 3/N".
- What we actually did: m7_eval/stats.py (wilson, rule_of_three, proportion, per_1000, bootstrap_mean_ci, paired_bootstrap, cluster_bootstrap_rate). Unit tests against hand-computed values: Wilson 0/50 = [0, 0.0713], 3/50 = [0.0206, 0.1622], rule of three, and seed reproducibility (m7_eval/tests/test_stats.py). Seed 20261109, 1000 resamples, in m7_eval/configs/eval.yaml.
- What could go wrong / weaknesses: 12 dev families (10 test families) is a small number of clusters, so the cluster range itself is uncertain. With 0 errors the cluster bootstrap is degenerate; we then rely on the rule of three. Bootstrap percentile intervals can be slightly too narrow with small N.
- What else could be done: A cluster bootstrap by template (finer than family), or a Bayesian beta-binomial model per family.
- How to change this decision later: `cluster_unit`, `seed`, `n_resamples` in m7_eval/configs/eval.yaml; functions in m7_eval/stats.py.
- Status: done

### D-?: How m7 keeps the test split closed   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: How to make sure `make eval` never reads a test file, and that `make eval-test` reads them only after the access is logged.
- Options we considered:
  1. Trust each function to pass only dev ids. Pro: no extra code. Con: one wrong glob silently reads test files; nothing proves it did not happen.
  2. A single guarded reader (SplitGuard) that every read goes through, refusing test files, plus a test that patches Python's `open` and checks every opened path. Pro: one place to check; the test is independent proof. Con: small extra code; files that mix dev and test rows need a rule.
- What we chose: Option 2.
- Why: The test split is frozen (PROJECT_BRIEF 6.5). A guard that refuses, plus a test that watches every file opened, is evidence rather than a promise.
- What we actually did: m7_eval/guard.py. In a DEV run it refuses: any path in data/splits/test.lock; any file whose name contains a test conversation id; any file inside a folder named `test`; the held-out test voice `mms_kan_pitch084`. It reads dev.txt, test.txt and test.lock only to know which ids to avoid. The test path (`python -m m7_eval eval-test`, registered as `m7-eval-test` in EVAL_TEST_TARGETS) refuses unless ALLOW_TEST=1, PURPOSE is set and results/test_access_log.md already has a row for the current git commit; that row is written by infra/scripts/eval_test_guard.py, which the root `make eval-test` runs first. Tests: m7_eval/tests/test_guard.py and test_pipeline.py (a full real DEV run with `open` patched: 0 test files opened; the CLI eval-test exits 3 with "REFUSED" and creates no log). manifest.json lists every input with its sha256 and a `test_files_opened` list (empty). Nobody ran eval-test; results/test_access_log.md does not exist.
- What could go wrong / weaknesses: Two module outputs mix dev and test rows in one file: results/m8_helper/predictions_*.jsonl (m8's own question split) and, once built, data/public_real/fleurs_kn_in_test_subset.jsonl. m7 opens them and drops the other split's rows before scoring; the rows are parsed but never used. A test file with an unusual name that is not in test.lock would not be caught by name.
- What else could be done: Ask m1 and m8 to write one file per split (open question); hash-check every opened file against test.lock as m4 does.
- How to change this decision later: m7_eval/guard.py and its tests; `held_out_voices` in m7_eval/configs/eval.yaml.
- Status: done

### D-?: E1 (speech recognition) input format, and "m2 not run yet" instead of a failure   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: m2_asr is not built, but `make eval` must still run end to end and be ready for m2's output.
- Options we considered:
  1. Skip E1 until m2 exists. Pro: no work now. Con: the format would be decided later under time pressure; nothing tested.
  2. Define the file format m7 expects, write and test the metrics on fixtures, and print "m2 not run yet" in the table when the files are missing.
- What we chose: Option 2.
- Why: The brief wants one command that always runs; an empty but honest table is better than a crash or a silent gap.
- What we actually did: Format (m7_eval/CONTRACT.md): results/m2_asr/<run>/<split>/transcripts.jsonl, one transcript.v1 per line, audio_id `<conversation>__<voice>__<variant>` (m1's audio naming, D-133) or the FLEURS file stem for real speech. m7_eval/asr_metrics.py computes CER (character error rate on normalised text: the share of characters that must be changed), grapheme CER, WER, CER without punctuation (secondary), critical-term recall per class (drug names from data/lexicon/drugs.csv, numbers, units, negation cues from the shared negation table), latency p50/p95 and real-time factor. Results are split by model, source (tts / public_real never pooled), variant (noise level, speed) and voice; models are compared with a paired bootstrap on the common subset (listed in tables/e1_common_subset__*.txt). Tested on a fake tree (m7_eval/mock.py). Today the table says "m2 not run yet".
- What could go wrong / weaknesses: m2 may choose another layout; then m2 or m7 must adapt (open question). The critical-term lists are UNVERIFIED starter lists (not native-validated). Gold text has punctuation, ASR output usually does not; the primary CER counts punctuation as the metrics document says, so we also print CER without punctuation.
- What else could be done: Read latency and hardware from a per-run run.json written by m2.
- How to change this decision later: m7_eval/experiments.py (e1_asr), m7_eval/configs/critical_terms.yaml, m7_eval/configs/eval.yaml `variants`.
- Status: partly done (pending m2)

### D-?: The check-removal experiment (E3) is computed from m4's saved per-check results, not by re-running m4   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: How to show what happens when each safety check C1..C8 is switched off, while `make eval` needs no re-run of other modules.
- Options we considered:
  1. Re-run m4 eight times with one check disabled. Pro: the real experiment. Con: m7 may not import m4 code; slow; writes into m4's folder.
  2. Use m4's saved raw rows: for every planted mistake m4 stored WHICH checks flagged the right field. Removing check X = asking whether any OTHER check flagged it. Same for the flags on error-free fields. Pro: instant, reproducible, uses saved raw outputs. Con: only correct if checks do not read each other's results.
- What we chose: Option 2, labelled as derived.
- Why: It answers the question from saved data in seconds; the label tells readers what was assumed.
- What we actually did: e3_e4_verifier in m7_eval/experiments.py; table results/m7_eval/dev/tables/e3_ablation.csv and plot plots/e3_ablation.png. Dev, planted errors, in-sample (DEV): with all checks, 1054 of 1491 unique transcript-level text-only mistakes escape [0.683, 0.730] while 271/1200 error-free fields are flagged [0.203, 0.250]; removing C4 lets 1458/1491 escape [0.969, 0.984] but cuts the flag rate to 63/1200 [0.041, 0.067]. Record level: removing C3 drops the catch rate most (see the CSV). Natural errors: m3 made 0 critical errors on dev, so verifier recall on natural errors is NOT MEASURABLE (0/0), and m4 has not yet been run on m3's output.
- What could go wrong / weaknesses: UNVERIFIED that the checks are independent; if one check uses another's result, the derived numbers differ from a real re-run. Planted errors on template text are easier than real ones.
- What else could be done: m4 adds a registry option to disable one check and writes eight runs; m7 then reads them and compares with this derivation.
- How to change this decision later: m7_eval/experiments.py (e3_e4_verifier).
- Status: done (derived; real re-run pending)

### D-?: Seen-frame versus unseen-frame marker from template text   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: D-90 asked m7 to report test results separately for test turns whose sentence frame also appears in dev ("seen") and frames never seen in dev, without opening test conversations.
- Options we considered:
  1. Compare test conversation text with dev conversation text. Pro: exact. Con: opens test files outside eval-test.
  2. Compare TEMPLATE text only: replace every slot like {D1.dose} with one placeholder, unwrap gold-span markers, normalise, and check if the same frame exists in a dev template. Turns that are only a slot (a yes/no answer) get a third label, "slot_only". Pro: no test conversation is opened; the marker is ready before the test run. Con: works at template-turn level, not on generated variations.
- What we chose: Option 2.
- Why: It follows the test-split rule and still gives the slice D-90 asked for.
- What we actually did: m7_eval/frames.py; tests in m7_eval/tests/test_frames.py. Result (template turns): test 83 = 15 seen, 56 unseen, 12 slot-only; the most common shared frame is the dosing frame of 10 template turns, which matches D-90's finding. Table: results/m7_eval/dev/tables/frame_overlap_templates.csv. In eval-test, every scored field gets the frame label of its gold turn (E2) and every planted mistake of its injected item (E4).
- What could go wrong / weaknesses: Exact frame match misses near-identical frames (one word different), so "unseen" may include almost-seen frames. Counts are per template turn, not per conversation turn (D-90 quoted 13.9% of conversation turns).
- What else could be done: A fuzzy match (edit distance on frames) as a second marker.
- How to change this decision later: m7_eval/frames.py.
- Status: done

### D-?: The rules-versus-LLM comparison stays STALE; a refresh target is added but not run   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: The only LLM outputs (results/m3_extract/llm_STALE_pre_refreeze/) were made on data that no longer exists (D-120). Rerun now, or report stale?
- Options we considered:
  1. Score the stale outputs anyway. Pro: a number. Con: wrong; the gold changed.
  2. Re-run the LLM from m7. Pro: current. Con: m7 may not import m3; the run takes about 25 minutes and writes into m3's folder.
  3. Mark STALE in the tables; add `mingw32-make m7-e2-llm-refresh`, which calls m3's own target `m3-run-llm-dev` only when Ollama with qwen3:4b-instruct answers on 127.0.0.1, then re-runs m7. m7 scores results/m3_extract/llm/ automatically when it exists.
- What we chose: Option 3.
- Why: Honest now, one command later, no boundary broken.
- What we actually did: e2_extraction in m7_eval/experiments.py; the LLM row says STALE and is not scored; the paired table says it was not computed. A test with fake fresh LLM outputs proves the scoring and the paired bootstrap work.
- What could go wrong / weaknesses: Even when refreshed, 32 of the 40 subset conversations are in-sample for the rules (D-121), which favours the rules.
- What else could be done: Choose a fresh LLM subset from dev conversations the rules were never fixed on (if any remain).
- How to change this decision later: m7_eval/module.mk (m7-e2-llm-refresh), m3_extract/module.mk.
- Status: needs human (run the refresh, about 25 min)

### D-?: E7 user-study kit: within-subject, flags shown versus hidden, simulated imperfect flags   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: How a small group of people can test whether verifier flags help reviewers or make them over-trust the flags (automation bias: trusting the machine and missing what it does not point at).
- Options we considered:
  1. Between-subject (half the people see flags). Pro: no learning effect. Con: needs many people; we will have few.
  2. Within-subject: everyone reviews 20 records, 10 with flags and 10 without, in counterbalanced blocks and random order. The flags are SIMULATED: 7 of 10 planted errors flagged, 3 not, plus 2 false flags on clean records. Pro: works with 6-12 people; shows automation bias directly. Con: people may learn during the session.
- What we chose: Option 2, descriptive results only.
- Why: With few participants, significance tests would mislead; catch rates with Wilson intervals and times are honest.
- What we actually did: m7_eval/e7_kit/: protocol.md, consent_form_en.md, consent_form_kn.md (not native-validated), sus_questionnaire.md, 20 records (record.v1, validated in tests) and review packets built from DEV gold, answer_key.csv, design.csv (12 participant slots), record_sheet.csv, build_records.py (seed 20261109), analyse.py (`python -m m7_eval e7-analyse <sheet>`). Not run with people.
- What could go wrong / weaknesses: The Kannada consent text and conversations are not native-validated. The SUS wording is paraphrased (UNVERIFIED against the original). Set A has 1 withheld flag and set B 2 (3 cannot split evenly). Ethics approval need is UNVERIFIED.
- What else could be done: More participants and a between-subject arm; real reviewers (nurses, pharmacists) instead of classmates.
- How to change this decision later: m7_eval/e7_kit/build_records.py (MISSED, FALSE_FLAG, N_PARTICIPANTS), then `mingw32-make m7-e7-kit`.
- Status: needs human (run the study)

### D-?: Where m7 writes, and what it did not write   (Phase C / m7_eval / research-scientist-eval / 2026-11-12)
- What we needed to decide: The brief lists results/tables, results/plots, results/failure_gallery.md and infra/cost_report.md as m7 outputs; this build was told to write only m7_eval/ and results/m7_eval/.
- Options we considered:
  1. Write to the brief's paths. Pro: matches section 7. Con: breaks this build's write boundary.
  2. Write everything under results/m7_eval/<split>/ and leave copying to the orchestrator.
- What we chose: Option 2.
- Why: The delegation message narrows the brief; boundaries keep parallel agents safe.
- What we actually did: results/m7_eval/dev/{tables,plots,summary.md,failure_gallery.md,cost_report.md,manifest.json,run_log.json}. infra/cost_report.md and the infra/inventory.md line are NOT written (human_todo item). Runtime of `make eval` on the laptop: about 43 s for all targets (m3-score, m4-mock, m7-eval); see run_log.json.
- What could go wrong / weaknesses: A reader looking at results/tables/ finds nothing until the orchestrator copies or links the files.
- What else could be done: The orchestrator widens m7's boundary and m7 writes the brief's paths directly.
- How to change this decision later: `--out` in m7_eval/__main__.py and m7_eval/module.mk.
- Status: done
