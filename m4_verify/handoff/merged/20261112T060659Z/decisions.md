### D-?: The verifier checks record.v2 itself, inside the existing checks C1..C8   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: How m4 should check the new record.v2 fields (route, strength, formulation, age band, weight, status, speaker, "as needed", food timing) without changing what it says about record.v1.
- Options we considered:
  1. Turn every v2 record back into v1 and check only the old fields. Pro: no new code. Con: the new safety classes (CR-ROUTE, CR-PAEDIATRIC, CR-LIQUID-STRENGTH) could never be caught.
  2. Add new check ids (C9, C10...). Pro: clear separation. Con: the verdict contract (verdict.v1) only allows C1..C8, so this needs a contract change that m4 may not make.
  3. Put the v2 parts inside the existing checks, in a separate file, and run them ONLY for record.v2 input. Pro: no contract change; v1 output provably unchanged. Con: one check (for example C3) now covers two related ideas (negation and status).
- What we chose: Option 3.
- Why: The verdict format stays valid for every consumer (m5, m6, m7). Keeping the v2 code in its own files and only calling it for v2 makes it easy to show that v1 results did not move.
- What we actually did: new files m4_verify/v2rules.py (word lists) and m4_verify/v2checks.py (checks); checks.py calls them only when `schema_version == "record.v2"`; verifier.py validates v2 input against record.v2. Mapping: C1 = every new evidence span exists; C2 = route, strength, formulation, age band, weight re-derived from their own span; C3 = status and speaker; C4 = route, paediatric, liquid strength, dose via strength; C5 = as_needed and food_timing. Tests: m4_verify/tests/test_v2_rules.py, test_v2_checks.py (51 of 67 check tests failed before the code existed). Proof that v1 is unchanged: `uv run python -m m4_verify e4 ... --out-dir <scratch>` gives files identical to results/m4_verify/dev/e4/ (summary.md, catch_rates.csv, clean_flag_rate.csv, per_field.csv, per_check.csv).
- What could go wrong / weaknesses: All Kannada word lists are AI-written and NOT native-validated. Check ablation (E3) now switches off v1 and v2 parts of a check together.
- What else could be done: ask the architect for verdict.v2 with separate ids for status, route and strength.
- How to change this decision later: m4_verify/v2checks.py, the `_v2()` calls in m4_verify/checks.py.
- Status: done

### D-?: Route check (CR-ROUTE): injection words in the evidence must match the route field   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: When to flag the route of a medicine.
- Options we considered:
  1. Only compare the route with its own evidence span. Pro: simple. Con: misses "route left empty although the doctor said IV".
  2. Compare with the words around the drug (its clause and the route/formulation spans), with the formulation, and with the drug list. Pro: catches missing routes, impossible pairs (tablet + IV) and injection-only drugs given by mouth. Con: more rules, more chances of false alarms.
- What we chose: Option 2.
- Why: A wrong or missing route can harm a patient directly, so we accept a few more review flags.
- What we actually did: v2checks.route_results: flags `route_missing` (route null, IV/IM/SC/injection said), `route_mismatch`, `route_unsupported`, `route_formulation_conflict`, `route_not_allowed` (lexicon note says injection-only or oral-only), `cannot_verify:route` for "other"/"unknown"; all [CR-ROUTE]. Route words: IV, IM, SC, injection, ಇಂಜೆಕ್ಷನ್, ಚುಚ್ಚುಮದ್ದು, ಕುಡಿ-, ನುಂಗ-, ಬಾಯಿಗೆ ...
- What could go wrong / weaknesses: A negated route ("IV ಬೇಡ") still counts as a route word. The lexicon has no route column; routes come from the free-text note. Word list not native-validated.
- What else could be done: a route column in the lexicon; negation-aware route words.
- How to change this decision later: ROUTE_VOCAB in m4_verify/v2rules.py; route_results in m4_verify/v2checks.py.
- Status: done

### D-?: A child's dose is never passed, even when the weight is known   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: What C4 does when the record says the patient is a child.
- Options we considered:
  1. Check the dose against the adult range anyway. Pro: some check. Con: this is exactly the CR-PAEDIATRIC error (a child dose "passing" an adult range).
  2. Flag every dose of a non-adult record as "not checkable", and use weight only when a fetched children's dosing table exists. Pro: safe. Con: every child record goes to a human.
- What we chose: Option 2. Non-adult = infant, child, adolescent and unknown band (the contracts README asks for every non-adult band; the brief named child/infant). Also a record that says "adult" while the conversation has a child word is flagged `age_band_conflict`.
- Why: We have no fetched paediatric table, so any "pass" would be invented safety.
- What we actually did: v2checks.c4_med adds `cannot_verify:paediatric [CR-PAEDIATRIC]` for any dose (any status) and never applies the adult range; the reason says that weight_kg was recorded but no paediatric dosing table has been fetched. C2 re-derives the age band from its span (number + ವರ್ಷ/ತಿಂಗಳು, or a child word, which allows child or infant).
- What could go wrong / weaknesses: Age-band cut-offs are the architect's UNVERIFIED choice. Large review burden for child visits (40 C4 paediatric flags on 328 dev records).
- What else could be done: fetch an official paediatric dosing table (mg/kg) and add a real weight-based check.
- How to change this decision later: NON_ADULT and _paediatric_reason in m4_verify/v2checks.py; age_bands in m4_verify/v2rules.py.
- Status: done

### D-?: Liquid medicines: a dose in ml needs a strength; with a strength, check the mg it gives   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: How to check syrup, suspension and drops doses.
- Options we considered:
  1. Keep the v1 rule (every ml dose "cannot verify"). Pro: safe. Con: never uses the new strength field.
  2. Flag a missing strength; when a strength is stated and supported by its span, turn the dose into mg (5 ml x 120 mg/5 ml = 120 mg) and check the lexicon range. Pro: a real check. Con: depends on correctly reading strength phrases.
- What we chose: Option 2 (also for tablets: "500 mg, two tablets" = 1000 mg).
- Why: The record now holds the strength, so we can check more without guessing.
- What we actually did: `strength_missing [CR-LIQUID-STRENGTH]` when the span states a strength the record lacks; `cannot_verify:liquid_strength` when no strength is anywhere; `span_mismatch [CR-LIQUID-STRENGTH]` when the stored strength is not in its span; `out_of_range` / `exceeds_max_daily` with class CR-LIQUID-STRENGTH for liquids. Equivalent units are accepted (120 mg/5ml = 24 mg/ml). For v2 only, C8 no longer reads "120 mg/5 ml" as a second, conflicting dose.
- What could go wrong / weaknesses: No dev gold record states a strength, so the dev data never tests this (only unit tests do). The paracetamol syrup range is still the adult tablet range (UNVERIFIED).
- What else could be done: fetch label strengths for common syrups into the lexicon.
- How to change this decision later: parse_strengths in m4_verify/v2rules.py; c4_med in m4_verify/v2checks.py.
- Status: done

### D-?: Status check: "prescribed" must not come from a past report or a "don't give"   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: How to check medications[].status against what was said.
- Options we considered:
  1. Trust the status field. Pro: nothing to build. Con: a "do not give ibuprofen" stored as "prescribed" would pass.
  2. Read the evidence for negation, "don't" endings (-ಬೇಡಿ, -ಬಾರದು), past tense (ನಿನ್ನೆ, ಕೊಟ್ಟೆ, ತೆಗೆದುಕೊಂಡೆ), commands (ತೆಗೆದುಕೊಳ್ಳಿ, ಕೊಡಿ) and use the severity mapping note.
- What we chose: Option 2. Given (prescribed, already_taken, continue_existing) versus not given (not_taken, advised_against) = `status_conflict [CR-NEG]`; other mismatches (for example prescribed but a past report) = [MA-STATUS], as docs/severity.md says. Rows that are already_taken / not_taken / advised_against / stopped_early are not range-checked as prescriptions (dose-versus-span is still checked). A prescription whose speaker is patient or caregiver is flagged `speaker_not_prescriber`; advice from a patient or caregiver is flagged unless the next speaker confirms it with a bare "ಹೌದು".
- Why: Status is the new home of the "not taken / advised against" meaning; a flip is as dangerous as a negation flip.
- What we actually did: v2checks._status_result and c3_extra. AFTER the first DEV run (dev-informed, disclosed): a stated regimen without past tense counts as a prescription; a permission question (-ಬಹುದಾ?, -ಲಾ?) answered "ಇಲ್ಲ"/"ಹೌದು" supports advised_against / prescribed; "did you finish? / no" supports stopped_early; ongoing use (ಕುಡಿಯುತ್ತೆ, ತಿನ್ನುತ್ತೆ) supports already_taken; patient advice confirmed by "ಹೌದು" is n/a. These cut clean-record status flags from 130/408 to 1/408. Each addition has positive, minimal-pair and trap tests.
- What could go wrong / weaknesses: The rule list is AI-written and was adjusted after seeing dev; the dev numbers are therefore optimistic. Speaker cannot be checked against transcript.v1 (no roles). Traps: ಕಲಾ (art) would match the "-ಲಾ?" rule.
- What else could be done: a native reviewer for the past-tense and permission forms; speaker roles in the transcript contract.
- How to change this decision later: PAST_VOCAB, AA_VOCAB, DIRECTIVE_VOCAB, ONGOING_RE, PERMISSION_RE in m4_verify/v2rules.py; _status_result in m4_verify/v2checks.py.
- Status: done

### D-?: "As needed" and food timing are checked against the evidence only (MAJOR)   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: How strictly to check as_needed and food_timing.
- Options we considered:
  1. Ignore them. Pro: fewer flags. Con: "only if fever" lost from a record goes unnoticed.
  2. Re-derive the stored value from its span; flag a null value when the drug's own clause says "ಇದ್ದರೆ ಮಾತ್ರ" or "ಊಟದ ನಂತರ".
- What we chose: Option 2, class MA-MED-ATTRIBUTE (docs/severity.md says MAJOR).
- Why: Cheap to check; the severity is fixed by the pre-registered mapping.
- What we actually did: v2checks.c5_extra (`as_needed_missing`, `as_needed_unsupported`, `food_timing_missing`, `food_timing_unsupported`). "ಆದರೆ" (but) and "ಅಂದರೆ" (that is) are traps, not conditions.
- What could go wrong / weaknesses: Food timing said in a later turn is not seen when the record leaves it empty. Not native-validated.
- What else could be done: search the whole conversation, not only the drug's clause.
- How to change this decision later: PRN_VOCAB, food_timings in m4_verify/v2rules.py; c5_extra in m4_verify/v2checks.py.
- Status: done

### D-?: An oral route may be shown by a tablet or syrup word (m1 gold differs from the contracts convention)   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: m1's gold.v2 sets route "oral" with its span on ಮಾತ್ರೆ / ಸಿರಪ್, but contracts/README.md says "route not said: null, even if the formulation implies it". With a strict rule, 284 of 408 clean dev routes were flagged.
- Options we considered:
  1. Keep strict and flag them all. Pro: follows the contract text. Con: a flood of meaningless flags.
  2. Accept "oral" when the span is an oral-only form word (tablet, capsule, syrup, suspension, sachet) and there is no injection word. Pro: clinically sound. Con: departs from the written convention.
- What we chose: Option 2 (dev-informed, disclosed); a tablet word can never support IV/IM/SC.
- Why: Tablets and syrups are taken by mouth; the danger is a wrong injection route, which is still flagged.
- What we actually did: m4_verify/v2checks.c2_extra route branch; test test_c2_oral_route_inferred_from_an_oral_formulation_word. Open question raised for the architect.
- What could go wrong / weaknesses: Rare non-oral tablets (vaginal tablets) would pass.
- What else could be done: the architect settles the convention; m1 or m4 changes to match.
- How to change this decision later: the `rr == "oral"` branch in c2_extra.
- Status: needs human

### D-?: E4-v2: a separate planted-mistake table for the new fields   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: How to measure whether the v2 checks catch mistakes, without mixing with the v1 E4 table.
- Options we considered:
  1. Add the new types to the v1 E4. Pro: one table. Con: changes the v1 numbers; mixes different record versions.
  2. A separate E4-v2 on DEV: records made by contracts/migrate_v1_to_v2.py from the v1 gold record, new fields filled from data/gold_v2 (refused if the two disagree), record level only.
- What we chose: Option 2, with types j route swap, k strength drop, l status flip (given <-> not given), m age band flip; 200 injections per type, seed 20261109, unique mutations with Wilson intervals, review burden on the same clean records.
- Why: Keeps the v1 numbers frozen and reports v2 honestly as its own experiment.
- What we actually did: m4_verify/e4_v2.py, CLI `uv run python -m m4_verify e4-v2`, target `make m4-e4-v2-dev`; output results/m4_verify/dev/e4_v2/. Result on 328 dev records (0 skipped): route swap 200/200 [0.9812, 1.0], status flip 200/200 [0.9812, 1.0], age band flip 80/80 [0.9542, 1.0] (unique); strength drop NOT MEASURABLE (no dev gold has a strength). New-field flags on clean records: status 1/408, speaker 1/408, others 0/408. Both gold folders go through the split guard (load_gold(schema="gold.v2")); a test proves a data/gold_v2 test id is refused without the file being opened.
- What could go wrong / weaknesses: Planted values still point at the original words, so they are easy for rules (an upper bound, not real extractor errors). Rules were adjusted after the first dev run. Synthetic template text; not native-validated.
- What else could be done: run on real m3 v2 output; add a gold strength in m1 templates so "strength drop" becomes measurable.
- How to change this decision later: TYPES_V2, ROUTE_SWAP, STATUS_FLIP, AGE_FLIP in m4_verify/e4_v2.py.
- Status: done

### D-?: The integration adapter sends record.v2 to the real m4 checks   (Phase C / m4_verify / safety-engineer / 2026-11-12)
- What we needed to decide: integration/verifier_adapter.py gave every v2 record one blanket fail-closed flag.
- Options we considered:
  1. Keep the blanket flag. Pro: safe. Con: v2 records can never be auto-acceptable and get no real feedback.
  2. Accept record.v1 and record.v2; anything else still fails closed.
- What we chose: Option 2.
- Why: m4 now validates and checks v2 itself.
- What we actually did: SUPPORTED = ("record.v1", "record.v2"), version integration-adapter-1.1+m4; integration/tests/test_verifier_adapter.py has 3 new v2 tests (they failed before the change) and "record.v3" now tests the fail-closed path.
- What could go wrong / weaknesses: A migrated v1 record has status "unknown", so its v2 classes are "not measurable" yet it can still be auto-acceptable, exactly as its v1 form.
- What else could be done: require a known status before auto-acceptance (a policy choice for m5).
- How to change this decision later: SUPPORTED in integration/verifier_adapter.py.
- Status: done
