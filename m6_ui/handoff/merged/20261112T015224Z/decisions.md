
### D-?: A saved record opens read-only from the server's stored result, never re-checked   (Phase C / m6_ui / frontend-engineer / 2026-11-12)
- What we needed to decide: When someone reopens a record that is already saved, what does the review screen show? Before, it asked the server to verify it again and got "404 not found".
- Options we considered:
  1. Keep calling the verify route and hide the error. Pro: no code change. Con: the screen is empty or wrong, and verifying a saved record is not allowed.
  2. Show the old local copy. Pro: always works. Con: may differ from what the server saved; the UI would be deciding.
  3. Ask the server's new read-only route (GET /records/{id}/review) and show what it stored. Pro: shows the truth, cannot change anything. Con: one more route to depend on.
- What we chose: Option 3.
- Why: The server is the authority on what was saved. A read-only route cannot create a verdict or reopen a finished record.
- What we actually did: m6_ui/gate.py (HttpGate.load_record checks the record status; if saved it calls /review, marks it saved and returns read_only data; MockGate.review mirrors it), m6_ui/app.py (banner in Kannada AND English, doctor's answers listed only when the role is physician, rows lock), three new i18n keys in kn.json and en.json. Tests: m6_ui/tests/test_readonly.py, test_gate.py (saved_*), test_live_m5.py (live, skips if API down). They failed first (404 from the fake server's verify), then passed. Run: `uv run pytest m6_ui -q`.
- What could go wrong / weaknesses: Kannada banner text is AI-drafted, not native-validated. The answers list shows check ids and paths, not plain-language sentences. A record with no stored verdict shows a note only.
- What else could be done: show each answer next to its field row with the old flag reason; add an audit line (who approved, when) from the same route.
- How to change this decision later: m6_ui/gate.py (_review, MockGate.review), m6_ui/app.py (_saved_work, _resolutions_box).
- Status: done
