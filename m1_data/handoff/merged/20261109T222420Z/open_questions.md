## m1_data (2026-11-09/10)

1. **Split interpretation** (orchestrator): I read "split by template family" as families
   INSIDE each category (a)-(i) (22 families, each category in both splits). Using the 9
   categories themselves as families would leave whole phenomena out of test. OK?
2. **Negation table gap** (architect / m3 / m4): `ಇಲ್ಲದೆ` ("without", e.g. ವೈದ್ಯರ ಚೀಟಿ ಇಲ್ಲದೆ,
   attested in KN-3) matches NO table entry (not V01: ಇಲ್ಲ is not a verb stem). It is used
   in templates c2 and d2 (not as a record-item negation). Should the table get an entry?
3. **Clause splitting hazard**: units/abbreviations with dots (`ಎಂ.ಜಿ`, `ಒ.ಆರ್.ಎಸ್`) contain
   `.`, which the table's CL01 splitter treats as a clause boundary inside a medication span.
4. **Gold convention**: "stopped before finishing" and "ಇದು X ಅಲ್ಲ" are `negated: true` (see
   docs/annotation_guide.md section 4). Clinically acceptable? A future record.v2 could add
   an adherence field.
5. **Dose ranges** are from US openFDA labels (UNVERIFIED for Indian practice); 12 drugs have
   none (UNVERIFIED). Paracetamol 1000-1000 mg (US OTC) means Indian 500/650 mg strengths
   fall outside the range; the generator therefore speaks paracetamol as 1000 mg or 1-2 tablets.
6. **NLEM rows** read only by automated JSON extraction (ibuprofen, ondansetron, metformin,
   iron-folic acid) and odd printed strengths (cefadroxil 100 mg, levofloxacin 300 mg): UNVERIFIED.
7. **Kannada** templates and drug spellings: not native-validated; 164/221 template words
   unattested in fetched sources (results/m1_data/unattested_tokens.json).
8. **Licences** of NLEM PDF, WHO AWaRe portal, ISMP PDF and the Wikipedia pages: UNVERIFIED.
9. **Repository data licence**: generated files carry `licence_spdx: NOASSERTION` until the
   project licence is chosen (LICENSE_PLACEHOLDER.md).
