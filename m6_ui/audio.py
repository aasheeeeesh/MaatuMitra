"""Synthetic audio fixture and 'play this part' cutting (stdlib `wave` only, no extra deps).

The fixture is a quiet 440 Hz tone with a short higher beep at every whole second, so a
listener can hear where in the file a clip starts. It is NOT speech.

Regenerate the committed fixture: `uv run python -m m6_ui.audio`
"""

from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 8000
DURATION_S = 12.0
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "audio" / "tone_fx.wav"


def make_tone_wav(duration_s: float = DURATION_S, sr: int = SAMPLE_RATE) -> bytes:
    n = int(duration_s * sr)
    frames = bytearray()
    for i in range(n):
        t = i / sr
        beep = (t % 1.0) < 0.08
        freq = 880.0 if beep else 440.0
        amp = 0.35 if beep else 0.12
        frames += struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * t)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def wav_duration(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        return w.getnframes() / w.getframerate()


def cut_wav(wav_bytes: bytes, start: float | None, end: float | None) -> bytes | None:
    """Return a WAV clip of start..end seconds, or None when there is no usable timing."""
    if start is None or end is None or start < 0 or end <= start:
        return None
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            params = w.getparams()
            sr, total = w.getframerate(), w.getnframes()
            a = min(round(start * sr), total)
            b = min(round(end * sr), total)
            if b <= a:
                return None
            w.setpos(a)
            data = w.readframes(b - a)
    except (wave.Error, EOFError, struct.error):
        return None
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setparams(params)
        out.writeframes(data)
    return buf.getvalue()


def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


if __name__ == "__main__":
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_bytes(make_tone_wav())
    print(f"wrote {FIXTURE} ({FIXTURE.stat().st_size} bytes)")
