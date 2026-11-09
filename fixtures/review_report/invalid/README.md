# Invalid review_report fixtures

Each file must be REJECTED by `contracts/validate.py`. Reason per file:

| file | why it is invalid |
|---|---|
| duplicate_finding_ids.json | two findings share the id F1 |
| finding_missing_confidence.json | confidence is required |
| label_not_ai_simulated.json | label must be 'ai_simulated_review' |
| severity_blocker.json | severity must be critical|major|minor |
