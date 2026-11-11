# m8_helper make targets. Owned by the counselling-helper-engineer builder.
#   m8-test    unit tests (no Ollama needed)
#   m8-mock    MODE=mock: fixture cards, lexical backend, results/m8_helper/mock/
#   m8-cards   validate m8_helper/cards against card.v1
#   m8-eval    dev-tuned threshold + held-out report -> results/m8_helper/ (ollama needs the daemon)

.PHONY: m8-test m8-mock m8-cards m8-eval

m8-test:
	$(UV) run pytest m8_helper/tests

m8-cards:
	$(UV) run python -m contracts.validate card.v1 m8_helper/cards

m8-mock: m8-cards
	$(UV) run python -m m8_helper mock

m8-eval:
	$(UV) run python -m m8_helper.evaluate --backend tfidf
	-$(UV) run python -m m8_helper.evaluate --backend ollama
