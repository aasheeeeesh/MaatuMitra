# Invalid manifest fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| missing_native_validated.json | native_validated is required |
| sha256_uppercase.json | sha256 must be lower-case hex |
| split_train.json | split must be dev or test |
| windows_absolute_path.json | file must be a relative POSIX path |
