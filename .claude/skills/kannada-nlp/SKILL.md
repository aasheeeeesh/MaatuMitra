---
name: kannada-nlp
description: Kannada text handling for MaatuMitra (NFC, ZWJ/ZWNJ policy, digits, tokenising with the regex library, negation cues and traps, number/frequency phrases, codepoint table). Use whenever code or data touches Kannada text in m1_data, m2_asr, m3_extract, m4_verify, m8_helper, or in a Kannada language review.
---

# Kannada NLP rules (PROJECT_BRIEF section 6.1 + AGENT 5 negation rules)

Nothing in this skill is native-validated. The team has no native Kannada speaker.
Every rule is a hypothesis until a real reviewer confirms it (HUMAN_TODO item b).

## 1. Normalisation (do this first, always, in this order)

1. Decode as UTF-8. Strip a leading BOM (U+FEFF) and every zero-width space (U+200B).
2. Unicode **NFC** (`unicodedata.normalize("NFC", s)`). All stored contract text is NFC;
   `contracts/validate.py` rejects non-NFC strings, BOM and U+200B.
3. **ZWJ (U+200D) / ZWNJ (U+200C) policy**: KEEP them in stored text (they change how a
   conjunct is drawn), REMOVE them in the comparison copy. Reason: both are category
   `Cf`, which is NOT in `[\p{L}\p{M}\p{N}]`, so a ZWNJ inside a word would split it
   into two tokens. Remove them BEFORE tokenising the comparison copy.
4. Kannada digits U+0CE6..U+0CEF (೦೧೨೩೪೫೬೭೮೯) -> ASCII 0..9 in the comparison copy only;
   keep the original digits in stored text and in evidence spans.
5. Latin text: compare case-insensitively (`casefold()`); keep English drug names in
   Latin script in gold; accept Kannada-script transliterations via the lexicon
   (`kn_primary`, `kn_variants`, `roman_variants`).

Offsets: every `char_start`/`char_end` in the contracts is a **code-point offset into
the stored NFC text**, end exclusive (Python slicing). Never compute evidence offsets on
the comparison copy (removing ZWJ/ZWNJ or digits conversion can shift positions); map back
or search the stored text.

## 2. Tokenising

```python
import regex  # NOT re: re has no \p{M}

TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
tokens = [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text)]
```
Kannada vowel signs (matras), anusvara/visarga and the virama are combining marks
(`Mn`/`Mc`). `\w`-style splitting or splitting on `\b` can break words. Graphemes
(for grapheme CER) use `regex.findall(r"\X", text)`.

## 3. Negation (the shared table)

Machine-readable table: `.claude/skills/kannada-nlp/negation_table.yaml` (ids, regex
patterns, types, examples, status `hypothesis_unverified`, origin `brief` or
`architect_addition`).

- **m3_extract** must call ONLY this table for its negation flag.
- **m4_verify** must NOT read it: it hand-codes its own rules so the verifier is
  independent (otherwise a mistake in the table would be invisible to the check).
- **m1_data** must make every pattern appear in >= 5 conversations.

Summary of the starting rules (from AGENT 5, treat as hypotheses):
- Strong cues, whole token: ಇಲ್ಲ, ಇಲ್ಲಾ, ಅಲ್ಲ, ಬೇಡ, ಬೇಡಿ, ಬಾರದು, ಕೂಡದು.
- Token-final suffixes by regex: -ಿಲ್ಲ (ಬರಲಿಲ್ಲ, ಆಗಿಲ್ಲ), -ುದಿಲ್ಲ (-ವುದಿಲ್ಲ), -ದಿದ್ದರೆ (if not),
  -ದೆ ("without doing", ONLY on verb stems from a verb lexicon).
  Architect additions: fused -ಬಾರದು / -ಕೂಡದು / -ಬೇಡ(ಿ) (ತೆಗೆದುಕೊಳ್ಳಬಾರದು, ಕೊಡಬೇಡಿ), and a
  refinement of -ದಿದ್ದರೆ that requires a bare consonant before it (so positive
  ಓದಿದ್ದರೆ / ಬಂದಿದ್ದರೆ do not match).
- Soft cue: casual -ಲ್ಲ on a verb stem (ಬರಲ್ಲ). Risky: flags via C8 unless the stem is in
  the verb lexicon.
- Compound: ಯಾವುದೇ ... ಇಲ್ಲ ("not any").
- Clause scope: split at punctuation and at ಆದರೆ, ಮತ್ತು, ಹಾಗೂ, ಆದ್ದರಿಂದ; a cue negates only
  its clause.
- Cross-turn: a turn that is only ಇಲ್ಲ or ಹೌದು answers the previous turn's question.
- MUST NOT trigger: ಎಲ್ಲ, ಎಲ್ಲಾ (all), ಇಲ್ಲಿ (here), ಅಲ್ಲಿ (there), ಅಲ್ವಾ, ಅಲ್ವ (tag "right?"),
  ಮಾತ್ರ (only), ಮಾತ್ರೆ (tablet). Architect additions: ಇದೆ, ಬಂದಿದೆ (end in ದೆ), ಇದ್ದರೆ,
  ಓದಿದ್ದರೆ, ಬೇಡಿಕೆ.
- Known blind spot: if ASR silently drops the negation, text-only checks cannot see it.
  Only C7 (ASR risk) can, and only partly. Say so in every report.

Matching rule: cues are matched as WHOLE tokens or as token-final suffixes by explicit
regex on ONE token, never as raw substrings of the sentence (raw `"ಇಲ್ಲ" in s` also
matches ಇಲ್ಲಿ).

## 4. Numbers, units, frequency, duration (STARTER list, UNVERIFIED)

Verify each phrase against a fetched source (grammar reference, Wiktionary, government
health page) before relying on it, and record the URL.

| Kannada (spoken) | meaning | normalised |
|---|---|---|
| ಒಂದು, ಎರಡು, ಮೂರು, ನಾಲ್ಕು, ಐದು, ಆರು, ಏಳು, ಎಂಟು, ಒಂಬತ್ತು, ಹತ್ತು | 1..10 | int |
| ಅರ್ಧ | half | 0.5 |
| ದಿನಕ್ಕೆ ಒಂದು / ಎರಡು / ಮೂರು ಬಾರಿ | once / twice / three times a day | frequency_per_day 1/2/3 |
| ಬೆಳಿಗ್ಗೆ, ಮಧ್ಯಾಹ್ನ, ರಾತ್ರಿ | morning, afternoon, night | may imply frequency (needs a rule + source) |
| ಐದು ದಿನ, ಒಂದು ವಾರ | five days, one week | duration_days 5 / 7 |
| ಮಾತ್ರೆ | tablet | dose_unit tablet |
| mg, ಎಂ.ಜಿ, ಮಿಲಿಗ್ರಾಂ | milligram | dose_unit mg |
| ml, ಎಂ.ಎಲ್ | millilitre | dose_unit ml |
| ಚಮಚ | spoon | dose_unit teaspoon (UNVERIFIED mapping) |

## 5. Annotation conventions (full guide: docs/annotation_guide.md, m1_data writes it)

- Write what was spoken (colloquial form), not the formal/literary spelling.
- Numbers: keep the form that was spoken (word, Kannada digits or ASCII digits).
- English words (drug names, "antibiotic", "mg") stay in Latin script.
- Punctuation: `.` `?` `,` only; they are clause boundaries.
- Mark every Kannada string as "not native-validated" unless a real reviewer signed it off.

## 6. Kannada codepoint table (U+0C80..U+0CFF)

Names, categories and decompositions below were printed with Python 3.11.15
`unicodedata` (Unicode 14.0.0) on 2026-11-09. Characters added after Unicode 14
(for example U+0CF3, if it exists) are not in that database: UNVERIFIED.

| range | what | category |
|---|---|---|
| U+0C80 | sign spacing candrabindu | Lo |
| U+0C81 | sign candrabindu | Mn |
| U+0C82, U+0C83 | anusvara (ಂ), visarga (ಃ) | Mc |
| U+0C84 | sign siddham | Po |
| U+0C85..U+0C94 | independent vowels ಅ..ಔ (gaps at U+0C8D, U+0C91) | Lo |
| U+0C95..U+0CB9 | consonants ಕ..ಹ (gaps at U+0CA9, U+0CB4) | Lo |
| U+0CBC | nukta | Mn |
| U+0CBD | avagraha | Lo |
| U+0CBE..U+0CCC | dependent vowel signs (matras) ಾ ಿ ೀ ು ೂ ೃ ೄ ೆ ೇ ೈ ೊ ೋ ೌ (gaps at U+0CC5, U+0CC9) | Mc or Mn |
| U+0CCD | **virama** ್ (joins consonants into conjuncts) | Mn |
| U+0CD5, U+0CD6 | length mark, AI length mark | Mc |
| U+0CDD, U+0CDE | nakaara pollu, letter FA | Lo |
| U+0CE0, U+0CE1 | vocalic RR, vocalic LL | Lo |
| U+0CE2, U+0CE3 | vowel signs vocalic L / LL | Mn |
| U+0CE6..U+0CEF | **digits** ೦..೯ | Nd |
| U+0CF1, U+0CF2 | jihvamuliya, upadhmaniya | Lo |
| U+200C / U+200D | ZWNJ / ZWJ (outside the block) | Cf |

Canonical decompositions that NFC recomposes (so decomposed input is "not NFC"):
U+0CC0 = U+0CBF U+0CD5; U+0CC7 = U+0CC6 U+0CD5; U+0CC8 = U+0CC6 U+0CD6;
U+0CCA = U+0CC6 U+0CC2; U+0CCB = U+0CCA U+0CD5.
