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

## From m6_ui (merged 20261110T081219Z)

## m6_ui (2026-11-10)

1. **Human-confirmed flags can never be saved.** m5's `POST /records/{id}/save` refuses (409) whenever any verdict check flags. The UI lets a reviewer confirm a flagged value ("Yes, this is correct"), but the record then stays "approved, NOT saved" forever unless an edit makes the verifier pass. Is a reviewer override wanted (for example a `review.v1` contract carrying each flag's answer + reason, accepted by m5 with an audit entry)? Contract change needed; not done by m6.
2. **record_id vs m5 database UUID.** record.v1 `record_id` is not the id m5 uses in its URLs. m6 live mode uses a stop-gap JSON map (`M6_SERVER_IDS`). Should m5 expose a lookup by `record_id`?
3. **Kannada UI wording (UNVERIFIED, not native-validated):** all of `m6_ui/i18n/kn.json`.
4. **Conjunct rendering on Android/Linux (UNVERIFIED):** checked only in headless Edge on Windows.
5. **360 px layout (UNVERIFIED):** headless screenshots of the live Streamlit app were blank.
6. **Variable font support on old Android WebViews (UNVERIFIED).**
7. **Live mode end to end (UNVERIFIED):** HttpGate tested only with a fake HTTP transport; SubprocessVerifier only with a fake command.

## From m3_extract (merged 20261110T084736Z)

## From m3_extract (nlp-engineer, 2026-11-10)

1. UNVERIFIED words in the rules pipeline: ಬಾರಿ, ಸಾರಿ, ಒಮ್ಮೆ ("times", "once"), ದಿನಕ್ಕೆ ("per day"), ಚಮಚ -> teaspoon, number words 11/12/16/20/30/100. Verified on Wiktionary (2026-11-10): 1-10, 13-15 (14 page and its number box), ಅರ್ಧ, ಸಲ, ದಿನ, ದಿವಸ, ವಾರ, ತಿಂಗಳು, ಚಮಚ (= spoon), ಜ್ವರ, ಕೆಮ್ಮು, ಚಳಿ, ನೋವು. Not native-validated.
2. Severity taxonomy gap: docs/severity.md has no class for a missed / extra advice item or follow-up. m3 counts them as MAJOR (MA-MISSED-ADVICE, MA-EXTRA-ADVICE, MA-MISSED-FOLLOWUP, MA-EXTRA-FOLLOWUP) under rule 5 ("when unsure, MAJOR"). Advice wording that differs from gold is MA-WORDING-UNJUDGED (MAJOR), because "same meaning" cannot be judged automatically. The architect / m7_eval should confirm or change this so every module scores advice the same way.
3. What is a "field"? m3 uses: medication 6, symptom 2, advice 2, follow-up 1; a missed item = 1 error; an extra item = +1 field and 1 error; patient_ref / encounter_type are NOT scored (they are supplied context, not extracted). Errors-per-1,000 depend on this definition; m7_eval should use one shared definition.
4. Negation table: NEG-S03 (-ದಿದ್ದರೆ "if not") is a conditional, not a negation of the record item. m3 treats it as "conditional" (selects the "does not" follow-up gloss, never sets `negated`). Should the table get a separate `type: conditional_negative`?
5. Negation table: clause punctuation NEG-CL01 splits at every ".", including inside ಎಂ.ಜಿ and ಒ.ಆರ್.ಎಸ್. m3 skips a dot that has a letter on both sides. Should the table say this?
6. Question scope (found on dev_holdout, fixed in rules v2): in "ನನಗೆ ಜ್ವರ ಇದೆ, ... ತೆಗೆದುಕೊಳ್ಳಬಹುದಾ? / ಇಲ್ಲ." the bare ಇಲ್ಲ answers only the question part. m3 v2 treats a comma clause that ends in ಇದೆ-type words as a statement. m4_verify's C8 rule ("bare ಇಲ್ಲ with no resolvable question") may want the same distinction (m4 must write its own rule).
7. ASR: no transcripts from m2_asr existed on 2026-11-10, so no ASR-input extraction was run (AGENT 4 step 5 partly done).
8. The LLM pipeline sees the same closed vocabulary as the rules (drug and symptom enums from our lists). That is fair for comparison but means neither pipeline can name a drug or symptom outside the lists.

## From m5_backend (merged 20261110T160937Z)

- m5 fix pass: contracts request: access_case.v1 `attack` has no value for saved-gate attacks, so the 13 new cases use `mass_assignment` / `id_guess`. Ask the architect whether to add `save_gate`.
- m5 fix pass: who supplies the real verifier? m5 cannot import m4 (module rule). Proposed: the integration layer passes an adapter to `create_app(verifier=...)` that loads the stored record AND its transcript (m4 `verify(record, transcript)` needs both; m5 stores no transcripts). UNVERIFIED: where the transcript comes from at integration.
- m5 fix pass: should a saved record require status `approved` first (the old `/approve` step)? Currently `/save` itself is the approval (resolutions + approver in one transaction), so draft and flagged records can be saved if every flag is resolved.
- m5 fix pass: Docker path for the new `OWNER_DB_PASSWORD` is UNVERIFIED (no Docker).
- m5 fix pass: R-order (does physical row order of the research table leak chronology?) still needs multi-month data. UNVERIFIED.
