# m3_extract make targets (nlp-engineer). Run from Git Bash: `mingw32-make <target>`.
#   m3-test          module tests (pytest m3_extract/tests); no model, no dev/test data needed
#   m3-mock          MODE=mock: rules pipeline on fixtures/ only -> results/m3_extract/mock/
#   m3-run-dev       rules pipeline (MAIN) on all DEV gold transcripts, then m3-score
#   m3-run-llm-dev   LLM pipeline (E2) on the seeded 40-conversation DEV subset (needs Ollama on
#                    127.0.0.1:11434 with qwen3:4b-instruct; ~25 min on the dev laptop), then m3-score
#   m3-score         recompute dev_scores.csv / failures_dev.md from saved outputs (registered in `make eval`)
#   m3-eval-full     m3-run-dev + m3-run-llm-dev (registered in `make eval-full`)
# The TEST split is refused unless ALLOW_TEST=1 (set only by `make eval-test`, owned by m7_eval).

.PHONY: m3-test m3-mock m3-run-dev m3-run-llm-dev m3-score m3-eval-full m3-clean

m3-test:
	$(UV) run pytest m3_extract/tests

m3-mock:
	MODE=mock $(UV) run python -m m3_extract mock

m3-run-dev:
	$(UV) run python -m m3_extract run-rules --split dev
	$(MAKE) m3-score

m3-run-llm-dev:
	$(UV) run python -m m3_extract run-llm
	$(MAKE) m3-score

m3-score:
	$(UV) run python -m m3_extract score > /dev/null
	@echo "wrote results/m3_extract/dev_scores.csv, error_codes_dev.csv, evidence_overlap_dev.csv, failures_dev.md"

m3-eval-full: m3-run-dev m3-run-llm-dev

m3-clean:
	rm -rf results/m3_extract/mock

EVAL_TARGETS += m3-score
EVAL_FULL_TARGETS += m3-eval-full
CLEAN_TARGETS += m3-clean
