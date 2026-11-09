# m4_verify make targets. Owned by the safety-engineer builder.
# Architect stub: passes while the module has only the skipped placeholder test.
# Builders: keep target names; add more targets freely (prefix them with m4-).

.PHONY: m4-test m4-mock

m4-test:
	$(UV) run pytest m4_verify/tests

m4-mock:
	@echo "m4-mock: no mock run yet (m4_verify builder replaces this with a MODE=mock run on fixtures/)"

# Register with root aggregate targets when ready, for example:
# DATA_TARGETS += m1-data
# EVAL_TARGETS += m7-eval
# EVAL_FULL_TARGETS += m2-eval-full
# EVAL_TEST_TARGETS += m7-eval-test
# DEMO_TARGETS += m6-demo
# CLEAN_TARGETS += m4-clean
