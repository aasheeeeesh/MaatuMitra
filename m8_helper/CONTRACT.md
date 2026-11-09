# m8_helper contract (STUB by architect; the builder keeps it current)

- Layer: L4b counselling helper
- Schema versions used: card.v1 (in)
- Inputs: data/cards/*.json (card.v1); fixture cards in fixtures/card/valid.
- Outputs: Answers with card id or the Kannada 'not sure, ask a doctor' abstention; m8_helper/eval/; results/m8_helper/.
- May write ONLY: m8_helper/, data/cards/, results/m8_helper/, and `m8_helper/handoff/*` for shared docs.
- May read: contracts/, fixtures/, data/ (read-only unless this is m1), results/<other module>/.
- May import: `contracts.validate` only. Never another module's code.
- MOCK MODE: `MODE=mock make m8-mock` runs purely on fixtures/.
- Every produced artifact is validated with
  `uv run python -m contracts.validate <schema> <path>` in this module's tests.
