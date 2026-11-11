### D-?: Remove test-only words from m3 and add a guard test (D-90 finding M3-1)   (Phase B fix pass / m3_extract / nlp-engineer / 2026-11-11)
- What we needed to decide: The integrity audit found words in m3 that occur only in test-family templates (the spoken "if you take" ending ಡ್ರೆ in a regex, ಮುಗಿಸದೆ in the LLM prompt, ಆಂಟಿಬಯಾಟಿಕ್ಗಳು and ಆ in unit tests). What to do, and how to stop it coming back?
- Options we considered:
  1. Keep the words and cite the annotation guide as their source. Pro: no work. Con: the ಡ್ರೆ branch can only ever fire on test text, so it can only help the test score.
  2. Remove them and add an automatic test. Pro: clean and repeatable. Con: tiny loss of coverage for that spoken form.
- What we chose: Option 2.
- Why: A rule that only changes test results is not allowed even if its word has a legitimate source. The test makes the rule permanent.
- What we actually did: Removed the ಡ್ರೆ branch (rules.py), the ಮುಗಿಸದೆ example (llm.py), and reworded 3 unit tests. New m3_extract/tests/test_no_test_only_words.py reads TEMPLATE text only (families that data/splits/split_plan.json maps to test; never a test transcript or test gold), takes away every word that also appears in dev templates, _forms.yaml, DEV gold transcripts or fixtures, and fails if any m3 .py/.yaml file contains what is left, or a fragment found only inside such a word. Shown red by re-adding ಡ್ರೆ, then removed. Run: `uv run pytest m3_extract/tests/test_no_test_only_words.py`.
- What could go wrong / weaknesses: DISCLOSURE: this removal was informed by the auditor having seen the test templates, so it is itself a decision made with test-template knowledge. The test cannot detect indirect influence of sentence frames (D-89). The negation table and annotation guide are deliberately not treated as legitimate sources, which may later flag words that really are shared. Not native-validated.
- What else could be done: Have m7 report the three test-only families (a_fever_cough__f3, c_stopped_early__f1, i_traps__f2) as separate slices.
- How to change this decision later: edit m3_extract/tests/test_no_test_only_words.py (sources) and the files it names.
- Status: done

### D-?: Kannada fixes from the language review: ಆಗಿದ್ದರೆ, fused symptoms, ಪ್ಯಾಕೆಟ್ (D-93)   (Phase B fix pass / m3_extract / nlp-engineer / 2026-11-11)
- What we needed to decide: Which of the Kannada reviewer findings (label ai_simulated_review) to implement in m3.
- Options we considered:
  1. Implement the three high or medium ones with a red test each. Pro: closes real gaps. Con: the new forms are grammar inference, not native-checked.
  2. Wait for a real speaker. Pro: no wrong rule. Con: the gaps stay and the generator already produces these forms.
- What we chose: Option 1.
- Why: The generator positive twin uses ಆಗಿದ್ದರೆ and sachets are spoken ಪ್ಯಾಕೆಟ್; ignoring them is a known miss.
- What we actually did: (a) phrases.yaml FU-FEVER-DOWN now accepts ಆಗಿದ್ದರೆ. (b) rules.py fused_forms builds ಜ್ವರವಿಲ್ಲ, ಕೆಮ್ಮಿಲ್ಲ, ವಾಂತಿಯಿಲ್ಲ, ಜ್ವರವಿದೆ and so on from each symptom (final ು becomes ಿ, glide ವ or ಯ); a fused word that already carries its own ಇಲ್ಲ no longer borrows the next clause predicate. (c) units.py: ಪ್ಯಾಕೆಟ್ = sachet. Red before green: the new tests in test_rules.py failed first (7 failures), then passed.
- What could go wrong / weaknesses: The sandhi rule and ಪ್ಯಾಕೆಟ್ = sachet are UNVERIFIED and not native-validated. ಗುಳಿಗೆ, ಟ್ಯಾಬ್ಲೆಟ್ and inflected ಮಾತ್ರೆಯನ್ನು from the same review are NOT done. A positive fused ಕೆಮ್ಮಿದೆ before a comma may still borrow the next clause.
- What else could be done: a native speaker fills reviews/human_sheets; add the remaining forms.
- How to change this decision later: m3_extract/rules.py (fused_forms), data/phrases.yaml, units.py and their tests.
- Status: partly done

### D-?: Accept both ORS spellings, ಓ.ಆರ್.ಎಸ್ (data) and ಒ.ಆರ್.ಎಸ್ (ASR)   (Phase B fix pass / m3_extract / nlp-engineer / 2026-11-11)
- What we needed to decide: REFREEZE-1 respelled ORS in the shared lexicon with the long vowel ಓ; ASR may still output the short vowel ಒ. What should m3 accept?
- Options we considered:
  1. Only the lexicon spelling. Pro: simple. Con: misses ASR output.
  2. Add the short form as an m3-side variant. Pro: both work; data/ stays untouched. Con: one more file to keep in sync.
- What we chose: Option 2.
- Why: We may not edit data/, and a missed ORS mention is a missed medication.
- What we actually did: m3_extract/data/asr_variants.yaml (ors: ಒ.ಆರ್.ಎಸ್, ಒ ಆರ್ ಎಸ್) loaded by lexicon.py as match_type "variant". test_multi_token_names_longest_match covers both; the xfail marker is removed (0 xfail left).
- What could go wrong / weaknesses: That ASR writes the short vowel is a guess; no ASR has been run. Not native-validated.
- What else could be done: ask m1 to add the form to the shared lexicon variants.
- How to change this decision later: edit m3_extract/data/asr_variants.yaml.
- Status: done

### D-?: Rescore on REFREEZE-1 data, child syrup in ml, honest labels, LLM comparison marked STALE   (Phase B fix pass / m3_extract / nlp-engineer / 2026-11-11)
- What we needed to decide: After the data was regenerated, how to rescore, which version to freeze, what to do with the old rules-vs-LLM table, and how to word results (D-90 M3-2, M3-3).
- Options we considered:
  1. Rerun the LLM comparison. Pro: a current comparison. Con: about 25 minutes for 40 conversations, over the 15-minute limit.
  2. Mark it STALE and keep the old outputs. Pro: honest and cheap. Con: no current LLM number.
- What we chose: Option 2 for the LLM; rescore the rules on all 328 DEV conversations.
- Why: The old LLM outputs were made on data that no longer exists, so scoring them against the new gold would be wrong.
- What we actually did: Rules rerun on DEV. First result: 10 critical errors (the child syrup dose "ಎರಡೂವರೆ ಎಂ.ಎಲ್" = 2.5 ml was unreadable; red test, then ಎರಡೂವರೆ = 2.5 added) plus 9 major (8 template-i5 conversations whose fever condition sits in the drug clause, and 1 follow-up "ವಾಂತಿ ಇದ್ದರೆ ತಕ್ಷಣ ಬನ್ನಿ"); fixed with dev-informed, in-sample additions (an allow_drug_clause flag and one follow-up pattern). Final: dev_tune critical 0/2704, major 0/2704; dev_holdout critical 0/920, major 48/920; all dev critical 0/3624 (pooled, not quoted as accuracy). A new "field" slice gives per-field rows with N and Wilson CIs. Frozen: results/m3_extract/rules_v3_frozen/ (current code and data); rules_v1_frozen stays as the historical unseen-wording estimate (7.6 per 1000, pre-REFREEZE). Old LLM outputs moved to results/m3_extract/llm_STALE_pre_refreeze/. README and failure_analysis.md say: everything is in-sample, 32 of the 40 comparison conversations are in-sample for the rules, no pooled headline. Child turns get ml doses and no adult tablet dose is invented (test_child_turn_without_dose_gets_no_invented_tablet_dose).
- What could go wrong / weaknesses: Wilson CIs treat fields as independent; errors cluster by template, so they are too narrow. The holdout is contaminated. Only gold transcripts, no ASR. ಎರಡೂವರೆ is UNVERIFIED (not fetched). ಒಂದೂವರೆ and other half-numbers are not handled.
- What else could be done: rerun `mingw32-make m3-run-llm-dev` (about 25 min) and read holdout ids only; per-template bootstrap CIs.
- How to change this decision later: re-run `uv run python -m m3_extract run-rules --split dev` and `score`; update m3_extract/failure_analysis.md.
- Status: partly done
