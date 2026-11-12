# E4-v2 planted record.v2 mistakes (m4_verify)

Gold sources: `data/gold` (328 DEV loaded, 264 not in dev.txt, never opened) and `data/gold_v2` (328 DEV loaded, 264 never opened). Source records = contracts/migrate_v1_to_v2.py on the v1 gold record + new fields filled from gold.v2: 328 built; skipped: {'no_v1_gold': 0, 'v1_v2_mismatch': 0}. Lexicon `C:\Users\AASHISH\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\scratch-workspaces\3b3f3360-0ebd-4d41-b52b-62b6ca92ff4a\467491e8-c22e-4280-a242-2bea353ccbd7\scratch-2026-11-09-3cb2b8\data\lexicon\drugs.csv`. Seed 20261109, up to 200 injections per type (repeats of one mutation counted ONCE). Verdicts validated against verdict.v1: 928 (errors: 0).

PLANTED errors on SYNTHETIC, template-generated text (not native-validated), RECORD level only (no transcript-level v2 table). This table is SEPARATE from the v1 E4 table (results/m4_verify/dev/e4/summary.md). Every proportion is k/n over unique mutations with a Wilson 95% CI in brackets. No clinical claim is made.

## Review burden on the SAME error-free v2 records

| unit | n | flagged (any) | Wilson 95% CI | flagged excl. cannot_verify | Wilson 95% CI |
|---|---|---|---|---|---|
| record | 328 | 190 | [0.5252, 0.6315] | 50 | [0.1176, 0.1953] |

Flags on the new v2 fields of error-free records (a field = one path; flagged = any flag at exactly that path):

| v2 field | n | flagged | Wilson 95% CI |
|---|---|---|---|
| route | 408 | 0 | [0.0, 0.0093] |
| strength_value | 408 | 0 | [0.0, 0.0093] |
| formulation | 408 | 0 | [0.0, 0.0093] |
| as_needed | 408 | 0 | [0.0, 0.0093] |
| food_timing | 408 | 0 | [0.0, 0.0093] |
| status | 408 | 1 | [0.0004, 0.0138] |
| speaker | 408 | 1 | [0.0004, 0.0138] |
| patient_age_band | 80 | 0 | [0.0, 0.0458] |

Flags on error-free records by check and reason code: `C4:cannot_verify:count_unit` 151, `C4:cannot_verify:paediatric` 40, `C2:uncoded` 39, `C6:uncoded` 39, `C4:cannot_verify:no_range` 32, `C8:uncoded` 24, `C4:cannot_verify:liquid_strength` 24, `C3:status_unsupported` 1, `C3:speaker_not_prescriber` 1

## Catch rate per planted v2 type (unique mutations)

`caught` = a flag on the injected field; `detected` = such a flag that is not cannot_verify and is new compared with the error-free record; `to review` = any flag anywhere in the record.

| type | candidate fields | n_unique | caught [CI] | detected [CI] | to review [CI] | injections | checks at field | classes at field | note |
|---|---|---|---|---|---|---|---|---|---|
| j route swap | 340 | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 | C2 200, C4 200 | CR-ROUTE 200, uncoded 200 |  |
| k strength drop | 0 | 0 | - | - | - | 0 | - | - | not measurable: 0 candidate fields in the 328 source records (no record has this field filled) |
| l status flip | 392 | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 | C3 200 | CR-NEG 200 |  |
| m age band flip | 80 | 80 | 80/80 [0.9542, 1.0] | 80/80 [0.9542, 1.0] | 80/80 [0.9542, 1.0] | 200 | C2 200, C4 200 | CR-PAEDIATRIC 200, uncoded 200 |  |

Known limits: field evidence of a planted value still points at the ORIGINAL words, so these are 'value disagrees with its own span' errors (easy for rules). Speaker cannot be checked against transcript.v1 (no roles). C7 does not look at the new v2 spans. Every Kannada rule is AI-written, not native-validated.
