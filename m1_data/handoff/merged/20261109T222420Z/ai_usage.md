## m1_data (data-scientist agent, Claude, 2026-11-09/10)

- Generated ALL code in `m1_data/` (generator, renderer, lexicon builder, negation matcher for
  coverage, split/lock, coverage, CLI, tests) and `data/generate.py`.
- Composed ALL Kannada template sentences (`data/templates/*.yaml`) and the ISO 15919 phonetic
  respellings behind the Kannada drug spellings. These are AI-written, not native-validated;
  164 of 221 template words are not attested in any fetched source
  (`results/m1_data/unattested_tokens.json`).
- Extracted lexicon facts from fetched pages with automated tools (firecrawl directQuote /
  JSON extraction of the NLEM PDF, the WHO AWaRe portal list, openFDA labels). The agent
  interpreted label text into a "lowest-highest single adult dose" range.
- Proposed name-similarity confusable pairs (marked UNVERIFIED in `verified_by`).
- Wrote `docs/annotation_guide.md` and the m1 handoff files.

What a human must check: Kannada naturalness of every template and drug spelling; the four
NLEM rows read only by JSON extraction; each dose range against the cited label; the gold
convention "stopped early = negated"; licences of the sources (see licences.md).
