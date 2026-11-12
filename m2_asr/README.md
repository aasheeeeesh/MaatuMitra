# m2_asr (L1 speech to text), DEV results only

Built 2026-11-12 by `ml-engineer-asr`. Everything below is DEV. No test audio was transcribed
(`asr/guard.py` refuses it; `results/test_access_log.md` does not exist). Nothing here is
native-validated. TTS speech is synthetic (MMS-TTS voice), not real patients.

## Commands
```
mingw32-make m2-test        # 17 tests (metrics with hand-computed values, guard, mock, runner)
mingw32-make m2-mock        # mock adapter on fixtures only: no model, no repo audio
uv run python -m m2_asr subset --n-conv 36          # writes results/m2_asr/common_subset.{txt,json}
uv run python -m m2_asr run --model faster-whisper-small            # dev only, resumable
uv run python -m m2_asr run --model whisper-small-vaani-kannada
uv run python -m m2_asr summarise                   # results/m2_asr/summary.csv, paired_cer.csv
uv run python -m m2_asr purge --model <name>        # deletes that model's HF cache
uv run python m2_asr/tools/m7_crosscheck.py <scratch dir>   # m7's E1 code reads our outputs
```
Notebook: `notebooks/m2_dev_run.ipynb` (parameters MODEL, RUN); executed copies with outputs are
`results/m2_asr/<model>/m2_dev_run.executed.ipynb`. The baseline notebook used `RUN=False` (the
real run was a background CLI job); the vaani notebook used `RUN=True` and only resumed
(292 files skipped in the first batch), because every file already existed.

## Layout of outputs
- `results/m2_asr/dev/<model>/<hash8>.json`: one transcript.v1 per audio file (448 per model). The file name is 8 hex chars of sha1(audio_id) because of Windows MAX_PATH; the real `audio_id` is inside. `uv run python -m contracts.validate transcript.v1 results/m2_asr/dev/<model>`: 448/448 valid for both models.
- `results/m2_asr/<model>/dev/transcripts.jsonl` + `run.json`: the layout m7_eval reads (E1).
- `results/m2_asr/common_subset.txt` / `.json`: the common subset. `summary.csv`, `paired_cer.csv`.

## Common subset (same files for every model; dev only)
36 TTS conversations (seed 20261109, sampled from the 80 dev conversations) with all 9 variants
(clean, white and pink noise at SNR 20/10/5 dB, speed 0.9 and 1.1) = 324 files, voice
`mms_kan_base` only; plus all 124 FLEURS kn_IN dev clips (`public_real`). 448 files, 5871 s audio.
Variants stored as `on_demand` were rebuilt with `m1_data audio-materialise` (sha256-verified) in
batches of 48 and deleted after each batch. TTS and public_real are always reported separately.
The reference for TTS is `data/transcripts/gold/<conv>__gold.json`; for FLEURS the `transcription`
field of the subset file. A "voice" slice exists but dev has only one voice.

## Models
| model | Kannada? | licence (HF API 2026-11-12) | revision | status |
|---|---|---|---|---|
| faster-whisper-small (Systran CTranslate2 of Whisper small), int8 CPU | listed among Whisper languages; quality: see results | MIT | 536b0662742c02347bc0e980a01041f333bce120 | ran, 448/448 |
| ARTPARK-IISc/whisper-small-vaani-kannada, converted here to CTranslate2 int8 | Kannada fine-tune (card also says `language: hi`: UNVERIFIED metadata slip) | Apache-2.0 | 65a803da247c0727bbd254b3c421046a60dd140b (+ct2-int8) | ran, 448/448 |
| ai4bharat/indic-conformer-600m-multilingual | has a Kannada head (file list) | MIT (API) | not pinned | pending: gated, 2.56 GB, custom code |
| ekacare/parrotlet-a-en-5b | card tag: English only, so NO Kannada | MIT (API) | not pinned | pending: gated, ~10 GB. Not run, recorded as expected negative |
| facebook/mms-1b-all | yes (MMS) | CC-BY-NC-4.0 (non-commercial; ok for coursework) | not pinned | pending: 3.86 GB > free disk |
| ai4bharat IndicWhisper | claimed | UNVERIFIED | none | no HF repo found by API (auth error) |
| vasista22/whisper-kannada-small | yes | Apache-2.0 | not pinned | not run: only pickle (`pytorch_model.bin`) weights |
| whisper-large-v3 | yes | MIT (UNVERIFIED this session) | none | not run: needs GPU runtime not installed |

Decoding (both runs, fixed before the full run): greedy (beam 1), temperature 0, language `kn`,
`condition_on_previous_text=False`, no VAD, 8 CPU threads, int8. A 3-clip dev probe showed that
beam 5 (33 s per clip) or repetition penalty gave no useful output for the Systran model, so the
pre-set greedy setting was kept. A 6-clip dev probe with the vaani model gave nearly identical CER
for language `kn` and `ka`; `kn` was kept.

## Results (DEV, CPU only, GPU not used)
Hardware: i7-12650H (16 logical CPUs, 8 threads used), 16 GB RAM, RTX 3050 Ti 4 GB NOT used (torch is
CPU-only; no CUDA runtime for CTranslate2). CER = Levenshtein on NFC code points after the
comparison normalisation, punctuation kept. CI = percentile bootstrap (1000 resamples, seed
20261109). Source of every number: `results/m2_asr/summary.csv`.

| model | source (N) | CER [95% CI] | grapheme CER | WER | latency p50 / p95 (ms) | RTF |
|---|---|---|---|---|---|---|
| faster-whisper-small | public_real (124) | 1.042 [0.998, 1.091] | 1.032 | 1.000 | 2814 / 2976 | 0.241 |
| faster-whisper-small | tts (324) | 1.269 [1.200, 1.343] | 1.175 | 1.006 | 2742 / 2956 | 0.240 |
| whisper-small-vaani-kannada | public_real (124) | 0.155 [0.130, 0.180] | 0.167 | 0.377 | 2637 / 2936 | 0.215 |
| whisper-small-vaani-kannada | tts (324) | 0.249 [0.233, 0.265] | 0.304 | 0.625 | 2552 / 4884 | 0.224 |

Paired (same files) CER difference, Systran minus vaani: tts +1.021 [0.949, 1.098], public_real
+0.887 [0.834, 0.944] (`paired_cer.csv`). The CI excludes 0, so the Kannada fine-tune is better on both.

Whisper small without fine-tuning is unusable here: CER above 1 because it falls into repetition
loops (for example "ಸಿಕಾರಿ ಸಿಕಾರಿ ..." until the 448-token limit), 0 hits for every critical-term class, and its latency
is the length of the loop, not of the speech (so its latency is not comparable with a model that stops).

Critical-term recall, vaani model (hits / reference terms; Wilson CIs in summary.csv):
TTS: negation 72/216, number 569/738, drug 18/351, unit 168/342. public_real: negation 12/13,
number 14/61, drug 0/0, unit 0/0. This is an EXACT-token match (same definition as m7): "ಇಲ್ಲ" in
the reference but "ಇಲ್ಲಾ" in the output is a miss, and "ದಿನದಿಲ್ಲಾ" (a different word ending in a
negation suffix) is a false hit. Drug names in Kannada script are transliterations and the model
spells them differently, so drug recall 18/351 mostly measures spelling, not understanding. Treat
all recall numbers as lower bounds. The FLEURS number miss (14/61) is probably digits versus words
(UNVERIFIED, not analysed).

Vaani model, TTS by variant (N = 36 each, CER [CI]): clean 0.243 [0.190, 0.307]; white SNR 20/10/5:
0.223 / 0.270 / 0.293; pink SNR 20/10/5: 0.243 / 0.236 / 0.262; speed 0.9 / 1.1: 0.231 / 0.241.
Noise at 5 dB raises CER, but the CIs overlap with clean, so with 36 conversations the effect is not
established. Code-switched references (Latin letters present; N = 135 TTS) have CER 0.346 [0.322, 0.373] versus
0.179 [0.167, 0.194] for the other 189 files.

Dropped negation, a known blind spot: CER does not show it. In `tests/test_metrics.py` one dropped
"ಇಲ್ಲ" gives CER 0.5 on a two-word phrase but critical-term negation recall 0/1; with a long sentence the
CER would be small while the meaning flips.

## Caveats (read these)
- The vaani model card says FLEURS was part of its training/evaluation data. Overlap with our
  FLEURS clips is UNVERIFIED; its public_real CER may be optimistic.
- Dev has one TTS voice and 36 conversations; the 9 variants of one conversation are not independent
  (same sentences), so the bootstrap CIs over files are too narrow for between-conversation claims.
- Latency: decode + inference per file, model load and one warm-up file excluded; the machine also ran
  other agents' jobs, so p95 is noisy. 8 of the 448 files per model came from a `--limit 8` probe run with the
  same settings (their latency was measured in that probe).
- Only 2 of the models in the brief ran. IndicWhisper, the AI4Bharat conformer, MMS and Parrotlet
  are `pending` for the reasons above, not skipped silently. See `human_todo.md` items.
- m7 cross-check: m7's independent E1 code reads these outputs and reproduces our CER means
  exactly (1.0416, 1.2694, 0.1548, 0.2489), but `make eval` currently crashes in m7 with
  `KeyError: 'file_name'` (the FLEURS file has key `file`). Real error text and the fix are in
  `handoff/open_questions.md`; `tools/m7_crosscheck.py` shows it with an in-memory shim. m7 was not edited.
- Phase C (test) run: NOT implemented. The runner refuses test audio by design. After human approval and
  the orchestrator's guarded `make eval-test` path, add a test subset builder and a wrapper that passes
  the guard explicitly; the models can be re-downloaded with `python -m m2_asr run` code at the
  pinned revisions above.

## Disk
Free C: 2.7 GB before, about 2.4 GB after (the pagefile also moves). The floor of 1.5 GB was never
crossed. Deleted: HF cache of Systran/faster-whisper-small (486 MB), HF cache of
ARTPARK-IISc/whisper-small-vaani-kannada (969 MB, deleted automatically inside the conversion once the
weights were in RAM), batches of materialised audio after each batch, and the scratch folder
`%TEMP%\m2scratch` (converted int8 model 243 MB) at the end.
