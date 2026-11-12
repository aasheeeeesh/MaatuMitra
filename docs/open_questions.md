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

## From m1_data (merged 20261110T180301Z)

- UNVERIFIED: age band for child syrup volumes was not added (no fetched age table). Child ml volumes are synthetic.
- Contract request: the lexicon CSV has no dose-unit column; ORS (sachet/ml) and iron-folic acid (mg iron, mcg folic acid) units are only in verified_by text. A unit column needs a contract change by the orchestrator.
- Numeric alias "625" for amoxicillin-clavulanate may be read by m3/m4 as a dose number; they should handle it.
- Optional ಸಲ ("times") was not generated; changing it would reshuffle all data. Decide at the next planned data change.
- Spaced form "ಕೊಡ ಬೇಡಿ" is an orthographic artefact kept only so NEG-W05 appears in >= 5 conversations; a native reviewer may prefer dropping W05 from the coverage rule.
- Outside my paths: m3_extract/tests/test_lexicon.py::test_multi_token_names_longest_match still expects ors spelled with short ಒ (ಒ.ಆರ್.ಎಸ್); the lexicon now has ಓ.ಆರ್.ಎಸ್.

## From infra (merged 20261110T180301Z)

- (D-110) Child syrup volumes in the regenerated data are synthetic and not checked against an age/weight table. UNVERIFIED.
- (D-110) How should the answer to a negative question (NEG-S07, -ಲ್ವಾ) be labelled in gold? Until decided, the generator does not produce it.

## From m4_verify (merged 20261111T141428Z)

## From the m4_verify fix pass (2026-11-11)

- **Test-access log location.** m4's guard logs any ALLOW_TEST=1 read to results/m4_verify/test_access_log.md, because m4 may only write inside its own folders. The brief's official log is results/test_access_log.md (written by `make eval-test`). Should `make eval-test` also read or merge m4's log? (Nobody set ALLOW_TEST in this pass, so the m4 log does not exist.)
- **Shared DEV guard.** m1, m3 and m7 may need the same allow-list guard (dev.txt + test.txt + test families + test.lock hashes). Modules may not import each other: should the orchestrator move m4_verify/split_guard.py into a shared helper (for example contracts/ or infra/)?
- **Contract gaps that C4 works around.** record.v1 has no age/weight, route or dose-form field, and drugs.csv has no unit column. m4 infers "child" from words in the transcript and allowed units from free-text lexicon notes plus an m4 config table. A record.v2 with age band, route and form, and a unit column in drugs.csv, would let C4 check instead of guess.
- **UNVERIFIED: paracetamol syrup in ml.** m4 allows ml for paracetamol only because the m1 data uses a paediatric syrup (D-104). No syrup strength (mg per 5 ml) was fetched, so every ml dose is flagged cannot_verify:liquid_strength.
- **UNVERIFIED: child word list** (ಮಗು, ಮಗೂ, ಮಕ್ಕಳ, ಕೂಸ, ಶಿಶು, ಪಾಪು, ಹಸುಗೂಸ; English child/baby/infant/kid/toddler/paediatric/newborn). ಮಗ/ಮಗಳು (son/daughter) are deliberately not cues. A native reviewer should confirm.
- **UNVERIFIED: new negation forms** (fused ಬೇಡ after a vowel sign or virama; ಇಲ್ರೀ, ಇಲ್ಲಪ್ಪ, ಬೇಡವಾ; negative question -ಲ್ವಾ; clause split after ಇದೆ/ಇಲ್ಲ; address words after an answer). None is native-validated, and none occurs in the real-text audit sentences.
- **How should an answer to a negative question be labelled?** (ಹೌದು after "ಜ್ವರ ಇಲ್ಲವಾ?"): m4 flags it as ambiguous; the m1 data does not generate it (NEG-S07 generate: false).
- **Oracle second transcript.** The E4 "second transcript" row uses the uncorrupted text, so it is an upper bound. The clean-record flag rate of C7 with a REAL second ASR output is not measured yet (needs two m2 ASR runs on the same dev audio).

## From m3_extract (merged 20261111T144008Z)

- UNVERIFIED Kannada forms added in the 2026-11-11 fix pass: fused ಜ್ವರವಿಲ್ಲ rule, ಪ್ಯಾಕೆಟ್ = sachet, ಎರಡೂವರೆ = 2.5, ಆಗಿದ್ದರೆ in the fever follow-up, short-vowel ORS as ASR output. Who confirms them?
- Not done from the Kannada review: ಗುಳಿಗೆ, ಟ್ಯಾಬ್ಲೆಟ್, inflected ಮಾತ್ರೆಯನ್ನು and ಮಾತ್ರೆಗಳನ್ನು as units; half-numbers other than ಎರಡೂವರೆ (for example ಒಂದೂವರೆ).
- Should m1 add ಒ.ಆರ್.ಎಸ್ to the shared lexicon variants instead of m3 holding it in data/asr_variants.yaml?

## From contracts (merged 20261111T233150Z)

- record.v2 age-band cut-offs and "ಮಗು = child" are an architect choice (UNVERIFIED); should they follow a WHO / national definition? (also in HUMAN_TODO)
- Strength versus dose convention for "500 mg tablet" with no count (UNVERIFIED, clinician to confirm).
- Should a "partly taken" status exist separately from "stopped_early"? (D-122 finding M3-M1 mentioned taken_partial.)
- Should U+200E / U+200F (direction marks) and U+061C also be rejected? They are not in the D-123 F6 list and are currently allowed.
- transcript.v1 has no speaker roles, so an extractor working from an ASR transcript can only write speaker "unknown". Does Phase C need a transcript.v2 with turn roles (or diarisation), or is speaker only meaningful on gold-text input?
- The validator cannot check that a ml dose of a liquid has a strength (it is a clinical rule left to m4). Confirm m4 owns this flag (CR-LIQUID-STRENGTH).

## From m1_data (merged 20261111T234406Z)

## From m1_data audio builder (2026-11-12)
1. TTS model is gated: ai4bharat/indic-parler-tts needs a logged-in HF account that accepted its terms (HTTP 401 for us). Can a team member provide a read token (stored only in .env as HF_TOKEN)? With it we can switch to Parler (named Kannada speakers Suresh, Anu, Chetan, Vidya per its model card) and get genuinely different speakers.
2. Is it acceptable to run third-party repo code (sulabhkatiyar/indic-tiny-tts-kannada, ONNX, male + female Kannada voices, CC-BY-4.0, MIT code, I read the ~600 lines: numpy + onnxruntime only)? The auto-mode classifier refused to execute it, so I did not. It would give two real speakers without a token.
3. Disk: free space fell from 13.6 GB to about 4.0 GB during this task while the Windows pagefile grew to 24.8 GB (modified 04:46). The 4 GB floor and the >= 9 GB final target cannot both be met until the machine is restarted or space is freed. Who frees space (restart, delete caches such as ~/.cache/codex-runtimes 1.8 GB, uv cache 5.7 GB)?
4. Common Voice Kannada: not on HF any more as a normal dataset (API returned nothing). Need a human to check Mozilla Data Collective licence and access.
5. The held-out voice rule is only weakly satisfied by the pitch-shifted MMS voice (same speaker model). Is that enough for the E1 protocol or must we wait for real second speakers?

## From m8_helper (merged 20261111T234650Z)

- card.v1 has no "approved" field. We use clinician_reviewed=true as "approved". Should the contract get an explicit review status?
- UNVERIFIED: does official Kannada text for these topics exist on ICMR/NCDC/MoHFW sites? Not fetched.
- UNVERIFIED: Kannada quality of nomic-embed-text beyond these 80 questions.
- The brief example topics (finish the course, leftovers, colds) are not stated in the fetched WHO pages; cards for them need other sources.

## From m7_eval (merged 20261112T002415Z)

## From m7_eval (2026-11-12)

- m2 output layout: m7 defined results/m2_asr/<run>/<split>/transcripts.jsonl (m7_eval/CONTRACT.md). m2 must follow it or tell m7.
- Mixed-split files: results/m8_helper/predictions_*.jsonl (and, once built, data/public_real/fleurs_kn_in_test_subset.jsonl) hold dev AND test rows. m7 drops the other split's rows, but it still opens the file. Should m8 and m1 write one file per split?
- E3 ablation is derived from stored per-check flags assuming the checks are independent (UNVERIFIED). Can m4 add a "disable check X" option?
- docs/severity.md lacks the advice/follow-up codes used by m3 and m7 (MA-MISSED-ADVICE, MA-EXTRA-ADVICE, MA-MISSED-FOLLOWUP, MA-EXTRA-FOLLOWUP, MA-WORDING-UNJUDGED); D-122 accepted adding them before any test run.
- Where do module test runs write their outputs for eval-test (configs/eval.yaml `inputs.test`)? Needs agreement with m3 and m4 before the single test run.
- E7: does the study need ethics approval (UNVERIFIED)? Kannada consent text not native-validated. SUS wording paraphrased (UNVERIFIED).

## From m1_data (merged 20261112T004444Z)

- Request (contracts/ untouched): manifest.v1 has no field for "file stored vs materialised on demand". Worked around with data/audio_index/tts_index.jsonl (`storage`). Consider an optional field.
- UNVERIFIED: audio bit-exactness on another machine or ffmpeg version; FLEURS licence page re-check.

## From m6_ui (merged 20261112T005833Z)

- m5 /approve (POST /records/{id}/approve) sets status approved and approved_by with NO flag check (D-123 F3). m6 no longer calls it, but it should be removed or gated like /save. Needs a small m5 change.
- m5 has no endpoint that lists records the caller may open. m6 live mode asks the user to type a record id and only lists patients (GET /patients). Request: GET /records returning id, patient, status and flagged count under the same row-level security.
- m5 has no transcript endpoint. m6 looks the transcript up locally by source_transcript_id; a record whose transcript is not in the local fixtures shows a load error.
- m5 rule: an edit that creates a NEW flag kind (not one of the original flags) can never be saved (409 'edited record is not cleanly re-verified'). Is that intended? The UI shows the refusal but cannot guide the physician.
- The role claim is decoded without verifying the signature (display only; m5 verifies). UNVERIFIED whether that is acceptable for the final audit.
- X-Frame-Options / frame-ancestors (F8): Streamlit 1.67 cannot set them; open unless a reverse proxy is added.
- Native review of the changed Kannada strings and a real-browser check are UNVERIFIED (see human_todo.md).

## From m5_backend (merged 20261112T011746Z)

- Contract request (m5 cannot edit contracts/): the access_case.v1 `resource` list lacks `records_list` and `transcript`; m5 uses resource "records" for those cases. Add both names if separate reporting is wanted.
- Where do real transcripts come from? m5 serves only files named `<encounter uuid>.json` placed by the operator or the seed. Integration (ASR) must write them there, or we add a transcripts table.
- Should status "approved" be removed from the schema now that only /save approves? (needs a migration)
- UNVERIFIED: MAATUMITRA_VERIFIER pointed at the real m4 verifier (Phase C integration).

## From integration (merged 20261112T013023Z)

- Should m5's verifier hook receive the encounter id so the transcript is bound to the encounter, not to a record field?
- Should a saved record be readable in m6 live (load without verify)? Today m6 cannot reopen it.
- Should the nurse keep read access to a record after it is saved? Today no (policy: draft/flagged only).
- Integration with real ASR and with record.v2 is UNVERIFIED.

## From m2_asr (merged 20261112T020635Z)

- (m2, UNVERIFIED) Model card of ARTPARK-IISc/whisper-small-vaani-kannada says `language: hi` in metadata and uses code `ka` in its usage example. A 6-clip dev check gave nearly identical CER with `kn` and `ka`; we used `kn`. Ask the authors which token was used in training.
- (m2, UNVERIFIED) Possible training-data overlap between the Vaani Kannada fine-tune (card lists FLEURS among training/evaluation data) and our FLEURS public_real clips. If overlapping, its public_real CER is optimistic. Not checked.
- (m2) m7_eval/experiments.py reads `r["file_name"]` from data/public_real/fleurs_kn_in_test_subset.jsonl, but that file has the key `file` (not `file_name`). If E1 crashes on public_real rows, m7 (or m1) needs to align the key. m2 writes audio_id = file stem for public_real, as m7 documents.
- (m2) The FLEURS subset file is named `..._test_subset.jsonl` but carries a per-row `split` (dev/test, m1's sentence-level split). m2 only reads rows with split == dev. Suggest m1 renames the file or documents this.
- (m2) m7 E1 groups by the run directory name. m2 writes `results/m2_asr/<model>/dev/transcripts.jsonl` (+ run.json) and also `results/m2_asr/dev/<model>/<hash8>.json` (one transcript.v1 per file). The folder `results/m2_asr/dev` therefore looks like a "run" named `dev` to m7 and is skipped (it has no `dev/transcripts.jsonl`).
- (m2) Per-file JSON names are 8 hex chars of sha1(audio_id) because the repo sits in a deep path and Windows MAX_PATH is 260 (LongPathsEnabled = 0). The real audio_id is inside each JSON.
- (m2) The baseline H2 comparison in m7 matches the run name substring `faster-whisper-small`; that run name is used.
- (m2, contract) transcript.v1 has no field for decoding settings; they are stored in `results/m2_asr/<model>/run.json`. A `settings` field in a transcript.v2 would help.
- (m2) Exact-token critical-term recall (shared definition with m7) undercounts: ref 'ಇಲ್ಲ' vs hyp 'ಇಲ್ಲಾ' is a miss. A spelling-variant-tolerant version needs a Kannada reviewer-approved variant list (see human_todo).
