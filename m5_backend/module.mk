# m5_backend make targets. Owned by the backend-security-engineer builder.
# Architect stub: passes while the module has only the skipped placeholder test.
# Builders: keep target names; add more targets freely (prefix them with m5-).

.PHONY: m5-test m5-mock

m5-test:
	$(UV) run pytest m5_backend/tests

m5-mock:
	@echo "m5-mock: no mock run yet (m5_backend builder replaces this with a MODE=mock run on fixtures/)"

# Register with root aggregate targets when ready, for example:
# DATA_TARGETS += m1-data
# EVAL_TARGETS += m7-eval
# EVAL_FULL_TARGETS += m2-eval-full
# EVAL_TEST_TARGETS += m7-eval-test
# DEMO_TARGETS += m6-demo
# CLEAN_TARGETS += m5-clean
