# E7 user-study kit (humans run it; not run)

Files: protocol.md (start here), consent_form_en.md, consent_form_kn.md (NOT native-validated),
sus_questionnaire.md, packets/ (20 review packets), records/ (the same 20 records as record.v1
JSON), answer_key.csv (FACILITATOR ONLY), design.csv (12 participant slots), record_sheet.csv
(blank sheet), build_records.py (rebuilds everything from DEV gold, seed 20261109), analyse.py.

Rebuild: `uv run python -m m7_eval.e7_kit.build_records`.
Analyse: `uv run python -m m7_eval e7-analyse <filled sheet> --out results/m7_eval/e7`.
