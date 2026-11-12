"""ASR adapter interface: transcribe(audio_path) -> transcript.v1 (a dict)."""

from __future__ import annotations

import re
import unicodedata
import wave
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

_WORD = re.compile(r"\S+")


def wav_duration_s(path: str | Path) -> float:
    """Duration of a PCM WAV in seconds (stdlib only, so mock mode needs no audio package)."""
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def clean_text(text: str) -> str:
    """Stored-text rules: no BOM, no zero-width space, NFC, single spaces. ZWJ/ZWNJ are kept."""
    text = text.translate({0xFEFF: None, 0x200B: None})
    return " ".join(unicodedata.normalize("NFC", text).split())


def build_transcript(
    audio_id: str,
    source: str,
    model_name: str,
    revision: str,
    text: str,
    latency_ms: float | None,
    duration_s: float | None,
    hardware: str | None,
) -> dict:
    """Assemble a transcript.v1 dict. Words are whitespace tokens with code-point offsets; no
    word timing or confidence is available from these adapters (null)."""
    text = clean_text(text)
    words = [
        {
            "w": m.group(),
            "char_start": m.start(),
            "char_end": m.end(),
            "start": None,
            "end": None,
            "conf": None,
        }
        for m in _WORD.finditer(text)
    ]
    return {
        "schema_version": "transcript.v1",
        "audio_id": audio_id,
        "source": source,
        "model": {"name": model_name, "revision": revision},
        "text": text,
        "words": words,
        "latency_ms": None if latency_ms is None else round(latency_ms, 1),
        "audio_duration_s": None if duration_s is None else round(duration_s, 3),
        "hardware": hardware,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


class ASRAdapter(ABC):
    """One adapter per model. `name` and `revision` identify the model in every output."""

    name: str = "unnamed"
    revision: str = "UNVERIFIED"
    hardware: str = "unknown"

    @abstractmethod
    def transcribe(
        self, audio_path: str | Path, audio_id: str | None = None, source: str = "tts"
    ) -> dict:
        """Return one transcript.v1 dict; latency_ms covers decode + inference, not model load."""
