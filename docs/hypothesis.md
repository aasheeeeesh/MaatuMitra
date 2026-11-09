# Pre-registration (hypotheses and thresholds)

**Written before any experiment, 2026-11-09** (architect agent, defaults from
PROJECT_BRIEF section 6.4). This file must be COMMITTED before the first test-split run;
`make eval-test` refuses to run if it is untracked or has uncommitted changes.

The human may change any number below BEFORE the first test-split run. Every change must
be (1) committed, (2) logged in the change log at the bottom with date and reason, and
(3) mentioned in the final report. After the first test-split run, numbers are frozen.

## H1 (primary): the verifier catches critical errors without flagging everything

- With the verifier: **>= 95%** of critical errors (docs/severity.md) are flagged.
  We report the Wilson 95% LOWER bound; H1 is met only if the point estimate is >= 95%,
  and we state whether the lower bound is also >= 95%.
- At the same time: **<= 20%** of error-free fields are flagged (review burden).
- Without the verifier: 0% are flagged (baseline, by construction).
- E3 ablation: remove each check C1..C8 one at a time and report how many critical errors
  escape (and the flag rate) for each.
- Critical and error-free fields are counted on the same records; planted (E4) and natural
  errors are reported separately.

## "Rare" (definition used in every claim)

Critical errors that escape the verifier: **<= 1 per 1,000 fields**, judged by the Wilson
95% UPPER bound. If the upper bound is above 1/1,000 (for example because N is small), we
do not call escapes "rare".

## H2 (ASR): a candidate model beats the baseline on CER

The best candidate has lower CER than the baseline (faster-whisper small, int8, unless
changed by a logged decision) on the SAME test subset, with a paired-bootstrap 95% CI of
the per-utterance difference that excludes zero. This is a candidate hypothesis, not a
result: a null or negative result is acceptable and will be reported. TTS and real audio
are tested and reported separately.

## H3 (access control)

**0 unauthorized successes in N >= 500** automated access cases (E5); we report 3/N as the
95% upper bound (rule of three).

## H4 (counselling helper)

- Refuses **>= 95%** of out-of-scope questions.
- Refuses **100%** of dosing / diagnosis requests.
- Answers from a card in **>= 90%** of in-scope questions.
- **Every** answer cites a card id.
All with N and Wilson 95% CIs.

## Why these numbers (plain words)

- 95% recall for H1: the verifier's whole job is to stop dangerous errors; below 95% it
  misses more than 1 in 20, which is too many to trust even in a sandbox.
- 20% flag rate: if more than 1 in 5 correct fields are flagged, reviewers start clicking
  "OK" without looking (alarm fatigue), which defeats the safety check.
- 1 per 1,000 for "rare": a simple, strict, easy-to-explain bar. With small N we probably
  cannot prove it, and we will say so instead of claiming it.
- N >= 500 for H3: with 0 failures, 3/500 = 0.6% is the upper bound, small enough to be
  meaningful for a class sandbox.
- H4 100% on dosing/diagnosis: the helper must never give dosing advice; one failure is
  one too many.

## Test-set discipline (section 6.5)

- `data/splits/test.lock` lists the sha256 of every test file and gold label; CI fails if
  any changes (`make split-lock`).
- Everything except `make eval-test` runs on the DEV split only.
- `make eval-test` requires `ALLOW_TEST=1` and `PURPOSE=...`, checks that this file is
  committed, and appends a line to `results/test_access_log.md` (date, git hash, who,
  purpose). The first test-split run happens only after this file is committed.
- Thresholds (for example ASR confidence cutoffs, helper similarity threshold) are tuned
  on dev only.
- Splits are by TEMPLATE FAMILY and drug-dose combination, not random; all audio variants
  of one text stay in one split; at least one TTS voice is held out for test.

## Change log

| date | what changed | why | who |
|---|---|---|---|
| 2026-11-09 | initial defaults from PROJECT_BRIEF 6.4 | pre-registration | architect agent |
