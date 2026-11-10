# Annotation guide (gold transcripts and gold records)

Owner: m1_data (data-scientist agent), 2026-11-09. Applies to every gold file in
`data/gold/` (gold.v1), `data/transcripts/gold/` (transcript.v1, model "gold") and the
minimal-pair twins in `data/twins/`. **Everything here was written by an AI agent and is
not native-validated.** A native Kannada speaker must review it (HUMAN_TODO).

**Example rule (REFREEZE-1, integrity finding M1-6):** every Kannada example printed in this
guide is drawn from dev-family templates or from the shared lexicon/table, never from words
that occur only in test-family templates. Builders read this guide, so it must not carry
test wording. `m1_data/tests/test_refreeze1.py` fails if a test-only word is added. When you
add an example, take it from a dev family (`data/splits/split_plan.json`, "families", "dev").

## 1. What "gold" means here

All conversations are synthetic, generated from templates (`data/templates/`). The gold
record is produced together with the text by the generator, so it is exactly what the
template says was spoken. "Gold" means *label consistent with the text*, not *clinically
correct advice* and not *natural Kannada*.

## 2. Text: what is written

| topic | rule | example |
|---|---|---|
| Spoken vs formal | Write what is said (colloquial forms allowed), not the literary form. Spoken forms we use on purpose: `ಕುಡಿಯಲ್ಲ` (casual "does not drink"), `ಇಲ್ಲಾ` (lengthened ಇಲ್ಲ). Spoken words for diarrhoea are `ಭೇದಿ` and `ಲೂಸ್ ಮೋಷನ್`; the formal `ಅತಿಸಾರ` is what the templates use (reviewer note, not yet generated). | ಮಗು ಸಿರಪ್ ಕುಡಿಯಲ್ಲ. |
| Numbers | Keep the form that was spoken: Kannada number words for counts/frequency/duration (`ಮೂರು ಬಾರಿ`, `ಐದು ದಿನ`), ASCII digits or Kannada digits for doses (`500 mg`, `೫೦೦ mg`). Gold values are always numbers (500, 3, 5). | ೨೫೦ mg → dose_value 250 |
| Week | `ಒಂದು ವಾರ` = duration_days 7. | |
| Units | `mg` (Latin) or `ಎಂ.ಜಿ` → "mg"; `ಮಾತ್ರೆ` count → "tablet"; `ಕ್ಯಾಪ್ಸೂಲ್` count → "capsule"; `ml` or `ಎಂ.ಎಲ್` → "ml". Dose is the amount per dose as spoken. | ಒಂದು ಮಾತ್ರೆ → 1 tablet |
| Child syrup | A child is never given an adult tablet dose. Child turns use a syrup in ml (`ಸಿರಪ್ ಐದು ಎಂ.ಎಲ್`, `5 ml`, `ಎರಡೂವರೆ ಎಂ.ಎಲ್` = 2.5) or carry no dose at all. The ml volumes are synthetic (2.5, 5, 7.5, 10) and are NOT age-checked: they are not dosing advice. | ಸಿರಪ್ 5 ml → dose_value 5, dose_unit "ml" |
| ORS | Spelled with the long vowel: `ಓ.ಆರ್.ಎಸ್` (reviewer: the English letter O is said long). The short `ಒ` form is wrong. Dose unit is sachet or ml, never mg. | ಓ.ಆರ್.ಎಸ್ |
| English words | English drug names, "antibiotic", "mg", "OK", "Tablet", "fever" stay in **Latin script** exactly as spoken (capitalised or not). Gold `drug` is always the lexicon `generic_en`. Kannada-script spellings of drug names come from `data/lexicon/drugs.csv`. | Azithromycin / ಅಜಿತ್ರೋಮೈಸಿನ್ → "azithromycin" |
| ZWJ / ZWNJ | Keep them in stored text when the spelling uses them (we use a ZWNJ before the plural suffix -ಗಳು of the antibiotic word, as in the fetched news text). Remove them only in comparison copies. Note: the tokeniser `[\p{L}\p{M}\p{N}]+` splits the STORED text at a ZWNJ (two `words` in the transcript). | |
| Forbidden | No BOM, no zero-width space (U+200B), text must be NFC. | |
| Punctuation | Only `.` `?` `,` (and `.` inside `ಎಂ.ಜಿ`, `ಎಂ.ಎಲ್`, `ಓ.ಆರ್.ಎಸ್`). They are clause boundaries for negation scope. A dot directly followed by a letter is part of an abbreviation and does not split (negation table v2); a naive splitter would still break `ಎಂ.ಜಿ`. | |
| Turns | One turn per line; the conversation text is the turns joined with one `\n`. No newline inside a turn. | |

## 3. Spans (where the evidence is)

- Offsets are **code points** into the conversation text (turns joined by `\n`), end
  exclusive, computed by the generator (never typed).
- Each span stays inside one turn and is minimal but complete:
  - symptom: the symptom word plus its polarity word if any (`ಕೆಮ್ಮು ಇಲ್ಲ`, `ಜ್ವರ ಬಂದಿದೆ`);
  - medication: drug name through the last spoken dose / frequency / duration word
    (`ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ`), plus the negation cue when the
    cue is in the same clause (`Diclofenac ಬೇಡ`, `... ತೆಗೆದುಕೊಳ್ಳದೆ ಬಿಟ್ಟೆ`);
  - advice / follow-up: the advice clause.
- **Cross-turn answers**: when a bare `ಇಲ್ಲ` / `ಇಲ್ಲಾ` / `ಹೌದು` answers a question, the span is
  the entity in the QUESTION turn; the polarity comes from the answer.
- One gold entry per drug per conversation, anchored on the decisive mention.

## 4. Polarity conventions (negation)

| situation | gold |
|---|---|
| symptom denied (`ಕೆಮ್ಮು ಇಲ್ಲ`, `ವಾಂತಿ ಆಗಿಲ್ಲ`, `ಯಾವುದೇ ನೋವು ಇಲ್ಲ`, question + bare `ಇಲ್ಲ`) | `present: false`. Real answers often add a polite word (`ಇಲ್ಲ ಅಕ್ಕ`, `ಇಲ್ರೀ`, `ಹೌದ್ರೀ`, `ಹೂಂ`); the generator only produces the bare forms (reviewer note) |
| drug not taken / refused / not to be taken (`... ಕುಡಿಯಲಿಲ್ಲ`, `... ಬೇಡ`, `ಕೊಡಬೇಡಿ`, `ಇದು X ಅಲ್ಲ`) | `negated: true` |
| drug stopped before finishing (the -ದೆ "without doing" forms, for example `ತೆಗೆದುಕೊಳ್ಳದೆ ಬಿಟ್ಟೆ`) | `negated: true` (convention: not being taken as prescribed; OPEN QUESTION for the clinical reviewer) |
| prohibitive advice (`ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು`; the ungrammatical `ಕೊಡುವುದು ಬೇಡಿ` was removed, write `ಕೊಡಬೇಡಿ`) | advice `negated: true`, text is the English gloss including "do not" (same as the architect fixtures) |
| negative condition in follow-up (`ವಾಂತಿ ನಿಲ್ಲದಿದ್ದರೆ ... ಬನ್ನಿ`) | follow_up has no negated field; English gloss says "if ... does not ..." |
| trap words (`ಎಲ್ಲ, ಎಲ್ಲಾ, ಇಲ್ಲಿ, ಅಲ್ಲಿ, ಅಲ್ವಾ, ಅಲ್ವ, ಮಾತ್ರ, ಮಾತ್ರೆ, ಇದೆ, ಬಂದಿದೆ, ಇದ್ದರೆ, ಓದಿದ್ದರೆ, ಬೇಡಿಕೆ, ಬೆಲ್ಲ`) | never negation. Reviewer suggests more traps (`ಕೂಡ`, `ತಪ್ಪದೆ`, `ಬಿಡದೆ`, `ಮರೆಯದೆ`, `ಅಲ್ಲವೇ`): not yet in the table |
| negative question (`ಬರಲ್ವಾ?` "doesn't he come?") | table v2 soft cue NEG-S07; m1 does not generate it (gold polarity of a negative question and of its answer is undecided; native reviewer must rule) |
| `ಇಲ್ಲದೆ` ("without": `ವೈದ್ಯರ ಚೀಟಿ ಇಲ್ಲದೆ`) | not a negation of the record item; NOTE: the shared table does not match it at all (gap reported in open questions) |

A negation cue negates only its clause: clauses split at `. ? ,` and at the clause words of the
shared table (`ಆದರೆ, ಮತ್ತು, ಹಾಗೂ` and the "therefore" word listed there); for example
`ತಲೆನೋವು ಇದೆ ಆದರೆ ವಾಂತಿ ಆಗಿಲ್ಲ` has a positive and a negated clause.

## 5. Tags

- `has_negation`: true iff the shared negation table detects a cue (clause splitters and a
  bare `ಹೌದು` do not count). The generator checks that the detected cues equal the cues the
  template put there.
- `trap_tokens`: must-not-trigger tokens of the table that occur, in order of first
  appearance; `ಇದೆ` is excluded (it is in almost every sentence).
- `code_switched`: the text contains any Latin letter (drug names, `mg`, `OK`, ...).
- `cross_turn_negation`: a turn whose only token is `ಇಲ್ಲ`/`ಇಲ್ಲಾ` answers the previous question.

## 6. Minimal-pair twins

For every negation slot rendered negative, `data/twins/twins_<split>.jsonl` holds the same
turn with only that cue replaced by its positive form (`ಇಲ್ಲ`→`ಇದೆ`, `ಬೇಡ`→`ಬೇಕು`,
`ಕುಡಿಯದಿದ್ದರೆ`→`ವಾಂತಿ ಮಾಡಿದರೆ`, bare `ಇಲ್ಲ.`→`ಹೌದು.`), with spans in both versions. Some twins
are artificial pairs (they test cue detection, not meaning); the follow-up twins of the three
templates the Kannada reviewer called nonsensical were rewritten so that both sides are
sensible sentences (`ವಾಂತಿ ನಿಲ್ಲದಿದ್ದರೆ`→`ವಾಂತಿ ಇದ್ದರೆ`), but the pair is still not a pure
negation removal (not native-validated). Twins of test
conversations are TEST data (locked).

## 7. Known limits

Not native-validated; many template words are not attested in any fetched source
(`results/m1_data/unattested_tokens.json`); dose values are synthetic (not dosing advice).
