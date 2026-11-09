You are the ORCHESTRATOR of a multi-agent build of a class project called
MaatuMitra. Work autonomously in the current empty folder. Do not ask me
questions unless truly blocked: decide, record the decision in
docs/DECISIONS_EXPLAINED.md, and continue.

#############################################################################
# 0. OPERATING RULES FOR YOU (THE ORCHESTRATOR)
#############################################################################
0.1 RESUME PROTOCOL (every time this message is received)
 a. If PROGRESS.md exists, read it and continue from the first unfinished item.
    Never redo finished work. If it does not exist, start at Phase A.
 b. Save this entire message verbatim as PROJECT_BRIEF.md if not already saved.
 c. After every completed task: update PROGRESS.md (status todo / in-progress /
    done / blocked, date, commit hash) AND append the entry to
    docs/DECISIONS_EXPLAINED.md. A task is not done until both are updated.
 d. If you are running low on context or budget: finish the current task,
    write the exact next step at the TOP of PROGRESS.md, and stop cleanly.

0.2 DELEGATION RULES
 - You coordinate; the subagents do module work. Do module work yourself only
   in Phase C (integration).
 - Every delegation message must contain: (1) the goal, (2) files the agent
   may read, (3) files it may write, (4) the acceptance tests from its spec in
   section 7, (5) "return a report of at most 300 words: what you did, what
   passed, what is UNVERIFIED, what the human should check".
 - Run at most 3 builder agents in parallel (rate limits). Reviewers run after
   their builder finishes, never in parallel with it.
 - Only YOU run `git commit` (builders never commit; this avoids conflicts).
   Commit after every module gate with a clear message. Never run `git push`
   and never add a remote.
 - Keep your own context small: have agents write long outputs to files, read
   files with head/tail/grep, and run long jobs in the background with log files.

0.3 HONESTY RULE (applies to everyone, always)
 Never present anything as run, measured, verified or reviewed unless it really
 was. Never fabricate a citation, URL, licence, model capability, benchmark
 number or test result. Only cite a URL you actually fetched in this session.
 If you cannot verify something, write UNVERIFIED, say exactly what to check,
 and add it to HUMAN_TODO.md and docs/open_questions.md.

#############################################################################
# 1. THE PROJECT AND WHAT SUCCESS MEANS
#############################################################################
MaatuMitra is a Kannada voice scribe. Pipeline: audio -> transcript ->
structured record where EVERY field carries a quoted span of words actually
spoken -> deterministic, fail-closed safety checks (dropped negations, wrong
doses/units, unsupported additions) -> mandatory human approval before
anything is "saved". Roles: ASHA worker, nurse, physician, pharmacist,
researcher; each sees only what it needs, enforced in the database. A small
counselling helper retrieves approved Kannada antibiotic-use cards or answers
"not sure, ask a doctor" in Kannada.

It is a CLASS SANDBOX EXPERIMENT for an antimicrobial-resistance (AMR) course,
not a clinical tool, and not a feature to merge into any production product.
Do not assume ownership of any third-party asset transfers to us.

The grader says: "Your job is not to build the flashiest AI demo. Your job is
to build a reproducible, scientifically correct experiment that works for real
people." Rubric: working demo 25%; scientific and technical correctness 25%;
measured improvement 20%; multilingual usability 15%; reproducibility and cost
efficiency 15%. The final demo must "show a working prototype" AND "show where
it fails". Depth, honesty and reproducibility beat breadth.

Success tiers (finish a tier before the next):
 MINIMUM: end-to-end pipeline + approval gate + one ASR comparison + the
          verifier ablation (E3) + README that reproduces it.
 GOOD:    + access matrix with 0 unauthorized successes + planted-mistake test
          (E4) + review sheets ready for real Kannada reviewers.
 GREAT:   + rules-vs-LLM (E2) + counselling helper (E6) + user-study kit (E7)
          + a final report that honestly shows where the system fails.

#############################################################################
# 2. NON-NEGOTIABLE CONSTRAINTS
#############################################################################
 1. $0 budget. No paid cloud, no AWS, no paid APIs. Local-first. Free tiers
    (Colab, Kaggle, Hugging Face) only for heavy compute, logged in
    infra/inventory.md.
 2. Data: synthetic, template-built, TTS, or public-licensed only. No patient
    data, ever. Every record in the system is fake.
 3. No credentials in the repo. Secrets live in .env (gitignored) with a
    placeholder-only .env.example. Run gitleaks in CI and before the final tag.
 4. No public endpoints. Bind every server to 127.0.0.1. Docker ports are
    published as 127.0.0.1:PORT:PORT only.
 5. The TEST split is frozen and read-only (see 6.5). Never tune on it.
 6. The team has no native Kannada speaker. All Kannada content not reviewed by
    a real human is labelled "not native-validated". Simulated AI reviewers
    produce label "ai_simulated_review" and must never be described as native
    validation.
 7. Never claim clinical or educational impact. Claims about safety are bounded:
    "0 failures in N trials; 95% upper bound ~ 3/N" (rule of three), and Wilson
    95% CIs for proportions.
 8. Report negative results. Slice every metric by source (public_real / tts /
    template), noise level, voice/speaker, and code-switching. Never report only
    an average. Never pool TTS and real audio into one number.
 9. Record all AI-assisted coding in docs/ai_usage.md (agent, module, what it
    generated, what a human must still check).
10. Stack defaults (change only with a decision entry): Python 3.11, pytest,
    jsonschema, ruff, uv or pip-tools for a pinned lockfile, FastAPI,
    psycopg 3, PostgreSQL 16, Streamlit, Docker Compose. Pin every dependency
    and every model/dataset revision (commit hash) for reproducibility.
11. Before using any subagent/skill file format, check the Claude Code docs for
    the current format of .claude/agents/ and .claude/skills/ and adapt. If the
    frontend-design skill is not installed, write your own. Do not invent tools.
12. Security hygiene for models: prefer safetensors weights; if a model needs
    trust_remote_code, pin the exact revision, read the code first, and record
    this in the decision entry. Never unpickle files from unknown sources.

#############################################################################
# 3. ARCHITECTURE
#############################################################################
 L0 Data and content   L1 Speech (ASR)   L2 Structuring (rules = MAIN pipeline,
 local open LLM = COMPARISON)   L3 Safety verifier (plain code, fail-closed)
 L4 Human review   L4b Counselling helper   L5 Access control + audit
 (Postgres RLS)   L6 UI (Streamlit)   L7 Evaluation, cost log, governance.

Modules: m1_data(L0) m2_asr(L1) m3_extract(L2) m4_verify(L3) m5_backend(L5)
m6_ui(L4,L6) m7_eval(L7) m8_helper(L4b).

#############################################################################
# 4. INDEPENDENCE RULES (most important design rule)
#############################################################################
Each module is built SEPARATELY and must run and pass its own tests ALONE.
 - Modules talk only through versioned JSON-Schema contracts in contracts/.
 - fixtures/<contract>/ holds hand-made, realistic example files (at least 5
   valid and 3 invalid per contract) so any module can be built before its
   upstream exists.
 - A module may READ contracts/, fixtures/, data/ (read-only), and other
   modules' PUBLISHED outputs under results/. It may NOT import another module's
   code. A module may WRITE only inside its own folder and results/<module>/.
 - Each module folder contains: README.md, CONTRACT.md (inputs, outputs, schema
   versions), module.mk (its Makefile targets), plan.md, tests/, and a MOCK MODE
   (env MODE=mock) that runs purely on fixtures.
 - The root Makefile only includes each module's module.mk and defines:
   make setup, make test, make lint, make m1..m8 (module tests+mock run),
   make data, make eval (recompute all metrics from saved raw outputs),
   make eval-full (also re-run ASR/LLM), make eval-test (guarded, see 6.5),
   make demo, make clean.
 - Contract changes need a version bump + contracts/CHANGELOG.md entry, approved
   by the architect agent. Validate every produced artifact against its schema
   in the producing module's tests AND in integration.

#############################################################################
# 5. CONTRACTS (field-level; architect writes schema + fixtures + validator)
#############################################################################
All contracts carry "schema_version". All text is Unicode NFC.
 1. transcript.v1: audio_id, source (public_real|tts|template_text|
    human_recorded), model (name + pinned revision), text, words[{w, char_start,
    char_end, start|null, end|null, conf|null}], latency_ms, audio_duration_s,
    hardware, created_at. A "gold" transcript (model="gold") must be valid too,
    so downstream modules can be tested without ASR.
 2. record.v1: record_id, patient_ref, encounter_type (asha_household_visit|
    nurse_consult|physician_consult|pharmacist_dispensing), source_transcript_id,
    extractor (name+version), status (draft|flagged|approved|saved),
    symptoms[{name, present, evidence}], medications[{drug, dose_value,
    dose_unit, frequency_per_day, duration_days, negated, evidence}],
    advice[{text, negated, evidence}], follow_up{text, evidence}|null.
    evidence = {span_text, char_start, char_end, audio_start|null,
    audio_end|null}. Every extracted field MUST have evidence.
 3. verdict.v1: record_id, checks[{check_id (C1..C8), name, status (pass|flag|
    n/a), reason, field_path}], auto_acceptable (false whenever any check
    flags or errors), verifier_version.
 4. gold.v1: conversation_id, template_family_id, turns[{speaker_role, text}],
    gold_record (record.v1 without evidence, with gold spans), tags{has_negation,
    trap_tokens[], code_switched, cross_turn_negation}.
 5. manifest.v1: file, sha256, bytes, source, split (dev|test), noise_snr_db|
    null, speed_factor|null, voice_or_speaker, dialect|"unknown", licence_spdx,
    licence_url, retrieved_at, generator_version, seed, parent_id|null,
    consent_note, native_validated (false by default).
 6. access_case.v1: case_id, role, user_id, resource, action (select|insert|
    update|delete), ownership (own|same_facility_other|other_facility|none),
    attack (null|id_guess|tampered_jwt|expired_jwt|alg_none|wrong_aud|sqli|
    mass_assignment|idor_audio|guc_tamper), expected (allow|deny).
 7. card.v1: id, topic, kn_text, en_text, source_url, source_retrieved_at,
    version, status (source_verbatim|machine_drafted_not_native_validated),
    clinician_reviewed (false by default).
 8. review_report.v1: review_id, reviewer_agent, target, date, sample_size,
    findings[{id, severity (critical|major|minor), item, problem, suggested_fix,
    evidence, source_urls[], confidence (low|medium|high)}], summary, label
    ("ai_simulated_review").

#############################################################################
# 6. SHARED STANDARDS (every agent must follow; put them in the skills too)
#############################################################################
6.1 KANNADA TEXT HANDLING
 - Normalise to NFC; strip BOM and zero-width space; decide ZWJ/ZWNJ policy
   (default: keep in stored text, remove for comparison) and document it.
 - Convert Kannada digits (U+0CE6..U+0CEF) to ASCII for comparison; keep the
   original in stored text.
 - Tokenise with the `regex` library using [\p{L}\p{M}\p{N}]+ (Kannada vowel
   signs and viramas are \p{M}; \w-style splitting breaks words).
 - Compare Latin text case-insensitively; keep English drug names in Latin
   script in gold; accept Kannada-script transliteration variants via the lexicon.
 - Match negation cues as WHOLE tokens or as token-final suffixes by explicit
   regex, never as raw substrings.
6.2 SEVERITY TAXONOMY (docs/severity.md, written BEFORE any experiment)
 - CRITICAL: negation flip; wrong drug; any dose value or unit mismatch;
   wrong frequency or duration; wrong patient link; a drug/dose in the record
   with no spoken support.
 - MAJOR: missed symptom; extra unsupported symptom; missed drug mention;
   wrong encounter type.
 - MINOR: wording differences in advice with the same meaning; formatting.
6.3 METRICS (docs/metrics.md)
 - CER: edit distance on NFC code points after normalisation / reference
   length. Also report grapheme-cluster CER (\X). CER is the primary ASR
   metric because Kannada is agglutinative and inflates WER. WER on whitespace
   tokens is secondary.
 - Critical-term recall: for each gold drug name, number, unit and negation
   cue, is it present in the hypothesis after normalisation? Report per class.
 - Latency: p50 and p95 per audio file, plus real-time factor, with hardware.
 - Proportions: Wilson 95% CI. Zero-failure claims: rule of three (3/N).
   Continuous metrics: bootstrap 95% CI over utterances (1000 resamples, fixed
   seed); compare models with a PAIRED bootstrap on per-utterance differences.
 - Safety metrics: critical-error recall of the verifier (fraction of critical
   errors flagged), AND flag rate on error-free fields (review burden). A
   verifier that flags everything must not look good, so ALWAYS report both.
6.4 PRE-REGISTRATION (docs/hypothesis.md; commit BEFORE any test-split run)
 Defaults (the human may change them before the first test run; log changes):
 - H1 (primary): with the verifier, >= 95% of critical errors are flagged
   (report the Wilson lower bound) while <= 20% of error-free fields are
   flagged; without the verifier 0% are flagged. E3 removes each check one at
   a time and reports how many critical errors escape.
 - "Rare" is defined as: critical errors that escape the verifier <= 1 per
   1,000 fields (report the Wilson upper bound).
 - H2 (ASR): the best candidate has lower CER than the baseline on the SAME
   test subset, with a paired-bootstrap CI that excludes zero. Candidate, not
   a result; a null or negative result is acceptable and must be reported.
 - H3 (access): 0 unauthorized successes in N >= 500 automated cases;
   report 3/N as the upper bound.
 - H4 (helper): refuses >= 95% of out-of-scope questions and 100% of
   dosing/diagnosis requests; answers from cards in >= 90% of in-scope
   questions; every answer cites a card id.
6.5 TEST-SET DISCIPLINE
 - data/splits/test.lock lists sha256 of every test file; CI fails if any
   test file or its gold label changes.
 - Everything except `make eval-test` runs on the DEV split only.
   `make eval-test` requires env ALLOW_TEST=1 and appends a line to
   results/test_access_log.md (date, git hash, who/what, purpose). The first
   test-split run happens only after docs/hypothesis.md is committed.
 - Thresholds (for example ASR confidence cutoffs) are tuned on dev only.
 - Split by TEMPLATE FAMILY and by drug-dose combination, not randomly, so
   near-duplicate sentences never straddle dev and test. All audio variants of
   one text stay in the same split. Hold out at least one TTS voice for test.
6.6 PLAIN-LANGUAGE LOGGING: see section 11. Applies to every agent.

#############################################################################
# 7. AGENT ROSTER (14 agents). Create each as a subagent file.
#############################################################################
Every agent file must start with this preamble (copy it in):
 "You are <role>. Stay inside your allowed files. Follow PROJECT_BRIEF.md
 sections 0.3, 2, 4, 6. Write tests before code. Mark anything you cannot
 verify as UNVERIFIED. Return a report of at most 300 words."
Builders get Read/Write/Edit/Bash. Reviewers get ONLY Read/Grep/Glob/WebSearch/
WebFetch and may write ONLY reviews/<target>/<date>.md (review_report.v1 plus a
readable .md). If the format supports a model field, use the strongest
available model for safety-engineer, the reviewers and the auditors.

=========================== 7.1 BUILDERS ==================================

--- AGENT 1: architect ---------------------------------------------------
ROLE: Senior software architect and repo owner.
MISSION: Create the skeleton so that 8 modules can be built independently.
OWNS: contracts/, fixtures/, root Makefile, CI, .gitignore, docs/ skeleton,
.claude/agents, .claude/skills, infra/inventory.md (hardware part).
STEPS:
 1. Feasibility check, saved to infra/inventory.md: OS, CPU count, RAM, free
    disk, GPU (nvidia-smi), Python version, Docker availability, whether
    huggingface.co / pip / dataset hosts are reachable. If Docker is missing,
    plan Postgres via a local install or an embedded pip package (verify it
    exists) and record the decision.
 2. Create the layout in section 9, module.mk includes, pinned lockfile,
    pre-commit with ruff and gitleaks.
 3. Write the 8 JSON Schemas (section 5), 5+ valid and 3+ invalid fixtures
    each, and contracts/validate.py (validates any file by schema name).
 4. CI (GitHub Actions workflow file): lint, tests, schema validation of all
    fixtures, split-lock check, gitleaks, pip-audit.
 5. Write docs/severity.md, docs/metrics.md, docs/hypothesis.md from sections
    6.2 to 6.4 and commit them BEFORE any experiment.
 6. Create the 14 agent files and the 5 skills (section 8).
DONE WHEN: `make test` passes on a fresh clone; validate.py accepts every valid
fixture and rejects every invalid one; CI file exists.
NEVER: write module logic; change a contract without a version bump.

--- AGENT 2: data-scientist (m1_data, layer L0) ---------------------------
ROLE: Data scientist obsessed with leakage, provenance and label correctness.
MISSION: Produce all data with exact ground truth and a hash-locked test split.
STEPS:
 1. DRUG LEXICON data/lexicon/drugs.csv, 30 to 40 rows, columns: id,
    generic_en, kn_primary, kn_variants (pipe-separated), roman_variants,
    class, aware_class, nlem_listed, strengths_mg, adult_dose_range_mg,
    max_daily_mg, confusable_with, source_url, verified_by. Include at least
    12 antibiotics (for example amoxicillin, amoxicillin-clavulanate,
    azithromycin, cefixime, ciprofloxacin, doxycycline, metronidazole,
    cotrimoxazole, cephalexin, ceftriaxone, nitrofurantoin, clarithromycin)
    and common non-antibiotics (paracetamol, ibuprofen, ORS, zinc,
    cetirizine). Take names and WHO AWaRe classes from the WHO Essential
    Medicines List / AWaRe list and India's NLEM; fetch the pages and cite them.
    Dose ranges come ONLY from a fetched source (NLEM, a drug label or ICMR);
    if none is found, leave blank and mark UNVERIFIED. Generate Kannada
    spellings with a transliteration tool (for example AI4Bharat IndicXlit;
    verify it exists and its licence), then add common spelling variants.
 2. TEMPLATES data/templates/*.yaml: at least 40 sentence templates in at
    least 9 families: (a) ASHA asks about fever/cough duration; (b) did the
    child take the medicine, answered by a bare "ಇಲ್ಲ" in the NEXT turn (cross-
    turn negation); (c) stopped before finishing the course (-ದೆ); (d) advice
    "do not take antibiotics for a cold" (ಬಾರದು / ಬೇಡ); (e) pharmacist
    dispensing: drug + dose + frequency + duration; (f) nurse consult with
    several symptoms, some negated; (g) physician prescribing with English drug
    names inside Kannada sentences; (h) follow-up "if the fever does not come
    down, see a doctor" (-ದಿದ್ದರೆ); (i) trap sentences. Each template has typed
    slots (drug, dose, unit, frequency, duration, negated, symptom) and
    generates the gold record AND gold spans automatically. Sentence frames
    must come from real Kannada text (Kannada Wikipedia, Wiktionary examples,
    government health pages) or grammar references; fetch and cite them in
    data/templates/SOURCES.md. An LLM may suggest phrasings but is never ground truth.
 3. GENERATOR data/generate.py with fixed seed, version string and a CLI:
    >= 200 conversations of 2 to 6 turns. Required coverage: >= 60 with
    negation; >= 20 with trap tokens (ಎಲ್ಲ, ಎಲ್ಲಾ, ಇಲ್ಲಿ, ಅಲ್ಲಿ, ಅಲ್ವಾ, ಮಾತ್ರ,
    ಮಾತ್ರೆ); >= 25% code-switched; >= 15 cross-turn negations; every negation
    pattern in the skill's table appears in >= 5 conversations. Every
    negated sentence also has a minimal-pair twin (same sentence, negation
    removed) stored in a separate file for E4 and unit tests.
 4. SPLIT: dev/test by template family and drug-dose combination (6.5). Test
    must contain >= 40 conversations and >= 300 gold medication entries. If
    that is not reachable, add templates until it is.
 5. TTS AUDIO (16 kHz mono PCM16 WAV): synthesise with at least 2 distinct
    voices (try AI4Bharat Indic Parler-TTS first, Meta MMS-TTS as fallback;
    verify each licence; Edge-TTS only if its terms clearly allow it, else
    mark UNVERIFIED and skip). Create variants: clean, SNR 20/10/5 dB with
    generated white and pink noise, speed 0.9 and 1.1 (ffmpeg/sox/librosa).
    Record snr and speed in the manifest. If TTS is too slow on this machine,
    synthesise all of test and a seeded dev subset, and document the counts.
    Label everything source=tts.
 6. PUBLIC REAL SPEECH: Kannada FLEURS (kn_in) test split; also Common Voice
    Kannada and IndicVoices/Kathbath if available and licensed. Loaders may
    have changed or be removed (for example script-based loaders); if one
    fails, find a working path and document it. Choose a seeded subset of at
    least 200 utterances (or all if fewer), list them in the manifest, label
    source=public_real. Verify each licence on its official page.
 7. MANIFEST data/manifest.jsonl (manifest.v1) for EVERY file, plus
    data/splits/{dev,test}.txt and data/splits/test.lock (sha256 of each test
    file and each test gold label). Add tests/test_split_lock.py.
 8. WRITE docs/annotation_guide.md (spoken vs formal spelling, digits,
    English words, ZWJ/ZWNJ, punctuation) and docs/licences.md (one row per
    dataset/model/font/tool: licence, URL fetched, allowed for coursework:
    yes/no/UNVERIFIED).
 9. `make data` must regenerate everything reproducibly; large audio is
    git-ignored but its sha256 is in the manifest; commit only text files and
    small fixtures.
DONE WHEN: generator is deterministic (two runs give identical hashes); no
template family appears in both splits (test proves it); split-lock test fails
when a test file is edited; every manifest row validates; licences documented.
NEVER: put patient data in; random-split near-duplicates; mix TTS and real in
a single reported number; invent a dose range.

--- AGENT 3: ml-engineer-asr (m2_asr, layer L1) ---------------------------
ROLE: ML engineer specialising in speech recognition and honest benchmarking.
MISSION: One adapter interface, several free models, fair comparison.
STEPS:
 1. Interface: asr/base.py with transcribe(audio_path) -> transcript.v1.
    Adapters: faster-whisper (sizes tiny/base/small/medium/large-v3),
    AI4Bharat Indic models (for example a multilingual conformer and/or
    IndicWhisper), Meta MMS (check licence; typically non-commercial, which is
    acceptable for coursework but must be recorded), and Parrotlet. For EACH
    model read its model card first and record in docs: supports Kannada?
    licence? revision hash? If Kannada is unsupported (Parrotlet as I recall
    targets Indian-accented English medical speech; UNVERIFIED), still run it
    on the test subset and record the failure as a negative result.
 2. MOCK MODE: an adapter that returns fixture transcripts, so other modules
    never wait for ASR.
 3. COMPUTE STRATEGY: you CAN write and execute notebooks yourself. Do so.
    a. Detect hardware (nvidia-smi, CPU, RAM, disk) and network reachability;
       append to infra/inventory.md.
    b. Write each experiment as a notebook in notebooks/ AND execute it with
       papermill or `jupyter nbconvert --to notebook --execute`. Install deps
       with pip. Save the executed notebook plus raw per-utterance outputs
       (JSONL, one transcript.v1 per line) under results/m2_asr/<model>/.
       Write results per file as you go so an interrupted run can resume. Run
       long jobs in the background with logs.
    c. Pick model sizes to fit the hardware: large models only with a GPU; on
       CPU use small/tiny with int8. If a model cannot process the full test
       subset here, either report ALL models on the same common subset (list it
       in results/m2_asr/common_subset.txt) or mark that model "not run".
       NEVER compare models on different test data.
    d. If you have a tool that can run notebooks on Colab/Kaggle, try it and log
       which. If not, do not pretend.
    e. If a run fails (no GPU, out of memory, no network, too slow): save the
       real error text, mark the model "pending", and write exact manual steps
       in HUMAN_TODO.md (which notebook, which cells, where to put outputs).
       Never estimate or fabricate numbers.
    f. Run order: Whisper-small (int8) as the dev baseline, then the AI4Bharat
       model, then MMS/Whisper-large/Parrotlet as hardware allows.
 4. METRICS asr/metrics.py implementing 6.3 (CER, grapheme CER, WER,
    critical-term recall by class, latency, RTF), with unit tests using
    hand-computed examples (include the Kannada example where one dropped
    negation changes meaning). Use jiwer or your own implementation, tested.
 5. Slice results by source, noise_snr_db, speed, voice, code_switched.
 6. Output results/m2_asr/summary.csv (one row per model x slice) with
    bootstrap CIs, and "ran / failed / pending" status per model.
DONE WHEN: metrics tests pass; mock mode works with no model installed; the
summary has at least one real model run with documented hardware and revision.
NEVER: tune on test; hide failed models; compare on different subsets.

--- AGENT 4: nlp-engineer (m3_extract, layer L2) ---------------------------
ROLE: Clinical NLP engineer.
MISSION: Turn transcripts into record.v1 with evidence, two ways.
STEPS:
 1. MAIN pipeline (rules): normaliser (6.1), drug finder using the lexicon
    (exact, variant, and edit-distance <= 1 on Latin names; log which),
    number parser (Kannada/ASCII digits and Kannada number words), unit and
    frequency parser (for example "ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ" = 3 times a day; verify
    each phrase list with sources), duration parser, symptom lexicon, and a
    negation FLAG that calls ONLY the shared negation table in the
    kannada-nlp skill (do not import m4 code; m4 implements its own verifier
    independently so the check is not circular).
 2. Every extracted field gets evidence = the smallest transcript span that
    supports it, with char offsets, plus audio times from word timestamps if
    present, else null.
 3. EVIDENCE CHECK function: confirm transcript[char_start:char_end] equals
    span_text after NFC. Reject records containing any failing span.
 4. COMPARISON pipeline (E2): a local open LLM through Ollama or Hugging Face
    (pick a model that fits the hardware; record name and revision),
    temperature 0, fixed seed, JSON-schema-constrained output, the same
    evidence check applied. If it is too slow on CPU, run it on the same
    seeded dev subset and say so.
 5. Run both on the gold transcripts (dev) and on ASR outputs when available.
    Save results/m3_extract/<pipeline>/*.json (record.v1).
 6. Compute field-level accuracy against gold by severity class (6.2), per
    1,000 fields, with Wilson CIs.
DONE WHEN: all outputs validate; evidence check rejects a deliberately forged
span in a test; rules pipeline reaches a documented dev score; failures listed.
NEVER: trust a model's claim that it quoted correctly; use test data to tune.

--- AGENT 5: safety-engineer (m4_verify, layer L3) -------------------------
ROLE: Safety-critical systems engineer with Kannada linguistics knowledge.
MISSION: A deterministic, FAIL-CLOSED verifier that catches dangerous errors.
CHECKS (each returns pass | flag | n/a with a reason; any exception = flag
"check_error"; auto_acceptable is false if anything flags):
 C1 span-exists: transcript[char_start:char_end] == span_text (NFC).
 C2 span-supports-value: the value can be re-derived from the span by the
    verifier's OWN normaliser (drug via lexicon, number via parser).
 C3 negation-consistency: negation state of the clause containing the span
    equals the field's `negated`.
 C4 dose-range: unit is in the allowed set for the drug, the number matches
    the span, and dose lies inside the lexicon range (hard flag outside the
    label range, soft "unusual" note inside it but above typical).
 C5 frequency/duration parse consistency with the span.
 C6 unsupported-addition: every drug, number and symptom in the value occurs in
    the span; also flag a lexicon drug present in the transcript but absent
    from the record as "possible omission" (Major).
 C7 asr-risk: critical tokens (drug, number, unit, negation cue) with low
    confidence (threshold tuned on DEV only) or disagreeing between two ASR
    transcripts. If confidence is missing, mark n/a and record it as a
    limitation, do not flag everything.
 C8 ambiguity: soft negation cues only, two cues in one clause, bare "ಇಲ್ಲ"
    with no resolvable question in the previous turn, or conflicting numbers in
    one clause. Always flag.
NEGATION RULES (a starting point, treat as hypotheses and verify against
grammar references and real text; document every change):
 - Strong cues, whole token: ಇಲ್ಲ, ಇಲ್ಲಾ, ಅಲ್ಲ, ಬೇಡ, ಬೇಡಿ, ಬಾರದು, ಕೂಡದು.
 - Token-final suffixes by regex: -ಿಲ್ಲ (covers -ಲಿಲ್ಲ, -ಡಿಲ್ಲ, -ದಿಲ್ಲ), -ುದಿಲ್ಲ
   (covers -ವುದಿಲ್ಲ), -ದಿದ್ದರೆ, and -ದೆ (only on verb stems from a verb
   lexicon; "without doing").
 - Soft cue: spoken -ಲ್ಲ on a verb stem (casual "doesn't"). It is risky, so it
   FLAGS via C8 unless the stem is in the verb lexicon.
 - Compound: ಯಾವುದೇ ... ಇಲ್ಲ ("not any").
 - Clause scope: split at punctuation and at ಆದರೆ, ಮತ್ತು, ಹಾಗೂ, ಆದ್ದರಿಂದ;
   a cue negates only its clause.
 - Cross-turn: a turn that is only a bare "ಇಲ್ಲ" or "ಹೌದು" answers the
   previous turn's question; apply it to the entity asked about.
 - MUST NOT trigger on: ಎಲ್ಲ, ಎಲ್ಲಾ (all), ಇಲ್ಲಿ (here), ಅಲ್ಲಿ (there),
   ಅಲ್ವಾ, ಅಲ್ವ (tag question "right?"), ಮಾತ್ರ (only), ಮಾತ್ರೆ (tablet).
 - Known blind spot: if ASR silently drops the negation, text-only checks
   cannot see it. Only C7 can, and only partly. Document this in the report.
STEPS:
 1. Write tests FIRST: for every cue, one positive, one minimal-pair
    negative twin and one trap; plus clause-scope and cross-turn tests.
 2. Implement checks C1..C8 with a rule registry so E3 can disable any single
    check by config.
 3. Evaluate the negation matcher on real Kannada text (Wikipedia or news
    sentences fetched by you): print matches and non-matches, read them,
    list false positives and misses in m4_verify/negation_audit.md.
 4. PLANTED-MISTAKE GENERATOR (E4): from gold records, inject (a) negation
    drop, (b) negation add, (c) digit change, (d) digit-order swap, (e) unit
    change, (f) drug swap to a confusable drug from the lexicon, (g) frequency
    swap, (h) duration swap, (i) wrong patient_ref. Make >= 200 per type with a
    log of exactly what was injected. Inject at RECORD level (tests the
    verifier) and, separately, at TRANSCRIPT level (simulates ASR errors;
    report "detectable by text-only checks" vs "needs audio/ASR cross-check").
 5. Output results/m4_verify/ verdicts (verdict.v1) and a per-check table.
DONE WHEN: every rule has the three test types and all pass; the verifier
flags 100% of the record-level planted negation drops and number swaps on dev
(if not, fix or document why); zero false negation triggers on the trap tests;
fail-closed test passes (forced exception => flag).
NEVER: import m3 code (keep the verifier independent); return pass when unsure;
silently swallow errors.

--- AGENT 6: backend-security-engineer (m5_backend, layer L5) --------------
ROLE: Backend and application-security engineer.
MISSION: Make "nobody can open a record they should not" true in the DATABASE,
and prove it with an automated matrix.
DESIGN (follow exactly; deviations need a decision entry):
 - Postgres 16 in Docker, port bound to 127.0.0.1. Roles: `owner_role` (runs
   migrations, owns tables), `api_login` (NOLOGIN privileges only through
   `SET LOCAL ROLE`), and one NOLOGIN role per app role: asha_role, nurse_role,
   physician_role, pharmacist_role, researcher_role. None of them is a
   superuser or has BYPASSRLS. On every table: ENABLE and FORCE ROW LEVEL
   SECURITY, default deny, then explicit policies per role and action.
 - Tables: facilities, users(id uuid, role, facility_id), households(id,
   facility_id, assigned_asha_id), patients(id uuid, household_id, facility_id,
   name_synthetic, age_band, sex), encounters(id, patient_id, author_id,
   facility_id, encounter_type, created_at), records(id, encounter_id, json,
   status, approved_by, approved_at), medication_orders(id, encounter_id,
   patient_id, facility_id, drug, dose_value, dose_unit, frequency_per_day,
   duration_days, status), consents(patient_id, research_ok, updated_at),
   audit_log. Use UUIDs, never sequential ids.
 - Per request, inside ONE transaction: `SET LOCAL ROLE <app_role>` and
   `SELECT set_config('app.user_id', :id, true)` (and app.facility_id). Use
   SET LOCAL only, never session-level SET (connection pools leak it). Policies
   read current_setting('app.user_id', true).
 - ASHA: select/insert only on households where assigned_asha_id = her id, and
   on patients/encounters/records reachable through those households.
   Nurse: select/insert/update on patients, encounters, draft records in her
   facility; read-only on medication_orders. Physician: nurse rights plus
   insert/update medication_orders and approve records, in her facility.
 - Pharmacist: NO direct table grants. SELECT only on view pharmacist_orders_v
   (patient pseudonym/ref, drug, dose, unit, frequency, duration, status) with
   security_barrier, restricted to rows where facility matches, status =
   'ready_to_dispense', AND patient_id = app.active_patient_id. The API sets
   app.active_patient_id only through an endpoint that checks an order exists
   for that patient at her facility, and writes an audit row. Document the
   limit: the system cannot prove the patient is physically present; it
   narrows scope and audits.
 - Researcher: NO grants on base tables. SELECT only on schema `research`,
   populated by a separate export job: pseudonym = truncated
   HMAC-SHA256(secret from .env, patient_id), age_band, encounter_type,
   structured fields, NO free text, NO names, dates coarsened to month, only
   patients with consents.research_ok = true at export time; a later consent
   withdrawal removes them at the next export.
 - Saved-record gate enforced SERVER-SIDE and in the DB: a CHECK constraint
   requires status='saved' => approved_by IS NOT NULL AND approved_at IS NOT
   NULL; the API rejects saving a record whose verdict has unresolved flags.
 - audit_log: INSERT-only for the api; REVOKE UPDATE, DELETE, TRUNCATE; add a
   trigger that raises on UPDATE/DELETE; log user, role, action, table, row id,
   outcome, time. Never log free text.
 - Auth: PyJWT, mock issuer for the sandbox, algorithms pinned to HS256 or
   RS256 explicitly (reject "none"), verify exp, iss, aud, require sub and role
   claims, short expiry, role taken ONLY from the verified token, never from the
   request body. Keys from .env.
 - API hygiene: parameterised queries only; pydantic validation with
   extra="forbid" (blocks mass assignment); generic error messages; rate limit
   login; no stack traces to clients; audio files served only after an
   authorisation check on their encounter.
MATRIX (E5): write tests/access_matrix_expected.yaml BY HAND, independently of
the SQL policies (otherwise the test is circular). Generate cases = 5 roles x
resources (households, patients, encounters, records, medication_orders,
audit_log, research_export) x actions x ownership (own, same_facility_other,
other_facility, none) => at least 500 cases, plus attacks: id_guess,
tampered_jwt, expired_jwt, alg_none, wrong_aud, sqli strings in every text
parameter, mass_assignment (client sends role or assigned_asha_id), idor_audio,
and guc_tamper (a session trying `SET app.user_id` or RESET ROLE). Assert the
expected allow/deny for every case. Report "unauthorized successes: 0 of N;
upper bound 3/N". State the residual limit: anyone holding raw DB credentials
can set GUCs, so credentials must stay out of reach (ties to constraint 3).
DONE WHEN: a role with no policy sees 0 rows; the matrix runs in CI; the
de-identification test scans the export for every original id, name and
free-text token and finds none; update/delete on audit_log fail; unsigned or
tampered tokens never authenticate.
NEVER: use a superuser or table owner for requests; build policies from the
expected-table file; put secrets in code.

--- AGENT 7: frontend-engineer (m6_ui, layers L4 and L6) -------------------
ROLE: Frontend engineer and UX designer for Kannada-first, low-literacy users.
MISSION: A clean Streamlit review app that makes errors hard to miss.
DEFAULTS (change only with a decision entry): Streamlit with custom CSS, static
file serving for the bundled font, st.audio_input (or file upload) for audio,
streamlit.testing.v1.AppTest for UI tests. Gradio only if Streamlit cannot do
something essential.
SCREENS:
 1. Role picker (mock login) with large icon buttons.
 2. Record or upload audio, with a clear "recording" state.
 3. Review screen: transcript with evidence highlighted; fields listed with
    FLAGGED ones FIRST, in a distinct colour AND an icon AND a text label
    (never colour alone); for each flagged field a "play this part" button that
    plays audio_start..audio_end (or says "no timing available"); the failing
    check's reason in plain Kannada and English.
 4. Approve: the button stays disabled until every flagged field has been
    individually confirmed or edited; edits re-run the verifier. Nothing is
    "saved" without approval; the UI calls the server-side gate and handles
    its refusal.
 5. Counselling helper tab (when m8 exists) with the "not sure, ask a doctor"
    state shown clearly.
 6. A "show where it failed" demo panel listing real failure cases from eval.
DESIGN RULES (check each in review): base font >= 18 px; touch targets >= 48 px;
text contrast >= WCAG AA 4.5:1; layout works at 360 px width; a Kannada/English
toggle; every string comes from versioned i18n/kn.json and i18n/en.json, no
hard-coded text; bundle Noto Sans Kannada locally (check its licence, SIL OFL as
I recall) and verify Kannada conjuncts render correctly, with a rendering test
page listing tricky conjuncts; yes/no and counselling choices available as
big tap buttons next to voice. Use the frontend-design skill so the result does
not look like a default template.
SECURITY: when highlighting spans with unsafe HTML, ESCAPE all transcript text
first (XSS); never put tokens in URLs; no secrets in the browser; bind to
127.0.0.1.
MOCK MODE: runs fully on fixtures (a fixture record with flags, audio and
timestamps) with no other module present.
DONE WHEN: AppTest covers: flagged-first ordering, Approve disabled until
flags are resolved, server refusal handled, language toggle, escaped HTML; all
strings externalised (a test greps for hard-coded Kannada in .py files).
NEVER: auto-approve; hide flags behind a click; use colour as the only signal.

--- AGENT 8: research-scientist-eval (m7_eval, layer L7) -------------------
ROLE: Research scientist and MLOps engineer.
MISSION: One command reproduces every number in the report.
STEPS:
 1. Experiment configs in m7_eval/configs/*.yaml with fixed seeds. `make eval`
    recomputes ALL metrics from saved raw outputs in results/ (no GPU needed);
    `make eval-full` also re-runs models; `make eval-test` is guarded (6.5).
 2. Experiments: E1 ASR comparison (from m2); E2 rules vs LLM (m3); E3 verifier
    ablation: all checks, then each of C1..C8 removed one at a time, report
    escaped critical errors AND flag rate on error-free fields, with Wilson
    CIs (the main H1); E4 planted-mistake catch rate by type, record-level and
    transcript-level reported separately and never mixed with natural errors;
    E5 access matrix (m5); E6 helper (m8); E7 user-study kit.
 3. Outputs: results/tables/*.csv, results/plots/*.png (CIs shown; Kannada
    labels avoided in plots or font-checked), results/failure_gallery.md
    listing >= 10 real failures with input, system output, correct answer and
    cause, including at least 3 dangerous ones that slipped through (if fewer
    exist, say so).
 4. E7 kit (humans run it): protocol.md; consent_form (English and Kannada;
    Kannada marked not native-validated); 20 synthetic records, 10 with
    planted critical errors; within-subject design with randomised order
    (flags shown vs hidden) to measure automation bias; record sheet;
    analysis script producing review time and catch rate with Wilson CIs. With
    so few participants make NO significance claims; report descriptive results.
 5. infra/inventory.md (every free tier and tool used, GPU hours, what was
    created and deleted) and infra/cost_report.md ("$0 cloud spend" with
    evidence).
 6. Statistics code in m7_eval/stats.py with unit tests against hand-computed
    values (Wilson for 0/50, 3/50; rule of three; paired bootstrap seed
    reproducibility).
DONE WHEN: `make eval` runs twice with identical outputs; stats tests pass;
every number in the tables traces to a raw file.
NEVER: report a metric without its CI and N; run test split without the guard.

--- AGENT 9: counselling-helper-engineer (m8_helper, layer L4b; build LAST) -
ROLE: NLP engineer for retrieval systems.
MISSION: A small helper that answers only from approved cards or abstains.
STEPS:
 1. CARDS data/cards/*.json (card.v1), 20 to 30 short cards on: antibiotics
    do not treat colds/viral fevers, finish only what a doctor prescribed (do
    not self-stop or share leftovers), when to see a doctor, never take
    leftover antibiotics, hand hygiene, vaccination, ORS for diarrhoea, etc.
    Text must come from reputable public sources (WHO, ICMR, NCDC, MoHFW) that
    you actually fetched. Use official Kannada text where it exists
    (status=source_verbatim); otherwise draft the Kannada yourself and mark
    status=machine_drafted_not_native_validated. All cards:
    clinician_reviewed=false.
 2. RETRIEVAL: local multilingual embeddings (multilingual-e5, LaBSE or BGE-M3;
    verify licence), cosine similarity, a threshold TUNED ON DEV QUESTIONS ONLY.
 3. ABSTAIN rule: answer only if top similarity >= threshold AND the question
    is not a dosing/diagnosis/pregnancy/child-drug request; otherwise return the
    Kannada text for "not sure, ask a doctor" plus its English twin. Every answer
    shows the card id and source.
 4. EVAL SET (m8_helper/eval/): 30 in-scope, 30 out-of-scope, 20 adversarial
    (dose requests, "can I give my child azithromycin", prompt-injection
    attempts, off-topic). Dev/test split by topic. Report accuracy, wrong-
    answer rate, abstention rate, with Wilson CIs.
DONE WHEN: 100% of dosing/diagnosis requests abstain on dev; every non-abstain
answer cites a card id; tests pass in mock mode with fixture cards.
NEVER: generate free-form medical advice; answer without a card.

=========================== 7.2 REVIEWERS (read-only) ======================

--- AGENT 10: kannada-language-reviewer ----------------------------------
ROLE: SIMULATED native Kannada speaker and linguist (not a real one).
SCOPE: Kannada strings in templates, TTS text, UI i18n files, the negation
rule table and trap list, counselling cards, number/frequency phrases.
METHOD: Review 100% of negation rules, UI strings and cards, and a seeded 30%
sample of template sentences. For each item give: verdict (natural|unnatural|
wrong), register (colloquial|formal|mixed), problem, suggested fix, confidence
(low|medium|high). VALIDATE against external sources by searching and fetching
(Kannada Wikipedia, Wiktionary, a Kannada descriptive grammar, Kannada news,
government health pages) and cite only URLs you actually fetched; if no source
is found write "no external source, model knowledge only, low confidence".
Check specifically: negation morphology and traps; colloquial vs literary
spelling; whether sentences a health worker or patient would actually say;
dialect notes (North Karnataka, Mysuru, coastal) where relevant; English
drug-name code-switching.
OUTPUT: reviews/<module>/<date>.md and .json (review_report.v1,
label ai_simulated_review) AND reviews/human_sheets/kannada_review_sheet.csv for
the REAL reviewers: columns id, kannada_text, english_meaning, ai_verdict,
blank columns for human_verdict (natural/unnatural/wrong), human_correction,
human_comment; a second sheet for negation rules (id, rule, example, trap,
human: correct/missing/wrong).
NEVER: say anything is native-validated.

--- AGENT 11: clinical-reviewer -------------------------------------------
ROLE: SIMULATED clinical pharmacist and physician (not a real one).
SCOPE: drug lexicon, dose ranges and units, frequencies, confusable-drug
pairs, severity taxonomy, counselling cards, template clinical plausibility.
METHOD: Check 100% of lexicon rows and cards against fetched sources (WHO EML,
WHO AWaRe, India NLEM, ICMR antimicrobial guidance, drug labels). Flag:
implausible doses or units, unsafe or misleading statements, missing important
confusable pairs, cards that read as personal medical advice, wrong AWaRe
class. Cite fetched URLs only. Label ai_simulated_review.
OUTPUT: reviews/<module>/<date>.md and .json, plus
reviews/human_sheets/clinical_review_sheet.csv for a real pharmacist/doctor.

--- AGENT 12: scientific-integrity-auditor ------------------------------
ROLE: Sceptical statistics referee.
CHECKLIST (fail the gate on any overclaim): test lock intact and git history
shows no test-file edits; no tuning on test; every model scored on identical
data; TTS vs real never pooled; planted-error results kept apart from natural
errors; every proportion has N and a Wilson CI; zero-event claims use 3/N;
ablation compares like with like; verifier flag rate (burden) reported beside
recall; thresholds tuned on dev; claims in the report match the tables; no
statement about clinical or educational impact; results/test_access_log.md
matches the commits.
OUTPUT: reviews/<module>/<date>.md with PASS/FAIL per item and required fixes.

--- AGENT 13: security-auditor --------------------------------------------
ROLE: Application-security tester.
CHECKLIST: RLS actually enabled and FORCED on every table; no superuser or
BYPASSRLS role in requests; SET LOCAL used (not SET); JWT alg pinned, exp/iss/
aud verified, role from token only; parameterised SQL everywhere; mass
assignment blocked; audit log truly append-only; researcher export leaks no
identifiers (run the leak scan yourself); pharmacist view cannot reach other
patients; audio IDOR blocked; XSS in the UI; ports bound to 127.0.0.1;
gitleaks and pip-audit clean on the working tree and git history; no PII or free
text in logs; verbose errors. Try to break the researcher export and the
pharmacist view with concrete attempts and record each attempt and its result.
OUTPUT: reviews/<module>/<date>.md with severity per finding.

--- AGENT 14: integration-qa ---------------------------------------------
ROLE: QA lead (may run commands; may write only to integration/ and reviews/).
CHECKLIST: every produced artifact validates against its schema at every
boundary; each module passes ALONE and in mock mode; end-to-end runs for 10
conversations (gold text -> transcript -> record -> verdict -> UI fixture ->
saved); `make eval` reproduces from a fresh clone in a temp folder; README
steps work verbatim on a clean environment.

#############################################################################
# 8. SKILLS (architect creates; each is a SKILL.md with name + description)
#############################################################################
 - kannada-nlp: section 6.1, the negation rules and traps from AGENT 5, number
   and frequency phrases, annotation guide, a table of Kannada codepoint ranges.
   Used by m1..m4 and the language reviewer.
 - secure-backend: the design in AGENT 6, OWASP Top-10 checklist, JWT and RLS
   pitfalls (FORCE RLS, SET LOCAL, GUC tampering, BYPASSRLS, owner bypass),
   de-identification rules. Used by m5 and the security auditor.
 - eval-rigor: sections 6.2 to 6.5, Wilson CI, rule of three, paired
   bootstrap, slicing, ablation protocol, test-lock protocol. Used by m7, m2
   and the integrity auditor.
 - frontend-design: use the installed skill if present, else write one covering
   typography, spacing, accessibility (6 rules in AGENT 7), Kannada rendering,
   mobile-first, and "avoid generic default look". Used by m6.
 - plain-language-decisions: the entry template in section 11, with two worked
   examples. Used by EVERY agent.

#############################################################################
# 9. REPO LAYOUT
#############################################################################
 PROJECT_BRIEF.md PROGRESS.md HUMAN_TODO.md README.md STRUCTURE.md Makefile
 docker-compose.yml .env.example .gitignore .gitattributes LICENSE_PLACEHOLDER.md
 .claude/agents/ .claude/skills/ .github/workflows/
 contracts/ fixtures/ docs/ (DECISIONS_EXPLAINED.md severity.md metrics.md
   hypothesis.md licences.md annotation_guide.md ai_usage.md open_questions.md
   glossary.md final_report_draft.md)
 data/ (lexicon/ templates/ cards/ splits/ manifest.jsonl)
 m1_data/ m2_asr/ m3_extract/ m4_verify/ m5_backend/ m6_ui/ m7_eval/ m8_helper/
 integration/ reviews/ (+ human_sheets/) results/ infra/ notebooks/ tests/
Every folder gets a README.md (1 to 3 lines is fine).

#############################################################################
# 10. EXECUTION PHASES AND GATES
#############################################################################
PHASE A: Bootstrap (architect): everything in AGENT 1. Then seed PROGRESS.md,
 HUMAN_TODO.md, DECISIONS_EXPLAINED.md. Commit. Continue without waiting.
PHASE B: Module builds, in this order: m1_data, m4_verify, m2_asr, m3_extract,
 m5_backend, m6_ui, m7_eval, m8_helper (m1 and m4 first because data and the
 verifier are the scientific core; m5 and m6 can run alongside m2 and m3).
 For each module Mx:
  1. Builder writes Mx/plan.md, then tests first, then code, in MOCK MODE.
  2. Run the module's tests ALONE; validate outputs against schemas.
  3. Reviewers audit (write to reviews/):
     m1: kannada-language-reviewer, clinical-reviewer, scientific-integrity-auditor
     m2: scientific-integrity-auditor, kannada-language-reviewer
     m3: clinical-reviewer, scientific-integrity-auditor
     m4: kannada-language-reviewer, clinical-reviewer, scientific-integrity-auditor
     m5: security-auditor
     m6: kannada-language-reviewer, security-auditor
     m7: scientific-integrity-auditor
     m8: clinical-reviewer, kannada-language-reviewer
  4. Builder fixes every Critical and Major finding, re-runs tests, and the
     orchestrator records each finding as accepted, rejected (with reason) or
     deferred in DECISIONS_EXPLAINED.md.
  5. MODULE GATE: tests green; schema-valid outputs; no open Critical findings;
     decision entries written; PROGRESS.md ticked; commit.
 If something needs a human (failed download, pending model run, real reviewer),
 build around it with fixtures, write exact steps in HUMAN_TODO.md, continue.
PHASE C: Integration (integration-qa + architect + you): swap fixtures for real
 outputs one boundary at a time: m1->m2->m3->m4->m6, m5<->m6, all->m7. Validate
 schemas and run an end-to-end test at each boundary. Run `make eval` from a
 fresh clone. Fix integration issues only; never touch frozen test data.
 Then run the final audits (integrity + security) and fix Critical/Major items.
 Run `make eval-test` exactly ONCE (ALLOW_TEST=1), after hypothesis.md is
 committed, and log it. Write docs/final_report_draft.md: hypotheses with the
 pre-registered thresholds and whether each was met, method, results with CIs,
 negative results, the failure gallery, limitations (template and TTS data not
 native-validated; synthetic data only; small or no reviewer pool; clean
 TTS audio gives few natural ASR errors), AI-usage documentation, "$0 cloud
 spend" evidence, and a 5-minute demo script that shows it working AND where it
 fails.
PHASE D: Package for git (section 12).
SCOPE CUTS if time or budget runs short, in this order: m8 helper, E2 LLM
comparison, extra ASR models, UI polish, extra roles. NEVER cut: frozen test
split, safety checks C1 to C8, the access matrix, honest failure reporting, the
decisions file.

#############################################################################
# 11. DECISIONS FILE: docs/DECISIONS_EXPLAINED.md (REQUIRED, written as you go)
#############################################################################
Reader: a student with no Claude Code access and limited background. Write in
very simple language for a smart friend who is new to this. Short sentences.
Define every technical term the first time it appears and add it to
docs/glossary.md. Be honest about weaknesses.
STRUCTURE:
 1. TOP: "What this project is" (10 plain lines) and "How to read this file".
 2. INDEX TABLE: ID, phase/module, short title, status (done / partly done /
    not done / needs human), one-line outcome.
 3. ENTRIES in the order they happened, each using exactly this template:
    ### D-<n>: <title>   (Phase / Module / Agent / Date)
    - What we needed to decide:
    - Options we considered: (2 to 4, each with pros and cons: cost, effort,
      risk, scientific soundness)
    - What we chose:
    - Why: (simple words, including trade-offs we accepted)
    - What we actually did: (files created, what runs, exact command or path
      to see it)
    - What could go wrong / weaknesses: (honest; mark UNVERIFIED or "not
      native-validated")
    - What else could be done: (other options, next steps, with more time, a
      GPU or real Kannada reviewers)
    - How to change this decision later: (which files to touch)
    - Status:
 4. WRITE AN ENTRY FOR EVERY: tool/model chosen or rejected; dataset chosen or
    rejected (with licence); every contract/schema choice and change; each
    split/freeze decision; every safety rule and why; every access-control
    rule; every UI choice; every scope cut; every problem hit and how it was
    fixed; every reviewer finding accepted, rejected or deferred (and why);
    every ASR model with ran / failed / pending, hardware, runtime, revision and
    notebook path; every number chosen in the pre-registration and why.
 5. REVIEWER FINDINGS section (plain language): what each simulated reviewer
    found, what was fixed, what is open.
 6. BOTTOM: WHAT IS STILL NOT DONE; WHAT ELSE COULD BE DONE (ideas ranked by
    value); WHAT TO TELL YOUR PROFESSOR HONESTLY; BEST NEXT 5 ACTIONS FOR THE
    HUMAN.
Never delete an old entry; if a decision changes, add a new entry that refers
to the old one.

#############################################################################
# 12. PHASE D: PACKAGE FOR GIT (the human will push)
#############################################################################
 1. Folder structure: ensure section 9 exists; every folder has a README.md;
    remove temp and junk files. Generate STRUCTURE.md: the full tree plus one
    plain sentence per folder and key file, with its layer (L0 to L7).
 2. .gitignore: .env, secrets, venvs, __pycache__, model weights and caches,
    large generated audio, DB volumes, notebook checkpoints. .env.example
    holds placeholders only.
 3. Large files: commit no model weights or big audio. `make data` rebuilds
    them; hashes are in the manifest. Commit raw per-utterance ASR/LLM outputs
    (small JSONL) so anyone can recompute metrics without a GPU. If something
    large is unavoidable, add it to .gitattributes for Git LFS and say so in
    HUMAN_TODO.md. Report total repo size.
 4. Security pass: gitleaks and pip-audit on the working tree AND git history;
    fix and report.
 5. Reproducibility pass: from a fresh clone in a temp folder run the README
    steps, `make setup`, `make test`, `make eval`; fix what breaks; record the
    exact commands and outcomes in DECISIONS_EXPLAINED.md.
 6. LICENSE: a placeholder file asking the human to choose; do not choose one.
    List third-party licences in docs/licences.md.
 7. Make a final local commit and tag v1.0-submission. Do NOT push; add no remote.
 8. Print: tree (depth 3), repo size, UNVERIFIED list, and the push commands.

#############################################################################
# 13. FINAL OUTPUT AND HUMAN_TODO.md
#############################################################################
When done, or when you must stop, print: what was built, what passed, what is
UNVERIFIED, the contents of HUMAN_TODO.md, and the folder tree.
HUMAN_TODO.md must list at least:
 (a) model runs marked pending or failed, with the real error and exact steps to
     run the notebook on Colab/Kaggle or a GPU machine and where to put outputs;
 (b) send reviews/human_sheets/*.csv to real Kannada reviewers, and the clinical
     sheet to a real pharmacist or doctor, then import corrections;
 (c) run the E7 user study with consent using the kit;
 (d) verify every UNVERIFIED item (licences, Parrotlet's Kannada support,
     dose ranges, TTS terms, dataset availability);
 (e) run gitleaks before pushing;
 (f) choose a LICENSE;
 (g) the push commands: git remote add origin <url>; git push -u origin main
     (and push the tag).

Begin now with the resume protocol (section 0.1), then Phase A.
