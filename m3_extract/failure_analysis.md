## Hand-written analysis (nlp-engineer, rewritten 2026-11-11 for the fix pass; read with the generated examples below)

Numbers: errors / fields, per 1,000 fields, Wilson 95% CI, N = fields. Source: `results/m3_extract/dev_scores.csv`.
Gold transcripts only (no ASR yet), synthetic template text from ONE generator, not native-validated.

**These are IN-SAMPLE numbers.** The rules were written while reading DEV conversations, so DEV is
where they were tuned. Do not read any row below as expected accuracy on new data. The only
unseen-wording evidence is the pre-REFREEZE v1 holdout line, which is historical.

Rules after the fix pass (version `rules_v3_frozen`, REFREEZE-1 data), all 328 DEV conversations:

| part | records | fields | critical /1000 [CI] | major /1000 [CI] |
|---|---|---|---|---|
| dev_tune (IN-SAMPLE) | 240 | 2704 | 0 (0) [0, 1.4] | 0 (0) [0, 1.4] |
| dev_holdout (CONTAMINATED: 9 holdout templates were looked at while fixing v2 and v3) | 88 | 920 | 0 (0) [0, 4.2] | 52.2 (48) [39.6, 68.5] |
| all dev (pooled, NOT an accuracy estimate) | 328 | 3624 | 0 (0) [0, 1.1] | 13.2 (48) [10.0, 17.5] |
| historical: rules v1, dev_holdout, PRE-REFREEZE data (the only unseen-wording figure) | 88 | 920 | 7.6 (7) [3.7, 15.6] | 52.2 (48) [39.6, 68.5] |

Errors are clustered (the 7 v1 critical errors came from one template, c5), so the Wilson intervals
are too narrow; a per-template bootstrap would be wider (not done).

Per field, all 328 DEV conversations (rules v3, IN-SAMPLE; field rows depend on how many gold items exist):

| field | N | critical errors /1000 [CI] | major errors /1000 [CI] |
|---|---|---|---|
| medication.drug / dose_value / dose_unit / frequency_per_day / duration_days / negated (each) | 408 | 0 [0, 9.3] | 0 [0, 9.3] |
| symptom.name / symptom.present (each) | 304 | 0 [0, 12.5] | 0 [0, 12.5] |
| advice.text | 120 | 0 [0, 31.0] | 40 (333.3) [255.3, 421.7] |
| advice.negated | 120 | 0 [0, 31.0] | 0 [0, 31.0] |
| follow_up.text | 328 | 0 [0, 11.6] | 8 (24.4) [12.4, 47.4] |

The 32-of-40 caveat: the old rules-vs-LLM subset (40 conversations) has 32 dev_tune ids, which the
rules were written against, and only 8 dev_holdout ids. Rules numbers on that subset are 80%
in-sample and must not be used to say the rules beat the LLM.

### Changes in the fix pass (2026-11-11)

- Removed the test-only branch `ಡ್ರೆ` and test-only words (D-90). Added fused symptoms (ಜ್ವರವಿಲ್ಲ),
  ಆಗಿದ್ದರೆ in the fever follow-up, ಪ್ಯಾಕೆಟ್ as sachet (D-93), short-vowel ORS variant, ಎರಡೂವರೆ = 2.5.
- REFREEZE-1 made dev_tune worse at first: 9 errors (child-syrup 2.5 ml unreadable, 8 conversations of
  template i5 with the fever condition in the drug clause, 1 follow-up wording). Fixed with
  dev-informed additions (in-sample, disclosed). Critical errors on DEV fell from 10 to 0.

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

### LLM pipeline (E2): STALE (computed on PRE-REFREEZE data; not rerun)

The comparison below was run before commit 66ff51a regenerated the data (new lexicon ranges, ORS
spelling, child syrup doses). A full rerun on the 40-conversation subset takes about 25 minutes
(median 47 s per conversation), above the 15-minute limit set for this fix pass, so it was NOT rerun.
Its outputs are kept in `results/m3_extract/llm_STALE_pre_refreeze/` and are no longer scored.
The old LLM numbers (kept only as history): critical 11.8/1000 (6 of 508 fields) [5.4, 25.5],
major 116.1/1000 (59) [91.1, 146.9], 4 records rejected by the evidence check. The matching rules
row was on 80% in-sample conversations, so no ranking of rules versus LLM follows from it.


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
