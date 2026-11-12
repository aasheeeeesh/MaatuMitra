"""faster-whisper (CTranslate2) adapter, CPU int8. Also converts a Hugging Face Whisper
checkpoint (safetensors) to a CT2 int8 folder."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .base import ASRAdapter, build_transcript, wav_duration_s
from .models import hardware_string


def convert_hf_to_ct2(
    hf_dir: str | Path,
    out_dir: str | Path,
    tokenizer_json: str | Path | None = None,
    after_load=None,
) -> Path:
    """HF Whisper (safetensors) -> CTranslate2 int8. Tokenizer.json is copied from a pinned
    Whisper CT2 snapshot (all multilingual Whisper sizes share one vocabulary)."""
    from ctranslate2.converters import TransformersConverter

    if after_load is not None:
        # Disk is tight: once the weights are in RAM, let the caller delete the source files
        # BEFORE the int8 copy is written, so the free-disk floor is never crossed.
        orig = TransformersConverter.load_tokenizer

        def patched(self, tokenizer_class, model_name_or_path, **kw):
            tok = orig(self, tokenizer_class, model_name_or_path, **kw)  # runs after the model load
            after_load()
            return tok

        TransformersConverter.load_tokenizer = patched
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    try:
        TransformersConverter(
            str(hf_dir),
            load_as_float16=False,
        ).convert(str(out), quantization="int8", force=True)
    finally:
        if after_load is not None:
            TransformersConverter.load_tokenizer = orig
    if tokenizer_json and Path(tokenizer_json).exists():
        shutil.copyfile(tokenizer_json, out / "tokenizer.json")
    return out


class FasterWhisperAdapter(ASRAdapter):
    def __init__(
        self,
        model_dir: str | Path,
        name: str,
        revision: str,
        language: str = "kn",
        beam_size: int = 1,
        compute_type: str = "int8",
        cpu_threads: int = 8,
    ):
        from faster_whisper import WhisperModel  # lazy: mock mode needs no package

        self.name, self.revision = name, revision
        self.language, self.beam_size = language, beam_size
        self.compute_type, self.cpu_threads = compute_type, cpu_threads
        self.hardware = hardware_string(compute_type, cpu_threads)
        self.model = WhisperModel(
            str(model_dir), device="cpu", compute_type=compute_type, cpu_threads=cpu_threads
        )

    def settings(self) -> dict:
        return {
            "language": self.language,
            "beam_size": self.beam_size,
            "temperature": 0.0,
            "condition_on_previous_text": False,
            "vad_filter": False,
            "task": "transcribe",
            "compute_type": self.compute_type,
            "cpu_threads": self.cpu_threads,
        }

    def transcribe(self, audio_path, audio_id=None, source="tts"):
        p = Path(audio_path)
        t0 = time.perf_counter()
        segs, _info = self.model.transcribe(
            str(p),
            language=self.language,
            task="transcribe",
            beam_size=self.beam_size,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        text = " ".join(s.text.strip() for s in segs)  # generator: decoding happens here
        lat = (time.perf_counter() - t0) * 1000
        return build_transcript(
            audio_id or p.stem,
            source,
            self.name,
            self.revision,
            text,
            lat,
            wav_duration_s(p),
            self.hardware,
        )
