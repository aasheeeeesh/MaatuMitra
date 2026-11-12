# E7 user-study protocol (kit only; NOT run by any agent)

Status: prepared by an AI agent (research-scientist-eval, 2026-11-12). No participant has been
recruited. A human runs it (HUMAN_TODO). Class sandbox only: no clinical or educational claim.

## Question
When reviewers see the verifier's flags, do they catch planted critical errors faster or more
often, and do they miss errors that the flags do NOT point at (automation bias)?

## Materials (all synthetic; no real patient data)
- `packets/e7-r01.md` .. `e7-r20.md`: a template-generated Kannada conversation (not
  native-validated) and the draft record to check. `records/*.json` are the same records as
  record.v1 JSON.
- 10 of the 20 records carry ONE planted critical error (wrong dose, frequency, duration,
  drug, or negation). `answer_key.csv` says which: the FACILITATOR keeps it; participants never
  see it.
- Simulated verifier flags (`simulated_flag` in answer_key.csv): 7 of the 10 errors are flagged,
  3 are not; 2 of the 10 clean records carry a false flag. These flags are designed by the kit,
  not produced by m4, so that over-trust can be observed.
- `design.csv`: 12 participant slots; within-subject: each person reviews all 20 records, 10
  with flags shown and 10 hidden (each half has 5 errors and 5 clean records); which half gets
  flags and which block comes first are counterbalanced; order inside a block is randomised
  (seed 20261109).
- `consent_form_en.md`, `consent_form_kn.md` (Kannada NOT native-validated), `sus_questionnaire.md`,
  `record_sheet.csv` (one line per participant x record).

## Participants
Adult classmates or volunteers who read Kannada well enough to compare a record with a short
conversation. No patients, no health data about the participant. Aim for 6-12 people; with so
few, results are DESCRIPTIVE only.

## Procedure (about 30 minutes per person)
1. Read the consent form aloud; the person signs or declines. Declining has no consequence.
2. Two practice records (use any dev packet NOT in the 20; say they do not count).
3. For each line of the participant's rows in `design.csv` (in `position` order): show the
   packet; in `flags_shown` rows also read out or show the simulated flag (field name only);
   start a stopwatch; the person says "error" (and which field) or "no error"; stop the watch.
   Write `review_seconds`, `marked_error` (yes/no) and `marked_field` in `record_sheet.csv`.
4. After all 20: the SUS-style questionnaire.
5. Debrief: explain that some flags were deliberately wrong or missing.

## Analysis
`uv run python -m m7_eval e7-analyse m7_eval/e7_kit/record_sheet_filled.csv --out results/m7_eval/e7`
gives per condition: median and mean review time (bootstrap CI), catch rate on planted errors,
false-alarm rate on clean records, and catch rate on errors whose flag was withheld, each with
k/n and a Wilson 95% CI. NO significance tests, NO p-values, NO claims beyond these people.

## Ethics and data
- Record only a participant code (P01..P12), never a name, in the sheet. Keep signed consent
  forms on paper, separate from the sheet. Delete stopwatch notes after entry.
- Ask the course instructor whether this counts as human-subjects research needing approval
  (UNVERIFIED; HUMAN_TODO).
