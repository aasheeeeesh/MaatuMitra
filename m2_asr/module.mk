# m2_asr make targets. Owned by the ml-engineer-asr builder.
# m2-mock needs no model and no audio package. Real runs (dev only) are explicit, see README.

.PHONY: m2-test m2-mock m2-summary m2-lint

m2-test:
	$(UV) run pytest m2_asr/tests

m2-mock:
	$(UV) run python -m m2_asr mock

# Recompute results/m2_asr/summary.csv from the saved per-file transcripts (no model, no GPU).
m2-summary:
	$(UV) run python -m m2_asr summarise

m2-lint:
	$(UV) run ruff check m2_asr
	$(UV) run ruff format --check m2_asr
