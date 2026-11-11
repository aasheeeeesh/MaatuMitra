# Invalid gold.v2 fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| bidi_isolate_in_turn_text.json | turn text ends with U+2067 RIGHT-TO-LEFT ISOLATE |
| route_not_in_enum.json | route 'intramuscular' not in the enum (use 'im') |
| speaker_not_turn_role.json | medication speaker 'caregiver' but its span is in a pharmacist turn |
| status_without_span.json | status 'prescribed' has no gold_field_spans.status |
| strength_span_offset_mismatch.json | strength span shifted: slice != span_text |
