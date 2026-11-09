# Invalid transcript fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| model_missing_revision.json | model.revision is required (pinning) |
| source_not_in_enum.json | source 'youtube' is not an allowed value |
| text_not_nfc.json | text contains decomposed U+0CBF U+0CD5 (not NFC) |
| word_offset_mismatch.json | words[1].char_start shifted by one: text slice no longer equals w |
