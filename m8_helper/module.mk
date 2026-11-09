# m8_helper make targets. Owned by the counselling-helper-engineer builder.
# Architect stub: passes while the module has only the skipped placeholder test.
# Builders: keep target names; add more targets freely (prefix them with m8-).

.PHONY: m8-test m8-mock

m8-test:
	$(UV) run pytest m8_helper/tests

m8-mock:
	@echo "m8-mock: no mock run yet (m8_helper builder replaces this with a MODE=mock run on fixtures/)"

# Register with root aggregate targets when ready, for example:
# DATA_TARGETS += m1-data
# EVAL_TARGETS += m7-eval
# EVAL_FULL_TARGETS += m2-eval-full
# EVAL_TEST_TARGETS += m7-eval-test
# DEMO_TARGETS += m6-demo
# CLEAN_TARGETS += m8-clean
