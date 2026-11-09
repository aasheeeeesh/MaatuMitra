# m7_eval make targets. Owned by the research-scientist-eval builder.
# Architect stub: passes while the module has only the skipped placeholder test.
# Builders: keep target names; add more targets freely (prefix them with m7-).

.PHONY: m7-test m7-mock

m7-test:
	$(UV) run pytest m7_eval/tests

m7-mock:
	@echo "m7-mock: no mock run yet (m7_eval builder replaces this with a MODE=mock run on fixtures/)"

# Register with root aggregate targets when ready, for example:
# DATA_TARGETS += m1-data
# EVAL_TARGETS += m7-eval
# EVAL_FULL_TARGETS += m2-eval-full
# EVAL_TEST_TARGETS += m7-eval-test
# DEMO_TARGETS += m6-demo
# CLEAN_TARGETS += m7-clean
