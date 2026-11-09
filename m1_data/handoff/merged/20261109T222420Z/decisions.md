### D-?: Where the drug lexicon's facts come from, and the "no invented dose" rule   (Phase B / m1_data / data-scientist / 2026-11-09)
- What we needed to decide: Which sources to trust for each column of `data/lexicon/drugs.csv` (34 drugs), especially dose ranges, which a safety check (m4 C4) will compare against.
- Options we considered:
  1. Write doses from memory. Pro: fast. Con: forbidden by the brief (an invented dose range could hide a real dosing error); not citable.
  2. India's NLEM 2022 only. Pro: Indian, official. Con: NLEM lists tablet strengths, not dose ranges.
  3. NLEM for strengths + WHO AWaRe portal for antibiotic class + official drug labels (openFDA, US) for dose ranges; blank + UNVERIFIED when nothing was fetched. Pro: every number has a fetched source. Con: US labels are not Indian practice.
- What we chose: Option 3.
- Why: A blank field that says UNVERIFIED is honest; a made-up number looks trustworthy and is dangerous. Dose range = lowest and highest single adult oral dose written in the label.
- What we actually did: `m1_data/lexicon_source.py` (facts + URLs), `m1_data/lexicon.py` (build), output `data/lexicon/drugs.csv`; 22 rows have a label dose range, 12 are blank (UNVERIFIED). Rebuild: `uv run --extra data python -m m1_data build-lexicon`.
- What could go wrong / weaknesses: NLEM rows were read by automated extraction of a 109-page PDF (four rows only by an LLM-based JSON extraction: ibuprofen, ondansetron, metformin, iron-folic acid); US label ranges do not match Indian practice (e.g. paracetamol 1000-1000 mg from a US OTC label, so a spoken "500 mg" is outside the range). UNVERIFIED until a human spot-checks.
- What else could be done: Use the Indian National Formulary or ICMR treatment guidelines for ranges; ask a pharmacist to review (clinical-reviewer agent is only simulated).
- How to change this decision later: edit `m1_data/lexicon_source.py`, rebuild, regenerate (`make data`; the test split will need `--refreeze` only if doses used in conversations change).
- Status: done

### D-?: Kannada spellings of drug names: rule-based transliteration instead of IndicXlit   (Phase B / m1_data / data-scientist / 2026-11-09)
- What we needed to decide: How to write English drug names in Kannada script (with common spelling variants) without a native speaker.
- Options we considered:
  1. AI4Bharat IndicXlit (MIT, verified on GitHub). Pro: learned model, natural spellings. Con: needs fairseq + torch; fairseq is hard to install on Windows/Python 3.11; heavy for 34 words.
  2. `indic-transliteration` 2.3.82 (MIT, verified on PyPI): rule-based conversion of a phonetic Latin respelling (ISO 15919) to Kannada. Pro: tiny, deterministic, pinned. Con: the respelling (e.g. "amāksisilin") is written by an AI agent, so the spelling is only as good as that guess.
  3. Type Kannada spellings by hand. Pro: none over option 2. Con: not reproducible, typo-prone.
- What we chose: Option 2, with 2-4 hand-written variant respellings per drug (vowel length, aspiration, short forms like ಅಮಾಕ್ಸಿ).
- Why: Reproducible and light; the real risk (unnatural spelling) is the same for all options without a native reviewer.
- What we actually did: optional extra `data = ["indic-transliteration==2.3.82"]` in pyproject.toml (added under the uv mutex); `m1_data/lexicon.py::_iso_to_kn`.
- What could go wrong / weaknesses: spellings and variants are not native-validated; real spoken variants may be missing.
- What else could be done: run IndicXlit on Colab to produce top-k variants and merge them; collect variants from Kannada pharmacy web pages.
- How to change this decision later: change `iso` / `iso_variants` in `m1_data/lexicon_source.py` or replace `_iso_to_kn`.
- Status: done

### D-?: Templates as a small mini-language with computed gold spans and a negation self-check   (Phase B / m1_data / data-scientist / 2026-11-09)
- What we needed to decide: How to produce >= 200 conversations whose gold labels and character offsets are exactly right.
- Options we considered:
  1. Write conversations and labels by hand. Pro: natural. Con: offsets are error-prone; does not scale.
  2. Let an LLM write conversations and labels. Pro: varied. Con: the brief forbids an LLM as ground truth; labels would be unverifiable.
  3. Templates with typed slots (`{D1.name}`, `{N1}` ...) and span markers (`[[m1|...]]`); the generator computes offsets while rendering and checks that the negation cues it finds (with the shared table) are exactly the ones the template declared.
- What we chose: Option 3: 59 templates, 9 categories, 22 families (`data/templates/`).
- Why: Gold is correct by construction and checked twice (offsets by contracts.validate, negation by the self-check).
- What we actually did: `m1_data/render.py`, `templates.py`, `generate.py`; sources in `data/templates/SOURCES.md`; `results/m1_data/unattested_tokens.json` lists template words NOT seen in any fetched source (164 of 221 Kannada words).
- What could go wrong / weaknesses: sentences are AI-composed, repetitive and not native-validated; many words are unattested; some twins are semantically odd on purpose.
- What else could be done: native-speaker review sheet per template; add real-text-derived frames from more sources.
- How to change this decision later: edit `data/templates/*.yaml`; run `make data` (test templates changing requires `--refreeze`).
- Status: done

### D-?: How the dev/test split is cut (template families inside each category + dosed drug-dose combinations)   (Phase B / m1_data / data-scientist / 2026-11-09)
- What we needed to decide: How to split dev/test "by template family and drug-dose combination" so near-duplicates never straddle.
- Options we considered:
  1. Random split of conversations. Con: near-duplicate sentences from one template in both splits (leakage); forbidden.
  2. Treat the 9 categories (a)-(i) as the families. Pro: strictest. Con: whole phenomena (e.g. cross-turn negation) would exist in only one split, so the test could not measure them.
  3. Several template families per category (22 in total, each a group of templates sharing sentence frames); half of each category's families (seeded) go to test. Dosed combinations (drug, value, unit) alternate dev/test per drug (seeded); bare drug mentions without a dose may appear in both.
- What we chose: Option 3.
- Why: No sentence frame and no dosed drug string is in both splits, while every phenomenon is in both.
- What we actually did: `m1_data/split.py`; `data/splits/{dev,test}.txt`, `split_plan.json`; tests `m1_data/tests/test_split.py` (no family / dosed combo in both splits; test = 264 conversations, 352 medication entries). Counts for categories e and g were raised from 8 to 16 per template to pass 300 test medication entries.
- What could go wrong / weaknesses: drug NAMES (without dose) occur in both splits; families within one category still share vocabulary. This reading of "family" is my interpretation: open question for the orchestrator.
- What else could be done: also hold out whole drugs for test; or use categories as families for a second, stricter evaluation.
- How to change this decision later: `plan_families` / `plan_combos` in `m1_data/split.py`, then `python -m m1_data generate --refreeze` + a new decision entry.
- Status: done

### D-?: Freezing the test split with a hash lock that the generator refuses to break   (Phase B / m1_data / data-scientist / 2026-11-09)
- What we needed to decide: How to make sure nobody silently edits test files or gold labels.
- Options we considered:
  1. Lock file only, checked in CI. Con: a regeneration would rewrite files and lock together.
  2. Lock file + generator guard: `make data` refuses to write a different `test.lock` unless `--refreeze` is given.
- What we chose: Option 2, same `<sha256>  <path>` format as `infra/scripts/check_split_lock.py`.
- Why: Accidental re-freezing becomes impossible; deliberate re-freezing leaves a visible trace.
- What we actually did: `data/splits/test.lock` (530 lines: 264 gold + 264 transcripts + twins_test.jsonl + test.txt); tests `m1_data/tests/test_split_lock.py`; root `make split-lock` already passes. Proof it fails: editing one label in a temp copy gives "data/gold/m1-a5-000.json: CHANGED since the test split was frozen", exit 1.
- What could go wrong / weaknesses: the lock was created and regenerated (--refreeze) during this build before anything was committed; once committed, any change needs a decision entry.
- What else could be done: sign the lock; store it outside the repo.
- How to change this decision later: `python -m m1_data generate --refreeze` + decision entry.
- Status: done

### D-?: Gold convention: a medicine stopped before finishing is "negated"   (Phase B / m1_data / data-scientist / 2026-11-09)
- What we needed to decide: What the gold record says for "ಕೋರ್ಸ್ ಮುಗಿಸದೆ ನಿಲ್ಲಿಸಿದೆವು" (stopped without finishing) and "ಇದು X ಅಲ್ಲ" (this is not X).
- Options we considered:
  1. negated: false (the drug was taken for a while). Con: the -ದೆ cue in the same clause would then contradict the record.
  2. negated: true meaning "not being taken as prescribed / not this drug".
- What we chose: Option 2, documented in docs/annotation_guide.md section 4.
- Why: It matches the clause-level negation rule the extractor and verifier use.
- What we actually did: templates c1-c5, e5.
- What could go wrong / weaknesses: clinically, "stopped early" differs from "never taken"; the record schema cannot express it. Open question for the clinical reviewer.
- What else could be done: add an `adherence` field in a future record.v2.
- How to change this decision later: items in `data/templates/c_stopped_early.yaml`.
- Status: needs human

### D-?: Problems hit while building m1 data and how they were fixed   (Phase B / m1_data / data-scientist / 2026-11-09)
- What we needed to decide: How to handle three problems found while testing.
- Options we considered: (a) Windows briefly locked a file during regeneration (WinError 32): fail, or retry; (b) the first tamper test passed for the wrong reason (Windows text mode rewrote line endings, the intended label edit did nothing): keep or fix; (c) the ORS row had no fetched source URL: drop ORS or cite the fetched Kannada ORS page for the name only.
- What we chose: (a) retry up to 5 s and only rewrite changed files; (b) the test now edits bytes and asserts the edit happened; (c) cite the Kannada ORS page for the name, dose stays UNVERIFIED.
- Why: Each fix makes a check honest instead of lucky.
- What we actually did: `m1_data/generate.py::_retry`, `m1_data/tests/test_split_lock.py`, `lexicon_source.py` (`name_source`).
- What could go wrong / weaknesses: none known.
- What else could be done: run the tests on Linux CI too.
- How to change this decision later: same files.
- Status: done
