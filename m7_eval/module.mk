# m7_eval make targets (research-scientist-eval). Run from Git Bash: `mingw32-make <target>`.
#   m7-test            unit + pipeline tests (no GPU, no network)
#   m7-mock            MODE=mock: fake tree built from fixtures/ -> results/m7_eval/mock/
#   m7-eval            DEV evaluation of E1-E6 from saved raw outputs -> results/m7_eval/dev/
#                      (registered in `make eval`)
#   m7-repro           run the DEV evaluation twice into temp folders and compare every output hash
#   m7-e7-kit          rebuild the E7 user-study kit (m7_eval/e7_kit/) from DEV gold
#   m7-e2-llm-refresh  re-run the STALE rules-vs-LLM comparison through m3's own target
#                      (needs Ollama on 127.0.0.1:11434 with qwen3:4b-instruct; ~25 min), then m7-eval
#   m7-eval-test       GUARDED test-split evaluation; only via root `ALLOW_TEST=1 PURPOSE=... make eval-test`
#                      (refuses unless ALLOW_TEST=1, PURPOSE and a results/test_access_log.md row for HEAD)

.PHONY: m7-test m7-mock m7-eval m7-repro m7-e7-kit m7-e2-llm-refresh m7-eval-test m7-clean

m7-test:
	$(UV) run pytest m7_eval/tests

m7-mock:
	MODE=mock $(UV) run python -m m7_eval mock

m7-eval:
	$(UV) run python -m m7_eval run

m7-repro:
	$(UV) run python -m m7_eval repro-check

m7-e7-kit:
	$(UV) run python -m m7_eval.e7_kit.build_records

m7-e2-llm-refresh:
	@if curl -s --max-time 3 http://127.0.0.1:11434/api/tags | grep -q 'qwen3:4b-instruct'; then \
	  $(MAKE) m3-run-llm-dev && $(MAKE) m7-eval; \
	else echo "m7-e2-llm-refresh: Ollama with qwen3:4b-instruct not reachable on 127.0.0.1:11434; E2 LLM stays STALE"; fi

m7-eval-test:
	$(UV) run python -m m7_eval eval-test

m7-clean:
	rm -rf results/m7_eval/mock

EVAL_TARGETS += m7-eval
EVAL_TEST_TARGETS += m7-eval-test
CLEAN_TARGETS += m7-clean
