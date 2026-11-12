# m4_verify: deterministic, fail-closed safety verifier (layer L3)

Plain Python rules (no ML). Given a `record.v1` and the `transcript.v1` it came from, it returns a
`verdict.v1`: checks C1..C8, each `pass | flag | n/a` with a reason and a JSON-pointer field path,
plus `auto_acceptable` (true only if nothing flags and at least one check passed).
Nothing Kannada in this module is native-validated.

## Run it

```bash
export UV_PROJECT_ENVIRONMENT=$USERPROFILE/.venvs/maatumitra   # Windows path-length workaround
mingw32-make m4            # tests + mock run (Linux/CI: make m4)
uv run pytest m4_verify/tests
MODE=mock uv run python -m m4_verify mock          # fixtures only -> results/m4_verify/
uv run python -m m4_verify verify --record R.json --transcript T.json \
    [--second-transcript T2.json] [--disable C3] [--encounter-index idx.json] [--out V.json]
mingw32-make m4-e4-dev     # = e4 --gold-dir data/gold --lexicon data/lexicon/drugs.csv --n 200 --seed 20261109 --out-dir results/m4_verify/dev
uv run python -m m4_verify audit --sentences m4_verify/audit/kn_wikipedia_jvara_sentences.txt
uv run python -m m4_verify tune-c7 --pairs <DEV asr/gold pairs .jsonl>
```

**DEV only (allow-list guard, `split_guard.py`).** `e4` and `tune-c7` read data through one guard:
under `data/` a file is opened only if its id is in `data/splits/dev.txt` (the 264 test files in
`data/gold/` are skipped without being opened); anywhere else a document is refused (exit code 2,
`error: REFUSED: ...`) if its id is in `test.txt`, its template family is a test family, or its bytes
match a hash in `test.lock`. Only `ALLOW_TEST=1` plus `PURPOSE=...` passes, and that is logged to
`results/m4_verify/test_access_log.md`. Never set it for m4.

## The checks (rule registry `m4_verify/checks.py::REGISTRY`; disable any one via config `disabled: [C3]`)

| id | name | flags when |
|---|---|---|
| C1 | span-exists | transcript[char_start:char_end] != span_text (NFC); offsets out of range; record points at another transcript; input fails its contract |
| C2 | span-supports-value | drug / dose / unit / symptom cannot be re-derived from the span with the verifier's own normaliser, number parser and lexicon; record omits a dose the span states. Free-text advice: n/a |
| C3 | negation-consistency | negation state of the clause(s) holding the span (own rules, cross-turn answers) != `negated` / `not present` |
| C4 | dose-range | Every flag starts with a reason code and severity class. Real violations: `span_mismatch` (dose/unit not what the span says), `unit_not_allowed` (per-drug units: config table, else the dosage form in the lexicon note, else solid oral only; CR-ROUTE for an injection-only drug), `out_of_range`, `exceeds_max_daily` (lexicon max_daily_mg). **Cannot verify (fail-closed, counted separately):** `cannot_verify:paediatric` (a child word such as ಮಗುವಿಗೆ anywhere in the conversation: a child's dose is NEVER passed), `no_range` (blank lexicon range), `not_in_lexicon`, `liquid_strength` (ml), `count_unit` (tablets). Inside range but above typical strengths = pass with an "unusual" note |
| C5 | frequency/duration | frequency_per_day / duration_days not parsed from the span, or span states one the record lacks |
| C6 | unsupported-addition | a drug, number or symptom in the value does not occur in its span; lexicon drug said but not in the record = "possible omission" (MAJOR); wrong patient_ref (only with an encounter index; else n/a = blind spot) |
| C7 | asr-risk | critical token (drug, number, unit, negation cue) below the confidence threshold; or a second transcript disagrees (flag at `/` AND at every item whose clause holds the difference). No confidences and no second transcript = n/a + limitation |
| C8 | ambiguity | soft cue; two cues in one clause; bare ಇಲ್ಲ with no resolvable question; bare answer to several / negative questions; span inside an unanswered question; coordination scope; conflicting numbers in one clause |

Any exception inside a check -> `flag`, reason `check_error: <Type>: <message>`.

## Results: E4 planted mistakes on m1 DEV gold (results/m4_verify/dev/e4/summary.md)

Run: `mingw32-make m4-e4-dev` (2026-11-11). 328 DEV conversations (data/gold filtered by
data/splits/dev.txt; the 264 test files were never opened), project lexicon data/lexicon/drugs.csv,
seed 20261109, 1800 record-level + 1600 transcript-level injections, 5528 verdicts (0 schema errors).
PLANTED errors on SYNTHETIC template text, not native-validated; never pool with natural errors.
Every number is k/n over UNIQUE mutations with a Wilson 95% CI. `caught` = a flag lands on the
injected field (or its item, or the other half of the dose pair); flags elsewhere do not count.

**Review burden on the SAME error-free records (read it next to every recall number):**
271/1200 fields flagged [0.203, 0.250] (189/328 records [0.522, 0.629]). Of these, only 63/1200
fields [0.041, 0.067] (48/328 records [0.112, 0.189]) carry a flag that is NOT `cannot_verify`.
The cannot_verify flags are doses the rules cannot check: tablet counts (152 flags), child doses
(40), blank lexicon ranges (32), ml liquids (24). The other flags are verifier vocabulary gaps
(symptom names chills / tiredness / breathing difficulty and the spelling ಮೈಕೈನೋವು are not in m4's
list: C2+C6, 78 flags) and C8 ambiguity (soft ಇಲ್ಲದೆ, unanswered questions: 24 flags).

| level / condition | negation drop | negation add | digit change | digit swap | unit | drug swap | frequency | duration | wrong patient |
|---|---|---|---|---|---|---|---|---|---|
| record, with encounter index | 193/193 [0.981, 1] | 200/200 [0.981, 1] | 200/200 [0.981, 1] | 139/139 [0.973, 1] | 200/200 [0.981, 1] | 185/185 [0.980, 1] | 200/200 [0.981, 1] | 200/200 [0.981, 1] | 200/200 [0.981, 1] |
| record, no encounter index | | | | | | | | | 0/200 [0, 0.019] |
| transcript, text-only | 14/193 [0.044, 0.118] | 13/200 [0.038, 0.108] | 115/197 [0.514, 0.650] | 104/118 [0.811, 0.928] | 191/200 [0.917, 0.976] | 0/183 [0, 0.021] | 0/200 [0, 0.019] | 0/200 [0, 0.019] | n/a |
| transcript, ORACLE second transcript (UPPER BOUND) | 193/193 [0.981, 1] | 200/200 [0.981, 1] | 197/197 [0.981, 1] | 118/118 [0.969, 1] | 200/200 [0.981, 1] | 183/183 [0.979, 1] | 200/200 [0.981, 1] | 200/200 [0.981, 1] | n/a |

Stricter "detected" (not cannot_verify, and new compared with the error-free record) is identical to
`caught` everywhere except transcript text-only digit change 52/197 [0.207, 0.330], digit swap
79/118 [0.581, 0.748] and unit 131/200 [0.587, 0.717]: there the text-only catch is partly an
already-present cannot_verify or range flag. Per field and per check: `per_field.csv`,
`per_check.csv`. Drug swaps use only lexicon confusable pairs: 231 of 408 medication items have no
listed confusable (paracetamol, zinc, ...) and are never swapped.

How to read it: record level, every planted value that disagrees with its own span is caught at the
field (DONE-WHEN: 100% of negation drops 193/193 and number swaps 200/200 + 139/139). Transcript level
(the record agrees with a corrupted transcript, as after an ASR error): text-only checks see almost no
dropped or added negation and no drug / frequency / duration change; those NEED an audio/ASR
cross-check. The oracle row uses the uncorrupted gold text as the second transcript, so it is an UPPER
BOUND; a real second ASR output has its own errors and its clean-record flag rate is not measured.

Fixture runs (6 conversations, too few to estimate anything): `results/m4_verify/e4/` (fixture
lexicon) and `results/m4_verify/data_lexicon/e4/` (project lexicon). Both: 0/18 error-free fields
flagged [0, 0.176]; negation drop 4/4 [0.510, 1.0] at record level, 0/4 [0, 0.490] text-only;
wrong patient 30/30 [0.887, 1.0] with the index, 0/30 [0, 0.114] without. (The integrity review's
1/18 with the project lexicon came from the old paracetamol range 1000-1000 mg; REFREEZE-1 changed it
to 500-1000, so it is 0/18 now. N = 18 cannot test the H1 bar of <= 20%: the upper bound 0.176 is too
close; use the DEV burden above.)

## Known blind spots

- ASR silently dropping a negation: invisible to text-only checks (DEV: 14/193 caught text-only;
  only C7 with a second transcript or low word confidence can see it, and only partly).
- A child's dose is never checked, only flagged (cannot_verify:paediatric); a child named only by
  ಮಗ/ಮಗಳು (son/daughter) is not recognised as a child.
- Wrong patient link: invisible without an encounter index (transcript.v1 has no patient field).
- Negation scope is clause-level and rule-based; see negation_audit.md for measured misses.

Files: `plan.md` (design), `CONTRACT.md` (inputs/outputs), `negation_audit.md`, `handoff/` (decisions).

## record.v2 (Phase C)

m4 accepts record.v1 and record.v2. For v2 input only, the checks also run `v2checks.py`
(word lists in `v2rules.py`, AI-written, not native-validated): C1 every new evidence span; C2 route,
strength, formulation, age band and weight re-derived from their own span; C3 status (CR-NEG /
MA-STATUS) and speaker; C4 route (CR-ROUTE), paediatric (never passed, CR-PAEDIATRIC), liquid
strength (CR-LIQUID-STRENGTH) and mg-equivalent range; C5 as_needed and food_timing
(MA-MED-ATTRIBUTE). v1 verdicts are unchanged (v1 E4 reproduces results/m4_verify/dev/e4 exactly).
E4-v2 (separate table): `make m4-e4-v2-dev` -> results/m4_verify/dev/e4_v2/.
