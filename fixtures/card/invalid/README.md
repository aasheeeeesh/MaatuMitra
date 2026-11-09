# Invalid card fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| kn_text_without_kannada.json | kn_text has no Kannada script |
| status_native_validated.json | status 'native_validated' is not allowed by card.v1 |
| version_zero.json | version must be >= 1 |
