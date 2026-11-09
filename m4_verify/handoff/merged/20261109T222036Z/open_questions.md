## m4_verify open questions (2026-11-10)

1. **Contract gap: turns in transcript.v1.** Cross-turn negation needs turn boundaries. m4 uses the gold.v1 convention (turns joined by "\n"). Real ASR transcripts of one audio file will have no newlines, so cross-turn answers cannot be resolved there. Request to the architect: optional `turns[{speaker, char_start, char_end}]` in a future transcript.v2, or diarisation in m2.
2. **Contract gap: patient link.** transcript.v1 has no patient_ref, so a wrong `patient_ref` is invisible to the verifier unless an encounter index `{audio_id: patient_ref}` is passed (C6). Who provides it in the integrated pipeline (m5 encounter table?)
3. **Lexicon gap: allowed units / dose forms.** The drug CSV has no allowed-unit or dose-form column; C4 uses a config default (`allowed_units`). Should m1 add `allowed_units` (and a range per form, e.g. syrup in ml)?
4. **Lexicon value:** paracetamol `adult_dose_range_mg = 1000-1000` in data/lexicon/drugs.csv (see human_todo). UNVERIFIED.
5. **UNVERIFIED Kannada:** all negation rules, number words, unit/frequency/duration phrases and symptom names in m4_verify are AI-written hypotheses (see human_todo).
6. **C7 threshold UNTUNED** (0.6 placeholder) until DEV ASR output exists.
7. **E4 on fixtures only:** 6 gold conversations give few unique mutations per type (3 to 90). The catch rates are not evidence about real data until re-run on m1 DEV gold.
8. **Audit optimism:** negation rules were fixed using the same 52 Wikipedia sentences they were then measured on; no held-out audit yet.
