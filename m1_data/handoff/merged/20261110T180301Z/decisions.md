### D-?: Child doses rewritten: syrup in ml or no dose   (Phase B / m1_data / data-scientist / 2026-11-10)
- What we needed to decide: Templates a3, e8, h2, h3, i5 showed a child ("ಮಗುವಿಗೆ") getting an adult tablet dose (1000 mg, 2 tablets, 400 mg). How do we fix the text and the gold labels?
- Options we considered:
  1. Give the child turn no dose at all. Pro: never invents a number. Con: the paediatric dose case is no longer tested.
  2. Use a paediatric syrup in ml (the Kannada reviewer's wording, "ಸಿರಪ್ ಐದು ಎಂ.ಎಲ್"). Pro: realistic, tests the ml unit. Con: the ml volumes (2.5, 5, 7.5, 10) are synthetic and NOT checked against an age band.
  3. Delete the child templates. Pro: simple. Con: loses the case where dosing danger is highest.
- What we chose: a mix. a3 (caregiver says what was given) has no dose ("Paracetamol ಸಿರಪ್ ಕೊಟ್ಟೆ"). e8, h2, h3, i5 use paracetamol syrup in ml with verb ಕೊಡಿ. New slot kind `dose: child_syrup` (only ml) separate from `dose: given` (adult, never ml).
- Why: A child must never get an adult dose in our own gold labels. We did not add an age band because we have no fetched age table and must not invent doses.
- What we actually did: data/templates/{a,e,h,i}_*.yaml, m1_data/generate.py, render.py, kn.py (ML_WORDS), lexicon.py/lexicon_source.py (syrup_ml hint), split.py (ml combinations alternate separately so both splits have two). Test: m1_data/tests/test_refreeze1.py. Per changed template (conversations): a3 dev 8, e8 dev 16, i5 dev 8, h2 test 8, h3 test 8, e2 test 16. Zinc 20 mg dispersible tablet in e7 stays (it is the paediatric dose per the WHO page the reviewer fetched).
- What could go wrong / weaknesses: ml volumes are synthetic and not age-checked (UNVERIFIED, not dosing advice). Kannada wording is ai_simulated_review only, not native-validated. m4 has no verified ml range, so it will flag these (intended).
- What else could be done: a fetched paediatric table (IAP or NLEM) so age band and ml can be paired and checked.
- How to change this decision later: data/templates, Drug.syrup_ml hint in m1_data/lexicon_source.py, then `uv run python -m m1_data generate --refreeze` (only before the first test run).
- Status: done (needs human review of the Kannada)

### D-?: Lexicon corrections from the clinical review   (Phase B / m1_data / data-scientist / 2026-11-10)
- What we needed to decide: Which lexicon rows to change after the simulated clinical review (D-91).
- Options we considered: (1) change only rows backed by a page the reviewer fetched; (2) change everything the reviewer suggested including unfetched values. We chose (1).
- What we chose: paracetamol 500-1000 mg, max daily 4000 (NHS page); ondansetron 4-24; metformin 500-1000; ibuprofen 200-800 (openFDA OTC + Rx labels); ORS note: unit is sachet or ml, never mg; iron-folic acid note: iron in mg, folic acid in mcg; alias "625" added to amoxicillin-clavulanate; alias "levo" and Kannada ಲೇವೋ removed from levofloxacin; ORS Kannada spelling now ಓ.ಆರ್.ಎಸ್ (long O). Metronidazole, cotrimoxazole and NLEM rows unchanged and still UNVERIFIED.
- Why: no dose range without a fetched source. The CSV has no unit column (other modules read it), so ORS and iron units are recorded in verified_by, not invented as numbers.
- What we actually did: m1_data/lexicon_source.py, lexicon.py; `uv run --extra data python -m m1_data build-lexicon`; data/lexicon/drugs.csv (8 rows changed). Numeric alias "625" is kept out of generated speech.
- What could go wrong / weaknesses: Ranges come from US/UK pages, not from NLEM (fetch failed). 1000 mg metformin single dose is a derivation. "625" may be read by m3 as a dose number. The reviewer is simulated.
- What else could be done: real pharmacist fills the clinical sheet; add a unit column through a contract change.
- How to change this decision later: m1_data/lexicon_source.py then rebuild lexicon and refreeze only before a test run.
- Status: partly done (human check pending)

### D-?: Shared negation table v2   (Phase B / m1_data / data-scientist / 2026-11-10)
- What we needed to decide: Apply the D-93 table changes inside the same refreeze, because the table is checked during generation.
- Options we considered: (1) edit now, inside REFREEZE-1; (2) edit later and refreeze again. Option 2 would change the test lock twice.
- What we chose: Option 1. Version 1 -> 2: soft cue now needs a bare consonant before -ಲ್ಲ (ಬೆಲ್ಲ jaggery no longer matches; also in exclude list and a trap entry NEG-T14); new soft cue NEG-S07 for the negative question -ಲ್ವಾ (marked generate: false, ಅಲ್ವಾ stays a trap); ಆಗ added to the -ದೆ stems (ಆಗದೆ); clause splitter no longer splits at a dot directly followed by a letter (ಎಂ.ಜಿ).
- Why: fixes over-flagging and missed cues; traps must stay at zero false triggers.
- What we actually did: .claude/skills/kannada-nlp/negation_table.yaml; m1_data/coverage.py skips `generate: false` entries; tests in test_refreeze1.py (every trap gives zero triggers). Form "ಕೊಡುವುದು ಬೇಡಿ" removed from templates (ungrammatical); the whole-token cue NEG-W05 is kept alive by the spaced artefact "ಕೊಡ ಬೇಡಿ".
- What could go wrong / weaknesses: not native-validated. m3 and m4 may need updates (m3 reads the table, new type use is soft_suffix). The full-stop rule fails for a full stop directly followed by a letter.
- What else could be done: native reviewer rules on negative questions and their answers.
- How to change this decision later: edit the table, bump version, add a decision.
- Status: done

### D-?: Three new CRITICAL severity classes   (Phase B / m1_data / data-scientist / 2026-11-10)
- What we needed to decide: Add the clinical reviewer's missing critical classes.
- Options we considered: add now (before any test run) or leave out. Adding after a test run would be goalpost moving.
- What we chose: add CR-ROUTE (wrong route), CR-PAEDIATRIC (child or weight-based dose treated as adult), CR-LIQUID-STRENGTH (mg per 5 ml or ml errors).
- Why: these are real dosing dangers not covered by CR-DOSE.
- What we actually did: docs/severity.md, marked "added before any test run, REFREEZE-1 (D-91)". Test in test_refreeze1.py.
- What could go wrong / weaknesses: from a simulated clinician; m7/m4 must implement the classes.
- What else could be done: real clinician review.
- How to change this decision later: docs/severity.md plus a new decision.
- Status: done

### D-?: Annotation guide no longer prints test-only words   (Phase B / m1_data / data-scientist / 2026-11-10)
- What we needed to decide: The guide printed 8 words found only in test templates (integrity finding M1-6). Builders read the guide, so it leaked test wording.
- Options we considered: mark them as test words (still leaks) or rewrite with dev-family examples only.
- What we chose: rewrite; plus a rule and a test.
- Why: a leak channel should be closed by construction.
- What we actually did: docs/annotation_guide.md rewritten examples (also ಓ.ಆರ್.ಎಸ್, ml rule, spoken variants); tests test_guide_has_no_test_only_vocabulary (computed from the current split plan) and test_guide_does_not_print_the_eight_leaked_words.
- What could go wrong / weaknesses: the test covers template vocabulary only, not wording of other docs. Optional ಸಲ for "times" was NOT generated (changing it would reshuffle all data); recorded as open.
- What else could be done: apply the same check to other docs builders read.
- How to change this decision later: docs/annotation_guide.md and m1_data/tests/test_refreeze1.py.
- Status: done

### D-?: REFREEZE-1 carried out   (Phase B / m1_data / data-scientist / 2026-11-10)
- What we needed to decide: Regenerate and relock the frozen test split once (D-91).
- Options we considered: see D-91.
- What we chose: one `--refreeze` after all fixes. Confirmed first that results/test_access_log.md does not exist (no test run ever).
- Why: fixes unsafe child doses before any evaluation.
- What we actually did: generator version m1-data-1.0.0 -> m1-data-1.1.0; `uv run python -m m1_data generate --refreeze`. Old test.lock sha256 05abfb0e15abade0ab184e90b4f023802271cee1aa198c82d36f806e67ac8403; new ef214fecd70e748f2dc7725d4e1259ec8c4396fad85ad19c15d74476fa7e9e59 (532 lines). Counts unchanged: 592 conversations, dev 328, test 264, test medication entries 352, twins dev 224 / test 193. Second plain run identical. No family or dosed combination overlap (tests pass). Added drug-conflict rule (quinolone/doxycycline with zinc/iron, two NSAIDs or steroids not co-dosed) and e2 patient line "ಎರಡೂ ಔಷಧಿ ಒಟ್ಟಿಗೆ ಕೊಡಬಹುದಾ?"; positive twins of h5, e7, h2 changed to sensible sentences.
- What could go wrong / weaknesses: still looks like moving the goalposts; the old lock is in git history. Test paracetamol ml volumes are only 5 and 7.5.
- What else could be done: none before first eval-test.
- How to change this decision later: never after the first make eval-test.
- Status: done (orchestrator commits)
