
### D-?: Integration tests no longer rewrite tracked files; e2e covers the two Phase C fixes   (Phase C / integration / frontend-engineer / 2026-11-12)
- What we needed to decide: Running `pytest integration` rewrote results/integration/asr_mock/*.json (new timestamps) and e2e_dev.md, so git showed changes after every test run.
- Options we considered:
  1. Fixed timestamps. Pro: files stay identical. Con: edits the mock ASR builder we do not own.
  2. Write test output to a temporary folder. Pro: no tracked file is touched. Con: the committed report is refreshed only on purpose.
- What we chose: Option 2.
- Why: Tests should only read the repo. A person refreshes the report deliberately with the command line.
- What we actually did: integration/e2e.py run_all writes mock transcripts to a temp dir; tests/test_e2e.py writes its report to tmp. Stale comments about the old stale-verdict behaviour fixed. New e2e cases: a second doctor (P2) verifies unchanged content and gets the same verdict, the first save still returns 200; saved records answer 404 on verify and 200 on /review, and m6's gate reopens them read-only. Refresh: `uv run python -m integration.e2e` (DB up). Result: 10 natural + 2 planted all saved, same verdict 12/12.
- What could go wrong / weaknesses: Mock ASR (gold text), 10 conversations; the committed asr_mock files are now just old samples.
- What else could be done: rerun with real m2 output.
- How to change this decision later: integration/e2e.py (run_all), integration/tests/test_e2e.py.
- Status: done
