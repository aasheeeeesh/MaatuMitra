# Invalid record fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| evidence_end_not_after_start.json | evidence char_end == char_start |
| extra_property_approved_by.json | record.v1 has no approver field; extra properties are forbidden (gate lives in m5) |
| medication_missing_evidence.json | a medication without evidence (every field must have evidence) |
| span_length_mismatch.json | char_end - char_start differs from len(span_text) |
| status_not_in_enum.json | status 'final' not in draft|flagged|approved|saved |
