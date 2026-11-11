# data

All data (synthetic, TTS or public-licensed only; no patient data). Built by m1_data with `make data`. Large audio is git-ignored; hashes live in manifest.jsonl.

## Audio (added by task B1b; NOT built yet, see m1_data/handoff/decisions.md)

Audio is git-ignored (`data/audio/**`); sha256 lives in `manifest.jsonl`; test audio hashes are appended to `splits/test.lock`.
Build with `mingw32-make m1-audio` (MMS-TTS Kannada, source=tts; FLEURS kn_in subset, source=public_real), check with `mingw32-make m1-audio-verify`.
`audio_index/tts_index.jsonl` (tracked) records voice, noise type, SNR, speed, seed, turn offsets and the Kannada-script TTS input per file;
`public_real/fleurs_kn_in_test_subset.jsonl` lists the FLEURS utterances and transcripts. Report TTS and public_real numbers separately.
