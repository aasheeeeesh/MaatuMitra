# E2E on DEV conversations (integration-qa, Phase C1)

Seeded choice (seed 20261112) of 10 ids from data/splits/dev.txt; the test split is never touched.
Path: gold text -> mock ASR transcript (m2 build_transcript; m2 has no real dev output for these template ids) -> m3 rules record.v1 -> real m5 HTTP API on 127.0.0.1 with MAATUMITRA_VERIFIER=integration.verifier_adapter:verify_record (m4) -> physician P1 resolves flags -> save -> read back as 11 users -> m6 HttpGate + Catalogue load it.

Natural conversations processed: 10/10; saved: 10.

## Natural records (m3 output as-is)

| # | id | flags | save w/o resolution | resolutions | save | final | RLS before save | RLS after save | transcript |
|---|---|---|---|---|---|---|---|---|---|
| 1 | m1-e4-003 | C4/medications/2/dose_value | 409 | confirmed:C4/medications/2/dose_value | 200 | saved | as expected | as expected | ok |
| 2 | m1-g7-010 | C4/medications/0/dose_value, C4/medications/1/dose_value | 409 | confirmed:C4/medications/0/dose_value, confirmed:C4/medications/1/dose_value | 200 | saved | as expected | as expected | ok |
| 3 | m1-e4-001 | C4/medications/0/dose_value, C4/medications/1/dose_value, C4/medications/2/dose_value | 409 | confirmed:C4/medications/0/dose_value, confirmed:C4/medications/1/dose_value, confirmed:C4/medications/2/dose_value | 200 | saved | as expected | as expected | ok |
| 4 | m1-f2-003 | none | 200 | - | 200 | saved | as expected | as expected | ok |
| 5 | m1-e5-007 | none | 200 | - | 200 | saved | as expected | as expected | ok |
| 6 | m1-i3-005 | C4/medications/0/dose_value | 409 | confirmed:C4/medications/0/dose_value | 200 | saved | as expected | as expected | ok |
| 7 | m1-b7-003 | none | 200 | - | 200 | saved | as expected | as expected | ok |
| 8 | m1-e5-004 | none | 200 | - | 200 | saved | as expected | as expected | ok |
| 9 | m1-g5-006 | none | 200 | - | 200 | saved | as expected | as expected | ok |
| 10 | m1-e8-013 | C4/medications/1/dose_value | 409 | confirmed:C4/medications/1/dose_value | 200 | saved | as expected | as expected | ok |

Reviewer rule used: every open flag is `confirmed`. This is a test policy, not clinical advice. 'save w/o resolution' = a save with an empty resolution list (409 = refused because a flag is open; 200 = nothing was open).

## Planted-error records (separate table, never pooled with natural ones)

| # | id | flags | save w/o resolution | resolutions | save | final | RLS before save | RLS after save | transcript |
|---|---|---|---|---|---|---|---|---|---|
| 1 | m1-f2-003 | C3/symptoms/0/present | 409 | edited:C3/symptoms/0/present | 200 | saved | as expected | as expected | ok |
| 2 | m1-e5-007 | C3/medications/0/negated | 409 | edited:C3/medications/0/negated | 200 | saved | as expected | as expected | ok |

For planted records the reviewer first tries to save without a resolution (409), edits the flipped field back, re-verifies (flags_after_edit below) and saves with `edited`.

- m1-f2-003: flags_after_edit = 0
- m1-e5-007: flags_after_edit = 0

## Flag reasons on natural records (check + m4 reason code)

- m1-e4-003: C4 cannot_verify:count_unit
- m1-g7-010: C4 cannot_verify:count_unit, C4 cannot_verify:no_range
- m1-e4-001: C4 cannot_verify:count_unit
- m1-f2-003: none
- m1-e5-007: none
- m1-i3-005: C4 cannot_verify:count_unit
- m1-b7-003: none
- m1-e5-004: none
- m1-g5-006: none
- m1-e8-013: C4 cannot_verify:liquid_strength, C4 cannot_verify:paediatric

## m6 view (HttpGate.load_record + Catalogue.case_for), first 3 records, DRAFT before save

- m1-e4-003: {'id': 'm1-e4-003', 'login': True, 'loaded': True, 'case_errors': [], 'reload_after_save': False}
- m1-g7-010: {'id': 'm1-g7-010', 'login': True, 'loaded': True, 'case_errors': [], 'reload_after_save': False}
- m1-e4-001: {'id': 'm1-e4-001', 'login': True, 'loaded': True, 'case_errors': [], 'reload_after_save': False}
