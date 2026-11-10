## Hand-written analysis (nlp-engineer, 2026-11-10; read with the generated examples below)

Numbers: errors / fields, per 1,000 fields, Wilson 95% CI. Source: `results/m3_extract/dev_scores.csv`.
Gold transcripts only (no ASR yet), synthetic template text, not native-validated.

| run | records | fields | critical /1000 [CI] | major /1000 [CI] | rejected |
|---|---|---|---|---|---|
| rules v2, full dev | 328 | 3624 | 0 (0/3624) [0, 1.1] | 13.2 (48) [10.0, 17.5] | 0 |
| rules v2, dev_tune (IN-SAMPLE) | 240 | 2704 | 0 [0, 1.4] | 0 [0, 1.4] | 0 |
| rules v2, dev_holdout (CONTAMINATED for the v2 fix) | 88 | 920 | 0 [0, 4.2] | 52.2 (48) [39.6, 68.5] | 0 |
| **rules v1 (frozen), dev_holdout: honest unseen-wording estimate** | 88 | 920 | **7.6 (7) [3.7, 15.6]** | 52.2 (48) [39.6, 68.5] | 0 |
| rules v2, LLM subset (40) | 40 | 488 | 0 [0, 7.8] | 8.2 (4) [3.2, 20.9] | 0 |
| LLM qwen3:4b-instruct, LLM subset (40) | 40 | 508 | 11.8 (6) [5.4, 25.5] | 116.1 (59) [91.1, 146.9] | 4 |

(The LLM has more fields on the same 40 conversations because every extra item it invents adds a field.)

### Rules pipeline: what fails and why

1. **Negation flip across a question (CR-NEG, rules v1, 7 of 8 conversations of holdout template c5).**
   Input: `ನನಗೆ ಜ್ವರ ಇದೆ, ಮನೆಯಲ್ಲಿ ಇದ್ದ ಅಜಿತ್ರೋಮೈಸಿನ್ ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ? / ಇಲ್ಲಾ.` Output v1: fever ABSENT;
   gold: fever present. Cause: v1 treated every clause of a `?` sentence as the question, so the
   bare ಇಲ್ಲಾ also "answered" the statement ನನಗೆ ಜ್ವರ ಇದೆ. Fixed in v2 (decision "Rules v2"); the
   v1 number above is the honest estimate of this kind of error on new wording.
2. **Advice / follow-up wording not in the phrase list (MA-MISSED-ADVICE 40, MA-MISSED-FOLLOWUP 8; all
   on holdout templates c5, d2, g5, h6, i3).** Example: `ಲಕ್ಷಣಗಳು ಮುಂದುವರಿದರೆ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ.`
   -> nothing; gold: "if the symptoms continue, consult a doctor". Cause: advice needs an English
   gloss and the rules only know the phrases written from dev_tune. This is a NEGATIVE RESULT for the
   rules design: on unseen templates every new advice phrase is missed. The patterns were NOT
   extended with holdout phrases (that would only memorise the holdout).
3. Medications and symptoms on the holdout: 0 errors, but the holdout reuses the same drug lexicon,
   symptom words and number/frequency phrasing as dev_tune (one generator), so this does not show
   robustness to real speech, dialects or ASR errors.

### LLM pipeline (E2): what fails and why

1. **Unit invented (CR-DOSE x4):** `ಕ್ಲಾರಿಥ್ರೋಮೈಸಿನ್ ಒಂದು ಮಾತ್ರೆ ...` -> dose_unit "capsule" (gold "tablet");
   the same for zinc and azithromycin. In `m1-e4-001` the next line says ಕ್ಯಾಪ್ಸೂಲ್ and the unit leaked
   across items. One dose value dropped to null (`m1-g7-006`).
2. **Wrong duration (CR-DUR):** `m1-g5-013` "ಏಳು ದಿನ" (7 days) recorded as 5.
3. **Rejected by the evidence check (4 of 40 records, 10%).** Two quotes were not verbatim: a quote
   joining two turns (`'ವಾಂತಿ ಇದೆಯಾ? ಇಲ್ಲ.'`, the newline was dropped) and a respelled drug name
   (`ನೈಟ್ರೊಫ್ಯುರಾಂಟಿನ್` for spoken `ನೈಟ್ರೋಫ್ಯುರಾಂಟಿನ್`). Two outputs were not JSON at all: the model
   looped (`ಆ.ಆ.ಆ.ಆ...`) inside a quote until the 1,536-token limit (`m1-e7-001`, `m1-e7-004`, ~260 s
   each). The check worked as designed: these records are kept in `llm/rejected/` and scored as empty.
4. **Invented advice (MA-EXTRA-ADVICE 20):** medication instructions repeated as advice ("give zinc one
   tablet once a day for 14 days") and inferences that were never said ("do not take azithromycin").
5. **Wording (MA-WORDING-UNJUDGED 12):** e.g. "do not take antibiotic for cold" vs gold "do not take
   antibiotics for a cold". Many of these are probably the same meaning; code cannot judge it, so they
   count as MAJOR (severity rule 5). Read the LLM major rate with this in mind.
6. Latency: p50 47 s, p95 253 s per conversation (Ollama runs the model 45% CPU / 55% GPU on the
   4 GB card; the two looping outputs dominate p95).

### Blind spots shared by both pipelines

- Text-only extraction cannot see a negation that ASR dropped (only m4's C7 can, partly).
- Inflected or unlisted symptom words (ಜ್ವರವಿದೆ, ವಾಂತಿಯಾಗಿದೆ) are missed by the rules.
- Both use the same closed drug / symptom vocabulary.
