---
name: eval-rigor
description: Evaluation rules for MaatuMitra (severity taxonomy, CER/grapheme CER/WER, critical-term recall, Wilson CI, rule of three, bootstrap and paired bootstrap, slicing, ablation protocol, frozen test split and access log). Use when computing, reporting or auditing any metric, in m2_asr, m7_eval, m3/m4 scoring, and the scientific-integrity audit.
---

# Evaluation rigour (PROJECT_BRIEF sections 6.2-6.5)

Source documents (pre-registered, written before any experiment on 2026-11-09):
`docs/severity.md`, `docs/metrics.md`, `docs/hypothesis.md`. If this skill and those files
ever disagree, the docs win; log the difference as an open question.

## 1. Never do

- Never tune anything (thresholds, prompts, rules, model choice) on the TEST split.
- Never report a proportion without N and a Wilson 95% CI.
- Never claim "zero failures" without "0 of N; 95% upper bound ~ 3/N".
- Never pool TTS and real audio, or planted errors and natural errors, into one number.
- Never report only an average: slice by source (public_real / tts / template_text),
  noise_snr_db, speed_factor, voice/speaker, code_switched.
- Never compare models on different utterances: use one common subset and list it.
- Never report a verifier's recall without its flag rate on error-free fields.
- Never claim clinical or educational impact.

## 2. Formulas

**Wilson 95% interval** for k successes in n trials, z = 1.959964:
```
p = k/n
centre = (p + z^2/(2n)) / (1 + z^2/n)
half   = z * sqrt(p(1-p)/n + z^2/(4n^2)) / (1 + z^2/n)
CI = [centre - half, centre + half]
```
Hand-checkable values for unit tests (compute and paste them in the test with the formula
in a comment; do not trust a library blindly): 0/50 gives [0, 0.0713];
3/50 gives [0.0206, 0.1622] (z = 1.959964, rounded to 4 places; computed by the architect with the formula above).

**Rule of three**: 0 events in n trials -> 95% upper bound about 3/n.

**Bootstrap 95% CI** for a mean over utterances: 1000 resamples with replacement,
fixed seed (record it), percentile interval [2.5%, 97.5%].
**Paired bootstrap** to compare model A vs B: per-utterance difference d_i = m_A,i - m_B,i
on the SAME utterances; resample the d_i; CI of mean(d). "A better" only if the CI excludes 0.

**CER**: Levenshtein distance on NFC code points after the comparison normalisation
(kannada-nlp skill section 1) / number of reference code points. Also grapheme CER on
`regex.findall(r"\X", s)`. WER on whitespace tokens is secondary (Kannada is
agglutinative, so WER is inflated).

**Critical-term recall**: for each gold drug name, number, unit and negation cue, is it
present in the hypothesis after normalisation? Report per class with Wilson CIs.

**Latency**: p50 and p95 per audio file, real-time factor = processing time / audio
duration, always with the hardware string.

## 3. Severity (docs/severity.md)

CRITICAL: negation flip; wrong drug; any dose value or unit mismatch; wrong frequency or
duration; wrong patient link; a drug/dose in the record with no spoken support.
MAJOR: missed symptom; extra unsupported symptom; missed drug mention; wrong encounter type.
MINOR: same-meaning wording differences in advice; formatting.
Report errors per 1,000 fields per class.

## 4. Ablation protocol (E3)

1. Run the full verifier (C1..C8) on the same fixed set of records.
2. Re-run with exactly ONE check disabled via the registry config, for each check.
3. For every run report: critical errors flagged / total critical (Wilson CI), escaped
   critical errors per 1,000 fields (Wilson upper bound), flag rate on error-free fields
   (Wilson CI). Same records, same seed, same code version in every run.
4. Planted (E4) and natural errors in separate tables; record-level and transcript-level
   planted results in separate tables.

## 5. Test-split discipline (6.5)

- `data/splits/test.lock`: one line per test file and gold label,
  `<sha256>  <posix path>` (sha256sum format). `make split-lock` and CI fail on any change.
- Split by template family AND drug-dose combination; all audio variants of one text in
  the same split; hold out >= 1 TTS voice for test.
- Only `make eval-test` reads the test split. It needs `ALLOW_TEST=1`, a `PURPOSE=...`,
  and a committed, unmodified `docs/hypothesis.md`; it appends a row to
  `results/test_access_log.md` (date, git hash, who, purpose). Run it once.
- Every number in a table must trace to a raw file under `results/`.
