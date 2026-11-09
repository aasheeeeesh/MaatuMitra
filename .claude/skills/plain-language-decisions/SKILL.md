---
name: plain-language-decisions
description: How every MaatuMitra agent records decisions in very simple language (the exact section 11 entry template, two worked examples, glossary rule, honesty rules) and how to hand them off through <module>/handoff/ so parallel agents never edit the shared docs at once. Use for EVERY decision, problem, scope cut or reviewer finding.
---

# Plain-language decision log

Reader: a student with no Claude Code access and limited background. Write for a smart
friend who is new to this. Short sentences. Define every technical term the first time
and add it to the glossary. Be honest about weaknesses. Never delete an old entry: if a
decision changes, write a new entry that points to the old one.

## 1. Where to write (handoff mechanism)

Builders run in parallel, so NOBODY except the architect/orchestrator edits
`docs/DECISIONS_EXPLAINED.md`, `docs/glossary.md`, `docs/ai_usage.md`,
`docs/open_questions.md`, `docs/licences.md` or `HUMAN_TODO.md` directly. You write:

| your file | merged into | format |
|---|---|---|
| `<module>/handoff/decisions.md` | docs/DECISIONS_EXPLAINED.md | entries below, heading `### D-?: ...` |
| `<module>/handoff/glossary.md` | docs/glossary.md | `- **Term**: definition` (existing terms skipped) |
| `<module>/handoff/ai_usage.md` | docs/ai_usage.md | agent, module, what it generated, what a human must check |
| `<module>/handoff/human_todo.md` | HUMAN_TODO.md | `- [ ]` items with exact steps |
| `<module>/handoff/open_questions.md` | docs/open_questions.md | free text |
| `<module>/handoff/licences.md` | docs/licences.md | table rows `\| item \| type \| licence \| URL fetched \| allowed for coursework \|` |

The orchestrator runs `make merge-handoff MODULE=<module>`
(`infra/scripts/merge_handoff.py`). It gives each `### D-?:` entry the next free number
D-<n>, adds a row to the index table (status from `- Status:`, outcome from
`- What we chose:`), skips glossary terms that already exist, de-duplicates licence rows,
appends the rest under "## From <module>", and moves your files to
`<module>/handoff/merged/<timestamp>/`. Write `D-?` (not a number) in headings.
Reviewers do not write handoff files; they put recommended decisions in their report.

## 2. The entry template (use EXACTLY these bullets, in this order)

```
### D-?: <title>   (<Phase> / <Module> / <Agent> / <YYYY-MM-DD>)
- What we needed to decide:
- Options we considered: (2 to 4, each with pros and cons: cost, effort, risk, scientific soundness)
- What we chose:
- Why: (simple words, including trade-offs we accepted)
- What we actually did: (files created, what runs, exact command or path to see it)
- What could go wrong / weaknesses: (honest; mark UNVERIFIED or "not native-validated")
- What else could be done: (other options, next steps, with more time, a GPU or real Kannada reviewers)
- How to change this decision later: (which files to touch)
- Status: (done / partly done / not done / needs human)
```

Write an entry for every: tool/model chosen or rejected; dataset chosen or rejected (with
licence); contract/schema choice or change; split/freeze decision; safety rule; access
rule; UI choice; scope cut; problem hit and how it was fixed; reviewer finding accepted,
rejected or deferred; ASR model with ran / failed / pending, hardware, runtime, revision
and notebook path; every number chosen in the pre-registration.

## 3. Honesty rules

- Never present anything as run, measured, verified or reviewed unless it really was.
- Cite only URLs you actually fetched in this session. Otherwise write UNVERIFIED and
  say exactly what to check; add it to `human_todo.md` and `open_questions.md`.
- Kannada not reviewed by a real person: "not native-validated". AI reviews:
  "ai_simulated_review", never "validated".

## 4. Worked example 1 (a tool choice)

```
### D-?: Use faster-whisper "small" with int8 as the first ASR baseline   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: Which speech-to-text model to run first, so every later model is compared against the same starting point.
- Options we considered:
  1. Whisper large-v3 on the laptop GPU. Pro: usually more accurate. Con: needs more GPU memory than our 4 GB card may have; slow; risk of out-of-memory.
  2. Whisper small with int8 ("8-bit numbers", smaller and faster) on the GPU. Pro: fits in 4 GB, fast, free. Con: less accurate, especially for Kannada.
  3. A cloud speech API. Pro: maybe accurate. Con: costs money and sends audio to a company; not allowed ($0, local-first).
- What we chose: Option 2 as the baseline. Larger models are run later only if they fit.
- Why: It runs on our hardware today and costs nothing. A weak baseline is fine; the experiment is about measuring honestly, not about winning.
- What we actually did: notebooks/m2_whisper_small.ipynb (executed, outputs saved); raw results in results/m2_asr/whisper-small/*.jsonl. Re-run: `make m2`.
- What could go wrong / weaknesses: Whisper's Kannada quality is UNVERIFIED for clinical words; our test audio is TTS, so real-world error rates will be higher.
- What else could be done: run large-v3 on a free Colab GPU (see HUMAN_TODO), or an AI4Bharat model trained on Indian languages.
- How to change this decision later: change `baseline_model` in m2_asr/configs/default.yaml and re-run `make eval-full`.
- Status: done
```

## 5. Worked example 2 (a problem hit and fixed)

```
### D-?: The word for "here" was being read as "no"   (Phase B / m4_verify / safety-engineer / 2026-11-14)
- What we needed to decide: How to stop the negation checker from treating ಇಲ್ಲಿ ("here") as ಇಲ್ಲ ("no").
- Options we considered:
  1. Keep searching for the letters ಇಲ್ಲ anywhere in the sentence. Pro: simple. Con: also matches ಇಲ್ಲಿ, so it raises false alarms (and could hide real ones).
  2. Cut the sentence into whole words first and only accept ಇಲ್ಲ as a complete word or as a word ending matched by a written rule. Pro: no ಇಲ್ಲಿ mistake. Con: needs a list of endings that we must check with real Kannada text.
- What we chose: Option 2.
- Why: A safety check that cries wolf trains people to ignore it. Whole-word matching is a small change that removes a whole class of mistakes.
- What we actually did: m4_verify/negation.py now tokenises first; new tests in m4_verify/tests/test_negation.py ("ಮಾತ್ರೆ ಇಲ್ಲಿ ಇದೆ" must NOT be negated). Run `make m4`.
- What could go wrong / weaknesses: The list of endings is not native-validated; spoken forms we did not think of may be missed.
- What else could be done: ask a real Kannada speaker to fill reviews/human_sheets/negation_rules_sheet.csv.
- How to change this decision later: edit the rule list in m4_verify/negation.py and its tests together.
- Status: done
```
