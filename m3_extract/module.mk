# m3_extract make targets. Owned by the nlp-engineer builder.
# Architect stub: passes while the module has only the skipped placeholder test.
# Builders: keep target names; add more targets freely (prefix them with m3-).

.PHONY: m3-test m3-mock

m3-test:
	$(UV) run pytest m3_extract/tests

m3-mock:
	@echo "m3-mock: no mock run yet (m3_extract builder replaces this with a MODE=mock run on fixtures/)"

# Register with root aggregate targets when ready, for example:
# DATA_TARGETS += m1-data
# EVAL_TARGETS += m7-eval
# EVAL_FULL_TARGETS += m2-eval-full
# EVAL_TEST_TARGETS += m7-eval-test
# DEMO_TARGETS += m6-demo
# CLEAN_TARGETS += m3-clean
