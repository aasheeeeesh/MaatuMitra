## m6_ui fix pass (2026-11-12) - frontend-engineer (AI)
Generated: gate.py (mock + HTTP save gate), login flow, bidi handling, record.v2 display, i18n changes (kn/en), a fake m5 test double, tests (test_gate, test_security, test_live_m5, additions to others).
Human must check: all Kannada strings (esp. reason.code.*, gate.code.*, reason.C3/C4, v2val.*) with a native speaker and a clinician; that the mock gate still matches m5 main.py save rules after any m5 change; the live login screen in a real browser on a phone.
