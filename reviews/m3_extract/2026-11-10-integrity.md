# Integrity review: m3_extract (2026-11-10), D-89 template exposure and dev-score honesty

Reviewer: scientific-integrity-auditor (AI agent). Label: **ai_simulated_review**.
Target: m3_extract at commit ce46096 (HEAD 3973bb5). Inputs used: data/templates/*.yaml, data/templates/_forms.yaml,
data/splits/split_plan.json (which family is test), data/splits/dev.txt and test.txt (id lists only), DEV gold,
fixtures, docs/annotation_guide.md, the shared negation table, m3_extract source, and results/m3_extract.
**No test gold or test transcript was opened for this part.** Script (temp): `<scratchpad>/scripts/m3_testonly.py`.

## Method
1. From the template files, I collected every Kannada token and English gloss per family and marked a token
   TEST-ONLY if it occurs in a test-family template and in no dev-family template. Result: 57 Kannada tokens, 18 glosses.
2. I removed tokens that legitimately reach builders through DEV gold (rendered slot fills) or fixtures.
   46 tokens remain.
3. I searched every .py and .yaml file under m3_extract (handoff/merged excluded) for exact tokens. I also searched for
   sub-strings that occur only inside test-only tokens (stem leaks).

## Checklist (PASS / FAIL)

| # | item | result |
|---|---|---|
| 1 | Test lock intact; no test edits | PASS: `mingw32-make split-lock` OK at HEAD; ce46096 touches no file under data/splits, data/gold or data/transcripts. |
| 2 | No test ids in m3 code or results | PASS: `grep -F -f data/splits/test.txt` over m3_extract/ and results/m3_extract/ found 0 files. splits.py refuses any id in test.txt (an id-based guard; m4 should copy it). |
| 3 | No m3 rule, phrase or regex matches TEST-ONLY wording | **FAIL (major)**: 3 hits, see M3-1. |
| 4 | English glosses | PASS: the only test-only gloss hit ("do not take antibiotics", phrases.yaml) also occurs in DEV gold. |
| 5 | In-sample vs held-out dev labelled | PASS (mostly): failures_dev.md and README label dev_tune "IN-SAMPLE", the v2 holdout "CONTAMINATED", and the frozen v1 holdout as the honest estimate: CR 7/920 fields = 7.6 per 1000 [3.7, 15.6]. |
| 6 | Every proportion has N and a Wilson CI | PASS: all dev_scores.csv rows have errors, n_fields and a CI. Zero events are shown with Wilson upper bounds (stricter than 3/N). |
| 7 | Models scored on identical data | PASS with a caveat (M3-2): rules and LLM both use the same 40 dev ids (results/m3_extract/llm_subset.txt). |
| 8 | Claims match tables | **FAIL (major)**: M3-2 and M3-3. |
| 9 | No clinical or educational impact claims | PASS: none found. |

## Findings

### M3-1 (major): three words in m3 occur only in TEST-family templates
| word | where in m3 | test family | where else the builder could have seen it |
|---|---|---|---|
| ತಗೊಂಡ್ರೆ (spoken "if you take") | rules.py:42 comment; **rules.py:44 `CONDITIONAL_RE = (ದರೆ\|ದ್ರೆ\|ಡ್ರೆ)$`**. The `ಡ್ರೆ` branch matches no DEV or fixture text at all. | i_traps__f2 | docs/annotation_guide.md line 19 |
| ಮುಗಿಸದೆ ("without finishing") | llm.py:174 (LLM prompt), tests/test_negation.py:47 | c_stopped_early__f1 | annotation guide section 4; shared negation table |
| ನಿಲ್ಲಿಸಿ ("stop") | appears as part of tests/test_negation.py:47 (ನಿಲ್ಲಿಸಿದರು) | c_stopped_early__f1 | annotation guide; negation table |

Each word has an allowed source (the annotation guide or the shared negation table), so no rule was proven to be copied
from the test template. But the `ಡ್ರೆ` regex branch can only change outputs on TEST text (i_traps__f2), and the LLM
prompt's ಮುಗಿಸದೆ example names the TEST family's key phrase. A subtle influence on word order or ideas cannot be ruled out (D-89).
**Required fix** (the D-89 rule): either remove the `ಡ್ರೆ` branch, or keep it with a decision entry citing
annotation_guide line 19 as its source. Dev scores do not change either way, because the branch never fires on dev.
m7 must report a_fever_cough__f3, c_stopped_early__f1 and i_traps__f2 as separate slices, next to the other test families.

### M3-2 (major): the rules-vs-LLM table hides that 32 of 40 subset conversations are in-sample for the rules
llm_subset.txt has 40 ids: 32 dev_tune (rules written while reading these templates) and 8 dev_holdout.
The table row "rules v2, LLM subset (40): critical 0 [0, 7.8]" sits next to "LLM ... 11.8 (6)" with no in-sample
note. The split is in dev_scores.csv: rules, holdout part, 0/68 fields [0, 53.5] per 1000; LLM, holdout part, 1/70.
**Fix**: label the rules row "80% in-sample". Compare on the 8 holdout conversations (and say N is too small to rank)
or on a fresh subset of holdout ids. Do not claim the rules beat the LLM from this table.

### M3-3 (major): "rules v2, full dev: 0 critical (0/3624)" is listed first and pools in-sample data
240 of the 328 records are in-sample, and the rest is a contaminated holdout. Mark this row "not an accuracy estimate".
The only honest unseen-wording figure is v1 holdout: 7.6 per 1000 [3.7, 15.6].

### M3-4 (minor): the holdout is weaker than it sounds; errors are clustered
The holdout is "unseen template, SEEN family": for example b4 shares family b_cross_turn__f2 with tune template b3.
It also shares the dose-instruction frame (reviews/m1_data M1-1). The 7 v1 CR-NEG errors all come from one template, c5
(7 of 8 conversations). A Wilson CI over 920 fields treats them as independent, so it is too narrow.
Use a per-template or cluster bootstrap.

### M3-5 (minor): different field denominators
The LLM has 508 fields and the rules 488 on the same 40 records, because invented items add fields. Also report errors per
GOLD field (same denominator) or per record.

## What m7 must do (from m3)
Report test results per family (especially the three families in M3-1), never quote in-sample dev numbers, compare
rules and LLM on held-out ids only, and keep TTS, real and template_text separate. No ASR has been run yet: every m3
number is on gold transcripts.

## UNVERIFIED
- Indirect influence of the a_fever_cough__f3 frames (D-89) that left no literal trace. Token matching cannot detect it.
- Kannada meaning of every hit (not native-validated).
- I did not re-run m3 scoring or the m3 tests.
