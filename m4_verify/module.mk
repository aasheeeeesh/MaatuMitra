# m4_verify make targets. Owned by the safety-engineer builder.
#   m4-test   unit tests (negation rules, checks C1..C8, fail-closed, E4 generator, CLI)
#   m4-mock   MODE=mock: fixtures only -> results/m4_verify/ (verdicts + E4 tables)
#   m4-e4-data  E4 on the 6 fixture conversations with data/lexicon/drugs.csv
#   m4-e4-dev   E4 on m1 DEV gold: data/gold filtered by data/splits/dev.txt (test files are never
#               opened; see m4_verify/split_guard.py). Fixed seed 20261109. Several minutes.
#   m4-audit  re-run the negation matcher on the stored Kannada Wikipedia sentences

.PHONY: m4-test m4-mock m4-e4-data m4-e4-dev m4-audit m4-clean

m4-test:
	$(UV) run pytest m4_verify/tests

m4-mock:
	MODE=mock $(UV) run python -m m4_verify mock --out-dir results/m4_verify

m4-e4-data:
	@if [ -f data/lexicon/drugs.csv ]; then \
	  $(UV) run python -m m4_verify e4 --lexicon data/lexicon/drugs.csv --out-dir results/m4_verify/data_lexicon; \
	else echo "m4-e4-data: data/lexicon/drugs.csv not built yet (make data)"; fi

m4-e4-dev:
	$(UV) run python -m m4_verify e4 --gold-dir data/gold --lexicon data/lexicon/drugs.csv --n 200 --seed 20261109 --out-dir results/m4_verify/dev

m4-audit:
	$(UV) run python -m m4_verify audit --sentences m4_verify/audit/kn_wikipedia_jvara_sentences.txt

m4-clean:
	rm -rf results/m4_verify

EVAL_TARGETS += m4-mock
