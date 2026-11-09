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
