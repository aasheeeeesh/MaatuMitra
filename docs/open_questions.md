# Open questions

Things nobody has verified yet, with what to check. Builders add items through
`<module>/handoff/open_questions.md`.

## From the architect (2026-11-09)

1. **manifest.v1 has no conversation_id.** How does m1 link an audio file to its gold
   conversation? Options: encode it in the file name, use `parent_id`, or bump to
   manifest.v2 with a `conversation_id` field. m1 decides; the architect approves a v2.
2. **One evidence span per medication** (record.v1) must cover drug, dose, frequency and
   duration; for long sentences the span is long. Is that precise enough for C2/C6? If
   not, record.v2 with per-field evidence.
3. **verdict.v1 has no "disabled checks" field.** E3 ablation verdicts are still valid, but
   do not say which check was removed; the run config must record it.
4. **pgserver**: which PostgreSQL major version does version 0.1.4 bundle, what is its
   licence, does it run on Windows? (m5 must verify before use.) Alternative: EnterpriseDB
   portable PostgreSQL 16 zip (URL, licence, size UNVERIFIED).
5. **docker-compose image digest** (postgres:16.15 @ sha256:f9a7b9eb...) was read from the
   Docker Hub tags API but never pulled (no Docker here).
6. **Negation table**: every rule is a hypothesis; especially the architect additions
   (-ಬಾರದು / -ಕೂಡದು / -ಬೇಡಿ fused endings, the stricter -ದಿದ್ದರೆ rule, traps ಇದೆ, ಬಂದಿದೆ,
   ಇದ್ದರೆ, ಓದಿದ್ದರೆ, ಬೇಡಿಕೆ) need a real Kannada speaker.
7. **uv bug**: why does `uv python install 3.11` fail on this laptop with "Missing expected
   target directory for Python minor version link"? Worked around; root cause unknown.
8. **CI** has never run; setup-uv v10 behaviour with `.python-version` is UNVERIFIED.
9. **Claude Code `skills:` preloading** in agent files: documented, but not yet observed working.

## From m5_backend (merged 20261109T222036Z)

## m5_backend (2026-11-10)

1. UNVERIFIED: the E5 matrix has run only locally (PostgreSQL 16.15, Windows 11). The CI job (snippet in m5_backend/handoff/human_todo.md) has not run yet.
2. UNVERIFIED: authenticity of the EnterpriseDB PostgreSQL 16.15 zip (no vendor checksum found) and its third-party licence notices.
3. Request to the architect: `.env.example` has `POSTGRES_USER=owner_role`. With Docker, `POSTGRES_USER` becomes the image's SUPERUSER, which would make owner_role a superuser. Please change the placeholder to `POSTGRES_USER=mm_bootstrap` (m5 may only add keys). dbtool refuses to run if owner_role is a superuser.
4. Clinical scope: nurses cannot read approved/saved records ("draft records" read as draft|flagged). Intended?
5. Consent workflow: no app role can create or change consents (default deny). Who records consent in the product?
6. The saved gate trusts the verdict.v1 the client sends; it does not re-run m4_verify, and verdict.v1 has no way to mark a flag "resolved by a human". Should m5 store verdicts server-side / should a contract bump add resolution?
7. Residual (by design, documented): raw `api_login` / `owner_role` / bootstrap credentials can set GUCs, SET ROLE, or disable triggers; they must stay in `.env` on the API host only.
8. The rule-of-three bound 3/1385 assumes independent trials; the cases share policies, so it is optimistic.

## From m4_verify (merged 20261109T222036Z)

## m4_verify open questions (2026-11-10)

1. **Contract gap: turns in transcript.v1.** Cross-turn negation needs turn boundaries. m4 uses the gold.v1 convention (turns joined by "\n"). Real ASR transcripts of one audio file will have no newlines, so cross-turn answers cannot be resolved there. Request to the architect: optional `turns[{speaker, char_start, char_end}]` in a future transcript.v2, or diarisation in m2.
2. **Contract gap: patient link.** transcript.v1 has no patient_ref, so a wrong `patient_ref` is invisible to the verifier unless an encounter index `{audio_id: patient_ref}` is passed (C6). Who provides it in the integrated pipeline (m5 encounter table?)
3. **Lexicon gap: allowed units / dose forms.** The drug CSV has no allowed-unit or dose-form column; C4 uses a config default (`allowed_units`). Should m1 add `allowed_units` (and a range per form, e.g. syrup in ml)?
4. **Lexicon value:** paracetamol `adult_dose_range_mg = 1000-1000` in data/lexicon/drugs.csv (see human_todo). UNVERIFIED.
5. **UNVERIFIED Kannada:** all negation rules, number words, unit/frequency/duration phrases and symptom names in m4_verify are AI-written hypotheses (see human_todo).
6. **C7 threshold UNTUNED** (0.6 placeholder) until DEV ASR output exists.
7. **E4 on fixtures only:** 6 gold conversations give few unique mutations per type (3 to 90). The catch rates are not evidence about real data until re-run on m1 DEV gold.
8. **Audit optimism:** negation rules were fixed using the same 52 Wikipedia sentences they were then measured on; no held-out audit yet.

## From m1_data (merged 20261109T222420Z)

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
