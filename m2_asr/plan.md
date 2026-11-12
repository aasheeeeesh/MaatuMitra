# m2_asr plan (builder: ml-engineer-asr, 2026-11-12)

1. Interface `asr/base.py`: `transcribe(audio_path) -> transcript.v1 dict`. Adapters: mock (no
   model), faster-whisper (CTranslate2) for Systran small and for a Kannada fine-tune converted
   to CT2 int8. Gated or too-big models are recorded as `not_run` with the reason.
2. Metrics `asr/metrics.py`: CER, grapheme CER, WER, critical-term recall, Wilson, bootstrap,
   latency p50/p95, RTF. Unit tests with hand-computed values come first.
3. Guard `asr/guard.py`: refuses test-split audio (path, conversation id, held-out voice, lock).
4. Common subset (seeded, dev only), same files for every model: `results/m2_asr/common_subset.txt`.
5. Runner: one transcript.v1 JSON per file in `results/m2_asr/dev/<model>/` (resume), plus
   `results/m2_asr/<model>/dev/transcripts.jsonl` + `run.json` in the layout m7 reads.
6. Summary `results/m2_asr/summary.csv`: model x source x slice, bootstrap CIs, status.
7. Disk: one model at a time, pinned revision, safetensors/CT2 only, cache deleted after use.
