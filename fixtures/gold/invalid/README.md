# Invalid gold fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| gold_span_offset_mismatch.json | gold span offsets shifted: slice no longer equals span_text |
| negated_item_but_has_negation_false.json | cough present=false but tags.has_negation is false |
| span_outside_its_turn.json | gold span lies in turn 1 but says turn_index 0 |
| turn_text_contains_newline.json | turn text may not contain a newline (newline is the turn separator) |
