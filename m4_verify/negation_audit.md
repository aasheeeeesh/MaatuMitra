# Negation audit on real Kannada text (m4_verify, step 3)

Auditor: safety-engineer AI agent. **Not native-validated.** Every "correct / wrong" judgement
below is my (an AI's) reading of the Kannada; a native speaker must re-check it
(m4_verify/handoff/human_todo.md).

## Sources actually fetched (2026-11-10)

| source | URL | licence | what is stored in the repo |
|---|---|---|---|
| Kannada Wikipedia article "ಜ್ವರ" (fever), oldid 1348466 | https://kn.wikipedia.org/wiki/ಜ್ವರ | CC BY-SA 4.0 | 52 sentences, verbatim, with attribution: `m4_verify/audit/kn_wikipedia_jvara_sentences.txt`; matcher output `m4_verify/audit/kn_wikipedia_jvara_matches.tsv` |
| Vijay Karnataka health article (29 Apr 2025) | https://vijaykarnataka.com/lifestyle/health/why-its-important-to-not-neglect-fever-in-the-summer/articleshow/120721236.cms | copyrighted news | **no sentences stored**; only 20 single words were tested (listed below) |
| Kannada Wikipedia "ಪ್ರತಿಜೀವಕ" | https://kn.wikipedia.org/wiki/ಪ್ರತಿಜೀವಕ | - | page does not exist (HTTP 404); nothing used |

Sentences were chosen by me from the article: every sentence that contained a negation-looking
word, a trap word (ಎಲ್ಲ, ಮಾತ್ರ, ಇಲ್ಲವೇ, ಅಲ್ಲದೆ, ಯಾವುದೇ, ಬೆಲ್ಲ...), plus some plain sentences. It is
**not a random sample**, so the counts below are not a precision/recall estimate for Kannada in general.

Re-run: `uv run python -m m4_verify audit --sentences m4_verify/audit/kn_wikipedia_jvara_sentences.txt`
(the TSV columns are: file line, NEG/---, cues found, sentence; sentence N = file line N+3).

## Round 1 (the brief's starting rules) -> what went wrong

1. **False positive, frequent: ಇಲ್ಲವೇ / ಇಲ್ಲವೆ means "or" in running text** (lines 11, 19, 25, 55 and
   many more in the article). My first version treated ಇಲ್ಲವೇ as a negative question (cue).
   Fix: ಇಲ್ಲವೇ/ಇಲ್ಲವೆ now split clauses like ಮತ್ತು; they count as a negation cue only when "?" follows.
2. **Copular negation fused to the noun was only "soft"**: ರೋಗವಲ್ಲ, ಸಾಮಾನ್ಯವಲ್ಲ, ಸುಲಭಸಾಧ್ಯವಲ್ಲ,
   ನಿಶ್ಚಿತವಲ್ಲ, ಪರ್ಯಾಯವಲ್ಲ (noun + ವ + ಅಲ್ಲ). Fix: new strong rule S-VALLA (`ವಲ್ಲಾ?$`), with the trap
   ಮಾತ್ರವಲ್ಲ ("not only", additive) excluded.
3. **Missed: negative verbal noun** ಇಲ್ಲದಿರುವುದು, ಬಾರದಿರುವುದು. Fix: S-DIRU (`C+ದಿರುವುದ[ುೂ]$`), same
   "bare consonant before" trick as -ದಿದ್ದರೆ so ಬಂದಿರುವುದು (has come) does not match.
4. **ಇಲ್ಲದ / ಇಲ್ಲದೆ ("without", absence)** were not cues. Fix: SOFT cue (counted as negation, C8 flags),
   because their scope is unclear (ಊಟ ಇಲ್ಲದೆ ಮಾತ್ರೆ... negates the food, not the tablet).

## Round 2 (after the fixes above) -> remaining misses, then fixed

Misses seen: ಅಧಿಕವಾಗಿಲ್ಲದಿದ್ದಾಗ, ಕಾಣಬರುವುದಿಲ್ಲವೆಂಬುದು, ಮಾರ್ಗವಿಲ್ಲದೆ, ರೋಗಲಕ್ಷಣವಾಗಿಲ್ಲದಿರುವ,
ಹರಡುವುದಿಲ್ಲವಾದ್ದರಿಂದ (a negative -ಿಲ್ಲ followed by more suffixes), ಸಾಧ್ಯವಾಗದೆ / ಹೀಗಾಗದೆ / ಉಂಟಾಗದೇ
(fused ಆಗ + ದೆ), ಗಣಿಸದೆ (causative stem + ದೆ), ಬರದಂತೆ ("so that it does not come").
Fixes, each with a positive / minimal-pair twin / trap test in `tests/test_negation.py`:
S-ILLA-FUSED `ಿಲ್ಲ[ದವ]` (trap ಜಿಲ್ಲೆ, ಚಿಲ್ಲರೆ), V-AAGADE `ಾಗದ[ೆೇ]$` (trap ಕಡಿಮೆಯಾಗಿದೆ),
V-ISADE `ಿಸದ[ೆೇ]$` (trap ಸೇವಿಸಿದೆ), S-DANTE `C+ದಂತೆ$` (trap ಹೇಳಿದಂತೆ).

## Final state on the 52 Wikipedia sentences (same sentences used to design the fixes!)

- 37 sentences with at least one cue; 15 with none (file lines 7 10 11 12 14 16 18 19 27 50-55; I read
  all 15 as truly without negation).
- Trap words present in the sentences, none of which triggered: ಎಲ್ಲ, ಮಾತ್ರ, ಮಾತ್ರವಲ್ಲ, ಇಲ್ಲವೇ = "or",
  ಅಲ್ಲದೆ, ಯಾವುದೇ (in ಯಾವುದೇ ಇರಲಿ), ಹೊದಿಸಿದ್ದನ್ನೆಲ್ಲ, ಬೆಲ್ಲಡೋನ್ನ, ಕೊಡಬೇಕಾದ್ದು. **Zero trap-word triggers.**
- **Remaining false positives (2)**: line 13 ಇಲ್ಲದಿದ್ದರೆ = "otherwise" (a discourse word, no entity is
  negated); line 24 "ಮಲೇರಿಯ ಒಂದರಲ್ಲೆ ಅಲ್ಲ" = "not only in malaria" (additive).
- **Wrong polarity (1)**: line 40 "...ಬರಬಾರದೆಂದೇನೂ ಇಲ್ಲ" = "it is not that it cannot come again" (double
  negation = positive). The fused ಬಾರದೆಂದೇನೂ is missed, so only ಇಲ್ಲ is seen and the clause reads as
  plain negation; C8's "two cues" rule cannot fire.
- **Still missed**: negation fused with quotative/emphatic endings in general (-ಬಾರದೆಂದು, -ಲ್ಲವೆಂದು are
  only caught when the ಿಲ್ಲ form is present); -ದೆ on stems that are not in the verb list and do not end
  in ಾಗ/ಿಸ (e.g. ತೆಗೆಯದೆ); -ಲಾರ ("cannot", ತಾಳಲಾರದೆ), ಬಾರದೆ (news words).
- Because the fixes were designed on these same sentences, the final numbers are **optimistic**
  (no held-out text). An honest held-out check needs a second, unseen article (human_todo).

## News article (20 single words tested, no sentences stored)

Matched as negation (my reading: correct): ಆಗಿಲ್ಲ, ಕಡಿಮೆಯಾಗಿಲ್ಲ, ಮಾಡಬಾರದು, ಹೋಗಬೇಡಿ, ಸಾಮಾನ್ಯವಲ್ಲ, ಪರ್ಯಾಯವಲ್ಲ,
ತೆಗೆದುಕೊಳ್ಳುವುದಿಲ್ಲ, ಆಗಿಲ್ಲದಿದ್ದರೆ. Soft (C8): ಲಕ್ಷಣಗಳಲ್ಲ (plural noun + ಅಲ್ಲ; a real negation that is only
soft). Debatable: ಮಾಡದೆ in "ನೆಗ್ಲೆಕ್ಟ್ ಮಾಡದೆ" ("without neglecting" = a positive instruction, like ಮರೆಯದೆ).
Not matched, correctly: ಇದಲ್ಲದೆ (besides), ತಪ್ಪದೆ (without fail), ನಮಗೆಲ್ಲಾ, ಎಲ್ಲಾ, ಮಾತ್ರವಲ್ಲ, ಯಾವುದೇ, ಹೌದು.
**Missed**: ತಾಳಲಾರದೆ (cannot bear), ಬಾರದೆ (without coming), and the typed-apart form "ಕಡಿಮೆಯಾಗ ದಿದ್ದರೆ" (a
space inside the word leaves a bare token ದಿದ್ದರೆ that the consonant-before rule cannot see). Spacing
errors like this are likely in ASR output too.

## Honest limits

- Written Wikipedia/news Kannada is formal; the project's conversations are spoken and colloquial
  (ಬರಲ್ಲ, ಆಗಿಲ್ಲ, ಗೊತ್ತಿಲ್ಲ). Colloquial forms were NOT audited on real speech transcripts (none fetched).
- Rules are token-level; scope is clause-level. Real negation scope (what exactly is negated) is not
  modelled. ಇಲ್ಲದೆ / ಇಲ್ಲದ, coordination ("A ಮತ್ತು B ಬೇಡ") and questions are handled conservatively
  (flag for review), not understood.
- **Known blind spot (most important):** if ASR silently drops the negation word, the transcript and
  the record agree and NO text-only check can see it. E4 measured this: transcript-level negation drop
  caught 0/4 unique cases text-only, 4/4 only when a second, correct transcript is available (C7).
