### D-?: gold.v2 accepted; the test split has no injection or as-needed cases   (Phase C / m1_data / orchestrator / 2026-11-12)
- What we needed to decide: m1 (Sonnet) generated record-format-v2 answer labels (gold.v2) for all 592 conversations as new files. Accept, and what must the report say?
- Options we considered: (1) Accept and disclose the gaps. Pro: no change to frozen data; labels come from template metadata, not guesses. Con: some v2 classes cannot be measured on test. (2) Add test templates with injections. Pro: fuller test coverage. Con: that would change the frozen test split after its contents were seen, which the brief forbids.
- What we chose: Option 1.
- Why: The frozen split must not be changed to make a metric possible; we report what cannot be measured instead.
- What we actually did: Re-ran checks myself: v1 gold, transcripts, lexicon and twins unchanged; test.lock +265 lines, 0 removed; manifest +592 rows, 0 removed; 592/592 gold.v2 valid; 5388/5388 manifest rows valid; split-lock OK; two generator runs gave identical data; `pytest m1_data tests m3_extract` 394 passed, 1 skipped; ruff clean.
- What could go wrong / weaknesses: All 16 injection entries and all 24 as-needed entries are in dev, so CR-ROUTE for injections and as-needed checks cannot be measured on test. No conversation says the patient is an adult, so adult age is left empty (null) everywhere. Route "oral" is set from words like ಮಾತ್ರೆ or "drink" (a judgement). Several status mappings are judgement calls (listed in open questions); none is native- or clinician-validated. Every liquid dose has no stated strength (24 dev, 16 test), so CR-LIQUID-STRENGTH flags are expected on all of them.
- What else could be done: A future data version could add injection and as-needed families to a NEW, separately locked test set (never to the current one).
- How to change this decision later: data/templates metadata keys, m1_data/goldv2.py; `make data`.
- Status: done
