# m1_data make targets (data-scientist). Run from Git Bash: `mingw32-make <target>`.
#   m1-test        module tests (pytest m1_data/tests)
#   m1-mock        MODE=mock generator run on fixtures/ only -> results/m1_data/mock/
#   m1-lexicon     rebuild data/lexicon/drugs.csv (needs the optional extra `data`)
#   m1-data        lexicon + generator + coverage report (registered in `make data`)
#   m1-audio      MMS-TTS audio + FLEURS subset (needs `uv sync --inexact --extra tts`, ffmpeg,
#                 ~2 GB free disk; resumable; appends only to test.lock). NOT in `make data`.
#   m1-audio-verify  manifest sha256 of audio rows vs files on disk (in `make data`)
#   m1-split-lock  frozen TEST split unchanged (m1's own test; root `split-lock` uses
#                  infra/scripts/check_split_lock.py on the same data/splits/test.lock)

.PHONY: m1-test m1-mock m1-lexicon m1-data m1-coverage m1-split-lock m1-audio m1-audio-verify

m1-test:
	$(UV) run pytest m1_data/tests

m1-mock:
	MODE=mock $(UV) run python -m m1_data mock

m1-lexicon:
	$(UV) run --extra data python -m m1_data build-lexicon

m1-coverage:
	$(UV) run python -m m1_data coverage > /dev/null
	@echo "wrote results/m1_data/coverage.json and results/m1_data/unattested_tokens.json"

# The generator REFUSES to change data/splits/test.lock (frozen test split). To refreeze on
# purpose: `$(UV) run python -m m1_data generate --refreeze` plus a decision entry.
m1-data: m1-lexicon
	$(UV) run python -m m1_data generate
	$(MAKE) m1-coverage

m1-split-lock:
	$(UV) run pytest m1_data/tests/test_split_lock.py -q

DATA_TARGETS += m1-data

m1-audio:
	$(UV) run --extra tts python -m m1_data audio-build
	$(UV) run python -m m1_data fleurs

m1-audio-verify:
	$(UV) run python -m m1_data audio-verify

DATA_TARGETS += m1-audio-verify
