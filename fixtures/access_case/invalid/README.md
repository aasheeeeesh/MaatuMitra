# Invalid access_case fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| action_drop.json | action 'drop' not allowed |
| alg_none_expected_allow.json | an alg=none token attack must always expect deny |
| user_id_not_uuid.json | user ids are UUIDs, never sequential ids |
