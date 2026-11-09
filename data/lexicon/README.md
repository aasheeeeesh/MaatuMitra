# data/lexicon

`drugs.csv` (34 rows, 18 antibiotics), built by `uv run --extra data python -m m1_data build-lexicon`
from `m1_data/lexicon_source.py`. Columns exactly as PROJECT_BRIEF AGENT 2 step 1.

- `aware_class`: WHO AWaRe portal (https://aware.essentialmeds.org/list), fetched 2026-11-09.
- `nlem_listed` / `strengths_mg`: India NLEM 2022 PDF (nppa.gov.in), fetched 2026-11-09 by automated
  extraction. Rows marked "JSON extraction" in `verified_by` need a manual spot-check.
- `adult_dose_range_mg` / `max_daily_mg`: ONLY from a fetched openFDA (US) label. Definition: lowest and
  highest single adult oral dose stated in the label's adult dosing text; max daily only if stated.
  Blank = UNVERIFIED (no label fetched). Not Indian guidance, not dosing advice.
- For combination products (`amoxicillin-clavulanate`, `cotrimoxazole`) mg values are the first component.
- `confusable_with`: ISMP-cited pairs (may name drugs outside the lexicon) + AI-proposed name-similarity /
  shared-stem pairs (UNVERIFIED). `verified_by` says which.
- Kannada spellings: ISO 15919 respelling by an AI agent -> `indic-transliteration` 2.3.82 (MIT).
  Not native-validated.
