# Invalid verdict fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| check_error_marked_pass.json | a check that errored must be 'flag' (fail-closed), not 'pass' |
| check_id_c9.json | check_id C9 does not exist (C1..C8 only) |
| flag_but_auto_acceptable.json | a check flags but auto_acceptable is true |
| no_checks_but_auto_acceptable.json | no checks ran but auto_acceptable is true |
