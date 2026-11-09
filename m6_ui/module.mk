# m6_ui make targets. Owned by the frontend-engineer builder.
# Architect stub: passes while the module has only the skipped placeholder test.
# Builders: keep target names; add more targets freely (prefix them with m6-).

.PHONY: m6-test m6-mock

m6-test:
	$(UV) run pytest m6_ui/tests

m6-mock:
	@echo "m6-mock: no mock run yet (m6_ui builder replaces this with a MODE=mock run on fixtures/)"

# Register with root aggregate targets when ready, for example:
# DATA_TARGETS += m1-data
# EVAL_TARGETS += m7-eval
# EVAL_FULL_TARGETS += m2-eval-full
# EVAL_TEST_TARGETS += m7-eval-test
# DEMO_TARGETS += m6-demo
# CLEAN_TARGETS += m6-clean
