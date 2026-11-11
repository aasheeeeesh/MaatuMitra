# Contracts changelog

Rule (PROJECT_BRIEF section 4): any change to a schema needs a version bump
(`<name>.v2.schema.json`, new `schema_version` const), an entry here, fixtures for the new
version, and approval by the architect agent. Old versions stay in `schemas/` until no
module produces them. Semantic rules in `validate.py` count as part of the contract.

## 2026-11-09: v1 of all eight contracts (architect)

Created `transcript.v1`, `record.v1`, `verdict.v1`, `gold.v1`, `manifest.v1`,
`access_case.v1`, `card.v1`, `review_report.v1` (JSON Schema draft 2020-12) exactly from
PROJECT_BRIEF section 5, plus these architect choices (explained in
docs/DECISIONS_EXPLAINED.md):

- All offsets are Unicode code-point offsets into NFC text, end exclusive (Python slicing).
- `additionalProperties: false` everywhere (typos and mass-assignment style extras fail).
- Nullable where the brief says `|null` and where a value cannot exist: `transcript.latency_ms`,
  `audio_duration_s`, `hardware` (gold has no ASR run); `words[].start/end/conf`.
- `record.v1` medications: `dose_unit` is an enum (mg, g, mcg, ml, tablet, capsule, sachet,
  drop, teaspoon, IU) or null; `dose_value`, `frequency_per_day`, `duration_days` > 0 or null.
  One `evidence` span per item (as in the brief), which must cover every value of that item.
- `record.v1` has NO approver field: the "saved needs an approver" rule is enforced by
  m5_backend (DB CHECK + API), not by the schema.
- `gold.v1`: conversation text = turns joined by one `\n`; `gold_span` = {turn_index,
  span_text, char_start, char_end} with offsets into that conversation text; turn text may
  not contain `\n`. Gold transcripts (transcript.v1 with model.name = "gold") use the same text.
- `verdict.v1`: errors inside a check are reported as status `flag` with reason starting
  `check_error` (no separate "error" status, matching the brief's pass|flag|n/a).
- `manifest.v1`: `licence_spdx` free string, `licence_url` http(s) URL or the literal
  `UNVERIFIED`; `file` is a relative POSIX path.
- `access_case.v1`: `user_id` is a UUID; resources include `facilities, users, households,
  patients, encounters, records, medication_orders, consents, audit_log, research_export,
  pharmacist_orders_v, audio`.
- `card.v1`: `version` is an integer >= 1.
- `review_report.v1`: `reviewer_agent` is one of the five reviewer/QA agents; `label` const
  `ai_simulated_review`.

Semantic validators (validate.py): NFC on every string; no BOM / U+200B; real ISO-8601
timestamps; transcript word offsets match `text`; evidence `char_end > char_start` and
length equals `len(span_text)`; verdict `auto_acceptable` false if any flag or no checks,
`check_error` must be `flag`; gold spans match the conversation text and stay in their turn,
`has_negation` consistent; auth/GUC attacks expect `deny`; card `kn_text` contains Kannada;
review finding ids unique.

## 2026-11-12: record.v2 and gold.v2, additive (architect, Phase C; D-122, D-123 F6)

New files `record.v2.schema.json` and `gold.v2.schema.json`. `record.v1` / `gold.v1` are
unchanged and remain the default for the bare names `record` / `gold`. Field table, rules,
conventions and per-module migration notes: contracts/README.md.

- Medication rows gain `route`, `strength_value` + `strength_unit` (separate from the dose),
  `formulation`, `as_needed`, `food_timing`, `status`, `speaker` and `field_evidence` (gold:
  `gold_field_spans`); advice rows gain `speaker`; records gain `patient_age_band` and `weight_kg`
  (each `null` or value + evidence).
- `negated` keeps only its sentence-level meaning; the clinical meaning moves to `status`.
- Architect additions to the requested enums (decision entry in contracts/handoff/decisions.md):
  route `injection_unspecified`; status `not_taken`; speaker `nurse`, `asha`, `pharmacist`.
- validate.py: v2 semantic rules (evidence for every non-null new field, none for null fields,
  strength pair, gold speaker = turn role); bidi control characters rejected in record.v2 /
  gold.v2 and opt-in for any document (`bidi_errors`, `validate_doc(..., reject_bidi=True)`);
  opt-in transcript check (`validate_doc(..., transcript_text=...)`,
  `record_spans_match_transcript`). v1 behaviour is unchanged unless a caller opts in.
- New `contracts/migrate_v1_to_v2.py` (conservative: status `unknown`, never `advised_against`).
- Fixtures: `fixtures/record.v2/` (11 valid, 9 invalid, 3 extra gold transcripts in
  `transcripts/`) and `fixtures/gold.v2/` (9 valid, 5 invalid). `fixtures/build_fixtures.py` now
  writes only changed files instead of deleting and rewriting every folder.
- tests/test_contracts.py: the "exactly eight schemas" test now allows numbered later versions
  of the eight contracts (it still requires all eight v1 schemas).
