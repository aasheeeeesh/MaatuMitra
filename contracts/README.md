# contracts

Versioned JSON-Schema contracts (`schemas/*.schema.json`) and `validate.py` (schema + semantic checks). Change = version bump + CHANGELOG.md entry approved by the architect.

## record.v2 and gold.v2 (Phase C, additive)

Why: the simulated clinical review of m3 (D-122, `reviews/m3_extract/2026-11-11-clinical.md`)
showed that record.v1 cannot hold route, liquid strength, age, "already taken versus
prescribed", "as needed" or food timing, so the critical classes CR-ROUTE, CR-PAEDIATRIC and
CR-LIQUID-STRENGTH (docs/severity.md) could not be measured.

**Additive:** `record.v1` and `gold.v1` are unchanged. The bare names `record` / `gold` still
mean v1 (`validate_doc("record", doc)` = v1). Use `record.v2` / `gold.v2` explicitly. Modules
move to v2 one by one in Phase C; v1 stays in `schemas/` until no module produces it.

### Field table (record.v1 -> record.v2)

| where | field | v1 | v2 | evidence in v2 |
|---|---|---|---|---|
| record | `schema_version` | `record.v1` | `record.v2` | - |
| record | `patient_age_band` | - | `null` or `{band, evidence}`; band: infant, child, adolescent, adult, older_adult, unknown | required inside the object |
| record | `weight_kg` | - | `null` or `{value (kg, >0, <=300), evidence}` | required inside the object |
| medication | `drug`, `dose_value`, `dose_unit`, `frequency_per_day`, `duration_days` | as v1 | unchanged; dose = amount PER ADMINISTRATION (5 ml, 1 tablet, 500 mg) | main `evidence` (as v1) |
| medication | `negated` | overloaded: "not", "not taken", "not finished", "advised against" | ONLY "the spoken sentence about this drug is negated" | main `evidence` |
| medication | `status` | - | prescribed, already_taken, not_taken, advised_against, stopped_early, continue_existing, unknown | `field_evidence.status` unless `unknown` |
| medication | `route` | - | oral, iv, im, sc, topical, inhaled, rectal, injection_unspecified, other, unknown, or null (not said) | `field_evidence.route` |
| medication | `strength_value` + `strength_unit` | - | product strength, separate from dose (500 mg tablet; 120 mg/5 ml syrup: `120` + `mg/5ml`); units mg, g, mcg, IU, mg/ml, mg/5ml, mcg/ml, IU/ml, %; both or neither | `field_evidence.strength` |
| medication | `formulation` | - | tablet, capsule, syrup, suspension, drops, injection, sachet, other, or null | `field_evidence.formulation` |
| medication | `as_needed` | - | true / false / null | `field_evidence.as_needed` |
| medication | `food_timing` | - | before_food, after_food, with_food, empty_stomach, or null | `field_evidence.food_timing` |
| medication | `speaker` | - | doctor, nurse, asha, pharmacist, patient, caregiver, unknown = who spoke the MAIN evidence span | - |
| medication | `field_evidence` | - | object; one evidence span per non-null new field (may be in another turn) | - |
| advice | `speaker` | - | same enum as medication | - |
| symptoms, follow_up, top-level v1 fields | | as v1 | unchanged | as v1 |

gold.v2 mirrors this exactly with `gold_span` / `gold_field_spans` instead of `evidence` /
`field_evidence`, and requires `speaker` = the role of the turn of the main gold span
(physician -> doctor).

### Rules checked by `validate.py` for v2

- Every non-null new field has its own span; no span for a null field; `status: unknown` needs none.
- `strength_value` and `strength_unit` are both set or both null.
- Every span passes the v1 rules (end > start, length = len(span_text), audio times consistent).
- No Unicode bidi control characters U+202A..U+202E, U+2066..U+2069 in ANY string (D-123 F6).
  Opt-in for v1: `bidi_errors(doc)` or `validate_doc(name, doc, reject_bidi=True)`.
- Opt-in for v1 and v2: `validate_doc("record.v2", rec, transcript_text=text)` or
  `record_spans_match_transcript(rec, text)` checks every span against the transcript text.
- NOT checked here (it is a clinical rule, the verifier's job): a liquid formulation (syrup,
  suspension, drops) with a dose in ml and no strength is structurally VALID; m4 must flag it
  (fixture `fixtures/record.v2/valid/rec2-fx-child-007-no-strength.json`).

### Annotation conventions (UNVERIFIED, for a clinician to confirm)

- "500 mg ಮಾತ್ರೆ" with no count: dose 500 mg (as v1), strength null. "500 mg, ಎರಡು ಮಾತ್ರೆ":
  dose 2 tablet, strength 500 mg. Liquids: dose in ml, strength in mg/5ml or mg/ml.
- "injection" without IV/IM/SC: route `injection_unspecified`, formulation `injection`.
- Route not said: `null`, even if the formulation implies it (a syrup is oral); the verifier may infer.
- Age bands: infant < 1 y, child 1-9 y, adolescent 10-17 y, adult 18-64 y, older_adult >= 65 y.
  A word for child with no age (ಮಗು) = `child`.
- A question answered "no" in the next turn ("did the child drink the syrup?" / "ಇಲ್ಲ"): status
  `not_taken`, `negated: true`, `field_evidence.status` = the "ಇಲ್ಲ" span, speaker = the asker.

### Migration (`contracts/migrate_v1_to_v2.py`)

`uv run python -m contracts.migrate_v1_to_v2 record in.jsonl -o out.jsonl` (or `gold`).
Conservative: all new fields null, `status: unknown` for every medication (`negated: true` does
NOT become `advised_against`), record `speaker: unknown`, gold `speaker` from the turn role.
A migrated record is valid v2 but carries no route/strength/age, so the three new critical
classes stay "not measurable" for it.

### What each module must change (Phase C)

- **m3_extract**: emit `record.v2`; fill status (past tense / ಇಲ್ಲ answer / -ಬೇಡಿ), route,
  formulation (ಸಿರಪ್, ಮಾತ್ರೆ, injection), strength vs dose (finding M3-M5), as_needed
  (ಇದ್ದರೆ ಮಾತ್ರ), food_timing, speaker from the turn role (needs the gold turn roles or a
  speaker-aware transcript; otherwise `unknown`), age band and weight, each with its span.
  Keep `negated` as the sentence-level flag from the negation table.
- **m4_verify**: accept v2 (and v1 via the migrator). C4 must: use `strength_*` for liquids and
  flag a liquid dose in ml without strength (CR-LIQUID-STRENGTH); treat every non-adult
  `patient_age_band` (and any weight-based case) as "not checkable against adult ranges" and
  flag it (CR-PAEDIATRIC); check `route` against the formulation and the lexicon's allowed
  routes (CR-ROUTE). C1/C2 must check every `field_evidence` span too. Keep m4 independent of
  m3's tables.
- **m5_backend**: new nullable columns on medication rows: route, strength_value, strength_unit,
  formulation, as_needed, food_timing, status (NOT NULL, default 'unknown'), speaker, and a
  JSONB `field_evidence`; on records: patient_age_band (+ evidence), weight_kg (+ evidence).
  The research export may include age_band (already planned) but not weight with evidence text.
  Reject bidi controls on input (call `bidi_errors`). Keep v1 ingestion until m3 switches.
- **m6_ui**: show status in words (prescribed / already taken / not taken / advised against...)
  instead of "negated"; show route, strength and formulation next to the dose; show age band and
  weight at the top; highlight each `field_evidence` span; reject or visibly mark bidi controls
  (D-123 F6). All new labels through i18n.
- **m7_eval (scorer)**: read gold.v2; emit CR-ROUTE (route mismatch, or formulation injection
  vs oral), CR-LIQUID-STRENGTH (strength value/unit mismatch, or ml dose with missing strength
  when gold has one), CR-PAEDIATRIC (age band mismatch child vs adult, or a non-adult record whose
  dose was accepted as an adult dose); score `status` mismatches as CR-NEG when they flip
  "given" vs "not given / advised against", otherwise MAJOR. Until gold.v2 exists for the data
  (m1), report these classes as "not measurable".
- **m1_data**: produce gold.v2 (the migrator gives a valid start, but route/strength/age must
  come from the templates).
