### D-?: Retrieval method: Ollama nomic-embed-text with a lexical fallback, no generation   (Phase C / m8_helper / counselling-helper-engineer / 2026-11-12)
- What we needed to decide: How to find the right card for a question, locally, without downloading a new model, and without letting a model write medical advice.
- Options we considered:
  1. multilingual-e5 / LaBSE / BGE-M3 (named in the brief). Pro: built for many languages. Con: needs a new download; disk is tight; not allowed in this task.
  2. Ollama nomic-embed-text (already installed). Pro: no download, local. Con: mainly English, so Kannada quality is doubtful.
  3. Our own TF-IDF (word counts) with Kannada 3-letter pieces. Pro: no model, runs anywhere, used for mock mode and tests. Con: weak on meaning, noisy on Kannada word endings.
  4. Let qwen3 paraphrase the card. Pro: friendlier text. Con: new risk of unsupported sentences; not required.
- What we chose: Options 2 and 3 side by side; the answer is always the stored card text. Option 4 not built.
- Why: Option 2 scored better on the dev questions (10 of 20 in-scope answered vs 7 of 20); option 3 works with no daemon. Quoting the card verbatim means no sentence can be unsupported.
- What we actually did: `m8_helper/helper.py` (TfidfRetriever, OllamaRetriever), `m8_helper/evaluate.py`. Re-run: `mingw32-make m8-eval`.
- What could go wrong / weaknesses: Only about half of in-scope questions get answered, far below the 90% target (H4). Kannada embedding quality is UNVERIFIED beyond these 80 questions. Option 1 was not tried.
- What else could be done: try multilingual-e5 or BGE-M3 when disk allows; add card paraphrases; native-written questions.
- How to change this decision later: `make_retriever` in `evaluate.py`, `build` and THRESHOLDS in `__main__.py`.
- Status: partly done

### D-?: Abstain rule: safety gate first, then a similarity threshold tuned on dev only   (Phase C / m8_helper / counselling-helper-engineer / 2026-11-12)
- What we needed to decide: When must the helper refuse, and what number is the similarity cut-off.
- Options we considered:
  1. Threshold only. Pro: simple. Con: a dose question naming "amoxicillin" can still match a card strongly.
  2. Safety gate (regex rules) before retrieval, then threshold. Pro: unsafe questions never reach a card, even at threshold 0. Con: hand-written rules can miss new wording.
  3. An LLM judge. Pro: flexible. Con: another unverified model inside a safety path.
- What we chose: Option 2. Gate categories: dosing, pregnancy, diagnosis or symptom report, stop-early, requesting a drug, child plus drug, leftover or sharing tablets, prompt injection. Threshold: the highest value with zero wrong dev answers that maximises correct dev answers: tfidf 0.28, ollama 0.75.
- Why: The brief says 100% of dosing and diagnosis requests abstain; a gate gives that by construction, a threshold cannot. The gate also over-blocks (for example any "can I take ...?"); we accept that.
- What we actually did: `safety_gate` in `m8_helper/helper.py`; tests in `m8_helper/tests/test_helper.py` check abstention even at threshold 0. Results: `results/m8_helper/eval_*.json`.
- What could go wrong / weaknesses: Rules were written knowing the adversarial categories, so the test split measures new wording only. Kannada and romanised-Kannada rules are not native-validated. The Kannada stop-word list was chosen after printing scores for ALL rows (including test), so test is not pristine for that choice.
- What else could be done: native Kannada reviewer pass on the rules; more adversarial wording.
- How to change this decision later: `_RULES` in `helper.py`; re-run `mingw32-make m8-eval` and update THRESHOLDS.
- Status: done

### D-?: Cards are AI-authored drafts; normal mode serves none   (Phase C / m8_helper / counselling-helper-engineer / 2026-11-12)
- What we needed to decide: Where card text comes from and which cards may be shown.
- Options we considered:
  1. Wait for clinician-written cards. Pro: safest. Con: nothing to demo.
  2. AI-write cards from fetched WHO pages and mark them draft. Pro: demoable and traceable. Con: still unreviewed.
  3. Write the brief example topics (finish the course, no antibiotics for colds) from memory. Con: breaks the rule against unfetched claims.
- What we chose: Option 2, only statements found in the three fetched pages (curl 2026-11-12: who.int antimicrobial-resistance, pneumonia, diarrhoeal-disease). card.v1 has no "approved" field, so approved means clinician_reviewed=true. Normal mode serves only those (none exist); demo mode (explicit flag) serves drafts with a DRAFT label.
- Why: Honest and safe by default; the demo still works.
- What we actually did: 16 cards in `m8_helper/cards/` (the brief asked for 20 to 30). Generator `m8_helper/author_cards.py`. Validated: 16/16 against card.v1.
- What could go wrong / weaknesses: Brief topics NOT covered because the fetched pages do not state them: finishing a course, never using leftovers, "antibiotics do not treat colds", when to see a doctor for a fever. Nothing was fetched from ICMR, NCDC or MoHFW, and no official Kannada page was found or looked for (UNVERIFIED whether one exists), so all Kannada is machine-drafted, not native-validated.
- What else could be done: fetch ICMR/MoHFW/NCDC pages and an official Kannada leaflet; clinician review; add the missing topics.
- How to change this decision later: edit `author_cards.py`, regenerate, re-run eval; set clinician_reviewed=true only after a real clinician signs.
- Status: needs human

### D-?: Evaluation design for the helper   (Phase C / m8_helper / counselling-helper-engineer / 2026-11-12)
- What we needed to decide: How to measure answering and abstaining honestly with a small set.
- Options we considered:
  1. One pooled accuracy. Pro: one number. Con: hides unsafe answers.
  2. Separate rates with Wilson intervals and a dev/test split by topic. Pro: honest about small N. Con: wide intervals.
- What we chose: Option 2. 80 AI-written questions: 30 in-scope, 30 out-of-scope, 20 adversarial; English, Kannada, romanised Kannada. Dev topics tune the threshold; test topics (diarrhoea, dengue, cancer, fever, skin, pregnancy, diagnosis, stop, request, leftover) are scored once at the frozen threshold.
- Why: The split is by topic as the brief asks; N and intervals show how little 80 questions prove.
- What we actually did: `m8_helper/eval/build_eval.py`, `m8_helper/evaluate.py`, results in `results/m8_helper/`. Wilson 95% results: tfidf dev unsafe answered 0/8 [0, 0.32], test 0/10 [0, 0.28]; wrong answers dev 0/46, test 0/34; in-scope answered with the right card dev 7/20, test 6/10. ollama: dev 10/20, test 6/10, same zero wrong answers. Abstain recall 26/26 dev and 24/24 test (both backends).
- What could go wrong / weaknesses: "0 of 10" only bounds the unsafe-answer rate near 30%. Questions are not from real users. H4 (answer 90% of in-scope) is NOT met. No clinical or educational impact is claimed.
- What else could be done: more questions from a native speaker; real user wording.
- How to change this decision later: `eval/build_eval.py` then `mingw32-make m8-eval`.
- Status: done
