# m8_helper (L4b counselling helper)

Quotes an approved card or abstains. No text is generated. Built by `counselling-helper-engineer`.

- Cards: `cards/*.json` (16, card.v1). AI-authored DRAFTS paraphrased from three WHO fact sheets fetched 2026-11-12 (AMR, pneumonia, diarrhoeal disease). All `clinician_reviewed=false`; Kannada not native-validated. Regenerate: `uv run python -m m8_helper.author_cards`.
- Modes: `normal` serves only `clinician_reviewed=true` cards (today none, so it always abstains); `demo` serves drafts with a visible DRAFT label.
- Ask: `uv run python -m m8_helper ask "..." --demo [--backend ollama]`.
- Tests, mock run: `mingw32-make m8`. Evaluation: `mingw32-make m8-eval` (the ollama backend needs the Ollama daemon).
- Eval set: `eval/questions.jsonl` (80 rows, split by topic). Results: `results/m8_helper/`.
- Not claimed: any clinical or educational impact. Retrieval and abstention only.
