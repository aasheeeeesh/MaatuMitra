# Integrity review: m1_data (2026-11-10)

Reviewer: scientific-integrity-auditor (AI agent). Label: **ai_simulated_review** (not human, native-speaker or clinical validation).
Target: m1_data at commit 9a3faf8 (freeze), repo HEAD 3973bb5. Working tree for data/, m1_data/ clean (`git status`).

## What I touched (test-split discipline)
- TEST gold and transcripts (264 + 264 files) were read ONLY by the scripted overlap check (families, template ids, dosed
  (drug, value, unit) tuples, normalised and slot-masked text, char 5-gram Jaccard) and by hashing. I did not print, read
  or analyse test labels for correctness. The only test text I looked at by eye: the shared slot-MASKED frames listed below
  (these come from templates and also occur in dev).
- Gold correctness: DEV only.
- Scripts and outputs (temp, not in repo): `<scratchpad>/scripts/leak.py`, `leak.json`, `scripts/gold_dev.py`.

## Checklist (PASS / FAIL)

| # | item | result |
|---|---|---|
| 1 | Test lock intact | PASS: `mingw32-make split-lock` -> `split-lock: OK` (exit 0); 530 locked entries (264 gold, 264 transcripts, twins_test.jsonl, test.txt). |
| 2 | Git history: freeze commit and no later test edits | PASS: `git log -- data/splits data/gold data/transcripts` shows only ef3a288 (Phase A, README) and 9a3faf8 (freeze). Later commits (c6fdf72 is earlier; 9426dcb, 67b2234, ce46096, 6f51610, 3973bb5) do not touch them. |
| 3 | results/test_access_log.md matches commits | PASS (vacuous): the file does not exist, so no `make eval-test` run is recorded, which matches the history. |
| 4 | Generator determinism | PASS: `python -m m1_data generate --out <tmp>` run twice; all 1191 generated files byte-identical between runs AND identical to the committed repo files (sha256 compared), including test.lock. |
| 5 | Family / template / dosed-combo separation | PASS: 0 shared families (12 dev / 10 test), 0 shared template ids, 0 shared dosed (drug, value, unit) tuples (40 dev / 34 test). All 30 test drug NAMES also occur in dev (disclosed in D-60). |
| 6 | Near-duplicate conversations across splits | PASS: 0 exact normalised matches, 0 slot-masked conversation matches. Nearest-neighbour char 5-gram Jaccard (slot-masked) test->dev: median 0.38, max 0.58, 0 pairs >= 0.6. Baseline dev->dev same family: median 1.00. Dev->dev other family, same category: max 0.35. |
| 7 | Near-duplicate SENTENCES / frames across splits | **FAIL (major, disclosure)**: see finding M1-1. |
| 8 | All variants of one text in one split | PASS: 224 dev and 193 test twins, 0 in the wrong split; every transcript is in its gold's split; manifest split labels 0 mismatches. 47 test twin texts equal a dev turn, but all are short (< 4 tokens, e.g. bare ಇದೆ/ಹೌದು answers). |
| 9 | D-64 sub-family reading disclosed adequately | **FAIL (major)**: D-60 says "No sentence frame ... is in both splits"; D-64 says near-copies "never straddle the split". Both are false at the clause level (finding M1-1). |
| 10 | Coverage claims match files | PASS: coverage.json and README (592 / 328 / 264 conversations, 408 / 352 medications, 848 test turns, 417 twins) equal my regenerated counts. |
| 11 | Gold correctness (DEV sample) | PASS: all 872 DEV items have spans with `text[char_start:char_end] == span_text` and lie inside `turn_index`; transcript text == turns joined by "\n" for all 592. Seeded sample (seed 20261110) of 20 DEV conversations reviewed by hand: m1-c3-007, d1-001, d1-004, e4-010, e4-013, e7-001, e7-011, e7-015, e8-012, f1-007, f3-005, f3-006, g5-013, g6-009, h5-000, h5-001, h5-007, h6-006, i1-001, i2-007. All negated/present flags agree with the text and annotation_guide section 4; Kannada digits (೪೦೦) and number words (ಹದಿನಾಲ್ಕು = 14, ಒಂದು ವಾರ = 7) map correctly. Kannada meaning is NOT native-validated. |
| 12 | "Stopped early => negated: true" convention | PASS with note (minor M1-4): written in docs/annotation_guide.md section 4 and D-62 as an open question. docs/severity.md does not mention it. |
| 13 | No tuning on test; thresholds from dev | PASS for m1 (no thresholds). |
| 14 | No clinical or educational impact claims | PASS: none found in m1_data/README.md or the D-57..D-64 entries. |

## Findings

### M1-1 (major): the dose-instruction sentence frame is shared by dev and test
- Evidence: after masking drug names, numbers and symptoms, 15 turn frames of >= 4 tokens occur in both splits. They make
  up **118 of 848 test turns (13.9%)**. At clause level it is 23 frames, **196 of 1083 test clauses (18.1%)**. The main one is
  `D N mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ N ಬಾರಿ N ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ` ("take drug N mg tablet N times a day for N days"): 8 dev / 25 test turns,
  plus its variants (ಸಾರಿ/ದಿವಸ/ವಾರ/ಎಂ ಜಿ/ಕ್ಯಾಪ್ಸೂಲ್). Source: the template text
  `[[m1|{D1.name} {D1.dose_tab} {D1.freq} {D1.dur}]] ತೆಗೆದುಕೊಳ್ಳಿ` is repeated in families of categories d, e, h and i on BOTH sides,
  and `{D.freq}` is drawn from one shared phrase list in m1_data/render.py line 104. Other shared frames are `S ಮತ್ತು S ಇದೆ` and
  `S ಎಷ್ಟು ದಿನದಿಂದ ಇದೆ`. Only 6 test turns match a dev turn exactly after normalisation (symptom-duration questions).
- Is it a leak under D-64? **Not a violation of the D-64 rule as written**: no family and no dosed combination crosses the split.
  **But it breaks the stated purpose** of PROJECT_BRIEF 6.5 ("near-duplicate sentences never straddle dev and test"). The
  shared frame carries exactly the CRITICAL fields (dose, frequency, duration). Any rule, regex or prompt written on dev will
  meet the same frame in test, so test dose, frequency and duration scores will be optimistic. D-60 and D-64 currently claim the opposite.
- Required fix (minimum, NO refreeze needed): a new decision entry that corrects D-60/D-64 with these numbers, and an m7
  requirement to report every test metric for two slices: items whose slot-masked clause frame occurs in dev ("seen frame")
  and items whose frame does not ("unseen frame"). Report both, never only the pooled number.
- Recommended (optional) refreeze: add 1-2 test-only medication-instruction frames (other word order or verb, for example
  frequency before the drug, ಕೊಡಿ/ಕುಡಿಯಿರಿ endings) as a new held-out family. It must happen BEFORE the first `make eval-test`
  (still allowed: no access log exists), with `--refreeze` and a decision entry. Without it, an "unseen dose frame" slice is
  small or empty, and m7 must say so.

### M1-2 (minor): split-lock passes if test.lock is deleted
`make split-lock` calls the checker with `--allow-missing`. If `data/splits/test.lock` is missing, it prints a WARNING and
exits 0. Now that the split is frozen, drop `--allow-missing` from the Makefile and CI.
`dev.txt` and `split_plan.json` are not locked. This is acceptable because `test.txt` is locked.

### M1-3 (minor): within-split duplicate conversations shrink the effective N
13 test conversations (and 17 dev conversations) have exactly the same normalised text as another conversation in the
same split. So the test split has 251 unique texts out of 264. m7 should report the unique-text N next to every
conversation-level N, or use a cluster bootstrap by template.

### M1-4 (minor): "stopped early" and "not finished" are labelled as negation
Example: DEV m1-c3-007 "ಅಮಾಕ್ಸಿಕ್ಲಾವ್ ಎಲ್ಲ ಮುಗಿಸಿದಿರಾ? / ಇಲ್ಲಾ" ("did you finish all the amoxiclav? / no") is gold `negated: true`.
This follows annotation_guide section 4, but clinically "partly taken" is not the same as "not taken". Under docs/severity.md,
a disagreement on these items counts as CR-NEG. m7 should report category c (stopped early) as its own slice and point to the open question.

### M1-5 (minor): code-switching is unbalanced between splits
code_switched_fraction is 0.70 in test vs 0.50 in dev (coverage.json).
This is already covered by the required code_switched slice (docs/metrics.md section 5). m7 must not pool these.

## What m7 must do to avoid overclaiming (from m1)
1. Slice by seen vs unseen clause frame (M1-1) and by category, code_switched and has_negation. Never pool TTS or
   real data with template_text.
2. State that test sentences share category style AND the dose-instruction frame with dev (D-64 plus M1-1).
3. Report unique-text N (M1-3).
4. Show category c (stopped-early convention) separately (M1-4).
5. All text is synthetic and not native-validated: no claims about real conversations.

## UNVERIFIED
- Kannada naturalness and the meaning of every template (not native-validated).
- Whether masking hid any further shared frames (my masker covers lexicon drug variants, SYMPTOMS, digits and 17 number words only).
- I did not check correctness of test gold labels, on purpose.

## Addendum (same day, after the m3 check)

### M1-6 (major): docs/annotation_guide.md contains test-only wording
57 Kannada tokens occur in TEST-family templates and in no DEV-family template. 46 of them occur in no DEV gold and no fixture.
Eight of those 46 are printed in docs/annotation_guide.md as polarity examples: ಆದ್ದರಿಂದ, ಕೋರ್ಸ್, ತಗೊಂಡ್ರೆ, ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ,
ನಿಲ್ಲಿಸಿ, ನಿಲ್ಲಿಸಿದೆ, ನಿಲ್ಲಿಸಿದೆವು, ಮುಗಿಸದೆ. Four of the 46 (ಆದ್ದರಿಂದ, ನಾಳೆ, ನಿಲ್ಲಿಸಿ, ಮುಗಿಸದೆ) are also in the shared
.claude/skills/kannada-nlp/negation_table.yaml. Builders may read the guide, so the guide is a channel for TEST
wording. m3 already uses three of these words (see reviews/m3_extract/2026-11-10-integrity.md).
**Fix**: replace the guide's examples with DEV-family wording, or mark them "appears in test families". m7 must
report the test families c_stopped_early__f1 and i_traps__f2 (and a_fever_cough__f3, D-89) as separate slices.
Changing the guide does not touch test.lock.
