# E4 planted-mistake results (m4_verify)

Gold source: `fixtures\gold\valid` (6 conversations). Lexicon: `fixtures\lexicon\drugs_fixture.csv`. Seed 20261109, 200 injections per type. C7 threshold 0.6 (UNTUNED placeholder (no DEV ASR run yet)). Verdicts produced and validated against verdict.v1: 5206 (errors: 0).

PLANTED errors on SYNTHETIC fixture text (not native-validated). Many injections repeat the same mutation, so the honest sample size is `n_unique`; CIs on `n` overstate certainty.

## Review burden on error-free gold

| unit | n | flagged | rate | Wilson 95% CI |
|---|---|---|---|---|
| record | 6 | 0 | 0.0 | 0.0-0.3903 |
| field | 18 | 0 | 0.0 | 0.0-0.1759 |

## Catch rate (critical-error recall) per type

| level | condition | type | n | caught | rate | n_unique | unique caught | unique Wilson 95% CI |
|---|---|---|---|---|---|---|---|---|
| record | no_encounter_index | i wrong patient_ref | 200 | 0 | 0.0 | 30 | 0 | 0.0-0.1135 |
| record | with_encounter_index | a negation drop | 200 | 200 | 1.0 | 4 | 4 | 0.5101-1.0 |
| record | with_encounter_index | b negation add | 200 | 200 | 1.0 | 7 | 7 | 0.6457-1.0 |
| record | with_encounter_index | c digit change | 200 | 200 | 1.0 | 90 | 90 | 0.9591-1.0 |
| record | with_encounter_index | d digit-order swap | 200 | 200 | 1.0 | 3 | 3 | 0.4385-1.0 |
| record | with_encounter_index | e unit change | 200 | 200 | 1.0 | 15 | 15 | 0.7961-1.0 |
| record | with_encounter_index | f drug swap (confusable) | 200 | 200 | 1.0 | 18 | 18 | 0.8241-1.0 |
| record | with_encounter_index | g frequency swap | 200 | 200 | 1.0 | 12 | 12 | 0.7575-1.0 |
| record | with_encounter_index | h duration swap | 200 | 200 | 1.0 | 12 | 12 | 0.7575-1.0 |
| record | with_encounter_index | i wrong patient_ref | 200 | 200 | 1.0 | 30 | 30 | 0.8865-1.0 |
| transcript | text_only | a negation drop | 200 | 0 | 0.0 | 4 | 0 | 0.0-0.4899 |
| transcript | text_only | b negation add | 200 | 0 | 0.0 | 7 | 0 | 0.0-0.3543 |
| transcript | text_only | c digit change | 200 | 75 | 0.375 | 73 | 29 | 0.2929-0.5119 |
| transcript | text_only | d digit-order swap | 200 | 200 | 1.0 | 3 | 3 | 0.4385-1.0 |
| transcript | text_only | e unit change | 200 | 200 | 1.0 | 12 | 12 | 0.7575-1.0 |
| transcript | text_only | f drug swap (confusable) | 200 | 73 | 0.365 | 16 | 4 | 0.1018-0.495 |
| transcript | text_only | g frequency swap | 200 | 67 | 0.335 | 15 | 5 | 0.1518-0.5829 |
| transcript | text_only | h duration swap | 200 | 0 | 0.0 | 16 | 0 | 0.0-0.1936 |
| transcript | with_second_transcript | a negation drop | 200 | 200 | 1.0 | 4 | 4 | 0.5101-1.0 |
| transcript | with_second_transcript | b negation add | 200 | 200 | 1.0 | 7 | 7 | 0.6457-1.0 |
| transcript | with_second_transcript | c digit change | 200 | 200 | 1.0 | 73 | 73 | 0.95-1.0 |
| transcript | with_second_transcript | d digit-order swap | 200 | 200 | 1.0 | 3 | 3 | 0.4385-1.0 |
| transcript | with_second_transcript | e unit change | 200 | 200 | 1.0 | 12 | 12 | 0.7575-1.0 |
| transcript | with_second_transcript | f drug swap (confusable) | 200 | 200 | 1.0 | 16 | 16 | 0.8064-1.0 |
| transcript | with_second_transcript | g frequency swap | 200 | 200 | 1.0 | 15 | 15 | 0.7961-1.0 |
| transcript | with_second_transcript | h duration swap | 200 | 200 | 1.0 | 16 | 16 | 0.8064-1.0 |

Transcript level: `text_only` = what text-only checks can see when the ASR error is consistent with the record; `with_second_transcript` = C7 compares against a second, correct transcript (an ASR cross-check). Anything caught only in the second condition NEEDS an audio/ASR cross-check. C7 word-confidence was not evaluated here: synthetic injections have no real confidences and inventing them would be circular.
