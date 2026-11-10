# m6_ui make targets. Owned by the frontend-engineer builder.
# m6-test : all m6 tests (pure logic + Streamlit AppTest), MODE=mock
# m6-mock : headless mock run on fixtures -> results/m6_ui/mock_summary.json + conjunct test page
# m6-run  : start the app on http://127.0.0.1:8501 (MODE=mock unless you set MODE=live)
# Streamlit reads m6_ui/.streamlit/config.toml only when started from inside m6_ui/, so
# m6-run does `cd m6_ui`; the address is ALSO forced on the command line.

.PHONY: m6-test m6-mock m6-run

M6_MODE ?= $(if $(MODE),$(MODE),mock)

m6-test:
	MODE=mock $(UV) run pytest m6_ui/tests

m6-mock:
	MODE=mock $(UV) run python -m m6_ui.mock_run

m6-run:
	cd m6_ui && MODE=$(M6_MODE) $(UV) run streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
