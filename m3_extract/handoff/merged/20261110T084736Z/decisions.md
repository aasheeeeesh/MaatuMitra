### D-?: Rules first: a hand-written rules pipeline is the MAIN extractor   (Phase B / m3_extract / nlp-engineer / 2026-11-10)
- What we needed to decide: How to turn a Kannada transcript into a structured record (symptoms, medicines with dose / frequency / duration, advice, follow-up) where every value points at the words that support it.
- Options we considered:
  1. Hand-written rules with word lists. Pro: same input always gives the same output, every decision can be logged and explained, runs in milliseconds, $0. Con: only knows the words and patterns we wrote, so new wording is missed; needs Kannada knowledge we do not have natively.
  2. A local LLM as the main extractor. Pro: copes with new wording. Con: slow on our laptop (30-60 s per conversation), can invent values, harder to explain; must still be checked.
  3. Train a small tagger. Con: we have no real labelled Kannada clinical data; training on our own synthetic templates would learn the templates.
- What we chose: Option 1 as MAIN (the brief requires it); option 2 as the E2 comparison.
- Why: A safety experiment needs a predictable extractor whose mistakes we can list and reproduce. Missing something (an omission) is visible to the reviewer; inventing something is worse.
- What we actually did: `m3_extract/rules.py` with `textnorm.py`, `lexicon.py`, `numbers.py`, `units.py`, `negation.py`, word lists in `m3_extract/data/`. Every record goes through the evidence check and record.v1 before it is saved. Run: `mingw32-make m3-run-dev`. Output: `results/m3_extract/rules/*.json`, logs in `results/m3_extract/rules/logs/`.
- What could go wrong / weaknesses: The rules were written by reading synthetic template conversations; they will miss real speech, other dialects and wording not in the lists. Kannada lists are not native-validated.
- What else could be done: Grow the lists with real reviewers; add morphology (inflected forms like ಜ್ವರವಿದೆ); use the LLM only to PROPOSE items that the rules then verify.
- How to change this decision later: `m3_extract/rules.py`, `m3_extract/data/*.yaml`.
- Status: done

### D-?: Keep a "dev_holdout" inside DEV to measure over-fitting of hand-written rules   (Phase B / m3_extract / nlp-engineer / 2026-11-10)
- What we needed to decide: How to give an honest dev score for rules that were written while looking at dev conversations.
- Options we considered:
  1. Report the score on all of dev. Pro: simple. Con: the rules were written from these examples, so the score is "in-sample" and too optimistic.
  2. Before writing any rule, set aside some dev templates and never look at them while writing rules. Pro: an honest estimate of how the rules handle unseen wording, without touching the frozen test split. Con: fewer examples to learn from; still synthetic.
  3. Use the test split. Not allowed (frozen, section 6.5).
- What we chose: Option 2. One template per category, chosen with `random.Random(20261110)`: a3 b4 c5 d2 e6 f3 g5 h6 i3 (88 conversations). The other 240 are "dev_tune".
- Why: Hand-written rules over-fit easily; this exposes it cheaply.
- What we actually did: `HOLDOUT_TEMPLATES` in `m3_extract/splits.py`; every score row in `results/m3_extract/dev_scores.csv` has a `dev_part` slice. The holdout was first scored on 2026-11-10 13:32 (+05:30) with frozen rules v1.
- What could go wrong / weaknesses: Holdout templates share vocabulary and sentence styles with dev_tune because one generator wrote all of them, so even the holdout score is optimistic for real speech.
- What else could be done: Real recorded conversations; a second holdout created later by m1.
- How to change this decision later: `m3_extract/splits.py` (`HOLDOUT_TEMPLATES`).
- Status: done

### D-?: Rules v2: fix "bare ಇಲ್ಲ answers the whole question sentence" (found on dev_holdout)   (Phase B / m3_extract / nlp-engineer / 2026-11-10)
- What we needed to decide: What to do after the first holdout score showed 7 CRITICAL negation flips, all in template c5: "ನನಗೆ ಜ್ವರ ಇದೆ, ಮನೆಯಲ್ಲಿ ಇದ್ದ X ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ? / ಇಲ್ಲ." ("I have fever, can I take X? / No."). Rules v1 applied "No" to fever too, recording fever as ABSENT.
- Options we considered:
  1. Leave the bug and only report it. Pro: the holdout stays clean. Con: the MAIN pipeline would knowingly keep a negation-flip bug that downstream modules use.
  2. Fix it, keep the v1 scores as the honest holdout estimate, and label the v2 holdout score as contaminated. Pro: better pipeline and an honest record. Con: the v2 holdout number is no longer an unseen-data estimate.
- What we chose: Option 2.
- Why: A negation flip is the most dangerous error class; the fix is general (a comma clause ending in ಇದೆ-type words is a statement, not part of the question), not specific to c5.
- What we actually did: `_is_question` in `m3_extract/rules.py`; tests `test_statement_clause_inside_question_sentence_is_not_answered` and `test_listed_nouns_in_question_stay_question`. v1 scores: `results/m3_extract/rules_v1_frozen/`. Version bumped to 0.2.0. Missed advice / follow-up phrases on the holdout were NOT added (that would just copy the holdout).
- What could go wrong / weaknesses: Comma clauses ending in other statement verbs (not in our short list) are still treated as part of a question.
- What else could be done: Use punctuation plus a list of question clitics (-ಆ, -ಾ?) per clause; ask a native speaker.
- How to change this decision later: `EXIST_WORDS` and `_is_question` in `m3_extract/rules.py`.
- Status: done

### D-?: Negation flag uses ONLY the shared table, with three documented interpretations   (Phase B / m3_extract / nlp-engineer / 2026-11-10)
- What we needed to decide: How the rules pipeline decides "negated / absent", given that m4_verify must check it independently.
- Options we considered:
  1. Read `.claude/skills/kannada-nlp/negation_table.yaml` and apply it per token and per clause. Pro: one shared, reviewable list; m4 writes its own rules so the check is not circular. Con: inherits the table's gaps.
  2. Write m3's own extra cues. Con: two hidden rule sets; against the brief.
- What we chose: Option 1, with three interpretations: (a) NEG-S03 "-ದಿದ್ದರೆ (if not)" marks a CONDITIONAL, it never sets `negated` on an item; (b) a soft cue (casual -ಲ್ಲ) on a stem that is not in `verb_stems` still negates but is logged as `soft_negation`; (c) the punctuation splitter skips abbreviation dots (ಎಂ.ಜಿ, ಒ.ಆರ್.ಎಸ್).
- Why: (a) "if the fever does not come down, come back" does not deny any symptom; (b) treating a probable "not" as "yes" is the more dangerous mistake; (c) otherwise "1000 ಎಂ.ಜಿ ಬೇಡ" would put the dose and the "no" in different clauses.
- What we actually did: `m3_extract/negation.py`; tests in `m3_extract/tests/test_negation.py` (15 cue / minimal-pair twins, 9 traps, clause scope, cross-turn). No import of m4 code.
- What could go wrong / weaknesses: Every table entry is a hypothesis (not native-validated). ಇಲ್ಲದೆ ("without") is not in the table at all.
- What else could be done: Add `type: conditional_negative` and an abbreviation rule to the table (open question).
- How to change this decision later: the table (with a decision entry) and `m3_extract/negation.py`.
- Status: done

### D-?: Evidence = smallest supporting span; the evidence check rejects the whole record   (Phase B / m3_extract / nlp-engineer / 2026-11-10)
- What we needed to decide: What span to quote for each value and what to do when a quote is wrong.
- Options we considered:
  1. Quote the whole sentence. Pro: easy. Con: a reviewer cannot see which words support the dose; a wrong value hides inside a long quote.
  2. Quote the smallest span: drug name through the last dose / frequency / duration word, plus the "not" word if in the same clause; for a cross-turn answer, the item in the QUESTION turn (annotation guide). Pro: precise. Con: more code.
  3. On a failing quote, repair it (fuzzy search). Con: hides model or code errors.
- What we chose: Option 2, and reject (never repair) any record with a failing span.
- Why: The verifier (m4) and the human reviewer rely on spans; a record with one fake quote cannot be trusted at all.
- What we actually did: `m3_extract/evidence.py` (`check_evidence`, `evidence_for`, `locate_quote`). Rejected records go to `results/m3_extract/<pipeline>/rejected/` with reasons and are scored as empty records. Tests: `test_forged_span_text_is_rejected`, `test_forged_offsets_are_rejected`, `test_forged_quote_rejects_whole_record`.
- What could go wrong / weaknesses: Our spans start at the drug name, gold spans sometimes start earlier (ಇದು ...); we report overlap with gold spans, not exact equality (`evidence_overlap_dev.csv`).
- What else could be done: Score span precision / recall in characters.
- How to change this decision later: `m3_extract/evidence.py`, span logic in `m3_extract/rules.py`.
- Status: done

### D-?: Scoring: what a "field" is and how advice is classed   (Phase B / m3_extract / nlp-engineer / 2026-11-10)
- What we needed to decide: How to count fields and errors for "errors per 1,000 fields", and which class to give advice errors that docs/severity.md does not list.
- Options we considered:
  1. Medication 6 fields, symptom 2, advice 2, follow-up 1; a missed item = 1 error; an extra item = +1 field and 1 error. Pro: simple, every gold value counted once. Con: a missed medication with 5 values counts as 1 error.
  2. Count every field of a missed item as an error. Con: double counts (severity.md: a missed drug is ONE major error).
- What we chose: Option 1. Missed / extra advice and follow-up are MAJOR; advice text that differs from gold is MA-WORDING-UNJUDGED (MAJOR) because "same meaning" cannot be judged by code (severity rule 5). patient_ref / encounter_type are supplied context, not extracted, so not scored.
- Why: Follows the "one field, one class" rule and the "when unsure, MAJOR" rule.
- What we actually did: `m3_extract/scoring.py` (Wilson CI with hand-checked values 0/50 -> [0, 0.0713], 3/50 -> [0.0206, 0.1622] in `tests/test_scoring.py`). Outputs `results/m3_extract/dev_scores.csv` (sliced by dev part, category, code_switched, has_negation, cross_turn_negation).
- What could go wrong / weaknesses: Other modules may count fields differently (open question). The LLM writes its own English glosses, so it gets many MA-WORDING-UNJUDGED errors that a human might call "same meaning".
- What else could be done: Human judgement of advice wording on a sample; a shared scorer in m7_eval.
- How to change this decision later: `m3_extract/scoring.py`.
- Status: done (needs architect / m7 confirmation)

### D-?: LLM comparison (E2) with qwen3:4b-instruct on a seeded 40-conversation dev subset   (Phase B / m3_extract / nlp-engineer / 2026-11-10)
- What we needed to decide: Which local open LLM to compare with the rules, how to make it reproducible, and on how many conversations.
- Options we considered:
  1. qwen3:4b-instruct through Ollama (already installed, 2.5 GB Q4_K_M). Pro: $0, local, supports JSON-schema output. Con: does not fit fully in the 4 GB GPU (Ollama ran it 45% CPU / 55% GPU), so it is slow; a 4B model is weak at Kannada.
  2. A larger model (7-8B). Con: would not fit in 4 GB VRAM; much slower on CPU; extra download on a nearly full disk.
  3. A Hugging Face transformers model. Con: new heavy dependency, same memory limits.
- What we chose: Option 1. Revision = Ollama digest 0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0; temperature 0, top_k 1, seed 20261110, num_ctx 8192, max 1,536 output tokens; JSON schema in Ollama `format` with drug and symptom names as fixed lists; 3 few-shot examples from fixtures (never dev or test). The model returns quotes; our code finds them verbatim and runs the same evidence check as the rules. Subset: `random.Random(20261110).sample` of 40 DEV conversations (`results/m3_extract/llm_subset.txt`, asked for by the orchestrator to save time); the rules are scored on the same 40.
- Why: It is the only model that fits our hardware and budget today. The same subset, same vocabulary and same evidence check make the comparison fair.
- What we actually did: `m3_extract/llm.py`; ran `mingw32-make m3-run-llm-dev` on 2026-11-10 (server 127.0.0.1:11434). Results: `results/m3_extract/llm/` (36 records, 4 rejected), `llm/latency.csv`, `llm/run_summary.json`. On the 40 conversations: LLM critical 6/508 fields = 11.8 per 1,000 (Wilson 95% CI 5.4-25.5), major 59/508 = 116.1 (91.1-146.9), 4 records rejected by the evidence check; rules v2 critical 0/488 (0-7.8), major 4/488 = 8.2 (3.2-20.9). Latency p50 47 s, p95 253 s per conversation.
- What could go wrong / weaknesses: 40 conversations is small (wide CIs). The rules were tuned on most of these templates (in-sample), the LLM was not, so the comparison favours the rules; on the 8 holdout conversations in the subset both pipelines miss things. Many LLM "major" errors are advice worded differently (MA-WORDING-UNJUDGED) and may be the same meaning. Latency depends on other load on the laptop.
- What else could be done: Run on all 328 dev conversations overnight (`uv run python -m m3_extract run-llm --all-dev`); a larger model on a free Colab GPU; use the LLM only to propose items for the rules to verify.
- How to change this decision later: `MODEL`, `EXPECTED_DIGEST`, options and prompt in `m3_extract/llm.py`; subset size in `m3_extract/splits.py`.
- Status: done

### D-?: Scope cut: no extraction from ASR transcripts yet   (Phase B / m3_extract / nlp-engineer / 2026-11-10)
- What we needed to decide: AGENT 4 step 5 asks to run both pipelines on ASR outputs "when available".
- Options we considered:
  1. Wait for m2_asr. Pro: real ASR errors. Con: not available on 2026-11-10 (`results/m2_asr/` does not exist).
  2. Make fake ASR errors ourselves. Con: that is m1/m7's planted-error job (E4) and would mix planted and natural errors.
- What we chose: Option 1; the runner already accepts `--transcripts DIR`.
- Why: Honest scope: nothing is claimed about ASR input.
- What we actually did: `uv run python -m m3_extract run-rules --transcripts <dir>` writes to `results/m3_extract/rules_<dir name>/`; scoring compares values with gold (offset overlap is skipped because the text differs). The ASR fixture test (`test_asr_fixture_keeps_audio_times_and_faithful_value`) shows audio times are filled from word timestamps.
- What could go wrong / weaknesses: Real ASR text (wrong spellings, missing punctuation) will break exact-token matching; expect many more misses.
- What else could be done: Edit-distance matching for Kannada drug names (now Latin only), punctuation-free clause splitting.
- How to change this decision later: run the command above, then extend `run.score_dev` with an ASR plan.
- Status: not done (needs m2 outputs)
