# m5_backend make targets (backend-security-engineer).
# m5-test : all m5 tests. DB tests SKIP with a clear message if no PostgreSQL 16 is reachable.
# m5-mock : MODE=mock, no database: generate + validate the >=500 access_case.v1 cases and run
#           the token/model/pseudonym checks.
# m5-db-up / m5-db-down : local PostgreSQL 16 without Docker (see m5_backend/README.md).
# m5-matrix : full E5 matrix against the DB; writes results/m5_backend/access_matrix_*.

.PHONY: m5-test m5-mock m5-db-up m5-db-down m5-matrix

m5-test:
	$(UV) run pytest m5_backend/tests

m5-mock:
	MODE=mock $(UV) run python -m m5_backend.matrix.generate
	MODE=mock $(UV) run python -m contracts.validate access_case results/m5_backend/access_cases.jsonl
	MODE=mock $(UV) run pytest m5_backend/tests -m "not needs_db" -q

m5-db-up:
	bash m5_backend/scripts/db_up.sh

m5-db-down:
	bash m5_backend/scripts/db_down.sh

m5-matrix:
	$(UV) run python -m m5_backend.matrix.run
