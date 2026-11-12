### D-?: Audio "clean on disk, variants on demand"   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: Disk had about 2.7 GB free; storing all 3360 WAVs did not fit and m2 needs room for models.
- Options we considered:
  1. Keep every variant on disk. Pro: simple. Con: does not fit.
  2. Keep only clean files; re-make noise/speed variants when needed from the clean file plus seed, noise type, SNR and speed, and check each against a stored sha256. Pro: about 4x smaller. Con: needs a command and bit-exact determinism.
  3. Drop variants. Con: loses the noise and speed experiments.
- What we chose: Option 2. Every variant hash is in data/manifest.jsonl (test ones also appended to test.lock). manifest.v1 has no "stored or not" field and contracts/ is off limits, so that flag lives in data/audio_index/tts_index.jsonl (storage = stored | on_demand, reproducible, clean_file).
- Why: Hashes are recorded before deletion, so nothing is unverifiable.
- What we actually did: m1_data/audio_build.py (render, build, materialise_row), audio_run.py, cli: `python -m m1_data audio-materialise --ids all --split dev --variants white_snr10 --out DIR` (test needs ALLOW_TEST=1), `audio-verify --materialise-sample N`. Checked all 2440 on-demand variants (dev + test, with ALLOW_TEST=1): all rebuilt bit-exact (results/m1_data/materialise_full_check.json). Tests: m1_data/tests/test_audio_ondemand.py.
- What could go wrong / weaknesses: Bit-exactness was shown on this machine only (numpy + ffmpeg version); another machine could differ. The 1.2 GB first run's _turns scratch was deleted, so the clean files cannot be rebuilt without running TTS again.
- What else could be done: ask for a stored-flag field in manifest.v1.
- How to change this decision later: audio_build.build and audio_run.
- Status: done

### D-?: 312 older dev noise files are kept on disk (not bit-reproducible)   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: The first run made dev noise variants from an unrounded float signal, so re-making them from the stored 16-bit clean file differs by up to one rounding step in some samples.
- Options we considered: (1) delete and redefine them from the clean file (saves about 127 MB, but changes the files); (2) keep the originals and record their hash as the truth.
- What we chose: Option 2, as instructed. Speed variants (104 files) and all test pitch voice noise variants were bit-exact and deleted. New variants are defined from the stored clean file, so they are exact.
- Why: Honest hashes beat saved space.
- What we actually did: 6 noise types x 52 dev conversations stay as storage=stored, reproducible=false; materialised_sha256 is recorded for comparison.
- What could go wrong / weaknesses: costs about 127 MB.
- What else could be done: redefine and delete them if disk is needed.
- How to change this decision later: delete the files and set storage in the index.
- Status: done

### D-?: FLEURS subset built; FLEURS WAVs are 32-bit float and converted to PCM16   (Phase B / m1_data / data-scientist / 2026-11-12)
- What we needed to decide: The first FLEURS run crashed: the files are IEEE-float WAV, not PCM16.
- Options we considered: store float (breaks 16-bit rule and python wave); convert deterministically to 16-bit.
- What we chose: Convert (round, clip), recorded sha256 is of the converted file.
- Why: Same format as all other audio.
- What we actually did: fleurs.float_wav_to_pcm16 plus tests. 250 utterances (124 dev, 126 test, split by sentence), 108 MB, CC-BY-4.0; 126 lines appended to test.lock.
- What could go wrong / weaknesses: speaker overlap between dev and test not ruled out; licence page not re-fetched by me this session (UNVERIFIED).
- What else could be done: Common Voice or Kathbath.
- How to change this decision later: fleurs.py.
- Status: done
