# m7_eval results (DEV split)

git e75280e; seed 20261109; 1000 bootstrap resamples. Every proportion: k/n [Wilson 95% CI]; zero counts also give the rule-of-three bound.

**IN-SAMPLE (DEV): the m3 rules and m4 checks were written and fixed while looking at dev (D-115, D-120, D-121); dev numbers are not an estimate of performance on new wording.**

## E4 headline: planted errors in the TRANSCRIPT, text-only checks (next to review burden)

| type | caught at field | flag rate on error-free fields |
|---|---|---|
| negation drop | 14/193 [0.044, 0.118] | 271/1200 [0.203, 0.250] |
| negation add | 13/200 [0.038, 0.108] | 271/1200 [0.203, 0.250] |
| digit change | 115/197 [0.514, 0.650] | 271/1200 [0.203, 0.250] |
| digit-order swap | 104/118 [0.811, 0.928] | 271/1200 [0.203, 0.250] |
| unit change | 191/200 [0.917, 0.976] | 271/1200 [0.203, 0.250] |
| drug swap (confusable) | 0/183 [0.000, 0.021] (0 of 183; upper ~3/N = 0.0164) | 271/1200 [0.203, 0.250] |
| frequency swap | 0/200 [0.000, 0.019] (0 of 200; upper ~3/N = 0.0150) | 271/1200 [0.203, 0.250] |
| duration swap | 0/200 [0.000, 0.019] (0 of 200; upper ~3/N = 0.0150) | 271/1200 [0.203, 0.250] |

Record-level and oracle (upper bound) rows: tables/e4_planted_by_type.csv, labelled.

## H1 dev preview (pre-registered thresholds; NOT the test result)

| row | critical caught | flag rate error-free fields |
|---|---|---|
| HEADLINE: error in the transcript itself, text-only checks | 437/1491 [0.271, 0.317] | 271/1200 [0.203, 0.250] |
| record-level: record mutated, transcript correct (easier) | 1707/1707 [0.998, 1.000] | 271/1200 [0.203, 0.250] |
| H1 records | 189/328 [0.522, 0.628] |  |

## E3 ablation (transcript text-only; remove one check)

| removed | escaped | flag rate error-free |
|---|---|---|
| none (all C1..C8) | 1054/1491 [0.683, 0.730] | 271/1200 [0.203, 0.250] |
| C1 | 1054/1491 [0.683, 0.730] | 271/1200 [0.203, 0.250] |
| C2 | 1054/1491 [0.683, 0.730] | 271/1200 [0.203, 0.250] |
| C3 | 1062/1491 [0.689, 0.735] | 271/1200 [0.203, 0.250] |
| C4 | 1458/1491 [0.969, 0.984] | 63/1200 [0.041, 0.067] |
| C5 | 1054/1491 [0.683, 0.730] | 271/1200 [0.203, 0.250] |
| C6 | 1054/1491 [0.683, 0.730] | 271/1200 [0.203, 0.250] |
| C7 | 1054/1491 [0.683, 0.730] | 271/1200 [0.203, 0.250] |
| C8 | 1067/1491 [0.692, 0.738] | 247/1200 [0.184, 0.230] |

## E2 extraction (natural errors; per 1,000 fields; primary CI = cluster bootstrap by template family)

| system | subset | severity | errors/fields | per 1000 | cluster CI | Wilson CI | rule of 3 | label |
|---|---|---|---|---|---|---|---|---|
| rules | full_dev | critical | 0/3624 | 0.0 | [0.0, 0.0] | [0.0, 1.06] | 0.83 | IN-SAMPLE (DEV): the m3 rules and m4 checks were written and |
| rules | full_dev | major | 48/3624 | 13.25 | [4.83, 23.3] | [10.0, 17.52] |  | IN-SAMPLE (DEV): the m3 rules and m4 checks were written and |
| rules | full_dev | minor | 0/3624 | 0.0 | [0.0, 0.0] | [0.0, 1.06] | 0.83 | IN-SAMPLE (DEV): the m3 rules and m4 checks were written and |
| rules | full_dev | any | 48/3624 | 13.25 | [4.83, 23.3] | [10.0, 17.52] |  | IN-SAMPLE (DEV): the m3 rules and m4 checks were written and |
| rules | llm_subset | critical | 0/488 | 0.0 | [0.0, 0.0] | [0.0, 7.81] | 6.15 | IN-SAMPLE (DEV): the m3 rules and m4 checks were written and |
| rules | llm_subset | major | 4/488 | 8.2 | [0.0, 16.08] | [3.19, 20.88] |  | IN-SAMPLE (DEV): the m3 rules and m4 checks were written and |
| rules | llm_subset | minor | 0/488 | 0.0 | [0.0, 0.0] | [0.0, 7.81] | 6.15 | IN-SAMPLE (DEV): the m3 rules and m4 checks were written and |
| rules | llm_subset | any | 4/488 | 8.2 | [0.0, 16.08] | [3.19, 20.88] |  | IN-SAMPLE (DEV): the m3 rules and m4 checks were written and |
| llm | llm_subset | - | None/None |  | [None, None] | [None, None] |  | STALE: LLM outputs were made on pre-REFREEZE-1 data (D-120); |

## E1 ASR

**m2 not run yet**: no results/m2_asr/<run>/dev/transcripts.jsonl found; E1 and the ASR part of H2 are pending (m2_asr is not built). Code tested on fixtures.

## E5 access matrix (m5)

| slice | n | unauthorized successes | unexpected denials |
|---|---|---|---|
| ALL=ALL | 1499 | 0/1398 [0.000, 0.003] (0 of 1398; upper ~3/N = 0.0021) | 0/101 [0.000, 0.037] (0 of 101; upper ~3/N = 0.0297) |
| layer=api | 594 | 0/571 [0.000, 0.007] (0 of 571; upper ~3/N = 0.0053) | 0/23 [0.000, 0.143] (0 of 23; upper ~3/N = 0.1304) |
| layer=db | 905 | 0/827 [0.000, 0.005] (0 of 827; upper ~3/N = 0.0036) | 0/78 [0.000, 0.047] (0 of 78; upper ~3/N = 0.0385) |

## E6 helper (m8, dev questions only)

| retriever | in-scope correct card | out-of-scope refused | dosing/diagnosis refused | answers cite card |
|---|---|---|---|---|
| tfidf | 7/20 [0.181, 0.567] | 18/18 [0.824, 1.000] | 8/8 [0.676, 1.000] | 7/7 [0.646, 1.000] |
| ollama | 10/20 [0.299, 0.701] | 18/18 [0.824, 1.000] | 8/8 [0.676, 1.000] | 10/10 [0.723, 1.000] |

## Frame overlap (D-90), from template text only

| template_split | n_template_turns | seen_in_dev | unseen | slot_only |
|---|---|---|---|---|
| dev | 98 | 86 | 0 | 12 |
| test | 83 | 15 | 56 | 12 |

## Notes

- Frame marker from TEMPLATE text only (data/templates); unit = template turn, not conversation turn. Dev templates are 'seen' by definition; the marker matters for the test split, where it slices results in the guarded eval-test run (D-90).
- E2: inputs are record.v1 / gold.v1, so CR-ROUTE, CR-PAEDIATRIC and CR-LIQUID-STRENGTH are NOT MEASURABLE (not zero). They appear once m1 writes gold.v2 and m3 record.v2.
- E6: 68 m8 rows of the other split were dropped without scoring
