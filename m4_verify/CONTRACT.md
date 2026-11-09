# m4_verify contract

- Layer: L3 safety verifier (plain code, deterministic, fail-closed). Version string: `m4_verify-1.0.0`.
- Imports: `contracts.validate` only. No code from m1/m3 or any other module; the shared negation
  YAML table is NOT read (independent hand-coded rules in `negation.py`).

## Inputs

| input | schema / format | notes |
|---|---|---|
| record | `record.v1` | evidence offsets are code-point offsets into the transcript text |
| transcript | `transcript.v1` | turns = lines of `text` split on `\n` (gold.v1 convention, see fixtures/build_fixtures.py). A transcript without newlines is one turn: cross-turn rules then cannot apply |
| second transcript (optional) | `transcript.v1` | used only by C7 (disagreement on drugs, doses, numbers, negation cues, bare answers) |
| lexicon | m1 CSV columns (`generic_en, kn_primary, kn_variants, roman_variants, strengths_mg, adult_dose_range_mg, max_daily_mg, confusable_with, ...`) | default `data/lexicon/drugs.csv` if present, else `fixtures/lexicon/drugs_fixture.csv`; `MODE=mock` forces the fixture |
| encounter index (optional) | JSON `{audio_id: patient_ref}` | enables the C6 patient-link check |
| config | YAML, `m4_verify/config/default.yaml` | `disabled`, `c7_conf_threshold` (+ status), `allowed_units`, `allowed_units_by_drug`, `blank_range_fails_closed`, `lexicon_path` |
| E4 gold | directory of `gold.v1` JSON or a JSONL | DEV only: paths with a `test` component are refused |

## Outputs (all under `results/m4_verify/`)

| path | schema | content |
|---|---|---|
| `verdicts/<record_id>.json` | `verdict.v1` | one per fixture record (mock run) |
| `fixture_per_check.csv` | CSV | pass/flag/n/a counts per check on fixtures |
| `e4/clean_verdicts/*.json` | `verdict.v1` | clean gold records |
| `e4/injection_log_{record,transcript}.jsonl` | JSONL | id, type, type_name, level, source_id, field_path, before, after, note, unique_key |
| `e4/injection_results.jsonl` | JSONL | per injection and condition: caught, caught_at_field, flagged_checks |
| `e4/sample_verdicts.jsonl` | JSONL of `{injection_id, condition, verdict: verdict.v1}` | 2 per type and condition |
| `e4/catch_rates.csv`, `e4/per_check.csv`, `e4/clean_flag_rate.csv`, `e4/summary.{json,md}` | CSV / JSON / MD | catch rate + Wilson CI (on n and on unique mutations), per-check counts, review burden |
| `data_lexicon/...` | same layout | the same runs with `data/lexicon/drugs.csv` |

Every verdict produced is validated with `contracts.validate.validate_doc("verdict", ...)` during the run
(count and errors in `summary.json`) and in the tests.

## Verdict semantics consumers must respect

- `auto_acceptable` is true only if no entry flags AND at least one enabled check passed.
- A disabled check appears once as `n/a`, reason `disabled by config (ablation)`.
- `field_path` `/` = whole record; `/medications` = record-level omission flag.
- `n/a` never means "checked and fine": read its reason (for example C7 without confidences, or
  C6 `/patient_ref` without an encounter index).
