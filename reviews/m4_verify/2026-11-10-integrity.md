# Integrity review: m4_verify (2026-11-10)

Reviewer: scientific-integrity-auditor (AI agent). Label: **ai_simulated_review**.
Target: m4_verify at commit c6fdf72 (results files dated 2026-11-10 03:47), HEAD 3973bb5.
Raw files used: `results/m4_verify/e4/*` (fixture lexicon) and `results/m4_verify/data_lexicon/e4/*` (data/lexicon/drugs.csv).
My recomputation script (temp, not in repo): `<scratchpad>/scripts/e4_check.py`. It has its own Wilson function, checked
against the skill's hand values 0/50 -> [0, 0.0713] and 3/50 -> [0.0206, 0.1622]. No test data was read.

## Checklist (PASS / FAIL)

| # | item | result |
|---|---|---|
| 1 | Planted errors kept apart from natural errors | PASS: E4 tables contain planted errors only; no natural-error numbers exist yet. Record-level and transcript-level are in separate rows. |
| 2 | Every proportion has N and a Wilson CI | PASS (tables): every catch_rates.csv row has n, n_unique and Wilson CIs. My recomputation matches all 52 rows (26 per lexicon run). |
| 3 | Unique mutations vs 200 repeats | PASS in the tables, **FAIL in prose** (finding M4-3). Unique N per type: a 4, b 7, c 90 (73 at transcript level), d 3, e 15/12, f 18/16 (53/56 with the data lexicon), g 12/15, h 12/16, i 30. Repeats are deterministic (0 unique keys with mixed outcomes), so the 200-row CIs are inflated: for example 200/200 gives a Wilson lower bound of 0.981, but the honest 4/4 gives [0.510, 1.0] and 3/3 gives [0.438, 1.0]. |
| 4 | Clean-record flag rate beside recall | PASS (fixture lexicon): 0/18 fields, [0, 0.176], next to recall. **FAIL (major) for the headline**: with the real lexicon it is 1/18 fields, 5.6% [0.010, 0.258], and 1/6 records. README quotes only 0/18 (finding M4-4). |
| 5 | Zero-event claims use 3/N | PASS with note: summary shows Wilson upper bounds; catch_rates.csv has a rule-of-three column (computed on unique N, e.g. 0.75 for 4 unique). |
| 6 | C7 threshold not tuned on test | PASS: `c7_conf_threshold: 0.6` is an untuned placeholder and is labelled UNTUNED everywhere. E4 does not use word confidences. |
| 7 | Test split cannot be read by E4 / tune-c7 | **FAIL (critical, latent)**: finding M4-1. |
| 8 | Negation-audit fixes measured on the same sentences (overfit disclosure) | PASS: negation_audit.md says "same sentences used to design the fixes!" and "optimistic (no held-out text)". D-49 says the same. Minor: "Zero trap-word triggers" is given without an N or a 3/N bound. The 52 sentences are not a random sample, which the audit itself states. |
| 9 | "Caught" means the error was flagged | **FAIL (major)**: finding M4-2. |
| 10 | Second-transcript condition is realistic | **FAIL (major, disclosure)**: finding M4-5. |
| 11 | Claims match tables | FAIL: see M4-3 and M4-4 (README and D-52 "200/200"). |
| 12 | No clinical or educational impact claims | PASS: none found in README, plan or decisions. |
| 13 | test_access_log matches commits | PASS (vacuous): no log file and no test access recorded. |

## Findings

### M4-1 (critical, latent): the "DEV only" guard cannot see test files
`planted.refuse_test_split` refuses a path only if one of its parts contains the word "test". m1 stores TEST gold at
`data/gold/m1-*.json`, next to dev gold, and TEST membership is defined only by `data/splits/test.txt`.
`load_gold_dir` is called in evaluate.py line 152 without an id filter. So the planned DEV re-run
(D-56: `python -m m4_verify e4 --gold-dir data/gold`) would load all 592 gold files, including the 264 TEST files.
The guard would not stop it. tune_c7 uses the same path-name guard.
No test data has been read so far: both E4 runs used `fixtures/gold/valid`.
**Fix before any DEV re-run**: load ids from `data/splits/dev.txt` and pass `ids=` to the loader. Refuse any id
listed in `test.txt` (and any path listed in test.lock). Add a test that `--gold-dir data/gold` returns only dev ids.
Do the same for tune_c7 input rows.

### M4-2 (major): "caught" counts ANY flag on the record, not a flag on the planted field
evaluate.py line 246 sets `caught = not v["auto_acceptable"]`. In the data-lexicon run, "wrong patient, no encounter
index" reports 33/200 caught, 5/30 unique, Wilson [0.073, 0.336]. But `caught_at_field` is **0**: every one of those
"catches" is the unrelated paracetamol C4 flag (lexicon range 1000-1000 mg). A verifier with a high clean flag rate
would look better on this column. Field-attributed recall (unique, my recomputation) for the transcript level:

| type | text_only | with_second_transcript: any flag | with_second_transcript: at the planted field |
|---|---|---|---|
| a negation drop | 0/4 | 4/4 | 0/4 [0, 0.490] |
| b negation add | 0/7 | 7/7 | 0/7 [0, 0.354] |
| c digit change | 29/73 | 73/73 | 29/73 |
| f drug swap | 4/16 | 16/16 | 4/16 |
| h duration swap | 0/16 | 16/16 | 0/16 [0, 0.194] |

Record-level caught and caught_at_field agree (fixture lexicon) for types a to i.
**Fix**: report field-attributed recall as the primary number. If any-flag recall is kept as "record sent to review",
label it as such and always show it next to the clean-record flag rate on the SAME records.

### M4-3 (major): prose quotes repeated-injection counts
README ("200/200 caught per type", "0/200 without it") and D-52 ("0/200 ... 200/200") use the repeated N. The honest
figures are 30/30 unique wrong-patient catches [0.887, 1.0] with the index and 0/30 [0, 0.114] without it.
Negation drop is 4/4 [0.510, 1.0]. **Fix**: quote unique k/n with a Wilson CI in README and decisions. Make the repeated
count secondary or drop it.

### M4-4 (major): the review-burden headline uses the favourable lexicon
README: "Error-free fixture fields flagged: 0/18". With the project lexicon (data/lexicon/drugs.csv), which m3 and m7 will
use, it is 1/18 fields, 5.6% [0.010, 0.258], and 1/6 records [0.030, 0.564]. Also, N = 18 cannot test H1's <= 20% bar:
the upper bound is above 20% in both runs. **Fix**: report both runs. State that the burden is not yet estimable.
Re-measure on m1 DEV gold, which has 872 items, after fixing M4-1.

### M4-5 (major, disclosure): "with second transcript" uses a PERFECT second transcript
evaluate.py line 240 passes `inj["clean_transcript"]`, the uncorrupted text, as the second transcript. Any difference
then flags, so 100% there is an oracle upper bound. A real second ASR output has its own errors, which would raise the
clean flag rate (not measured: on clean records both transcripts are identical) and could share errors with the first.
README says "a second transcript (C7) catches 4/4". **Fix**: label this condition "oracle second transcript (upper
bound)". Measure the clean-record flag rate with a real or noisy second transcript before claiming anything about C7.

### M4-6 (minor): the data-lexicon run is not mentioned in the README
`results/m4_verify/data_lexicon/` (both burden and catch rates) should be linked from the README.

## What m7 must do to avoid overclaiming (from m4)
1. Use field-attributed recall. Always show it next to the clean-field flag rate on the same records, with unique N.
2. Keep planted (E4) separate from natural errors, and record-level separate from transcript-level. Label the
   second-transcript row "oracle".
3. Do not call escapes "rare" unless the Wilson upper bound is <= 1/1000. With these N it cannot be.
4. Run E4 again only on dev ids from dev.txt (M4-1). Never on data/gold as a whole.
5. Negation-rule quality has no held-out estimate. Do not quote the audit counts as accuracy.

## UNVERIFIED
- Kannada negation rules and the audit's correct/wrong judgements (not native-validated).
- I did not re-run E4 (expensive). I recomputed every rate from the committed raw `injection_results.jsonl`.
- I did not run the m4 pytest suite in this session.
