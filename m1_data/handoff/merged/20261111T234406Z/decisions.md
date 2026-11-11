### D-?: TTS model: MMS-TTS Kannada, because Indic Parler-TTS is gated   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: Which text-to-speech model makes our synthetic test audio, when the brief's first choice (AI4Bharat Indic Parler-TTS) cannot be downloaded.
- Options we considered:
  1. Indic Parler-TTS (Apache-2.0). Pro: named Kannada speakers (Suresh, Anu, Chetan, Vidya), good quality. Con: the Hugging Face repo is gated; without a logged-in account that accepted the terms the download fails with HTTP 401 (checked 2026-11-11). We have no token.
  2. A third-party mirror of Parler weights (some accounts re-upload it ungated). Pro: downloads today. Con: it bypasses the owner's access terms and the weights come from an unknown uploader. Rejected.
  3. MMS-TTS Kannada (facebook/mms-tts-kan), the brief's named fallback. Pro: not gated, small (about 150 MB safetensors), CPU is enough, loads with the standard transformers library (no remote code). Con: ONE speaker only, CC-BY-NC-4.0 (non-commercial), plainer sound.
  4. indic-tiny-tts-kannada (male and female voices, CC-BY-4.0). Pro: two real speakers, ONNX, tiny. Con: needs running about 600 lines of third-party repo code. I read it (numpy + onnxruntime only) but the tool permission system refused to run it, so it was not run.
- What we chose: Option 3 in code (m1_data/tts_model.py), with option 4 and the Parler upgrade written down as human decisions.
- Why: It is the only model we may use today without tokens or approval, and the brief named it. The weakness is accepted and written down: one speaker.
- What we actually did: m1_data/tts_model.py (pinned revision 30e3c5d5, safetensors only), m1_data/tts_pronounce.py (MMS skips Latin letters, so English drug words are respelled in Kannada script for the TTS input only; gold text is untouched, the respelling is stored as `tts_input` in data/audio_index/tts_index.jsonl), tests in m1_data/tests/. The real synthesis run is NOT done (see the disk decision).
- What could go wrong / weaknesses: The respelling table (WORDS in tts_pronounce.py) is not native-validated. MMS audio sounds flat; ASR scores on it will not match real speech. The licence of the generated audio is UNVERIFIED. Torch CPU float output may differ in the last bits between machines, so audio hashes are only guaranteed on this machine (see the reproducibility entry).
- What else could be done: HF token then Parler (real speakers), or approve running indic-tiny-tts (two speakers).
- How to change this decision later: replace the class in m1_data/tts_model.py, keep the signature `model(text_kn, seed) -> float32 16 kHz`, bump AUDIO_VERSION in m1_data/audio_build.py, rebuild with `mingw32-make m1-audio`.
- Status: partly done (code and tests done, audio not yet built)

### D-?: Two "voices": the real MMS voice and a pitch-shifted copy held out for test   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: The brief wants at least 2 distinct voices and one voice used only for the test split, but MMS has one speaker.
- Options we considered:
  1. Wait for a real second speaker (token or approval). Pro: honest, real. Con: blocks the audio work.
  2. Make a second voice by lowering the pitch of the same synthetic speaker (ffmpeg asetrate + atempo, ratio 0.84). Pro: deterministic, free, still tests "voice the dev work never saw". Con: it is NOT a different speaker model; it only sounds lower.
  3. Use seed changes only. Pro: simple. Con: same timbre, not a voice at all.
- What we chose: Option 2, named `mms_kan_pitch084`, used ONLY for test. `mms_kan_base` is used for dev and also for test (clean files only).
- Why: It satisfies the "held-out voice" rule in the weakest sensible form and keeps the pipeline moving. Reports must call it a pitch-shifted copy.
- What we actually did: m1_data/audio_dsp.py `shift_pitch` (tested: 400 Hz tone becomes 320 Hz, same duration), m1_data/audio_build.py plan(): test = held-out voice with ALL 9 variants plus base voice clean for every test conversation; dev = base voice, 9 variants, seeded subset of 80 conversations. A test (test_plan_on_real_data_respects_the_split_rules) proves the held-out voice never appears in dev.
- What could go wrong / weaknesses: Generalisation to a new voice is only weakly tested. Pitch shift also moves formants, so it may sound odd.
- What else could be done: Parler speakers Suresh (test only) and Anu (dev), or the two voices of indic-tiny-tts.
- How to change this decision later: edit BASE_VOICE, HELD_OUT_VOICE, PITCH_RATIO in m1_data/audio_build.py and the plan() function.
- Status: partly done

### D-?: Audio variants, file layout, subset sizes and the size cap   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: Which variants, how many conversations, and where files go, inside a 2.5 GB cap.
- Options we considered:
  1. Every variant for every conversation and both voices: about 4 GB. Over the cap.
  2. Full variants only for the held-out voice on test and a seeded dev subset: about 1.5 GB. Fits.
  3. Clean only: about 0.2 GB. Too thin for the noise and speed experiments.
- What we chose: Option 2. Variants: clean; white and pink noise at SNR 20, 10, 5 dB (SNR measured over the whole clip, gaps included, tested within 0.05 dB); speed 0.9 and 1.1 (ffmpeg atempo, pitch kept). Clean audio is peak-normalised to 0.5 so noise never clips. One WAV per conversation (turns joined by 0.5 s silence), 16 kHz mono PCM16, path data/audio/tts/<split>/<voice>/<variant>/<conv>.wav.
- Why: Whole-test coverage keeps the test numbers honest; a seeded dev subset keeps dev tuning cheap. Plan size: 3360 files (264 test conversations x 10 + 80 dev x 9), estimated 1.5 GB (the 14 s per conversation is an assumption, UNVERIFIED until built).
- What we actually did: `uv run python -m m1_data audio-plan` prints the counts. Index with snr, noise type, speed, voice, seed, turn offsets and TTS input text: data/audio_index/tts_index.jsonl (tracked, written by the build). Manifest rows go into data/manifest.jsonl; audio is git-ignored.
- What could go wrong / weaknesses: Turn offsets for the pitch voice are approximate (within a few ms). Speed 0.9 and 1.1 are applied to clean only (not combined with noise).
- What else could be done: more dev conversations if disk allows; combined noise and speed.
- How to change this decision later: VARIANTS and DEV_SUBSET_N in m1_data/audio_build.py.
- Status: partly done (planned and tested with a fake synthesiser, not yet built for real)

### D-?: Disk blocker: audio and FLEURS not built; the pagefile ate 9 GB   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: Whether to run the real synthesis when free disk is at the floor.
- Options we considered:
  1. Run anyway and dip below the 4 GB floor. Pro: finishes. Con: breaks the orchestrator's hard rule and risks the ASR work.
  2. Delete other people's caches (uv cache 5.7 GB, HF 2.1 GB, codex-runtimes 1.8 GB). Pro: space. Con: not my files; may break running agents (`uv cache clean` itself waited for another uv process).
  3. Stop, finish code, tests and docs, and hand over exact steps. Pro: safe. Con: no audio yet.
- What we chose: Option 3.
- Why: Free space went from 13.6 GB to about 4.0 GB while I installed torch; I found C:\pagefile.sys at 24.8 GB (grown at 04:46). Nothing I downloaded explains it (my CUDA venv was deleted, my uv cache additions are small). A pagefile only shrinks after a restart.
- What we actually did: Built everything with a free-disk guard (`--min-free-gb`, default 4.0; unit-tested) and resumable steps. FLEURS is streamed (no 615 MB tarball). Nothing large was downloaded. The old CUDA torch environment and the Parler worker were removed.
- What could go wrong / weaknesses: The deliverables "audio files, FLEURS subset, test.lock audio lines" do not exist yet. The final free-disk target (>= 9 GB) is unreachable until the pagefile shrinks or caches are cleaned.
- What else could be done: restart Windows; or run on another machine and copy only the manifest/lock lines; or Colab.
- How to change this decision later: run `mingw32-make m1-audio` after freeing space (see human_todo.md).
- Status: needs human

### D-?: Public real speech: Kannada FLEURS test split, streamed, split by sentence   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: Where to get real speech, how to load it now that script loaders are gone, how to split it.
- Options we considered:
  1. FLEURS kn_in via the datasets library script loader. Con: scripts are no longer supported.
  2. FLEURS files straight from the repo (data/kn_in/test.tsv and audio/test.tar.gz, revision 70bb2e84). Pro: works with plain HTTP. Con: the tarball is 615 MB (streamed, so never stored).
  3. Common Voice, IndicVoices, Kathbath. Con: gated or no clear licence page (see licences); skipped.
- What we chose: Option 2. 838 utterances in the official test split, 344 sentences. Seeded selection by whole sentence until at least 250 utterances, sentences dealt alternately to our dev and test, so one sentence is never in both. Labelled source=public_real; never pooled with TTS.
- Why: At least 200 utterances needed; sentence-level grouping avoids near-duplicate leakage between dev and test. CC-BY-4.0.
- What we actually did: m1_data/fleurs.py (tested offline with a fake tarball), `python -m m1_data fleurs`. The transcripts of the subset go to data/public_real/fleurs_kn_in_test_subset.jsonl; test-assigned files get lines appended to test.lock. NOT RUN yet (disk). I did fetch test.tsv: 838 rows, 7 columns, mean 13.6 s per utterance (about 110 MB for 250).
- What could go wrong / weaknesses: Speaker ids are not in the data, so speaker overlap between dev and test cannot be ruled out. FLEURS text is read news/Wikipedia sentences, not clinical speech.
- What else could be done: Common Voice or Kathbath with a token.
- How to change this decision later: N_MIN and SEED in m1_data/fleurs.py.
- Status: partly done

### D-?: Test lock may only gain lines; the text generator keeps audio rows   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: How audio hashes join data/splits/test.lock and data/manifest.jsonl without breaking the frozen text split.
- Options we considered:
  1. A second lock file. Pro: no change to the old one. Con: the brief and CI read one file.
  2. Append audio lines after a comment line at the end of test.lock; make `generate` preserve that tail and the audio manifest rows. Pro: old lines stay byte-identical; `git diff` shows additions only. Con: generate.py needed a small edit.
- What we chose: Option 2.
- Why: Keeps one lock; proves "only gains lines" with a plain diff.
- What we actually did: m1_data/split.py (`split_audio_tail`; missing git-ignored audio under data/audio/ is skipped, changed audio still fails), m1_data/generate.py (keeps `data/audio/` manifest rows and the lock tail), m1_data/audio_build.py `append_lock` (raises if an already locked file changed). Tests: m1_data/tests/test_audio_lock_integration.py, test_audio_build.py.
- What could go wrong / weaknesses: A fresh clone has no audio, so the audio lock lines are only checked after `make m1-audio`.
- What else could be done: ship a few tiny fixtures.
- How to change this decision later: edit append_lock and split_audio_tail.
- Status: done (code); lines will appear when the audio is built

### D-?: Reproducibility of audio hashes   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: Can `make` regenerate audio with identical sha256?
- Options we considered: lock only the hashes we can reproduce, or lock everything and accept re-lock on drift.
- What we chose: Deterministic design: one torch seed per utterance, CPU only, noise from numpy with a per-file seed, ffmpeg with -bitexact. Verified with the fake synthesiser (two builds give identical hashes). NOT verified for the real MMS model: needs two real runs.
- Why: GPU runs are avoided; CPU torch is usually repeatable on one machine but not guaranteed across machines or versions.
- What we actually did: test_build_is_deterministic_and_rows_validate. `audio-verify` compares the manifest with files on disk.
- What could go wrong / weaknesses: UNVERIFIED that two real runs give the same hashes. If they differ, the test.lock audio lines would flag a rebuild as a change; then rebuild once, accept the hashes as the frozen reference and say so.
- What else could be done: lock the 16 kHz clean turn files' decoded samples with a tolerance instead of a byte hash.
- How to change this decision later: m1_data/audio_build.py (seeds), `mingw32-make m1-audio-verify`.
- Status: partly done
