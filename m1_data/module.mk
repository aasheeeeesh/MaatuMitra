# m1_data make targets. Owned by the data-scientist builder.
# Architect stub: passes while the module has only the skipped placeholder test.
# Builders: keep target names; add more targets freely (prefix them with m1-).

.PHONY: m1-test m1-mock

m1-test:
	$(UV) run pytest m1_data/tests

m1-mock:
	@echo "m1-mock: no mock run yet (m1_data builder replaces this with a MODE=mock run on fixtures/)"

# Register with root aggregate targets when ready, for example:
# DATA_TARGETS += m1-data
# EVAL_TARGETS += m7-eval
# EVAL_FULL_TARGETS += m2-eval-full
# EVAL_TEST_TARGETS += m7-eval-test
# DEMO_TARGETS += m6-demo
# CLEAN_TARGETS += m1-clean
