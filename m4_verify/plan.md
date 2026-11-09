# m4_verify plan (safety-engineer, 2026-11-09)

Written BEFORE tests and code. Nothing Kannada here is native-validated.

## Goal
`verify(record, transcript, lexicon, config, second_transcript=None) -> verdict.v1`,
deterministic and FAIL-CLOSED, with checks C1..C8 in a registry so any single check can be
disabled by config (E3 ablation). Plus a planted-mistake generator (E4) and a negation audit
on real Kannada text.

## Design
1. **Own text layer** (`textnorm.py`): NFC, strip BOM/ZWSP; comparison copy removes ZWJ/ZWNJ and
   maps Kannada digits to ASCII; Latin casefold; tokeniser `regex` `[\p{L}\p{M}\p{N}]+`. The
   comparison copy keeps a map back to stored offsets (only deletions happen, so a per-char map).
2. **Own numbers** (`numbers.py`): ASCII/Kannada digits (with decimals), Kannada number words
   1..10, tens, hundreds, compound "ಇನ್ನೂರ ಐವತ್ತು" = 250, ಅರ್ಧ = 0.5, ಒಂದೂವರೆ = 1.5.
   English number words for advice/follow-up text (C6).
3. **Own lexicon access** (`lexicon.py`): reads the m1 CSV column set (path from config;
   default `fixtures/lexicon/drugs_fixture.csv`, `data/lexicon/drugs.csv` when it exists).
   Drug matching by token SEQUENCES of every variant (kn_primary, kn_variants,
   roman_variants, generic_en). Units, frequency and duration phrases, and a small symptom
   lexicon are hand-coded here (UNVERIFIED).
4. **Own negation rules** (`negation.py`): hand-coded, NOT read from the shared YAML table
   (independence). Strong whole tokens; token-final suffixes; -ದೆ only on a hand-coded verb-stem
   list; soft -ಲ್ಲ (flags C8); compound ಯಾವುದೇ...ಇಲ್ಲ; trap tokens never trigger.
5. **Structure** (`structure.py`): turns = transcript text split on "\n" (gold.v1 convention in
   fixtures/build_fixtures.py and contracts/validate.py). Clauses split at punctuation and at
   ಆದರೆ/ಮತ್ತು/ಹಾಗೂ/ಆದ್ದರಿಂದ, with offsets. A clause ending in "?" is a question. A turn whose
   only token is ಇಲ್ಲ/ಇಲ್ಲಾ/ಹೌದು answers the previous turn's question clause(s).
6. **Checks** (`checks.py`), each returns a list of (status, reason, field_path):
   C1 span-exists, C2 span-supports-value, C3 negation-consistency, C4 dose-range,
   C5 frequency/duration, C6 unsupported-addition (+ possible omission, + patient link when an
   encounter index is configured), C7 asr-risk, C8 ambiguity.
   Registry: `REGISTRY = {"C1": Check(...), ...}`; disabled => one `n/a` "disabled by config".
   Any exception => `flag`, reason `check_error: <Type>: <msg>`.
   `auto_acceptable` = no flag AND at least one enabled check returned `pass`.
7. **CLI** `uv run python -m m4_verify verify --record R --transcript T [--second-transcript T2]
   [--disable C3] [--config cfg.yaml] [--out verdict.json]`; also `mock`, `planted`, `audit`.
8. **E4 planted mistakes** (`planted.py`): source gold dir is configurable (fixtures now;
   data DEV gold later; refuses any path with a `test` component). Types (a)..(i), >= 200 per
   type, seed 20261109, JSONL injection log (id, type, level, field_path, before, after).
   Record level: mutate the gold-derived record. Transcript level: mutate the transcript text
   and build the record a faithful extractor would produce from it; evaluate text-only and
   with a second (clean) transcript to separate "text-only detectable" from "needs ASR
   cross-check". Report unique-mutation counts next to N (duplicates are not independent).
9. **Results** `results/m4_verify/`: verdicts (validated with contracts.validate), per-check
   CSV, catch-rate CSV with Wilson 95% CIs, clean flag rate (record and field level), summary.
10. **Negation audit**: fetch kn.wikipedia articles + Kannada news, run the matcher, read the
    output, write `negation_audit.md` (URLs + fetch date, FP, misses, limits).

## Tests first (m4_verify/tests)
- Every cue: positive, minimal-pair twin (cue removed), trap. Clause scope. Cross-turn.
- Numbers, normaliser, lexicon matcher.
- Each check C1..C8 on hand-made cases; fixtures produce valid verdicts; clean fixture
  records are auto-acceptable; the ASR-error fixture is flagged.
- Fail-closed: monkeypatch a check to raise => flag + check_error + auto_acceptable false.
- Registry: disabling a check gives n/a "disabled".
- Planted generator: deterministic, >= 200 per type, log fields; record-level negation drops
  and number swaps are flagged 100%.
- CLI smoke test; all produced verdicts validate.

## Known limits (stated up front)
- ASR silently dropping a negation is invisible to text-only checks; only C7 (low confidence or
  a second transcript) can see it, and only partly.
- Wrong patient_ref is invisible without an encounter index (transcript.v1 has no patient).
- Lexicon has no allowed-unit column: allowed units are a verifier config default.
- Fixtures give only 6 gold conversations, so the 200+ injections per type contain many
  duplicates; unique counts are reported.
