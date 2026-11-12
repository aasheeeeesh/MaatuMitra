# Failure gallery (DEV only; no test-split example)

18 real failures from saved module outputs. 8 are DANGEROUS errors that slipped through the verifier. All are on synthetic, template-generated, not native-validated text. Causes are auto-suggested by m7 and must be confirmed by a human.

**Natural dangerous errors:** the m3 rules made 0 critical errors on dev (in-sample: the rules were fixed on dev), so every dangerous slip-through below is a PLANTED error (E4). Fewer than 3 natural dangerous failures exist on dev; we say so instead of inventing any.

## 1. natural extraction error (m3 rules, DEV, in-sample)

- id: `m1-c5-000` (family/topic: c_stopped_early__f2)
- input: ಸ್ವಯಂ ಔಷಧಿ ಮಾಡದೆ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ.
- system output: text = None
- correct answer: text = 'do not self-medicate; consult a doctor'
- class: MA-MISSED-ADVICE; dangerous: False; slipped through: n/a (m4 not yet run on m3 output)
- cause: advice sentence not extracted (no advice pattern matched this wording) (auto-suggested cause; a human should confirm)

## 2. natural extraction error (m3 rules, DEV, in-sample)

- id: `m1-d2-000` (family/topic: d_no_antibiotic__f1)
- input: ವೈದ್ಯರ ಚೀಟಿ ಇಲ್ಲದೆ ಆಂಟಿಬಯಾಟಿಕ್ ಕೊಡುವಂತಿಲ್ಲ.
- system output: text = None
- correct answer: text = "antibiotics cannot be given without a doctor's prescription"
- class: MA-MISSED-ADVICE; dangerous: False; slipped through: n/a (m4 not yet run on m3 output)
- cause: advice sentence not extracted (no advice pattern matched this wording) (auto-suggested cause; a human should confirm)

## 3. natural extraction error (m3 rules, DEV, in-sample)

- id: `m1-g5-000` (family/topic: g_physician_english__f2)
- input: paracetamol ಎರಡು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಮಾತ್ರ, fever ಇದ್ದರೆ ಮಾತ್ರ.
- system output: text = None
- correct answer: text = 'only if there is fever'
- class: MA-MISSED-ADVICE; dangerous: False; slipped through: n/a (m4 not yet run on m3 output)
- cause: advice sentence not extracted (no advice pattern matched this wording) (auto-suggested cause; a human should confirm)

## 4. natural extraction error (m3 rules, DEV, in-sample)

- id: `m1-h6-000` (family/topic: h_followup__f2)
- input: ಲಕ್ಷಣಗಳು ಮುಂದುವರಿದರೆ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ.
- system output: text = None
- correct answer: text = 'if the symptoms continue, consult a doctor'
- class: MA-MISSED-FOLLOWUP; dangerous: False; slipped through: n/a (m4 not yet run on m3 output)
- cause: follow-up instruction not extracted (pattern gap) (auto-suggested cause; a human should confirm)

## 5. PLANTED transcript error that slipped through (m4 text-only, DEV)

- id: `E4-T-a-0001` (family/topic: a_fever_cough__f1)
- input: conversation m1-a1-000: transcript edit at [61,66): deleted 'ಇಲ್ಲ' | original turns: ಮಗುವಿಗೆ ಎಷ್ಟು ದಿನದಿಂದ ಜ್ವರ ಇದೆ? / ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ, ಅತಿಸಾರ ಇಲ್ಲ.
- system output: no flag on /symptoms/1/present (flags elsewhere: none)
- correct answer: /symptoms/1/present: spoken value False; record (from corrupted transcript) True must be flagged
- class: negation drop; dangerous: True; slipped through: True
- cause: text-only checks compare the record with the SAME corrupted transcript, so they agree; only a second, independent transcript or audio check (C7) can see this

## 6. PLANTED transcript error that slipped through (m4 text-only, DEV)

- id: `E4-T-b-0001` (family/topic: a_fever_cough__f1)
- input: conversation m1-a1-000: transcript edit at [50,53): 'ಇದೆ' -> 'ಇಲ್ಲ' | original turns: ಮಗುವಿಗೆ ಎಷ್ಟು ದಿನದಿಂದ ಜ್ವರ ಇದೆ? / ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ, ಅತಿಸಾರ ಇಲ್ಲ.
- system output: no flag on /symptoms/0/present (flags elsewhere: none)
- correct answer: /symptoms/0/present: spoken value True; record (from corrupted transcript) False must be flagged
- class: negation add; dangerous: True; slipped through: True
- cause: text-only checks compare the record with the SAME corrupted transcript, so they agree; only a second, independent transcript or audio check (C7) can see this

## 7. PLANTED transcript error that slipped through (m4 text-only, DEV)

- id: `E4-T-c-0002` (family/topic: c_stopped_early__f2)
- input: conversation m1-c4-001: transcript edit at [48,51): '500' -> '300' | original turns: ಜ್ವರ ಕಡಿಮೆ ಆದ ಮೇಲೆ ಏನು ಮಾಡಿದಿರಿ? / ಸೆಫ್ಯುರಾಕ್ಸಿಮ್ 500 mg ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳದೆ ಬಿಟ್ಟೆ. / ಉಳಿದ ಮಾತ್ರೆ ಹಂಚಿಕೊಳ್ಳ ಕೂಡದು.
- system output: no flag on /medications/0/dose_value (flags elsewhere: none)
- correct answer: /medications/0/dose_value: spoken value 500; record (from corrupted transcript) 300 must be flagged
- class: digit change; dangerous: True; slipped through: True
- cause: text-only checks compare the record with the SAME corrupted transcript, so they agree; only a second, independent transcript or audio check (C7) can see this

## 8. PLANTED transcript error that slipped through (m4 text-only, DEV)

- id: `E4-T-d-0007` (family/topic: c_stopped_early__f2)
- input: conversation m1-c4-006: transcript edit at [52,55): '೨೫೦' -> '೫೨೦' | original turns: ಜ್ವರ ಕಡಿಮೆ ಆದ ಮೇಲೆ ಏನು ಮಾಡಿದಿರಿ? / ಸಿಪ್ರೋಫ್ಲಾಕ್ಸಾಸಿನ್ ೨೫೦ mg ಮಾತ್ರೆ ತೆಗೆದುಕೊಳ್ಳದೆ ಬಿಟ್ಟೆ. / ಉಳಿದ ಮಾತ್ರೆ ಹಂಚಿಕೊಳ್ಳಕೂಡದು.
- system output: no flag on /medications/0/dose_value (flags elsewhere: none)
- correct answer: /medications/0/dose_value: spoken value 250; record (from corrupted transcript) 520 must be flagged
- class: digit-order swap; dangerous: True; slipped through: True
- cause: text-only checks compare the record with the SAME corrupted transcript, so they agree; only a second, independent transcript or audio check (C7) can see this

## 9. PLANTED transcript error that slipped through (m4 text-only, DEV)

- id: `E4-T-e-0014` (family/topic: d_no_antibiotic__f1)
- input: conversation m1-d1-005: transcript edit at [111,117): 'ಮಾತ್ರೆ' -> 'g' | original turns: ನೆಗಡಿ ಮತ್ತು ಕೆಮ್ಮು ಎರಡು ದಿನದಿಂದ ಇದೆ, ಆಂಟಿಬಯಾಟಿಕ್ ಕೊಡಿ. / ನೆಗಡಿಗೆ ಪ್ರತಿಜೈವಿಕ ತೆಗೆದುಕೊಳ್ಳ ಬಾರದು. / ಪ್ಯಾರಸಿಟಮೋಲ್ ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ ಮೂರು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ.
- system output: no flag on /medications/0/dose_unit (flags elsewhere: none)
- correct answer: /medications/0/dose_unit: spoken value 'tablet'; record (from corrupted transcript) 'g' must be flagged
- class: unit change; dangerous: True; slipped through: True
- cause: text-only checks compare the record with the SAME corrupted transcript, so they agree; only a second, independent transcript or audio check (C7) can see this

## 10. PLANTED transcript error that slipped through (m4 text-only, DEV)

- id: `E4-T-f-0001` (family/topic: b_cross_turn__f2)
- input: conversation m1-b3-002: transcript edit at [6,20): 'ಸೆಫ್ಯುರೋಕ್ಸಿಮ್' -> 'ಸೆಫಿಕ್ಸಿಮ್' (confusable_with (lexicon, either direction)) | original turns: ಈ ವಾರ ಸೆಫ್ಯುರೋಕ್ಸಿಮ್ ತೆಗೆದುಕೊಂಡಿದ್ದೀರಾ? / ಹೌದು. / ಕೆಮ್ಮು ಇದೆಯಾ? / ಹೌದು.
- system output: no flag on /medications/0/drug (flags elsewhere: none)
- correct answer: /medications/0/drug: spoken value 'cefuroxime'; record (from corrupted transcript) 'cefixime' must be flagged
- class: drug swap (confusable); dangerous: True; slipped through: True
- cause: text-only checks compare the record with the SAME corrupted transcript, so they agree; only a second, independent transcript or audio check (C7) can see this

## 11. PLANTED transcript error that slipped through (m4 text-only, DEV)

- id: `E4-T-g-0001` (family/topic: d_no_antibiotic__f1)
- input: conversation m1-d1-000: transcript edit at [109,113): 'ಒಂದು' -> 'ನಾಲ್ಕು' | original turns: ನೆಗಡಿ ಮತ್ತು ಕೆಮ್ಮು ಮೂರು ದಿನದಿಂದ ಇದೆ, ಆಂಟಿಬಯಾಟಿಕ್ ಕೊಡಿ. / ನೆಗಡಿಗೆ ಪ್ರತಿಜೈವಿಕ ಬೇಡ. / cetrizine ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಮೂರು ದಿವಸ ತೆಗೆದುಕೊಳ್ಳಿ.
- system output: no flag on /medications/0/frequency_per_day (flags elsewhere: C4)
- correct answer: /medications/0/frequency_per_day: spoken value 1; record (from corrupted transcript) 4 must be flagged
- class: frequency swap; dangerous: True; slipped through: True
- cause: text-only checks compare the record with the SAME corrupted transcript, so they agree; only a second, independent transcript or audio check (C7) can see this

## 12. PLANTED transcript error that slipped through (m4 text-only, DEV)

- id: `E4-T-h-0001` (family/topic: d_no_antibiotic__f1)
- input: conversation m1-d1-000: transcript edit at [119,123): 'ಮೂರು' -> 'ಹದಿನಾಲ್ಕು' | original turns: ನೆಗಡಿ ಮತ್ತು ಕೆಮ್ಮು ಮೂರು ದಿನದಿಂದ ಇದೆ, ಆಂಟಿಬಯಾಟಿಕ್ ಕೊಡಿ. / ನೆಗಡಿಗೆ ಪ್ರತಿಜೈವಿಕ ಬೇಡ. / cetrizine ಒಂದು ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಮೂರು ದಿವಸ ತೆಗೆದುಕೊಳ್ಳಿ.
- system output: no flag on /medications/0/duration_days (flags elsewhere: C4)
- correct answer: /medications/0/duration_days: spoken value 3; record (from corrupted transcript) 14 must be flagged
- class: duration swap; dangerous: True; slipped through: True
- cause: text-only checks compare the record with the SAME corrupted transcript, so they agree; only a second, independent transcript or audio check (C7) can see this

## 13. false alarm on an ERROR-FREE record (review burden, m4, DEV)

- id: `rec-m1-a1-001` (family/topic: a_fever_cough__f1)
- input: error-free record field /symptoms/1
- system output: C2: symptom 'chills' is not in the verifier's symptom list; cannot re-derive it; C6: symptom 'chills' unknown to the verifier: support cannot be confirmed
- correct answer: no flag (field matches gold)
- class: false alarm; dangerous: False; slipped through: False
- cause: verifier vocabulary gap (word not in m4's own list), so it cannot confirm support

## 14. false alarm on an ERROR-FREE record (review burden, m4, DEV)

- id: `rec-m1-a1-006` (family/topic: a_fever_cough__f1)
- input: error-free record field /symptoms/1
- system output: C2: symptom 'chills' is not in the verifier's symptom list; cannot re-derive it; C6: symptom 'chills' unknown to the verifier: support cannot be confirmed
- correct answer: no flag (field matches gold)
- class: false alarm; dangerous: False; slipped through: False
- cause: verifier vocabulary gap (word not in m4's own list), so it cannot confirm support

## 15. helper failure (m8 tfidf, dev)

- id: `tfidf:q001` (family/topic: amr)
- input: What is antimicrobial resistance?
- system output: abstained
- correct answer: card amr-what-is
- class: answer / low_similarity (score 0.21); dangerous: False; slipped through: False
- cause: similarity below the dev-tuned threshold (lexical/embedding mismatch)

## 16. helper failure (m8 tfidf, dev)

- id: `tfidf:q003` (family/topic: amr)
- input: AMR means what? drug resistance andre enu
- system output: abstained
- correct answer: card amr-what-is
- class: answer / low_similarity (score 0.19); dangerous: False; slipped through: False
- cause: similarity below the dev-tuned threshold (lexical/embedding mismatch)

## 17. helper failure (m8 ollama, dev)

- id: `ollama:q002` (family/topic: amr)
- input: ಔಷಧ ನಿರೋಧಕತೆ ಎಂದರೇನು?
- system output: abstained
- correct answer: card amr-what-is
- class: answer / low_similarity (score 0.52); dangerous: False; slipped through: False
- cause: similarity below the dev-tuned threshold (lexical/embedding mismatch)

## 18. helper failure (m8 ollama, dev)

- id: `ollama:q005` (family/topic: amr)
- input: ಆಂಟಿಬಯಾಟಿಕ್ ಅಗತ್ಯವಿಲ್ಲದಾಗ ತೆಗೆದುಕೊಂಡರೆ ಏನಾಗುತ್ತದೆ?
- system output: abstained
- correct answer: card amr-misuse-main-driver
- class: answer / low_similarity (score 0.52); dangerous: False; slipped through: False
- cause: similarity below the dev-tuned threshold (lexical/embedding mismatch)

