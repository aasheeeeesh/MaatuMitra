# m1_data plan (data-scientist, pass B1a = TEXT DATA ONLY)

Written before tests and code, 2026-11-09. Audio (AGENT 2 steps 5-6) is a later pass.

## Goal of this pass

AGENT 2 steps 1, 2, 3, 4, 7 (text files), 8, 9: drug lexicon, Kannada templates, a
deterministic generator, a leakage-safe dev/test split with a hash lock, a manifest,
the annotation guide, and `make data`.

## Sources fetched this session (2026-11-09)

| id | what | used for |
|---|---|---|
| NLEM | nppa.gov.in NLEM 2022 PDF (query extraction) | `nlem_listed`, `strengths_mg` |
| AWARE | aware.essentialmeds.org/list (WHO AWaRe portal) | `aware_class` |
| FDA | openFDA drug labels (api.fda.gov, via firecrawl provider) | `adult_dose_range_mg`, `max_daily_mg` |
| ISMP | ISMP list of confused drug names (ECRI PDF) | `confusable_with` (cited pairs) |
| XLIT | github.com/AI4Bharat/IndicXlit, pypi.org/project/indic-transliteration | transliteration tool choice + licence |
| KN-1..6 | Kannada grammar (en.wikipedia), ಜ್ವರ (kn.wikipedia), news18 Kannada antibiotics article, CARE Hospitals Kannada ORS page, Kannada script numerals (en.wikipedia), Kannada cardinal numbers (en.wiktionary) | sentence frames, vocabulary (data/templates/SOURCES.md) |

## Design

1. **Lexicon** (`m1_data/lexicon_source.py` -> `data/lexicon/drugs.csv`, 34 rows, 18 antibiotics).
   Kannada spellings: ISO 15919 phonetic respellings written by the agent (UNVERIFIED), converted
   to Kannada script with `indic-transliteration` 2.3.82 (MIT, rule-based, verified on PyPI).
   IndicXlit (MIT) rejected for now: needs fairseq + torch (heavy, Windows build risk).
   Dose ranges only from a fetched openFDA label; otherwise blank + UNVERIFIED.
2. **Templates** (`data/templates/*.yaml`, 50 templates, 9 categories (a)..(i), 22 template
   families). Mini-language: `{D1.name}` typed slots, `[[M1|...]]` gold-span markers,
   `{N1}` negation slots with a (negative form, positive twin form, pattern ids) triple.
   Gold spans are COMPUTED from rendered text, never typed.
3. **Generator** (`m1_data/generate.py`, CLI `python -m m1_data generate` and
   `data/generate.py`): fixed seed 20261109, version `m1-data-1.1.0`, per-instance RNG
   seeded with sha256(seed, template, index) so output never depends on dict/hash order.
   Writes gold.v1, transcript.v1 (model=gold, source=template_text), minimal-pair twins
   (`data/twins/twins_{dev,test}.jsonl`), manifest, splits, lock, coverage.
   Self-check: the negation table's regexes are run on every generated token; any cue the
   template did not declare (or a declared cue that does not fire) aborts generation.
4. **Split**: unit = template family (`<category>__f<n>`), each category has families in
   both splits. Drug-dose combinations WITH a dose are split-exclusive (each drug's dosed
   combos alternate dev/test, seeded); bare drug mentions (no dose) are allowed in both.
   Lock = sha256 of every test gold file, gold transcript, test twins file and test.txt.
   The generator refuses to overwrite a different test.lock unless `--refreeze`.
5. **Audio later**: manifest rows carry `parent_id`; every audio variant inherits its
   conversation's split; plan: TTS voice A in dev+test, voice B test-only (held out).

## Tests first (m1_data/tests)

kn/render unit tests; lexicon columns/sources/UNVERIFIED rules; templates (>=40, 9
categories, slot types, grounding ids exist in SOURCES.md); generator (determinism =
regenerate into tmp and compare sha256 with committed files; every doc validates with
contracts.validate; coverage thresholds; negation self-check; twins); split (no family /
dosed combo in both splits; test >= 40 conv and >= 300 meds); split lock (passes on repo,
FAILS on an edited temp copy); manifest (every generated file, sha256 matches); mock mode.

## Risks

All Kannada is AI-composed and not native-validated; several phrases are not attested in
any fetched source (listed automatically in results/m1_data/unattested_tokens.json).
US label dose ranges may not match Indian practice. NLEM strengths came from automated
extraction of a PDF (spot-check needed).
