# Cost report (m7_eval)

**$0 cloud spend.** Every number in results/m7_eval/ was computed on the local laptop
(i7-12650H, 16 GB RAM, RTX 3050 Ti 4 GB VRAM, Windows 11 (infra/builder_rules.md)) from files already in the repository. m7 uses no GPU, no network, no paid API and
no cloud account. Evidence: m7_eval has no network client code and no credentials; `make eval`
only reads files listed in manifest.json.

Runtime of the latest `make eval`: see run_log.json (kept out of the reproducible outputs).

| component | status | n | latency p50 (ms) | latency p95 (ms) | hardware | cloud cost (USD) |
|---|---|---|---|---|---|---|
| m3 LLM extraction (qwen3:4b-instruct) | STALE pre-REFREEZE-1 | 40 | 47169.9 | 253269.0 | i7-12650H, 16 GB RAM, RTX 3050 Ti 4 GB VRAM, Windows 11 (builder_rules.md) | 0 |
| m2 ASR | m2 not run yet |  |  |  |  | 0 |
| m7 evaluation (this run) | local CPU, no GPU, no network |  |  |  | i7-12650H, 16 GB RAM, RTX 3050 Ti 4 GB VRAM, Windows 11 (infra/builder_rules.md) | 0 |

UNVERIFIED: the other modules' own cost claims (their inventory entries) are not re-checked here.
