# Invalid record.v2 fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| age_band_without_evidence.json | patient_age_band has no evidence |
| bidi_isolate_in_drug.json | drug name contains U+2066 LEFT-TO-RIGHT ISOLATE |
| bidi_override_in_advice_text.json | advice text contains U+202E RIGHT-TO-LEFT OVERRIDE (displayed text differs from stored text; D-123 F6) |
| evidence_for_null_route.json | field_evidence.route given but route is null |
| route_without_evidence.json | route is set but field_evidence has no 'route' span |
| status_negated_not_in_enum.json | 'negated' is not a status (use advised_against, not_taken or unknown) |
| strength_value_without_unit.json | strength_value 120 but strength_unit null |
| v1_style_medication_row.json | medication row lacks the v2 fields (route, strength, formulation, as_needed, food_timing, status) |
| weight_kg_zero.json | weight_kg.value must be > 0 |
