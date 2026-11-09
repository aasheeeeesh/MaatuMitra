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
