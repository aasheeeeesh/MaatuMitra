### D-?: gold.v2 labels come from the templates, field by field   (Phase C / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: How to produce gold.v2 (route, formulation, strength, status, as-needed, food timing, speaker, age band) for all 592 conversations so the scorer can measure CR-ROUTE, CR-PAEDIATRIC and CR-LIQUID-STRENGTH, without guessing from the text.
- Options we considered:
  1. Run the contract migrator (`contracts/migrate_v1_to_v2.py`). Pro: instant and valid. Con: every new field is null and every status is "unknown", so nothing new is measurable.
  2. Read the finished sentences and guess (for example "contains ಸಿರಪ್ so syrup"). Pro: no template edits. Con: that is the same kind of guessing the extractor does; the gold would share its mistakes.
  3. Add metadata to each template item (which words state the status, the form, the route) and let the generator copy it into the gold. Pro: the label is known at generation time, with an exact evidence span. Con: about 46 template edits; the metadata is still our own reading of each sentence.
- What we chose: Option 3.
- Why: The gold must be independent of the tools it grades. Because the template says which words carry the meaning, the evidence span is exact and nothing is searched for afterwards. Rendering is unchanged: the 592 gold.v1 files, transcripts, twins and lexicon are byte-identical (`git diff --stat` on them is empty).
- What we actually did: New metadata keys on medication items (`status` or `status_neg`+`status_pos`, `status_span`, `formulation`, `route`, `as_needed`, `food_timing`, `strength`, each with a span marker; data/templates/README.md). The renderer now allows nested markers and reports the form word of a dose text ("ಮಾತ್ರೆ") as an automatic sub-span. New `m1_data/goldv2.py`; `generate` writes `data/gold_v2/<cid>.json` (592 files, 592/592 valid under `contracts.validate gold.v2`). Rules: status comes from the sentence intent ("ನಿನ್ನೆ ... ಕೊಟ್ಟೆ" = already_taken; ಇಲ್ಲ answer = not_taken; ಬೇಡ / ಬೇಡಿ / ಬಾರದು about a drug = advised_against; the c family "ಮುಗಿಸದೆ ನಿಲ್ಲಿಸಿದೆ" = stopped_early; instructions "ತೆಗೆದುಕೊಳ್ಳಿ" = prescribed; "this is not X" = unknown, no evidence). Formulation is only set when the sentence says it (ಸಿರಪ್, ಮಾತ್ರೆ, Tablet, ಕ್ಯಾಪ್ಸೂಲ್, injection); route follows it (tablet, capsule, syrup = oral, injection = injection_unspecified), and ORS "drink" verbs give oral. Coverage table: results/m1_data/gold_v2_coverage.md. Tests: m1_data/tests/test_gold_v2.py. Regenerate: `uv run python -m m1_data generate` (part of `make data`).
- What could go wrong / weaknesses: Every status and route convention is OUR reading of AI-composed Kannada, not native-validated and not clinician-reviewed (UNVERIFIED). Judgement calls: (a) the c3 question "did you finish all?" answered ಇಲ್ಲ is mapped to stopped_early, though "not finished" could also mean "still taking"; (b) "can I take it?" answered ಹೌದು is mapped to prescribed; (c) a pos form such as "ಕುಡಿಯುತ್ತೆ" (drinks) is mapped to already_taken; (d) route oral from the word ಮಾತ್ರೆ / ಸಿರಪ್ departs from the contract note "route not said = null" - we followed the task instruction and put the form word as evidence. No template says "continue" (continue_existing = 0) and no template states a strength (strength set on 0 of 760 medications; all 40 liquid doses have null strength, which is exactly the CR-LIQUID-STRENGTH case m4 must flag). The frozen family split leaves injection (16) and as_needed (24) only in DEV: the test split has 0 injection and 0 as-needed entries, so CR-ROUTE can only be tested on oral cases there until new test templates are added (needs a new freeze decision).
- What else could be done: A clinician or native speaker fills a review sheet for the status rules; add templates with a spoken strength ("120 mg per 5 ml") and an injection or as-needed family in the test split (new freeze); add "continue the same medicine" templates.
- How to change this decision later: edit the metadata keys in data/templates/*.yaml (rendering is unaffected), then `uv run python -m m1_data generate`; gold.v2 TEST files are locked, so changing them needs `--refreeze` and a decision entry.
- Status: done (conventions UNVERIFIED)

### D-?: Age band is "child" only where the word for child is spoken; otherwise null   (Phase C / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: The brief said "child when the conversation is about ಮಗು, else adult unless stated, with evidence spans". The contract demands an evidence span for every non-null age band.
- Options we considered:
  1. Label everything else "adult". Pro: simple, matches the brief wording. Con: nobody ever says "adult" in the sentences, so there is no honest evidence span; we would invent evidence.
  2. Label the rest "unknown". Pro: no false claim. Con: the contract still requires a span, so it would also be invented.
  3. Label child where ಮಗು... is spoken (span = that word), and null everywhere else.
- What we chose: Option 3.
- Why: A gold label with a made-up evidence span is worse than a missing label. The verifier treats a missing band like an adult default anyway.
- What we actually did: Marker `g1` on the first ಮಗು word of 14 templates. Result: 128 of 592 conversations have age child (80 dev, 48 test); 464 are null; weight_kg is null everywhere (no template states a weight).
- What could go wrong / weaknesses: Template h2 gives a paediatric ml syrup dose without ever saying ಮಗು ("bring to hospital" only), so its age is null although the dose is a child dose; the CR-PAEDIATRIC check cannot use age there. Adults are never labelled, so "adult" recall cannot be measured. Rendered text may not be edited in this task.
- What else could be done: add the word ಮಗು to h2 in a future text refreeze; add explicit adult-age templates ("45 ವರ್ಷದ ...").
- How to change this decision later: put a `[[g1|...]]` marker in a template turn.
- Status: done

### D-?: The test lock is append-only for gold.v2 (264 lines added, none changed)   (Phase C / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: gold.v2 files of the 264 test conversations are new test files, but the lock was frozen with v1 only.
- Options we considered:
  1. `--refreeze` (rebuild the lock). Pro: tidy. Con: rewrites a frozen file; exactly what the lock exists to prevent.
  2. Insert the new lines next to the v1 lines. Pro: sorted. Con: changes the middle of a frozen file.
  3. Append the new lines at the end under their own comment, like the audio lines were.
- What we chose: Option 3.
- Why: Existing lines stay byte-identical, so the audit is one command: `git diff data/splits/test.lock` shows only `+` lines (265: one comment plus 264 hashes).
- What we actually did: `append_v2_lock` in m1_data/generate.py adds a missing line, never edits one, and raises an error if a locked gold.v2 file would change. `split_audio_tail` in m1_data/split.py now treats every appended section (audio, gold.v2) as the tail, so the v1 freeze check is unchanged. Tests: m1_data/tests/test_gold_v2.py (lock lists all v2 test files and no dev file; every old line still present in order, checked against commit a7ba312; editing a v2 test file is caught). `mingw32-make split-lock` prints OK. The generator also keeps audio manifest rows in their existing order after the text rows, so manifest diffs are additions only (592 rows added). One existing test that required a fully sorted manifest was updated to say text rows sorted, audio rows kept after them.
- What could go wrong / weaknesses: If the audio builder appends later, its lines land after the gold.v2 section without a new comment (cosmetic). The lock proves the labels did not change after freezing, not that they are correct.
- What else could be done: a nightly job that compares the lock with git history.
- How to change this decision later: only with `--refreeze` and a new decision entry.
- Status: done
