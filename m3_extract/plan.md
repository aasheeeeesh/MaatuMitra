# m3_extract plan (nlp-engineer, written 2026-11-10 before tests and code)

Goal: transcript.v1 -> record.v1 with evidence, two ways (rules = MAIN, local LLM = E2
comparison), plus field-level scoring against gold by severity class. Synthetic data only.
Nothing Kannada here is native-validated.

## 0. Discipline

- Test split: `m3_extract/splits.py` refuses any id listed in `data/splits/test.txt` unless
  `ALLOW_TEST=1` (only `make eval-test` sets it). Every gold/transcript loader goes through it.
- Rules are tuned on DEV only. To get an honest estimate of over-fitting, DEV itself is split
  BEFORE any rule was written into
  - `dev_tune` (24 template ids, 240 conversations): examples I read while writing rules;
  - `dev_holdout` (9 template ids, one per category, chosen with `random.Random(20261110)`:
    a3 b4 c5 d2 e6 f3 g5 h6 i3; 88 conversations): never printed or read while writing rules.
  Scores are reported for both parts. The holdout is not a substitute for the test split.
- Never import m4_verify (or any module) code; only `contracts.validate`.

## 1. Rules pipeline (`rules.py`)

1. Normaliser (`textnorm.py`): refuse non-NFC / BOM / ZWSP input (fail closed: the contract
   says transcript text is already NFC). Tokenise the STORED text with
   `[\p{L}\p{M}\p{N}]` runs that may contain ZWJ/ZWNJ inside (so a ZWNJ does not split a word),
   plus decimal numbers. Each token has a comparison form: ZWJ/ZWNJ removed, Kannada digits ->
   ASCII, `casefold()`. Offsets always refer to the stored text.
2. Segmentation: turns = lines. Sentences end at `. ? !` (not at abbreviation dots such as
   `ಎಂ.ಜಿ`, `ಒ.ಆರ್.ಎಸ್`: a dot with a letter directly on both sides). Clauses follow the shared
   table (NEG-CL01..05) with the same abbreviation-dot exception.
3. Drug finder (`lexicon.py`): longest token-sequence match against `generic_en`,
   `kn_primary`, `kn_variants`, `roman_variants` (match types `exact`, `variant`); then
   Levenshtein distance <= 1 for Latin tokens of length >= 6 against single-token Latin names,
   only if exactly one drug is that close (`edit1`). Every match is logged.
4. Numbers (`numbers.py`): ASCII and Kannada digits (with decimals), Kannada number words
   (1-10, 13-15 verified on Wiktionary; others UNVERIFIED), ಅರ್ಧ = 0.5.
5. Units / frequency / duration (`units.py`): number + unit token (mg, ಎಂ.ಜಿ, ಮಾತ್ರೆ ...);
   `ದಿನಕ್ಕೆ N ಬಾರಿ|ಸಾರಿ|ಸಲ` and `ದಿನಕ್ಕೆ ಒಮ್ಮೆ`; `N ದಿನ|ದಿವಸ` days, `N ವಾರ` = 7N.
   Exact tokens only, so `ದಿನದಿಂದ` ("since") and `ದಿನದಲ್ಲಿ` ("within") are not durations.
6. Negation flag (`negation.py`): loads ONLY `.claude/skills/kannada-nlp/negation_table.yaml`;
   cues are matched per token; a cue negates its clause; cross-turn NEG-X01/X02.
7. Symptoms (`data/symptoms.yaml`): whole-token lexicon. A mention counts if it is in a
   statement (present = clause not negated), in a question answered by a bare ಇಲ್ಲ/ಹೌದು turn
   (cross-turn), or in a "how many days" (ಎಷ್ಟು) question (presupposed present). Mentions in
   conditional clauses (`...ದರೆ`) are hypothetical and ignored. Bare-noun clauses before
   ಮತ್ತು/ಹಾಗೂ/`,` share the next clause's polarity (coordination).
8. Medications: attributes are read from the drug token to the end of its clause/sentence
   (stopping at the next drug). One entry per drug: the decisive mention (cross-turn >
   statement with most attributes > question).
9. Advice / follow-up (`data/phrases.yaml`): phrase patterns with an English gloss for each
   polarity; polarity comes from the negation table, not the pattern. Clauses with a drug are
   medication instructions, not advice. Follow-up fallback: a non-question sentence with
   `ಬನ್ನಿ` ("come") gets an `[untranslated]` text.
10. Encounter context: `patient_ref` and `encounter_type` cannot be heard in the transcript.
    They are supplied as encounter context (in the app: the logged-in worker picks the patient);
    for dev runs they are read from the gold record. They are therefore NOT scored.

## 2. Evidence (`evidence.py`)

Smallest span that supports the value: drug token through the last attribute / negation cue in
the same clause; symptom token through its polarity word; cross-turn: the entity in the QUESTION
turn (annotation guide 3). Audio times = first/last word timestamps inside the span, else null.
`check_evidence(record, transcript_text)` -> list of failures (bounds, NFC equality, timing).
Any failure rejects the whole record: it goes to `<pipeline>/rejected/` with the reason and is
scored as an empty record plus a rejection count. A test forges a span and expects rejection.

## 3. LLM pipeline (`llm.py`, E2)

Ollama on 127.0.0.1:11434, `qwen3:4b-instruct`, revision = Ollama digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`, temperature 0, seed
20261110, `format` = JSON schema (drug names and symptom names are enums; same closed vocabulary
as the rules). The model returns QUOTES only; offsets are computed by our code (exact substring
search); a quote not found verbatim fails the evidence check. Few-shot examples come from
fixtures (never from dev/test). Plain httpx, no new dependency. Seeded dev subset of 40
conversations (`random.Random(20261110).sample`) in `results/m3_extract/llm_subset.txt`;
the rules pipeline is scored on the same subset. Latency per conversation is recorded.

## 4. Scoring (`scoring.py`)

Fields per gold item: medication 6 (drug, dose_value, dose_unit, frequency, duration, negated),
symptom 2 (name, present), advice 2 (text, negated), follow-up 1. Matching: by drug / symptom
name; advice by exact gloss, then by span overlap. Classes from docs/severity.md; missed item
= 1 error (MAJOR), extra item = 1 error and +1 field. Advice/follow-up wording that differs
cannot be judged automatically: MAJOR per severity rule 5 (code `MA-WORDING-UNJUDGED`).
Missed / extra advice and follow-up are MAJOR (extension, decision entry). Errors per 1,000
fields with Wilson 95% CI and N, sliced by template category, code_switched, has_negation,
cross_turn_negation, dev part (tune / holdout). Outputs: `results/m3_extract/dev_scores.csv`,
`results/m3_extract/failures_dev.md`.

## 5. Make targets

`m3-test`, `m3-mock` (MODE=mock on fixtures -> results/m3_extract/mock/), `m3-run-dev`
(rules on full dev + score), `m3-run-llm-dev` (LLM on the subset + score), `m3-score`.

## 6. Not done / limits

No ASR transcripts exist yet (results/m2_asr absent): the runner takes `--transcripts DIR` so
it can be re-run later (HUMAN_TODO). Frequency from ಬೆಳಿಗ್ಗೆ/ರಾತ್ರಿ is not implemented (no source).
