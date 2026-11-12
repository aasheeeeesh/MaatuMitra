# gold.v2 coverage

Counts are conversations (patient_age_band, conversations) or medication entries (all others), derived from data/gold_v2 (labels come from the templates). Liquid doses are doses in ml; none states a strength, so all have null strength (the case m4 must flag as CR-LIQUID-STRENGTH). Age is null where nobody says the word for child.

| field | value | dev | test | all |
|---|---|---|---|---|
| status | advised_against | 15 | 35 | 50 |
| status | already_taken | 13 | 15 | 28 |
| status | not_taken | 20 | 22 | 42 |
| status | prescribed | 329 | 269 | 598 |
| status | stopped_early | 15 | 11 | 26 |
| status | unknown | 16 | 0 | 16 |
| route | None | 68 | 145 | 213 |
| route | injection_unspecified | 16 | 0 | 16 |
| route | oral | 324 | 207 | 531 |
| formulation | None | 108 | 145 | 253 |
| formulation | capsule | 24 | 26 | 50 |
| formulation | injection | 16 | 0 | 16 |
| formulation | syrup | 40 | 24 | 64 |
| formulation | tablet | 220 | 157 | 377 |
| as_needed | None | 384 | 352 | 736 |
| as_needed | True | 24 | 0 | 24 |
| food_timing | None | 384 | 272 | 656 |
| food_timing | after_food | 24 | 80 | 104 |
| patient_age_band | child | 80 | 48 | 128 |
| patient_age_band | null | 248 | 216 | 464 |
| conversations | | 328 | 264 | 592 |
| medications | | 408 | 352 | 760 |
| liquid_doses_ml | | 24 | 16 | 40 |
| liquid_doses_with_null_strength | | 24 | 16 | 40 |
| strength_set | | 0 | 0 | 0 |
| weight_kg_set | | 0 | 0 | 0 |
