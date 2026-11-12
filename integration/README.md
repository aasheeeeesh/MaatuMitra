# integration

Boundary and end-to-end checks (integration-qa, Phase C1). Only this folder may import several modules.

- `verifier_adapter.py`: `verify_record(record) -> verdict`, loaded by m5 with
  `MAATUMITRA_VERIFIER=integration.verifier_adapter:verify_record`. Finds the transcript in
  `MAATUMITRA_TRANSCRIPT_DIRS` (default `data/transcripts/gold`) and calls m4. Fails closed (one flag).
- `boundary.py`: validates samples of every cross-module output (`uv run python -m integration.boundary`).
- `e2e.py`: 10 seeded DEV conversations through the real HTTP API (`uv run python -m integration.e2e`).
  Start the DB first: `bash m5_backend/scripts/db_up.sh`; stop it: `bash m5_backend/scripts/db_down.sh`.
- Tests: `uv run pytest integration -q` (DB tests skip with a message when PostgreSQL is down).
- Results: `results/integration/e2e_dev.md`, `results/integration/boundary_checks.md`.
