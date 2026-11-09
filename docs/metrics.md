# Metrics

**Written before any experiment, 2026-11-09** (architect agent, from PROJECT_BRIEF
section 6.3). Implementations: m2_asr/asr/metrics.py (ASR), m7_eval/stats.py (statistics),
each with unit tests against hand-computed values.

## 1. ASR metrics

- **CER (primary)**: Levenshtein edit distance between hypothesis and reference, counted
  on Unicode NFC code points AFTER the comparison normalisation (kannada-nlp skill:
  strip BOM/zero-width space, remove ZWJ/ZWNJ, Kannada digits -> ASCII, Latin casefold),
  divided by the number of reference code points. Primary because Kannada is
  agglutinative (one long word carries many meanings), which inflates WER.
- **Grapheme CER**: the same, but on grapheme clusters (`regex.findall(r"\X", s)`), so one
  visible Kannada letter-with-signs counts as one unit.
- **WER (secondary)**: edit distance on whitespace tokens / reference tokens.
- **Critical-term recall**: for every gold drug name, number, unit and negation cue, is it
  present in the hypothesis after normalisation? Reported per class
  (drug / number / unit / negation) as k/n with a Wilson 95% CI.
- **Latency**: p50 and p95 of per-file processing time, plus real-time factor
  (processing seconds / audio seconds), always with the hardware string.

## 2. Statistics

- **Proportions**: Wilson 95% CI (z = 1.959964). Always show k, n and the CI.
- **Zero failures**: "0 failures in N trials; 95% upper bound ~ 3/N" (rule of three).
- **Continuous metrics** (CER, latency): bootstrap 95% CI over utterances, 1000 resamples,
  fixed seed recorded in the config.
- **Model comparison**: PAIRED bootstrap on per-utterance differences, same utterances for
  both models (common subset listed in results/m2_asr/common_subset.txt). A difference is
  only called real if the 95% CI excludes zero.

## 3. Safety (verifier) metrics: ALWAYS report both

- **Critical-error recall** = critical errors flagged by the verifier / all critical errors.
- **Flag rate on error-free fields** = error-free fields flagged / all error-free fields
  (this is the review burden). A verifier that flags everything would have recall 1.0 and
  flag rate 1.0; that must look bad, so the two numbers always appear together.
- **Escaped critical errors per 1,000 fields** with the Wilson upper bound (see the
  definition of "rare" in docs/hypothesis.md).

## 4. Extraction metrics

Field-level accuracy against gold, errors per 1,000 fields per severity class
(docs/severity.md), Wilson CIs.

## 5. Slicing (never report only an average)

Every metric is reported per slice: source (public_real / tts / template_text, never
pooled), noise_snr_db (clean / 20 / 10 / 5), speed_factor (0.9 / 1.0 / 1.1), voice or
speaker, code_switched (yes / no). Planted errors (E4) are never mixed with natural errors.
