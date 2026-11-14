### D-?: Rules pipeline now writes record.v2 by default; record.v1 stays behind a flag   (Phase C / m3_extract / nlp-engineer / 2026-11-12)
- What we needed to decide: How to move the rules extractor to the new record format (record.v2) without breaking modules that still read v1.
- Options we considered:
  1. Replace v1 completely. Pro: one code path. Con: breaks integration and m7 fixtures at once.
  2. v2 by default, v1 behind `schema="record.v1"` (CLI `--schema record.v1`). Pro: old behaviour kept byte for byte; Con: two paths to keep.
  3. Keep v1 by default. Con: contradicts the migration plan.
- What we chose: Option 2. v2 output goes to `results/m3_extract/rules_v2/` (logs in `rules_v2_logs/` so the folder holds only records); the old `results/m3_extract/rules/` is untouched.
- Why: the v1 run reproduces the frozen v1 dev files exactly (checked with `diff -rq`), so nothing downstream can silently change. `integration/` and other modules call `extract()` and validate as v1; with the new default they will see v2 until they switch (UNVERIFIED by us, outside our folder).
- What we actually did: `m3_extract/rules.py` (`extract(..., schema=)`), `run.py`, `__main__.py`. Commands: `uv run python -m m3_extract run-rules --split dev` (v2) and `... --schema record.v1`. Existing tests now pass `schema="record.v1"`; one new test checks both.
- What could go wrong / weaknesses: any caller of `extract()` that expects v1 breaks until it passes `schema="record.v1"`. The speaker field needs turn roles; we pass the gold roles on dev (oracle diarisation), so speaker accuracy on ASR text is UNMEASURED.
- What else could be done: a diarisation step in m2; point `integration/` to the flag or to v2.
- How to change this decision later: default of `schema` in `rules.extract`, `--schema` default in `__main__.py`.
- Status: done

### D-?: Status of each medication (prescribed, already taken, not taken, advised against, stopped early)   (Phase C / m3_extract / nlp-engineer / 2026-11-12)
- What we needed to decide: How rules decide what a spoken drug mention MEANS, because `negated` alone mixed several meanings (review M3-M1).
- Options we considered:
  1. Only from the negation flag. Pro: simple. Con: that is exactly the old confusion.
  2. From the verb in the drug's clause plus, for a question answered by a bare "ಹೌದು/ಇಲ್ಲ", the kind of question (finished? taken? may I take?). Pro: matches gold.v2 labels; Con: word lists are hand-made.
  3. Ask the LLM. Con: slower, not auditable.
- What we chose: Option 2. Verb lists in `m3_extract/v2fields.py`. A drug named without any verb is "prescribed" only if a clinician role spoke it and it has a dose, frequency or duration; otherwise "unknown" (no evidence span). "continue_existing" is never produced (no dev wording to learn from).
- Why: "unknown" is safer than a guess; every non-unknown status has its own evidence span (the verb or the answer word).
- What we actually did: `v2fields.statement_status`, `question_status`; tests in `m3_extract/tests/test_v2_fields.py`. Dev: 0 status errors of 408 (in-sample, N=408, Wilson 0.0 to 9.3 per 1000).
- What could go wrong / weaknesses: verb forms and the three question classes are UNVERIFIED and not native-validated; 0 errors is in-sample (we tuned on DEV) and says little about new wording. Words found only in test templates were removed by the no-test-only-words guard.
- What else could be done: a Kannada reviewer to confirm the verb lists; more question classes.
- How to change this decision later: lists at the top of `m3_extract/v2fields.py`.
- Status: done (needs human review of word lists)

### D-?: Route, formulation, strength and dose are separate fields   (Phase C / m3_extract / nlp-engineer / 2026-11-12)
- What we needed to decide: How to extract route, form (tablet, syrup, injection ...), product strength, and how to keep strength apart from the amount given (CR-ROUTE, CR-LIQUID-STRENGTH, review M3-C1, M3-M5).
- Options we considered:
  1. Keep "first number plus unit = dose". Con: "500 mg, two tablets" gives 500 mg.
  2. A mass (mg) together with a count (tablet) = strength + dose; a mass alone stays the dose (gold convention); "120 mg/5 ml" (with "/", "per" or ಪ್ರತಿ) = liquid strength; a mass and a volume without a separator = left null and logged. Pro: never guesses; Con: loses data in odd phrasing.
- What we chose: Option 2. A comma no longer cuts an instruction off from its next clause (one following clause without a drug is read too). Route comes from a form word (ಮಾತ್ರೆ, ಕ್ಯಾಪ್ಸೂಲ್, ಸಿರಪ್ = oral; injection = injection_unspecified) or a drink verb; "ಮಾತ್ರೆ ಬೇರೆ" (another tablet) and denied identities give no form.
- What we actually did: `units.py` (`parse_attributes`, new `legacy` flag keeps v1), `v2fields.py`, `rules.py`. Dev: route 0 errors of 408 (340 non-null gold), formulation 3 of 408 (7.3 per 1000, Wilson 2.5 to 21.4): g5 templates say "Tablet X ... ಕ್ಯಾಪ್ಸೂಲ್" (contradiction) and gold says tablet, we say capsule.
- What could go wrong / weaknesses: gold.v2 has NO spoken strength and NO weight on DEV, so strength (0 non-null of 408) and weight_kg are not measured on real data; they are only unit-tested on made-up sentences. Only 1 ml and 5 ml volumes are read for liquid strength.
- What else could be done: add dev templates that say a strength; flag contradictions instead of picking one.
- How to change this decision later: `units._decide_dose`, `v2fields.FORM_WORDS`.
- Status: partly done (strength and weight unmeasured)

### D-?: As needed, food timing, age band and weight   (Phase C / m3_extract / nlp-engineer / 2026-11-12)
- What we needed to decide: Rules for four more fields and which drug a phrase belongs to.
- Options we considered: attach to the whole record (wrong when several drugs), or to the nearest drug in the same sentence. We chose the nearest drug in the same sentence (ties: the earlier one); a food phrase in its own sentence (a patient question) attaches to the drug just dictated if that was at most one turn earlier and the next turn is not a bare "no".
- What we chose: as_needed = "<symptom> ಇದ್ದರೆ ಮಾತ್ರ" (the symptom word is part of the span, as in gold). Food phrases: ಊಟದ ನಂತರ/ಮೊದಲು/ಜೊತೆ, ಖಾಲಿ ಹೊಟ್ಟೆ. Age: "<N> ವರ್ಷದ" (bands from the README table), "<N> ತಿಂಗಳ" (under 12 = infant), else the word ಮಗು (child, Wiktionary 2026-11-12) or ಶಿಶು (infant); "ವರ್ಷದಿಂದ" (for years) is a duration. Weight: "<N> ಕೆಜಿ/kg/ಕಿಲೋ", 0 to 300 only.
- Why: same spans as gold; nothing is filled without words.
- What we actually did: `v2fields.py`, `rules._sentence_fields`. Dev: as_needed 0 of 408 errors (24 non-null), food 0 of 408 (24 non-null), age band 0 of 328 (80 non-null).
- What could go wrong / weaknesses: tiny counts; a bare ಮಗು in a follow-up sentence also sets child; ವರ್ಷ without ದಿಂದ is read as an age even if it is a duration. ಕೆಜಿ and ಊಟದ ... are UNVERIFIED (Wiktionary 404).
- What else could be done: real Kannada review; link advice items to drugs.
- How to change this decision later: `v2fields.py`.
- Status: done (small samples)

### D-?: Accepted clinical-review items fixed in the rules   (Phase C / m3_extract / nlp-engineer / 2026-11-12)
- What we needed to decide: Which findings of `reviews/m3_extract/2026-11-11-clinical.md` fit the rules.
- Options we considered: fix all, fix some, defer. We fixed: M3-M4 "N ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ" (once every N days) is no longer read as per day (frequency null, event logged; also in v1); M3-m1 ಒಂದೂವರೆ = 1.5 (UNVERIFIED, Wiktionary 404); M3-M6 ಚಮಚ gives a dose only next to a liquid form word and ಪ್ಯಾಕೆಟ್ only for ORS (otherwise dose null, event logged; v2 only); M3-M7 combination products: "625" is a drug only right after an amoxicillin/amoxiclav word ("amox 625" becomes amoxicillin-clavulanate) or before a tablet word, and a mg dose of iron-folic acid is left null; M3-m2 a duration next to a symptom word ("fever 3 days") is not a course length (v2 only). Deferred: M3-M8 (advice severity), 1-0-1 style frequencies.
- Why: each is a case where a wrong value would look trustworthy.
- What we actually did: `units.py`, `numbers.py`, `lexicon.py`, tests `test_v2_fields.py` (49+ tests).
- What could go wrong / weaknesses: all phrase lists are not native-validated; null instead of a guess loses information.
- What else could be done: ask a real speaker how ಚಮಚ and ಪ್ಯಾಕೆಟ್ are used.
- How to change this decision later: the named functions.
- Status: done

### D-?: Scoring of the record.v2 fields with a per-template bootstrap   (Phase C / m3_extract / nlp-engineer / 2026-11-12)
- What we needed to decide: How to score the new fields and the new error classes.
- Options we considered: Wilson interval only (assumes independent fields), or also a cluster bootstrap over templates (the 8 conversations of a template are near copies, so Wilson is too narrow).
- What we chose: both. Mapping as in docs/severity.md (2026-11-12 note): route and injection-vs-other form = CR-ROUTE; strength mismatch = CR-LIQUID-STRENGTH; status flip given/not given = CR-NEG, other status = MA-STATUS; child recorded as adult/missing with a dosed drug = CR-PAEDIATRIC; the rest MA-MED-ATTRIBUTE. Bootstrap: 2000 resamples of templates, seed 20261112, percentile 95%.
- What we actually did: `m3_extract/scoring_v2.py`, `uv run python -m m3_extract score-v2` writes `results/m3_extract/dev_scores_v2.csv` and `failures_dev_v2.md`. New fields on DEV: 3 errors in 3512 fields (0.85 per 1000; Wilson 0.3 to 2.5; bootstrap 0.0 to 2.9), all major, 0 critical. ALL numbers are in-sample (rules written on DEV). Fields with no non-null gold (strength, weight) are listed with that count, not as proof of zero errors.
- What could go wrong / weaknesses: bootstrap CI of 0 errors is [0,0], which understates uncertainty; speaker uses oracle roles.
- What else could be done: leave-one-template-out evaluation; test evaluation once, via the frozen procedure.
- How to change this decision later: `scoring_v2.py`.
- Status: done
