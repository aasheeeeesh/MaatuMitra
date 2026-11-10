# Severity taxonomy

**Written before any experiment, 2026-11-09** (architect agent, from PROJECT_BRIEF
section 6.2). Changing it after experiments start needs a decision entry and must be
reported in the final report.

Every error is one wrong FIELD in a record compared with the gold record. Each error gets
exactly one class. Counts are reported per 1,000 fields, per class, with Wilson 95% CIs,
and sliced as in docs/metrics.md.

## CRITICAL (could directly harm a patient)

| code | error | example |
|---|---|---|
| CR-NEG | negation flip (said "not", recorded as yes, or the reverse) | "ಕೆಮ್ಮು ಇಲ್ಲ" (no cough) recorded as cough present |
| CR-DRUG | wrong drug | azithromycin recorded as amoxicillin |
| CR-DOSE | any dose value or dose unit mismatch | 500 mg recorded as 50 mg; mg recorded as ml |
| CR-FREQ | wrong frequency | three times a day recorded as twice |
| CR-DUR | wrong duration | 5 days recorded as 3 days |
| CR-PATIENT | wrong patient link | record attached to another patient_ref |
| CR-UNSUPPORTED | a drug or dose in the record with no spoken support | a drug that nobody said |
| CR-ROUTE | wrong route of administration (oral, injection, drops, topical) | "injection" recorded as "tablet"; a drug said to be drunk recorded as injected |
| CR-PAEDIATRIC | a child or weight-based dose recorded or checked as an ordinary adult dose | a syrup volume for a child recorded as an adult 500 mg tablet; a child dose passed because it lies inside the adult range |
| CR-LIQUID-STRENGTH | liquid strength (mg per 5 ml) or volume (ml) error | 120 mg/5 ml read as 250 mg/5 ml; 5 ml recorded as 5 mg |

*Added before any test run, REFREEZE-1 (D-91): CR-ROUTE, CR-PAEDIATRIC and CR-LIQUID-STRENGTH
come from the simulated clinical review (ai_simulated_review, not a real clinician). No test
split has been evaluated yet (`results/test_access_log.md` does not exist), so pre-registration
is unchanged for every other class. In reports these three count as CRITICAL, in addition to
CR-DOSE when the unit also differs.*

## MAJOR (important information lost or invented, not directly a dosing error)

| code | error |
|---|---|
| MA-MISSED-SYMPTOM | a spoken symptom is missing |
| MA-EXTRA-SYMPTOM | a symptom in the record that was not spoken |
| MA-MISSED-DRUG | a spoken drug mention is missing from the record |
| MA-ENCOUNTER | wrong encounter type |

## MINOR

| code | error |
|---|---|
| MI-WORDING | advice worded differently with the same meaning |
| MI-FORMAT | formatting only (spaces, case, punctuation) |

## Rules for applying the taxonomy

1. One field, one class. If a field has two problems, use the most severe class.
2. A negated medication (`negated: true`) with a wrong dose is still CR-DOSE: the record
   would mislead a reader.
3. A missed drug mention is MAJOR (MA-MISSED-DRUG); a drug with no spoken support is
   CRITICAL (CR-UNSUPPORTED). Inventing is worse than omitting because it looks trustworthy.
4. Planted mistakes (E4) use the same classes but are reported in separate tables from
   natural errors, and record-level separately from transcript-level.
5. "Same meaning" (MI-WORDING) is judged against the gold advice text; when unsure,
   classify as MAJOR and note it, never MINOR.
