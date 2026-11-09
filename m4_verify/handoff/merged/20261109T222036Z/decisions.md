### D-?: Fail-closed verifier with a rule registry   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: How the safety checker should behave when something goes wrong inside it, and how to switch single checks off for the ablation experiment (E3).
- Options we considered: (1) Catch errors and ignore them: simple, but a crash would silently let a bad record through (unsafe). (2) Stop the whole program on any error: safe but one bad record blocks a batch. (3) Turn any error inside a check into a "flag" for that check and keep going: safe and keeps working. For switching checks off: (a) edit code, (b) a list of checks in a config file.
- What we chose: (3) plus (b). Every check is a plain function in `REGISTRY` (checks.py); the verifier calls it, and ANY exception becomes status "flag" with reason "check_error: ...". A record is "auto-acceptable" only if nothing flags AND at least one check actually passed.
- Why: "Fail-closed" means: when unsure, ask a human. A checker that says "fine" after crashing is the worst outcome. A config list (`disabled: [C3]`) lets E3 remove one check at a time without touching code.
- What we actually did: `m4_verify/verifier.py`, `m4_verify/checks.py`, `m4_verify/config/default.yaml`. Tests: `uv run pytest m4_verify/tests/test_checks.py -k "fail_closed or disable or garbage or malformed"` (forced exception in each of C1..C8 gives flag + check_error + auto_acceptable false).
- What could go wrong / weaknesses: A check that returns "pass" by mistake (a logic bug, not an exception) is not caught by this mechanism; only tests can find that. If ALL checks are disabled the record is never auto-acceptable (by design).
- What else could be done: Run two independent verifiers and require both to pass; property-based tests.
- How to change this decision later: `m4_verify/verifier.py` (the try/except and the auto_acceptable rule).
- Status: done

### D-?: C1 span-exists   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: How to prove that the quoted evidence really is in the transcript.
- Options we considered: (1) Search the span anywhere in the transcript: tolerant, but a span could be "found" in the wrong turn (for example inside a question instead of the answer). (2) Compare the exact slice at the stated offsets after Unicode NFC: strict and simple.
- What we chose: (2), plus a check that the record's `source_transcript_id` equals the transcript's `audio_id`, plus a contract validation of both inputs.
- Why: Offsets decide WHICH clause (and so which negation) the span belongs to; a span at the wrong place could change the meaning.
- What we actually did: `checks.py::c1_span_exists`; tests `test_c1_*`.
- What could go wrong / weaknesses: An extractor that computes offsets on a different normalisation of the text (for example after removing ZWNJ) will be flagged everywhere; that is intended but costs review time.
- What else could be done: Report the nearest matching position to help the reviewer.
- How to change this decision later: `checks.py::c1_span_exists`.
- Status: done

### D-?: C2 span-supports-value, using the verifier's own parsers   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: How to check that a value (drug, dose, symptom) really follows from the quoted words, without trusting the extractor.
- Options we considered: (1) Re-use m3's parser: cheap, but the same bug would hide in both (not independent). (2) Write our own small normaliser, number parser and lexicon matcher: more work, independent. (3) Ask an LLM: not deterministic.
- What we chose: (2): `textnorm.py` (NFC, BOM/zero-width removal, ZWJ/ZWNJ removed for comparison only, Kannada digits to ASCII, `regex` tokeniser), `numbers.py` (digits + Kannada number words), `lexicon.py` (drug variants as token sequences). Free-text advice/follow-up gets "n/a" (meaning cannot be re-derived by rules).
- Why: Independence is the whole point of a safety check. Unknown drugs or symptoms FLAG instead of passing.
- What we actually did: `checks.py::c2_span_supports_value`; tests in test_checks.py and test_text_numbers_lexicon.py.
- What could go wrong / weaknesses: Kannada number words and symptom words were written by an AI agent (UNVERIFIED, not native-validated). Missing spoken variants cause false flags (safe direction, but review burden). Advice text is not checked for meaning.
- What else could be done: Native-speaker review of the number/symptom lists; English-Kannada advice paraphrase checks.
- How to change this decision later: `numbers.py`, `lexicon.py` (SYMPTOMS, UNIT_FORMS), `checks.py`.
- Status: done (word lists UNVERIFIED)

### D-?: C3 negation-consistency with independent, hand-coded rules   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: How to decide whether the words around a span say "not", and compare that with the record's `negated` / `present` field.
- Options we considered: (1) Read the shared table `.claude/skills/kannada-nlp/negation_table.yaml` (same as m3): a mistake in the table would then be invisible. (2) Hand-code our own rules from the brief and grammar knowledge: independent. (3) A statistical model: needs labelled Kannada data we do not have.
- What we chose: (2). Whole-word cues (ಇಲ್ಲ, ಇಲ್ಲಾ, ಅಲ್ಲ, ಬೇಡ, ಬೇಡಿ, ಬಾರದು, ಕೂಡದು), token-final suffixes (-ಿಲ್ಲ, -ುದಿಲ್ಲ, consonant+ದಿದ್ದರೆ, fused -ಬಾರದು/-ಕೂಡದು/-ಬೇಡ(ಿ)), -ದೆ only on a verb-stem list, soft casual -ಲ್ಲ, ಯಾವುದೇ...ಇಲ್ಲ, English no/not/never. Scope = the clause (split at punctuation and ಆದರೆ/ಮತ್ತು/ಹಾಗೂ/ಆದ್ದರಿಂದ). Cross-turn: a turn whose FIRST clause is only ಇಲ್ಲ/ಇಲ್ಲಾ/ಹೌದು answers the previous turn's question clause(s). Soft cues count as negation (conservative) and also raise C8.
- Why: Matching on whole tokens (never substrings) avoids the classic trap ಇಲ್ಲಿ (here) containing ಇಲ್ಲ. "First clause" (not "whole turn") was chosen because answers like "ಇಲ್ಲ, ಅವನು ಮಲಗಿದ್ದ." are common; this is a documented extension of the brief.
- What we actually did: `negation.py`; 125+ tests in `tests/test_negation.py` (every cue: positive, minimal-pair twin, trap; clause scope; cross-turn); audit in `negation_audit.md`.
- What could go wrong / weaknesses: Not native-validated. Coordination ("A ಮತ್ತು B ಬೇಡ") is handled by a heuristic (bare item inherits the negation and C8 flags it). Questions without "?" (ASR text often has no punctuation) are not recognised as questions. Double negation fused with quotatives is missed (audit line 40).
- What else could be done: Native-speaker review of every rule; a held-out real-text audit; real spoken transcripts.
- How to change this decision later: `negation.py` (rule tables at the top) and its tests.
- Status: partly done (rules are hypotheses; needs human)

### D-?: Negation rules changed after the real-text audit   (Phase B / m4_verify / safety-engineer / 2026-11-10)
- What we needed to decide: What to do with the errors found when running the rules on a real Kannada Wikipedia article and a news article.
- Options we considered: (1) Keep the brief's starting rules unchanged and only report errors. (2) Fix clear, narrow errors with tests, and report the rest honestly.
- What we chose: (2). Changes: ಇಲ್ಲವೇ/ಇಲ್ಲವೆ now mean "or" (clause split) unless "?" follows (was a frequent false positive); new strong rules S-VALLA (ರೋಗವಲ್ಲ, trap ಮಾತ್ರವಲ್ಲ), S-DIRU (ಬಾರದಿರುವುದು), S-ILLA-FUSED (ಮಾರ್ಗವಿಲ್ಲದೆ), S-DANTE (ಬರದಂತೆ), V-AAGADE (ಸಾಧ್ಯವಾಗದೆ), V-ISADE (ಗಣಿಸದೆ); ಇಲ್ಲದ/ಇಲ್ಲದೆ became SOFT cues.
- Why: The "or" reading of ಇಲ್ಲವೇ would have marked many harmless sentences as negated; the missed fused forms are real negations.
- What we actually did: `negation.py`, new test rows in `tests/test_negation.py`, `negation_audit.md`, `m4_verify/audit/`.
- What could go wrong / weaknesses: The fixes were designed on the same 52 sentences they were measured on, so the after-fix numbers are optimistic. Formal written Kannada differs from spoken Kannada.
- What else could be done: Audit a second, unseen article and real conversational transcripts.
- How to change this decision later: `negation.py`; re-run `mingw32-make m4-audit`.
- Status: done (needs human re-check)

### D-?: C4 dose-range: blank lexicon range is a flag (fail-closed)   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: What to do when the lexicon has no verified dose range, when the unit is not in milligrams, and what counts as "unusual".
- Options we considered: (1) Blank range -> "n/a" (no review cost, but an unchecked dose can be auto-accepted). (2) Blank range -> "flag: no verified range" (safe, but every such medication needs a human). (3) Invent ranges: not allowed (no source).
- What we chose: (2), also for non-mass units (tablet, ml, sachet...), because lexicon ranges are in mg. Also: dose and unit must match the span; unit must be in the allowed set; dose x frequency must not exceed max daily; a dose inside the range but above the listed strengths passes with an "unusual" note (soft).
- Why: A wrong dose is a CRITICAL error. Cost we accept: with `data/lexicon/drugs.csv`, 12 of 34 rows have a blank range, so every dosed record for those drugs goes to a human (review burden).
- What we actually did: `checks.py::c4_dose_range`; config `blank_range_fails_closed: true`; tests `test_c4_*`.
- What could go wrong / weaknesses: The lexicon has no "allowed units" column, so the allowed-unit list is a config default (contract gap, open_questions). The m1 lexicon gives paracetamol `1000-1000` mg, which flags a normal 500 mg tablet (lexicon question for m1/human).
- What else could be done: Add per-drug unit and per-dose-form columns to the lexicon; separate paediatric ranges.
- How to change this decision later: `config/default.yaml` (`blank_range_fails_closed`, `allowed_units`, `allowed_units_by_drug`), `checks.py`.
- Status: done

### D-?: C5 frequency and duration parse   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: How to check "times per day" and "number of days" against the span.
- Options we considered: (1) Any number in the span counts. (2) Parse phrases: number + ಬಾರಿ/ಸಲ with a per-day word (ದಿನಕ್ಕೆ), ಒಮ್ಮೆ, OD/BD/TDS; number + ದಿನ / ವಾರ (x7).
- What we chose: (2). Times-of-day words (ಬೆಳಿಗ್ಗೆ/ರಾತ್ರಿ) are NOT turned into a frequency: a record frequency based on them flags.
- Why: "ಮೂರು ದಿನದಿಂದ" (since three days) or "ದಿನಕ್ಕೆ" (per day) must not be read as a 3-day course.
- What we actually did: `lexicon.py::parse_frequencies/parse_durations`, `checks.py::c5_freq_duration`; tests.
- What could go wrong / weaknesses: Phrase list is AI-written, UNVERIFIED; "ವಾರಕ್ಕೆ ಎರಡು ಬಾರಿ" (twice a week) flags as "not per day".
- What else could be done: A native-reviewed phrase table from real prescriptions.
- How to change this decision later: `lexicon.py` (FREQ_MARK, PER_DAY, DAY_WORDS...).
- Status: done (phrases UNVERIFIED)

### D-?: C6 unsupported additions, omissions and the patient-link blind spot   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: How to catch values nobody said, drugs that were said but left out, and a record attached to the wrong patient.
- Options we considered: For patient links: (1) ignore; (2) check against an "encounter index" (which audio belongs to which patient) when one is given; (3) change the transcript contract to carry patient_ref (contract change, not ours to make).
- What we chose: Every drug, number and symptom in a value must occur in its span; English numbers/drugs in advice text must occur in the span; a lexicon drug said in the transcript but missing from the record is a "possible omission" (MAJOR) unless it sits inside an advice/follow-up span; patient link: option (2), and "n/a: blind spot" without an index.
- Why: transcript.v1 has no patient field, so text alone cannot detect a wrong patient. E4 shows it: 0/200 wrong-patient injections caught without the index, 200/200 with it.
- What we actually did: `checks.py::c6_unsupported`; CLI `--encounter-index`; tests `test_c6_*`; contract request in open_questions.md.
- What could go wrong / weaknesses: Symptom omissions are not checked (questions mention symptoms that are not findings). The index must come from a trusted source (m5 encounter table).
- What else could be done: m5 passes the encounter index automatically.
- How to change this decision later: `checks.py::c6_unsupported`.
- Status: done (patient link needs integration)

### D-?: C7 ASR risk: threshold from DEV only, n/a when no confidences   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: How to warn about words the speech recogniser was unsure of, and what to do when it gives no confidence.
- Options we considered: (1) Flag every record with no confidence (huge review burden, no information). (2) Mark "n/a" and record it as a limitation. For the cutoff: (a) pick a number by hand; (b) tune it on DEV ASR output only.
- What we chose: (2) and (b). Critical words = drug, number, unit, negation cue. A second transcript (another ASR model or run), when given, is compared on drugs, doses, numbers, negation cues and bare answers. The cutoff 0.6 in `config/default.yaml` is an UNTUNED PLACEHOLDER until m2 produces DEV output; `python -m m4_verify tune-c7` does the tuning and refuses test paths.
- Why: Tuning on test data would leak (PROJECT_BRIEF 6.5).
- What we actually did: `checks.py::c7_asr_risk`, `tune_c7.py`, tests `test_c7_*`, `test_tune_c7.py`.
- What could go wrong / weaknesses: Word confidences from Whisper-style models are often badly calibrated. C7 is the only check that can see an ASR-dropped negation, and only partly.
- What else could be done: Align the two transcripts word by word instead of comparing counts.
- How to change this decision later: `config/default.yaml` (`c7_conf_threshold`, `c7_threshold_status`), `checks.py`.
- Status: partly done (threshold UNTUNED)

### D-?: C8 ambiguity always flags   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: Which unclear situations should go to a human even when C3 agrees.
- Options we considered: (1) Let C3 decide everything. (2) A separate check that always flags known ambiguous patterns.
- What we chose: (2): soft cue; two cues in one clause; bare ಇಲ್ಲ with no resolvable question; bare answer after several questions or after a negative question; span inside a question nobody answered with yes/no; negation possibly shared across "A ಮತ್ತು B ಬೇಡ"; conflicting dose/frequency/duration values in one clause.
- Why: In these cases even a careful rule can be wrong; asking a human is cheaper than a negation flip.
- What we actually did: `checks.py::c8_ambiguity`, ambiguity notes from `negation.py`; tests `test_c8_*`.
- What could go wrong / weaknesses: Adds review burden on real conversations (0/18 fixture fields flagged, but fixtures are few and clean).
- What else could be done: Measure C8's burden on m1 DEV data and narrow the rules that fire most.
- How to change this decision later: `checks.py::c8_ambiguity`, `negation.py`.
- Status: done

### D-?: Turn structure comes from newlines in the transcript text   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: Cross-turn negation needs to know where turns start, but transcript.v1 has no turn list.
- Options we considered: (1) Ask for a contract change (turn list in transcript.v1). (2) Use the existing convention: conversation text = turns joined by "\n" (gold.v1, fixtures/build_fixtures.py, contracts/validate.py::conversation_text).
- What we chose: (2), and logged (1) as an open question.
- Why: No contract change is needed now; gold and gold-style transcripts already follow it.
- What we actually did: `negation.py::_split_clauses` splits turns on "\n".
- What could go wrong / weaknesses: Real ASR output on one audio file has no newlines: then the whole conversation is one turn and cross-turn answers are not resolved (a bare ಇಲ್ಲ inside one long line is simply a negation cue in its clause).
- What else could be done: Speaker diarisation in m2, or turn timestamps in transcript.v2.
- How to change this decision later: `negation.py` and a contract bump by the architect.
- Status: done (contract gap open)

### D-?: E4 planted-mistake generator design   (Phase B / m4_verify / safety-engineer / 2026-11-09)
- What we needed to decide: How to create >= 200 planted mistakes per type, honestly, when only 6 fixture conversations exist.
- Options we considered: (1) Only unique mutations (few per type). (2) 200 per type with repeats, reported with the number of UNIQUE mutations next to it. (3) Wait for m1 DEV gold.
- What we chose: (2) now, with a configurable gold source so it re-runs on m1 DEV gold (DEV only; any path with "test" is refused). Seed 20261109. Every injection is logged (id, type, field_path, before, after, note, unique_key). Record level tests the verifier; transcript level edits the transcript and rebuilds the record as a faithful extractor would, then is scored text-only and with a second (clean) transcript.
- Why: Repeating a mutation 50 times is not 50 independent trials; Wilson CIs are therefore also reported on unique mutations.
- What we actually did: `planted.py`, `evaluate.py`, `results/m4_verify/e4/`.
- What could go wrong / weaknesses: Transcript-level edits use the verifier's own cue finder to locate what to delete (some circularity in where errors are planted). Word confidences were not simulated (inventing them would be circular), so C7's confidence path is not evaluated by E4.
- What else could be done: Re-run on m1 DEV gold (`mingw32-make m4-e4-data` after DEV gold exists, with `--gold-dir`); add natural ASR errors from m2.
- How to change this decision later: `planted.py` (TYPES, value lists), `evaluate.py`.
- Status: done on fixtures; DEV re-run pending
