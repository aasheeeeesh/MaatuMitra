# m7_eval contract (STUB by architect; the builder keeps it current)

- Layer: L7 evaluation, cost log, governance
- Schema versions used: all (read)
- Inputs: Raw outputs under results/<module>/ (all contracts); data/splits.
- Outputs: results/tables/*.csv, results/plots/*.png, results/failure_gallery.md, E7 kit, infra/cost_report.md.
- May write ONLY: m7_eval/, results/tables/, results/plots/, results/failure_gallery.md, results/m7_eval/, infra/inventory.md (append), infra/cost_report.md, and `m7_eval/handoff/*` for shared docs.
- May read: contracts/, fixtures/, data/ (read-only unless this is m1), results/<other module>/.
- May import: `contracts.validate` only. Never another module's code.
- MOCK MODE: `MODE=mock make m7-mock` runs purely on fixtures/.
- Every produced artifact is validated with
  `uv run python -m contracts.validate <schema> <path>` in this module's tests.
