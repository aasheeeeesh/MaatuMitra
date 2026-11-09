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
uv run python -m m4_verify e4 --gold-dir <DEV gold dir or .jsonl> --lexicon data/lexicon/drugs.csv --out-dir results/m4_verify/dev
uv run python -m m4_verify audit --sentences m4_verify/audit/kn_wikipedia_jvara_sentences.txt
uv run python -m m4_verify tune-c7 --pairs <DEV asr/gold pairs .jsonl>
```

## The checks (rule registry `m4_verify/checks.py::REGISTRY`; disable any one via config `disabled: [C3]`)

| id | name | flags when |
|---|---|---|
| C1 | span-exists | transcript[char_start:char_end] != span_text (NFC); offsets out of range; record points at another transcript; input fails its contract |
| C2 | span-supports-value | drug / dose / unit / symptom cannot be re-derived from the span with the verifier's own normaliser, number parser and lexicon; record omits a dose the span states. Free-text advice: n/a |
| C3 | negation-consistency | negation state of the clause(s) holding the span (own rules, cross-turn answers) != `negated` / `not present` |
| C4 | dose-range | dose/unit not what the span says; unit not allowed; outside lexicon range; dose x frequency > max daily; **blank range = flag "no verified range" (fail-closed)**; non-mass unit (tablet, ml) = flag (ranges are in mg). Inside range but above typical strengths = pass with an "unusual" note |
| C5 | frequency/duration | frequency_per_day / duration_days not parsed from the span, or span states one the record lacks |
| C6 | unsupported-addition | a drug, number or symptom in the value does not occur in its span; lexicon drug said but not in the record = "possible omission" (MAJOR); wrong patient_ref (only with an encounter index; else n/a = blind spot) |
| C7 | asr-risk | critical token (drug, number, unit, negation cue) below the confidence threshold; or a second transcript disagrees. No confidences and no second transcript = n/a + limitation |
| C8 | ambiguity | soft cue; two cues in one clause; bare ಇಲ್ಲ with no resolvable question; bare answer to several / negative questions; span inside an unanswered question; coordination scope; conflicting numbers in one clause |

Any exception inside a check -> `flag`, reason `check_error: <Type>: <message>`.

## Results (fixtures; see results/m4_verify/e4/summary.md)

Record-level planted mistakes (a)-(i): 200/200 caught per type (with encounter index); wrong patient
0/200 without it. Error-free fixture fields flagged: 0/18 (Wilson 95% CI 0-0.18). Transcript-level
(simulated ASR) errors: text-only checks catch 0/4 negation drops; a second transcript (C7) catches 4/4.
Only 6 fixture conversations exist, so the number of UNIQUE mutations is small (reported per type).

## Known blind spots

- ASR silently dropping a negation: invisible to text-only checks (only C7 with a second transcript or
  low word confidence can see it, and only partly).
- Wrong patient link: invisible without an encounter index (transcript.v1 has no patient field).
- Negation scope is clause-level and rule-based; see negation_audit.md for measured misses.

Files: `plan.md` (design), `CONTRACT.md` (inputs/outputs), `negation_audit.md`, `handoff/` (decisions).
