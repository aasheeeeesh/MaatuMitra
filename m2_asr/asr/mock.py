"""Mock adapter: returns fixture transcripts, needs no model and no audio library."""

from __future__ import annotations

import time
from pathlib import Path

from .base import ASRAdapter, build_transcript, wav_duration_s

DEFAULT_TEXT = "ಜ್ವರ ಇದೆ"  # fallback when a file has no fixture entry (synthetic, not a real answer)


class MockAdapter(ASRAdapter):
    name = "mock"
    revision = "mock-1"
    hardware = "none (mock fixtures, no model)"

    def __init__(self, fixtures: dict[str, str] | None = None, default: str = DEFAULT_TEXT):
        self.fixtures = fixtures or {}
        self.default = default

    def transcribe(self, audio_path, audio_id=None, source="tts"):
        p = Path(audio_path)
        t0 = time.perf_counter()
        aid = audio_id or p.stem
        text = self.fixtures.get(aid, self.fixtures.get(p.stem, self.default))
        dur = wav_duration_s(p)
        return build_transcript(
            aid,
            source,
            self.name,
            self.revision,
            text,
            (time.perf_counter() - t0) * 1000,
            dur,
            self.hardware,
        )
