# m2_asr make targets. Owned by the ml-engineer-asr builder.
# Architect stub: passes while the module has only the skipped placeholder test.
# Builders: keep target names; add more targets freely (prefix them with m2-).

.PHONY: m2-test m2-mock

m2-test:
	$(UV) run pytest m2_asr/tests

m2-mock:
	@echo "m2-mock: no mock run yet (m2_asr builder replaces this with a MODE=mock run on fixtures/)"

# Register with root aggregate targets when ready, for example:
# DATA_TARGETS += m1-data
# EVAL_TARGETS += m7-eval
# EVAL_FULL_TARGETS += m2-eval-full
# EVAL_TEST_TARGETS += m7-eval-test
# DEMO_TARGETS += m6-demo
# CLEAN_TARGETS += m2-clean
