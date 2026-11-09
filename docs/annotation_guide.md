# Annotation guide (gold transcripts and gold records)

Owner: m1_data (data-scientist agent), 2026-11-09. Applies to every gold file in
`data/gold/` (gold.v1), `data/transcripts/gold/` (transcript.v1, model "gold") and the
minimal-pair twins in `data/twins/`. **Everything here was written by an AI agent and is
not native-validated.** A native Kannada speaker must review it (HUMAN_TODO).

## 1. What "gold" means here

All conversations are synthetic, generated from templates (`data/templates/`). The gold
record is produced together with the text by the generator, so it is exactly what the
template says was spoken. "Gold" means *label consistent with the text*, not *clinically
correct advice* and not *natural Kannada*.

## 2. Text: what is written

| topic | rule | example |
|---|---|---|
| Spoken vs formal | Write what is said (colloquial forms allowed), not the literary form. Spoken forms we use on purpose: `ಕುಡಿಯಲ್ಲ` (casual "does not drink"), `ತಗೊಂಡ್ರೆ`, `ಇಲ್ಲಾ` (lengthened ಇಲ್ಲ). | ಮಗು ಸಿರಪ್ ಕುಡಿಯಲ್ಲ. |
| Numbers | Keep the form that was spoken: Kannada number words for counts/frequency/duration (`ಮೂರು ಬಾರಿ`, `ಐದು ದಿನ`), ASCII digits or Kannada digits for doses (`500 mg`, `೫೦೦ mg`). Gold values are always numbers (500, 3, 5). | ೨೫೦ mg → dose_value 250 |
| Week | `ಒಂದು ವಾರ` = duration_days 7. | |
| Units | `mg` (Latin) or `ಎಂ.ಜಿ` → "mg"; `ಮಾತ್ರೆ` count → "tablet"; `ಕ್ಯಾಪ್ಸೂಲ್` count → "capsule". Dose is the amount per dose as spoken. | ಒಂದು ಮಾತ್ರೆ → 1 tablet |
| English words | English drug names, "antibiotic", "mg", "OK", "Tablet", "fever" stay in **Latin script** exactly as spoken (capitalised or not). Gold `drug` is always the lexicon `generic_en`. Kannada-script spellings of drug names come from `data/lexicon/drugs.csv`. | Azithromycin / ಅಜಿತ್ರೋಮೈಸಿನ್ → "azithromycin" |
| ZWJ / ZWNJ | Keep them in stored text when the spelling uses them (we use ZWNJ in `ಆಂಟಿಬಯಾಟಿಕ್‌ಗಳು`, as in the fetched news text). Remove them only in comparison copies. Note: the tokeniser `[\p{L}\p{M}\p{N}]+` splits the STORED text at a ZWNJ (two `words` in the transcript). | |
| Forbidden | No BOM, no zero-width space (U+200B), text must be NFC. | |
| Punctuation | Only `.` `?` `,` (and `.` inside `ಎಂ.ಜಿ`, `ಒ.ಆರ್.ಎಸ್`). They are clause boundaries for negation scope. Note the hazard: the dots inside `ಎಂ.ಜಿ` / `ಒ.ಆರ್.ಎಸ್` also split clauses for a naive splitter. | |
| Turns | One turn per line; the conversation text is the turns joined with one `\n`. No newline inside a turn. | |

## 3. Spans (where the evidence is)

- Offsets are **code points** into the conversation text (turns joined by `\n`), end
  exclusive, computed by the generator (never typed).
- Each span stays inside one turn and is minimal but complete:
  - symptom: the symptom word plus its polarity word if any (`ಕೆಮ್ಮು ಇಲ್ಲ`, `ಜ್ವರ ಬಂದಿದೆ`);
  - medication: drug name through the last spoken dose / frequency / duration word
    (`ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ`), plus the negation cue when the
    cue is in the same clause (`Diclofenac ಬೇಡ`, `... ಕೋರ್ಸ್ ಮುಗಿಸದೆ ನಿಲ್ಲಿಸಿದೆವು`);
  - advice / follow-up: the advice clause.
- **Cross-turn answers**: when a bare `ಇಲ್ಲ` / `ಇಲ್ಲಾ` / `ಹೌದು` answers a question, the span is
  the entity in the QUESTION turn; the polarity comes from the answer.
- One gold entry per drug per conversation, anchored on the decisive mention.

## 4. Polarity conventions (negation)

| situation | gold |
|---|---|
| symptom denied (`ಕೆಮ್ಮು ಇಲ್ಲ`, `ವಾಂತಿ ಆಗಿಲ್ಲ`, `ಯಾವುದೇ ನೋವು ಇಲ್ಲ`, question + bare `ಇಲ್ಲ`) | `present: false` |
| drug not taken / refused / not to be taken (`... ಕುಡಿಯಲಿಲ್ಲ`, `... ಬೇಡ`, `ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ`, `ಇದು X ಅಲ್ಲ`) | `negated: true` |
| drug stopped before finishing (`ಮುಗಿಸದೆ ನಿಲ್ಲಿಸಿದೆವು`, `ತೆಗೆದುಕೊಳ್ಳದೆ ಬಿಟ್ಟೆ`) | `negated: true` (convention: not being taken as prescribed; OPEN QUESTION for the clinical reviewer) |
| prohibitive advice (`ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು`) | advice `negated: true`, text is the English gloss including "do not" (same as the architect fixtures) |
| negative condition in follow-up (`ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ... ಬನ್ನಿ`) | follow_up has no negated field; English gloss says "if ... does not ..." |
| trap words (`ಎಲ್ಲ, ಎಲ್ಲಾ, ಇಲ್ಲಿ, ಅಲ್ಲಿ, ಅಲ್ವಾ, ಅಲ್ವ, ಮಾತ್ರ, ಮಾತ್ರೆ, ಇದೆ, ಬಂದಿದೆ, ಇದ್ದರೆ, ಓದಿದ್ದರೆ, ಬೇಡಿಕೆ`) | never negation |
| `ಇಲ್ಲದೆ` ("without": `ವೈದ್ಯರ ಚೀಟಿ ಇಲ್ಲದೆ`) | not a negation of the record item; NOTE: the shared table does not match it at all (gap reported in open questions) |

A negation cue negates only its clause: clauses split at `. ? ,` and at `ಆದರೆ, ಮತ್ತು, ಹಾಗೂ,
ಆದ್ದರಿಂದ` (`ಈಗ ಜ್ವರ ಇಲ್ಲ ಆದ್ದರಿಂದ ಐಬ್ಯುಪ್ರೋಫೆನ್ ಮಾತ್ರೆ ಬೇಡ` has two negated clauses).

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
`ಮುಗಿಸದೆ`→`ಮುಗಿಸಿ`, bare `ಇಲ್ಲ.`→`ಹೌದು.`), with spans in both versions. Some twins are
semantically odd on purpose (they test cue detection, not meaning). Twins of test
conversations are TEST data (locked).

## 7. Known limits

Not native-validated; many template words are not attested in any fetched source
(`results/m1_data/unattested_tokens.json`); dose values are synthetic (not dosing advice).
