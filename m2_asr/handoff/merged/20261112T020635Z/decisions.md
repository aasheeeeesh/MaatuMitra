### D-?: One adapter interface, a mock adapter and our own metrics   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: How every speech model plugs into the project, how other modules work without any model, and how errors are measured.
- Options we considered:
  1. Call each model's own script and parse the output. Pro: no wrapper code. Con: every model looks different; the mock and the metrics would be copied many times.
  2. One small interface `transcribe(audio_path) -> transcript.v1`, one adapter per model, a mock adapter, and our own tested metric code. Pro: same output for all, easy to test, other modules can use the mock. Con: we must test our own CER code.
  3. Use the `jiwer` library for metrics. Pro: less code. Con: it does not do Kannada normalisation, grapheme CER or term recall, so we would still write most of it.
- What we chose: Option 2.
- Why: A fair comparison needs the same output format and the same metric code for every model. Our CER, grapheme CER, WER, term recall, Wilson and bootstrap code is short and each function has a hand-computed test.
- What we actually did: `m2_asr/asr/base.py` (interface and transcript builder), `mock.py` (returns fixture text, needs no model and no audio library), `metrics.py`, tests in `m2_asr/tests/` (17 passing). Run `mingw32-make m2-test` and `mingw32-make m2-mock`.
- What could go wrong / weaknesses: The hand-computed examples were also chosen by us. The metric definitions follow docs/metrics.md as we read it; m7_eval has a separate implementation and gives the same CER means on the same files (cross-check), which is some protection but not a proof. Nothing is native-validated.
- What else could be done: Add word-level timestamps and confidence to the adapters; compare against jiwer in a test.
- How to change this decision later: `m2_asr/asr/base.py` for the interface, `m2_asr/asr/metrics.py` for the numbers.
- Status: done

### D-?: Baseline model: Whisper small, CTranslate2, int8, on the CPU   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: Which model to run first so later models have a reference point.
- Options we considered:
  1. Whisper large-v3 on the GPU. Pro: strongest Whisper. Con: about 3 GB of weights, needs a CUDA runtime we do not have and cannot afford on disk.
  2. Whisper small (Systran CTranslate2 build) with int8 on the CPU. Pro: 486 MB, MIT licence, runs here. Con: weak in Kannada.
  3. Whisper tiny. Pro: smaller. Con: even weaker; adds little as a baseline.
- What we chose: Option 2, revision 536b0662742c02347bc0e980a01041f333bce120, greedy decoding, language forced to `kn`.
- Why: It fits the hardware and the 1.5 GB disk floor, and it is the model named in the brief as the dev baseline. A weak baseline is acceptable; the experiment is about honest measurement.
- What we actually did: `uv run python -m m2_asr run --model faster-whisper-small` on 448 dev files (324 TTS, 124 FLEURS), 1235 s on an i7-12650H, GPU not used. Result: it is unusable for Kannada here. Dev CER 1.04 (public_real, N=124, 95% CI 1.00 to 1.09) and 1.27 (tts, N=324, 1.20 to 1.34); every critical-term class had 0 hits. The outputs are repetition loops. A beam-5 and a repetition-penalty try on 3 dev clips did not help, so the pre-set greedy setting stayed. Outputs: `results/m2_asr/dev/faster-whisper-small/`, notebook `results/m2_asr/faster-whisper-small/m2_dev_run.executed.ipynb`.
- What could go wrong / weaknesses: Only 3 clips were used to try other decoder settings; a better decoder setup might reduce the loops (not shown). Latency of this model equals the loop length, so it is not comparable with a model that stops on time.
- What else could be done: whisper-medium or large-v3 on a GPU (Colab or this laptop with a CUDA runtime); a fairer decoder search on a separate dev subset.
- How to change this decision later: `MODELS` in `m2_asr/asr/models.py`; decoding settings in `m2_asr/asr/whisper_ct2.py`.
- Status: done

### D-?: A Kannada fine-tuned Whisper small as the second model (converted to CTranslate2 int8)   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: Which Kannada-capable model can really run on this laptop with 2.9 GB of free disk.
- Options we considered:
  1. AI4Bharat IndicConformer 600M. Pro: built for Indian languages, MIT. Con: gated (needs a logged-in account), 2.56 GB, custom code we would have to review.
  2. vasista22/whisper-kannada-small (Apache-2.0). Pro: Kannada model. Con: weights exist only as a pickle file (`pytorch_model.bin`); our rule is safetensors only.
  3. ARTPARK-IISc/whisper-small-vaani-kannada (Apache-2.0), safetensors, 967 MB, converted to CTranslate2 int8 on this machine. Pro: Kannada fine-tune, fits, safe format. Con: the model card has a wrong-looking `language: hi` tag and says FLEURS was part of training or evaluation data.
- What we chose: Option 3, revision 65a803da247c0727bbd254b3c421046a60dd140b.
- Why: It is the only Kannada model we could run safely within the disk and safety rules. We accept the possible FLEURS overlap and report it.
- What we actually did: Downloaded only the allow-listed files at the pinned revision, converted to int8 in memory, deleted the source weights automatically before the output was written (so free disk never went below 1.5 GB), and ran the same 448 files (1256 s). Dev results: public_real CER 0.155 (N=124, CI 0.130 to 0.180), WER 0.377; tts CER 0.249 (N=324, CI 0.233 to 0.265), grapheme CER 0.304, WER 0.625. Paired against the baseline the CER gap is 1.02 [0.95, 1.10] (tts) and 0.89 [0.83, 0.94] (public_real). Critical-term recall (exact token): negation 72/216, number 569/738, drug 18/351, unit 168/342 on TTS. Command: `uv run python -m m2_asr run --model whisper-small-vaani-kannada`; notebook `results/m2_asr/whisper-small-vaani-kannada/m2_dev_run.executed.ipynb`.
- What could go wrong / weaknesses: Possible training overlap with FLEURS (UNVERIFIED), so public_real may be optimistic. The conversion was done by us with ctranslate2 4.8.5 and not compared to the original model's output (UNVERIFIED that int8 conversion costs no accuracy). Recall numbers are lower bounds (spelling variants count as misses).
- What else could be done: Compare the CTranslate2 output with the original transformers model on 20 files; try the medium Kannada fine-tunes; fine-tune on our own clinical-style TTS data.
- How to change this decision later: `MODELS["whisper-small-vaani-kannada"]` in `m2_asr/asr/models.py`; conversion in `m2_asr/asr/whisper_ct2.py`.
- Status: done

### D-?: Models not run: IndicConformer, Parrotlet, MMS, IndicWhisper, vasista22, large-v3   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: What to do with the models the brief names that we could not run here.
- Options we considered:
  1. Quietly drop them. Pro: shorter report. Con: hides failures; not allowed.
  2. Download them anyway and risk the disk floor. Pro: more results. Con: breaks the hard 1.5 GB rule and other agents' work.
  3. Record each one as `pending` or `not_run` with the real reason and exact manual steps.
- What we chose: Option 3.
- Why: Honest reporting is a project rule, and a missing model is a result.
- What we actually did: Facts from the Hugging Face API (2026-11-12): ai4bharat/indic-conformer-600m-multilingual is gated, 2.56 GB, MIT, has a Kannada head; ekacare/parrotlet-a-en-5b is gated, tagged English only (so no Kannada), about 10 GB, MIT; facebook/mms-1b-all has a 3.86 GB safetensors file, CC-BY-NC-4.0; no `ai4bharat/IndicWhisper` repo was found (auth error from the API); vasista22 models are pickle-only. They are listed with status and reason as rows in `results/m2_asr/summary.csv` and in `m2_asr/README.md`. Manual steps are in `m2_asr/handoff/human_todo.md`.
- What could go wrong / weaknesses: The Parrotlet claim "English only" comes from the card metadata tag (the README itself is behind the gate): UNVERIFIED. The IndicWhisper location is UNVERIFIED. The brief's "run Parrotlet and record the failure" was not met by running it; the reason is disk and the gate, not Kannada.
- What else could be done: Run them on Colab or on a machine with 6+ GB free and a Hugging Face login, on the same common subset.
- How to change this decision later: `NOT_RUN` in `m2_asr/asr/models.py`; add an adapter and move the entry to `MODELS`.
- Status: needs human

### D-?: Common dev subset and a guard that refuses test audio   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: Which files every model is scored on, and how to be sure test audio is never used.
- Options we considered:
  1. All 720 dev TTS files plus FLEURS dev. Pro: more data. Con: 3 hours of audio per model on the CPU.
  2. A seeded sample of 36 of the 80 dev conversations with all 9 variants, plus all 124 FLEURS dev clips. Pro: about 20 minutes per model, every variant covered. Con: small N per variant (36).
  3. Different subsets per model depending on speed. Con: not comparable; forbidden.
- What we chose: Option 2, seed 20261109. The list is `results/m2_asr/common_subset.txt` (448 ids).
- Why: Same files for all models, covers every slice, finishes in reasonable time.
- What we actually did: `asr/guard.py` refuses a path if a folder is named `test`, the conversation id is in `data/splits/test.txt`, the path is in `data/splits/test.lock`, or the voice is the held-out `mms_kan_pitch084`. The runner checks all paths before any model work. Tests: `m2_asr/tests/test_guard_mock_runner.py`. `results/test_access_log.md` does not exist.
- What could go wrong / weaknesses: Only dev, one voice. The 9 variants of one conversation share sentences, so per-file CIs are narrower than between-conversation uncertainty. The FLEURS file is named `..._test_subset.jsonl` but we use only rows whose `split` is `dev`.
- What else could be done: More conversations (needs more materialised audio); a conversation-level (cluster) bootstrap.
- How to change this decision later: `--n-conv` of `python -m m2_asr subset`; `m2_asr/asr/subset.py`.
- Status: done

### D-?: Disk, path-length and cache strategy on a nearly full drive   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: How to run two models with 2.9 GB free and a 1.5 GB floor, and with Windows paths limited to 260 characters.
- Options we considered:
  1. Keep all caches. Con: crosses the floor.
  2. One model at a time, pinned revision, allow-listed files only, delete the cache after use; rebuild audio variants in batches and delete them; short output file names.
  3. Turn on Windows long paths. Con: a system setting we should not change.
- What we chose: Option 2.
- Why: It keeps the machine usable for the other agents.
- What we actually did: `models.fetch()` refuses a download that would cross the floor; `models.purge()` deletes only our own cache folder. For the 969 MB model the converted int8 copy (243 MB) would have crossed the floor, so the conversion deletes the source weights as soon as they are in RAM (first try failed because the tokenizer was loaded after the delete; fixed by deleting after the tokenizer load). Per-file outputs are named by 8 hex chars of sha1(audio_id) because a 41-character audio id made the path longer than 260 characters (real error: `FileNotFoundError ... speed0.9.tmp`). Free disk: 2.7 GB at start, lowest about 1.7 GB, 2.4 GB at the end.
- What could go wrong / weaknesses: Deleting source weights during conversion means a failed conversion needs a new 1 GB download. Hash file names are not human friendly (the id is inside each JSON).
- What else could be done: Run on a machine with more disk, or enable long paths.
- How to change this decision later: `m2_asr/asr/models.py` (floor, purge), `m2_asr/asr/runner.py` (`out_name`).
- Status: done

### D-?: Metric definitions, term recall and latency method   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: Exactly how CER, WER, critical-term recall and latency are computed and reported.
- Options we considered:
  1. CER on raw text. Con: ZWJ/ZWNJ, digits and case differences count as errors.
  2. CER on the comparison copy from the kannada-nlp skill (NFC, drop ZWJ/ZWNJ, Kannada digits to ASCII, casefold), punctuation kept as the primary number, `cer_nopunct` as a secondary column; grapheme CER with `\X`; WER on whitespace tokens (secondary).
  3. Recall with spelling-variant matching. Pro: fairer. Con: the variant lists are not native-validated.
- What we chose: Option 2 for CER; exact-token term recall (same as m7); latency = wall time of decode plus inference per file with model load and one warm-up file excluded, RTF = latency / audio duration, p50 and p95, always with the hardware string.
- Why: Same definitions as m7 so the two implementations can be cross-checked; they reproduce each other's CER means exactly.
- What we actually did: `m2_asr/asr/metrics.py`, `summary.py`; slices by source, variant, noise type, SNR, speed, voice and code-switched (reference has Latin letters). Bootstrap CI 1000 resamples seed 20261109 for means; Wilson 95% for recall. Output `results/m2_asr/summary.csv` (one row per model x source x slice, plus status rows for models not run).
- What could go wrong / weaknesses: Exact-token recall counts "ಇಲ್ಲ" vs "ಇಲ್ಲಾ" as a miss and a suffix match inside another word as a hit, so recall is a lower bound and negation false hits exist. A dropped negation barely moves CER. Latency was measured while other jobs shared the CPU.
- What else could be done: Variant-tolerant recall once a Kannada reviewer approves the variant list; a flip-detection metric; a cluster bootstrap by conversation.
- How to change this decision later: `m2_asr/asr/metrics.py` and its tests.
- Status: done

### D-?: m7 expects a file key the FLEURS file does not have   (Phase B / m2_asr / ml-engineer-asr / 2026-11-12)
- What we needed to decide: What to do when `mingw32-make eval` fails inside m7 on our outputs.
- Options we considered:
  1. Edit m7. Con: not allowed (other module).
  2. Rename keys in the m1 data file. Con: not allowed (data/).
  3. Write the issue, prove with an in-memory shim that m7 otherwise reads our outputs correctly, and leave the fix to the owner.
- What we chose: Option 3.
- Why: Module boundaries protect the other agents.
- What we actually did: Real error text: `KeyError: 'file_name'` at `m7_eval/experiments.py` line 144 (the file `data/public_real/fleurs_kn_in_test_subset.jsonl` has key `file`). `m2_asr/tools/m7_crosscheck.py` applies the shim in memory and writes m7's E1 tables to a scratch folder; m7's CER means equal ours (1.0416, 1.2694, 0.1548, 0.2489). We write `audio_id` = file stem for FLEURS as m7 documents.
- What could go wrong / weaknesses: Until m7 or m1 changes one line, `make eval` fails at E1 for everyone, not only for these models.
- What else could be done: m7 reads `r.get("file_name") or r["file"]`.
- How to change this decision later: `m7_eval/experiments.py` line 144 (m7 owner).
- Status: needs human
