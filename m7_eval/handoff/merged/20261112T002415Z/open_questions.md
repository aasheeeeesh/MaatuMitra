## From m7_eval (2026-11-12)

- m2 output layout: m7 defined results/m2_asr/<run>/<split>/transcripts.jsonl (m7_eval/CONTRACT.md). m2 must follow it or tell m7.
- Mixed-split files: results/m8_helper/predictions_*.jsonl (and, once built, data/public_real/fleurs_kn_in_test_subset.jsonl) hold dev AND test rows. m7 drops the other split's rows, but it still opens the file. Should m8 and m1 write one file per split?
- E3 ablation is derived from stored per-check flags assuming the checks are independent (UNVERIFIED). Can m4 add a "disable check X" option?
- docs/severity.md lacks the advice/follow-up codes used by m3 and m7 (MA-MISSED-ADVICE, MA-EXTRA-ADVICE, MA-MISSED-FOLLOWUP, MA-EXTRA-FOLLOWUP, MA-WORDING-UNJUDGED); D-122 accepted adding them before any test run.
- Where do module test runs write their outputs for eval-test (configs/eval.yaml `inputs.test`)? Needs agreement with m3 and m4 before the single test run.
- E7: does the study need ethics approval (UNVERIFIED)? Kannada consent text not native-validated. SUS wording paraphrased (UNVERIFIED).
