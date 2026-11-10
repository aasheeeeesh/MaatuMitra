## m3_extract (agent: nlp-engineer, Claude, 2026-11-09/10)

What the AI agent generated: all code in `m3_extract/` (normaliser, tokeniser, drug finder, number/unit/frequency/duration parsers, negation flag reading the shared table, rules pipeline, evidence check, Ollama LLM pipeline and prompt, scoring, runners, CLI, module.mk), all tests in `m3_extract/tests/`, the word lists `m3_extract/data/symptoms.yaml` and `m3_extract/data/phrases.yaml` (Kannada words and English glosses), plan.md, README.md, CONTRACT.md, `m3_extract/failure_analysis.md`, and every file under `results/m3_extract/` (produced by running that code).

What a human must check:
- The Kannada in symptoms.yaml and phrases.yaml and the extraction rules in rules.py (question scope, coordination, conditional detection) are AI hypotheses, NOT native-validated.
- The scoring definitions (what a "field" is, advice classes) in scoring.py; they decide every number we report.
- That the dev_holdout templates (a3 b4 c5 d2 e6 f3 g5 h6 i3) really were not used to write rules before the first holdout score (2026-11-10 13:32 +05:30). The agent saw a holdout failure and then fixed one bug (rules v2); the v1 scores are kept in `results/m3_extract/rules_v1_frozen/`.
- Disclosure: before deciding to stop reading template files, the agent read the template file for category a (`data/templates/a_asha_fever_cough.yaml`), which includes the TEST family a_fever_cough__f3 (symptom pool pain / body ache / headache). No test gold, test transcript or other test template was opened. ನೋವು (pain) is in the symptom list; its listed sources are Wiktionary and KN-3.
- The LLM latency numbers depend on what else was running on the laptop (the agent ran unit tests during the LLM run).
