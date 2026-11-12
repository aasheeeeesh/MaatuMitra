## m5_backend Phase C follow-ups (backend-security-engineer, 2026-11-12)
- Generated: removal of /approve, GET /records, GET /records/{id}/transcript, load_verifier, record.v2 acceptance, new matrix cases and tests (m5_backend/tests/test_followups.py).
- A human must check: the hand-written `endpoints` expectations in tests/access_matrix_expected.yaml; that no client still calls /approve; that the transcript folder is not world-readable.
