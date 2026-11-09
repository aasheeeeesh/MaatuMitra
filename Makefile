# MaatuMitra root Makefile.
# Linux / CI: `make <target>`.  Windows: run `mingw32-make <target>` from GIT BASH
# (the recipes need bash; SHELL := bash). Only GNU make features are used.
SHELL := bash
.SHELLFLAGS := -e -o pipefail -c
.DEFAULT_GOAL := help

MODULES := m1_data m2_asr m3_extract m4_verify m5_backend m6_ui m7_eval m8_helper
UV ?= uv

# Windows MAX_PATH (260 chars): a deep repo path + site-packages breaks the venv.
# Keep the env at a short path unless the user already chose one.
ifeq ($(OS),Windows_NT)
ifndef UV_PROJECT_ENVIRONMENT
export UV_PROJECT_ENVIRONMENT := $(subst \,/,$(USERPROFILE))/.venvs/maatumitra
endif
endif

# Aggregates. Each module.mk may append its targets (see m*/module.mk).
DATA_TARGETS :=
EVAL_TARGETS :=
EVAL_FULL_TARGETS :=
EVAL_TEST_TARGETS :=
DEMO_TARGETS :=
CLEAN_TARGETS :=

include $(foreach m,$(MODULES),$(m)/module.mk)

.PHONY: help setup test lint fmt validate-fixtures split-lock audit data eval eval-full \
	eval-test demo clean merge-handoff m1 m2 m3 m4 m5 m6 m7 m8

help:
	@echo "setup             uv sync --locked (base deps only; extras: uv sync --extra asr|tts|llm|helper)"
	@echo "test              all tests (repo + every module)"
	@echo "lint              ruff check + ruff format --check"
	@echo "fmt               ruff format + ruff check --fix"
	@echo "validate-fixtures every valid fixture passes, every invalid fixture fails"
	@echo "split-lock        frozen test split unchanged (warns if test.lock not created yet)"
	@echo "audit             pip-audit on the locked dependency set"
	@echo "m1 .. m8          one module: its tests + its mock run"
	@echo "data | eval | eval-full | demo | clean   (modules register their parts)"
	@echo "eval-test         GUARDED: ALLOW_TEST=1 PURPOSE='...' make eval-test"
	@echo "merge-handoff     MODULE=m1_data make merge-handoff"

setup:
	$(UV) sync --locked

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

validate-fixtures:
	$(UV) run python -m contracts.validate --check-fixtures fixtures

split-lock:
	$(UV) run python infra/scripts/check_split_lock.py --allow-missing

audit:
	@mkdir -p .cache
	$(UV) export --locked --all-extras --format requirements-txt --no-hashes --no-emit-project -o .cache/requirements-audit.txt >/dev/null
	$(UV) run pip-audit --disable-pip --no-deps -r .cache/requirements-audit.txt

m1: m1-test m1-mock
m2: m2-test m2-mock
m3: m3-test m3-mock
m4: m4-test m4-mock
m5: m5-test m5-mock
m6: m6-test m6-mock
m7: m7-test m7-mock
m8: m8-test m8-mock

data:
	@if [ -z "$(strip $(DATA_TARGETS))" ]; then \
	  echo "make data: no module has registered a data target yet (DATA_TARGETS is empty)"; \
	else $(MAKE) $(DATA_TARGETS); fi

eval:
	@if [ -z "$(strip $(EVAL_TARGETS))" ]; then \
	  echo "make eval: no module has registered a eval target yet (EVAL_TARGETS is empty)"; \
	else $(MAKE) $(EVAL_TARGETS); fi

eval-full:
	@if [ -z "$(strip $(EVAL_FULL_TARGETS))" ]; then \
	  echo "make eval-full: no module has registered a eval-full target yet (EVAL_FULL_TARGETS is empty)"; \
	else $(MAKE) $(EVAL_FULL_TARGETS); fi

demo:
	@if [ -z "$(strip $(DEMO_TARGETS))" ]; then \
	  echo "make demo: no module has registered a demo target yet (DEMO_TARGETS is empty)"; \
	else $(MAKE) $(DEMO_TARGETS); fi

# The TEST split is frozen (docs/hypothesis.md, section 6.5). Order matters:
# 1) refuse unless ALLOW_TEST=1, PURPOSE set and docs/hypothesis.md committed;
# 2) refuse if no module registered an eval-test target (nothing is logged);
# 3) log the access to results/test_access_log.md, then run.
eval-test:
	@$(UV) run python infra/scripts/eval_test_guard.py --check-only
	@if [ -z "$(strip $(EVAL_TEST_TARGETS))" ]; then \
	  echo "make eval-test: REFUSED: no module has registered an eval-test target yet (m7_eval adds one). Nothing logged."; \
	  exit 1; \
	fi
	@$(UV) run python infra/scripts/eval_test_guard.py
	$(MAKE) $(EVAL_TEST_TARGETS)

merge-handoff:
	@if [ -z "$(MODULE)" ]; then echo "usage: make merge-handoff MODULE=m1_data"; exit 2; fi
	$(UV) run python infra/scripts/merge_handoff.py $(MODULE)

clean:
	rm -rf .pytest_cache .ruff_cache .cache
	find . -path ./.venv -prune -o -name __pycache__ -type d -prune -exec rm -rf {} +
	@if [ -n "$(strip $(CLEAN_TARGETS))" ]; then $(MAKE) $(CLEAN_TARGETS); fi
