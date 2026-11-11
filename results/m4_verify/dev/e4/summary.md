# E4 planted-mistake results (m4_verify)

Gold source: `data/gold`: 328 conversations loaded (264 files not in dev.txt, never opened). Lexicon: `data/lexicon/drugs.csv`. Seed 20261109, up to 200 injections per type (repeats of the same mutation are counted ONCE). C7 threshold 0.6 (UNTUNED placeholder (no DEV ASR run yet)). Verdicts validated against verdict.v1: 5528 (errors: 0).

PLANTED errors on SYNTHETIC text (not native-validated). Every proportion is k/n over UNIQUE mutations with a Wilson 95% CI in brackets. No clinical claim is made.

## Review burden on the SAME error-free records (read this next to every recall number)

| unit | n | flagged (any) | Wilson 95% CI | flagged excl. cannot_verify | Wilson 95% CI |
|---|---|---|---|---|---|
| record | 328 | 189 (0.5762) | [0.5222, 0.6285] | 48 (0.1463) | [0.1122, 0.1887] |
| field | 1200 | 271 (0.2258) | [0.2031, 0.2503] | 63 (0.0525) | [0.0412, 0.0666] |

Flags on error-free records by check and reason code (cannot_verify = the rules cannot check this value; it is not evidence of an error):

`C2:uncoded` 39, `C4:cannot_verify:count_unit` 152, `C4:cannot_verify:liquid_strength` 24, `C4:cannot_verify:no_range` 32, `C4:cannot_verify:paediatric` 40, `C6:uncoded` 39, `C8:uncoded` 24

## Catch rate per planted type (unique mutations)

`caught` = a flag on the injected field; `detected` = such a flag that is not cannot_verify and is new compared with the error-free record; `to review` = any flag anywhere in the record.

| level | condition | type | n_unique | caught at field [CI] | detected [CI] | to review [CI] | injections |
|---|---|---|---|---|---|---|---|
| record | no_encounter_index | i wrong patient_ref | 200 | 0/200 [0.0, 0.0188] | 0/200 [0.0, 0.0188] | 103/200 [0.4461, 0.5833] | 200 |
| record | with_encounter_index | a negation drop | 193 | 193/193 [0.9805, 1.0] | 193/193 [0.9805, 1.0] | 193/193 [0.9805, 1.0] | 200 |
| record | with_encounter_index | b negation add | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| record | with_encounter_index | c digit change | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| record | with_encounter_index | d digit-order swap | 139 | 139/139 [0.9731, 1.0] | 139/139 [0.9731, 1.0] | 139/139 [0.9731, 1.0] | 200 |
| record | with_encounter_index | e unit change | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| record | with_encounter_index | f drug swap (confusable) | 185 | 185/185 [0.9797, 1.0] | 185/185 [0.9797, 1.0] | 185/185 [0.9797, 1.0] | 200 |
| record | with_encounter_index | g frequency swap | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| record | with_encounter_index | h duration swap | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| record | with_encounter_index | i wrong patient_ref | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | a negation drop | 193 | 193/193 [0.9805, 1.0] | 193/193 [0.9805, 1.0] | 193/193 [0.9805, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | b negation add | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | c digit change | 197 | 197/197 [0.9809, 1.0] | 197/197 [0.9809, 1.0] | 197/197 [0.9809, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | d digit-order swap | 118 | 118/118 [0.9685, 1.0] | 118/118 [0.9685, 1.0] | 118/118 [0.9685, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | e unit change | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | f drug swap (confusable) | 183 | 183/183 [0.9794, 1.0] | 183/183 [0.9794, 1.0] | 183/183 [0.9794, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | g frequency swap | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| transcript | oracle_second_transcript_upper_bound | h duration swap | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] | 200 |
| transcript | text_only | a negation drop | 193 | 14/193 [0.0437, 0.1181] | 14/193 [0.0437, 0.1181] | 75/193 [0.3226, 0.4589] | 200 |
| transcript | text_only | b negation add | 200 | 13/200 [0.0384, 0.108] | 13/200 [0.0384, 0.108] | 119/200 [0.5258, 0.6606] | 200 |
| transcript | text_only | c digit change | 197 | 115/197 [0.514, 0.6503] | 52/197 [0.2073, 0.3296] | 152/197 [0.7081, 0.8247] | 200 |
| transcript | text_only | d digit-order swap | 118 | 104/118 [0.8107, 0.928] | 79/118 [0.5805, 0.7478] | 111/118 [0.8826, 0.971] | 200 |
| transcript | text_only | e unit change | 200 | 191/200 [0.9167, 0.9761] | 131/200 [0.5868, 0.7174] | 195/200 [0.9428, 0.9893] | 200 |
| transcript | text_only | f drug swap (confusable) | 183 | 0/183 [0.0, 0.0206] | 0/183 [0.0, 0.0206] | 132/183 [0.6523, 0.7812] | 200 |
| transcript | text_only | g frequency swap | 200 | 0/200 [0.0, 0.0188] | 0/200 [0.0, 0.0188] | 179/200 [0.8448, 0.9303] | 200 |
| transcript | text_only | h duration swap | 200 | 0/200 [0.0, 0.0188] | 0/200 [0.0, 0.0188] | 179/200 [0.8448, 0.9303] | 200 |

## Per field (unique mutations)

| level | condition | field | n_unique | caught at field [CI] | detected [CI] |
|---|---|---|---|---|---|
| record | no_encounter_index | patient_ref | 200 | 0/200 [0.0, 0.0188] | 0/200 [0.0, 0.0188] |
| record | with_encounter_index | dose_unit | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] |
| record | with_encounter_index | dose_value | 186 | 186/186 [0.9798, 1.0] | 186/186 [0.9798, 1.0] |
| record | with_encounter_index | drug | 185 | 185/185 [0.9797, 1.0] | 185/185 [0.9797, 1.0] |
| record | with_encounter_index | duration_days | 285 | 285/285 [0.9867, 1.0] | 285/285 [0.9867, 1.0] |
| record | with_encounter_index | frequency_per_day | 258 | 258/258 [0.9853, 1.0] | 258/258 [0.9853, 1.0] |
| record | with_encounter_index | negated | 222 | 222/222 [0.983, 1.0] | 222/222 [0.983, 1.0] |
| record | with_encounter_index | patient_ref | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] |
| record | with_encounter_index | present | 171 | 171/171 [0.978, 1.0] | 171/171 [0.978, 1.0] |
| transcript | oracle_second_transcript_upper_bound | dose_unit | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] |
| transcript | oracle_second_transcript_upper_bound | dose_value | 315 | 315/315 [0.988, 1.0] | 315/315 [0.988, 1.0] |
| transcript | oracle_second_transcript_upper_bound | drug | 183 | 183/183 [0.9794, 1.0] | 183/183 [0.9794, 1.0] |
| transcript | oracle_second_transcript_upper_bound | duration_days | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] |
| transcript | oracle_second_transcript_upper_bound | frequency_per_day | 200 | 200/200 [0.9812, 1.0] | 200/200 [0.9812, 1.0] |
| transcript | oracle_second_transcript_upper_bound | negated | 222 | 222/222 [0.983, 1.0] | 222/222 [0.983, 1.0] |
| transcript | oracle_second_transcript_upper_bound | present | 171 | 171/171 [0.978, 1.0] | 171/171 [0.978, 1.0] |
| transcript | text_only | dose_unit | 200 | 191/200 [0.9167, 0.9761] | 131/200 [0.5868, 0.7174] |
| transcript | text_only | dose_value | 315 | 219/315 [0.6423, 0.7435] | 131/315 [0.3628, 0.471] |
| transcript | text_only | drug | 183 | 0/183 [0.0, 0.0206] | 0/183 [0.0, 0.0206] |
| transcript | text_only | duration_days | 200 | 0/200 [0.0, 0.0188] | 0/200 [0.0, 0.0188] |
| transcript | text_only | frequency_per_day | 200 | 0/200 [0.0, 0.0188] | 0/200 [0.0, 0.0188] |
| transcript | text_only | negated | 222 | 11/222 [0.0279, 0.0865] | 11/222 [0.0279, 0.0865] |
| transcript | text_only | present | 171 | 16/171 [0.0584, 0.1466] | 16/171 [0.0584, 0.1466] |

## Conditions

- `with_encounter_index`: record-level mutation, encounter index given (patient link checkable)
- `no_encounter_index`: record-level wrong patient_ref, no encounter index (known blind spot)
- `text_only`: ASR-like transcript edit; record agrees with the corrupted text; text-only checks
- `oracle_second_transcript_upper_bound`: same, plus C7 against the UNCORRUPTED gold text as second transcript: an UPPER BOUND (a real second ASR output has its own errors)

Transcript level: `text_only` = detectable by text-only checks; anything caught only under `oracle_second_transcript_upper_bound` NEEDS an audio/ASR cross-check, and that row is an UPPER BOUND (the second transcript is the uncorrupted gold text). C7 word confidence was not evaluated: synthetic injections have no real confidences and inventing them would be circular.

Drug swaps (type f) use only lexicon confusable pairs: 231 of 408 medication items have a drug with no listed confusable and are never swapped.

Per check: `per_check.csv` (unique mutations where the check flagged at the field / detected / was the only detector). Raw rows: `injection_results.jsonl`; logs: `injection_log_*.jsonl`.
