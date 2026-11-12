# Boundary checks (integration-qa, Phase C1)

Every sampled module output is validated with `contracts.validate`. DEV only; caps at 400 items per boundary (sorted order).

| boundary | check | schema | N | mismatches | result |
|---|---|---|---|---|---|
| m1 -> m2 | m1 manifest -> m2/m3 | manifest.v1 | 400 | 0 | OK |
| m1 -> m3 (scoring) / m4 (E4) | m1 gold records | gold.v1 | 328 | 0 | OK |
| m1 -> m2/m3/m4 | m1 gold transcripts | transcript.v1 | 328 | 0 | OK |
| m1 internal consistency | gold text == transcript text | (rule) | 328 | 0 | OK |
| m2 -> m3 | m2 dev transcripts (per-file) | transcript.v1 | 400 | 0 | OK |
| m2 -> m7 | m2 transcripts.jsonl (m7 input layout) | transcript.v1 | 400 | 0 | OK |
| m2 -> m3 | m2 mock adapter output | transcript.v1 | 1 | 0 | OK |
| m2 -> m3 | m2 real transcript -> m3 extract (no crash) | (behaviour) | 20 | 0 | OK |
| m3 -> m4 | m3 rules records (with spans vs transcript) | record.v1 | 328 | 0 | OK |
| m3 -> m4 | m3 records through the m4 adapter: no input-contract flag | (behaviour) | 328 | 0 | OK |
| m4 -> m5/m6 | m4 fixture verdicts | verdict.v1 | 7 | 0 | OK |
| m4 -> m5/m6 | m4 E4 clean verdicts | verdict.v1 | 6 | 0 | OK |
| m4 -> m6/m7 | m4 E4 sample verdicts (jsonl) | verdict.v1 | 52 | 0 | OK |
| m5 -> m7 (E5) | m5 access cases | access_case.v1 | 1757 | 0 | OK |
| m8 -> m6/m7 | m8 helper cards | card.v1 | 16 | 0 | OK |
| reviewers -> orchestrator | review reports | review_report.v1 | 12 | 0 | OK |

## Notes

- m1 manifest -> m2/m3: dev rows only, first 400
- m5 access cases: all lines
