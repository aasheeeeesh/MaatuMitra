# E4 planted-mistake results (m4_verify)

Gold source: `fixtures/gold/valid`: 6 conversations loaded (0 files not in dev.txt, never opened). Lexicon: `fixtures/lexicon/drugs_fixture.csv`. Seed 20261109, up to 200 injections per type (repeats of the same mutation are counted ONCE). C7 threshold 0.6 (UNTUNED placeholder (no DEV ASR run yet)). Verdicts validated against verdict.v1: 5206 (errors: 0).

PLANTED errors on SYNTHETIC text (not native-validated). Every proportion is k/n over UNIQUE mutations with a Wilson 95% CI in brackets. No clinical claim is made.

## Review burden on the SAME error-free records (read this next to every recall number)

| unit | n | flagged (any) | Wilson 95% CI | flagged excl. cannot_verify | Wilson 95% CI |
|---|---|---|---|---|---|
| record | 6 | 0 (0.0) | [0.0, 0.3903] | 0 (0.0) | [0.0, 0.3903] |
| field | 18 | 0 (0.0) | [0.0, 0.1759] | 0 (0.0) | [0.0, 0.1759] |

Flags on error-free records by check and reason code (cannot_verify = the rules cannot check this value; it is not evidence of an error):

(none)

## Catch rate per planted type (unique mutations)

`caught` = a flag on the injected field; `detected` = such a flag that is not cannot_verify and is new compared with the error-free record; `to review` = any flag anywhere in the record.

| level | condition | type | n_unique | caught at field [CI] | detected [CI] | to review [CI] | injections |
|---|---|---|---|---|---|---|---|
| record | no_encounter_index | i wrong patient_ref | 30 | 0/30 [0.0, 0.1135] | 0/30 [0.0, 0.1135] | 0/30 [0.0, 0.1135] | 200 |
| record | with_encounter_index | a negation drop | 4 | 4/4 [0.5101, 1.0] | 4/4 [0.5101, 1.0] | 4/4 [0.5101, 1.0] | 200 |
| record | with_encounter_index | b negation add | 7 | 7/7 [0.6457, 1.0] | 7/7 [0.6457, 1.0] | 7/7 [0.6457, 1.0] | 200 |
| record | with_encounter_index | c digit change | 90 | 90/90 [0.9591, 1.0] | 90/90 [0.9591, 1.0] | 90/90 [0.9591, 1.0] | 200 |
| record | with_encounter_index | d digit-order swap | 3 | 3/3 [0.4385, 1.0] | 3/3 [0.4385, 1.0] | 3/3 [0.4385, 1.0] | 200 |
| record | with_encounter_index | e unit change | 15 | 15/15 [0.7961, 1.0] | 15/15 [0.7961, 1.0] | 15/15 [0.7961, 1.0] | 200 |
| record | with_encounter_index | f drug swap (confusable) | 2 | 2/2 [0.3424, 1.0] | 2/2 [0.3424, 1.0] | 2/2 [0.3424, 1.0] | 200 |
| record | with_encounter_index | g frequency swap | 12 | 12/12 [0.7575, 1.0] | 12/12 [0.7575, 1.0] | 12/12 [0.7575, 1.0] | 200 |
| record | with_encounter_index | h duration swap | 12 | 12/12 [0.7575, 1.0] | 12/12 [0.7575, 1.0] | 12/12 [0.7575, 1.0] | 200 |
| record | with_encounter_index | i wrong patient_ref | 30 | 30/30 [0.8865, 1.0] | 30/30 [0.8865, 1.0] | 30/30 [0.8865, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | a negation drop | 4 | 4/4 [0.5101, 1.0] | 4/4 [0.5101, 1.0] | 4/4 [0.5101, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | b negation add | 7 | 7/7 [0.6457, 1.0] | 7/7 [0.6457, 1.0] | 7/7 [0.6457, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | c digit change | 73 | 73/73 [0.95, 1.0] | 73/73 [0.95, 1.0] | 73/73 [0.95, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | d digit-order swap | 3 | 3/3 [0.4385, 1.0] | 3/3 [0.4385, 1.0] | 3/3 [0.4385, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | e unit change | 12 | 12/12 [0.7575, 1.0] | 12/12 [0.7575, 1.0] | 12/12 [0.7575, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | f drug swap (confusable) | 2 | 2/2 [0.3424, 1.0] | 2/2 [0.3424, 1.0] | 2/2 [0.3424, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | g frequency swap | 15 | 15/15 [0.7961, 1.0] | 15/15 [0.7961, 1.0] | 15/15 [0.7961, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | h duration swap | 16 | 16/16 [0.8064, 1.0] | 16/16 [0.8064, 1.0] | 16/16 [0.8064, 1.0] | 200 |
| transcript | text_only | a negation drop | 4 | 0/4 [0.0, 0.4899] | 0/4 [0.0, 0.4899] | 0/4 [0.0, 0.4899] | 200 |
| transcript | text_only | b negation add | 7 | 0/7 [0.0, 0.3543] | 0/7 [0.0, 0.3543] | 0/7 [0.0, 0.3543] | 200 |
| transcript | text_only | c digit change | 73 | 29/73 [0.2929, 0.5119] | 29/73 [0.2929, 0.5119] | 29/73 [0.2929, 0.5119] | 200 |
| transcript | text_only | d digit-order swap | 3 | 3/3 [0.4385, 1.0] | 3/3 [0.4385, 1.0] | 3/3 [0.4385, 1.0] | 200 |
| transcript | text_only | e unit change | 12 | 12/12 [0.7575, 1.0] | 8/12 [0.3906, 0.8619] | 12/12 [0.7575, 1.0] | 200 |
| transcript | text_only | f drug swap (confusable) | 2 | 0/2 [0.0, 0.6576] | 0/2 [0.0, 0.6576] | 1/2 [0.0945, 0.9055] | 200 |
| transcript | text_only | g frequency swap | 15 | 5/15 [0.1518, 0.5829] | 5/15 [0.1518, 0.5829] | 5/15 [0.1518, 0.5829] | 200 |
| transcript | text_only | h duration swap | 16 | 0/16 [0.0, 0.1936] | 0/16 [0.0, 0.1936] | 0/16 [0.0, 0.1936] | 200 |

## Per field (unique mutations)

| level | condition | field | n_unique | caught at field [CI] | detected [CI] |
|---|---|---|---|---|---|
| record | no_encounter_index | patient_ref | 30 | 0/30 [0.0, 0.1135] | 0/30 [0.0, 0.1135] |
| record | with_encounter_index | dose_unit | 15 | 15/15 [0.7961, 1.0] | 15/15 [0.7961, 1.0] |
| record | with_encounter_index | dose_value | 54 | 54/54 [0.9336, 1.0] | 54/54 [0.9336, 1.0] |
| record | with_encounter_index | drug | 2 | 2/2 [0.3424, 1.0] | 2/2 [0.3424, 1.0] |
| record | with_encounter_index | duration_days | 20 | 20/20 [0.8389, 1.0] | 20/20 [0.8389, 1.0] |
| record | with_encounter_index | frequency_per_day | 24 | 24/24 [0.862, 1.0] | 24/24 [0.862, 1.0] |
| record | with_encounter_index | negated | 7 | 7/7 [0.6457, 1.0] | 7/7 [0.6457, 1.0] |
| record | with_encounter_index | patient_ref | 30 | 30/30 [0.8865, 1.0] | 30/30 [0.8865, 1.0] |
| record | with_encounter_index | present | 4 | 4/4 [0.5101, 1.0] | 4/4 [0.5101, 1.0] |
| transcript | oracle_second_transcript_upper_bound | dose_unit | 12 | 12/12 [0.7575, 1.0] | 12/12 [0.7575, 1.0] |
| transcript | oracle_second_transcript_upper_bound | dose_value | 76 | 76/76 [0.9519, 1.0] | 76/76 [0.9519, 1.0] |
| transcript | oracle_second_transcript_upper_bound | drug | 2 | 2/2 [0.3424, 1.0] | 2/2 [0.3424, 1.0] |
| transcript | oracle_second_transcript_upper_bound | duration_days | 16 | 16/16 [0.8064, 1.0] | 16/16 [0.8064, 1.0] |
| transcript | oracle_second_transcript_upper_bound | frequency_per_day | 15 | 15/15 [0.7961, 1.0] | 15/15 [0.7961, 1.0] |
| transcript | oracle_second_transcript_upper_bound | negated | 7 | 7/7 [0.6457, 1.0] | 7/7 [0.6457, 1.0] |
| transcript | oracle_second_transcript_upper_bound | present | 4 | 4/4 [0.5101, 1.0] | 4/4 [0.5101, 1.0] |
| transcript | text_only | dose_unit | 12 | 12/12 [0.7575, 1.0] | 8/12 [0.3906, 0.8619] |
| transcript | text_only | dose_value | 76 | 32/76 [0.3165, 0.5332] | 32/76 [0.3165, 0.5332] |
| transcript | text_only | drug | 2 | 0/2 [0.0, 0.6576] | 0/2 [0.0, 0.6576] |
| transcript | text_only | duration_days | 16 | 0/16 [0.0, 0.1936] | 0/16 [0.0, 0.1936] |
| transcript | text_only | frequency_per_day | 15 | 5/15 [0.1518, 0.5829] | 5/15 [0.1518, 0.5829] |
| transcript | text_only | negated | 7 | 0/7 [0.0, 0.3543] | 0/7 [0.0, 0.3543] |
| transcript | text_only | present | 4 | 0/4 [0.0, 0.4899] | 0/4 [0.0, 0.4899] |

## Conditions

- `with_encounter_index`: record-level mutation, encounter index given (patient link checkable)
- `no_encounter_index`: record-level wrong patient_ref, no encounter index (known blind spot)
- `text_only`: ASR-like transcript edit; record agrees with the corrupted text; text-only checks
- `oracle_second_transcript_upper_bound`: same, plus C7 against the UNCORRUPTED gold text as second transcript: an UPPER BOUND (a real second ASR output has its own errors)

Transcript level: `text_only` = detectable by text-only checks; anything caught only under `oracle_second_transcript_upper_bound` NEEDS an audio/ASR cross-check, and that row is an UPPER BOUND (the second transcript is the uncorrupted gold text). C7 word confidence was not evaluated: synthetic injections have no real confidences and inventing them would be circular.

Drug swaps (type f) use only lexicon confusable pairs: 2 of 4 medication items have a drug with no listed confusable and are never swapped.

Per check: `per_check.csv` (unique mutations where the check flagged at the field / detected / was the only detector). Raw rows: `injection_results.jsonl`; logs: `injection_log_*.jsonl`.
