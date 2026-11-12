## m4_verify (Phase C, 2026-11-12)

- Oral route convention conflict: contracts/README.md ("route not said: null, even if the formulation implies it") vs data/gold_v2 (route "oral" with the span on the formulation word, 324 dev medications). m4 accepts an oral-form word as support for "oral" (never for injections). Architect to decide.
- verdict.v1 allows only C1..C8, so status, route and strength checks live inside C2..C5; E3 ablation cannot switch them off separately. Should there be a verdict.v2 with more ids?
- Speaker cannot be verified: transcript.v1 has no speaker roles. m4 only flags "prescribed by patient/caregiver" from the record's own speaker field.
- UNVERIFIED: all v2 Kannada word lists (not native-validated); age band cut-offs; paracetamol syrup range (adult tablet range used).
- C7 (ASR risk) does not look at the new v2 evidence spans (route, strength, status).
