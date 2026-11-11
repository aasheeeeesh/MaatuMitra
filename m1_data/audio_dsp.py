"""Audio helpers for m1_data: noise at a target SNR, speed change, 16 kHz mono PCM16 WAV I/O.

Only numpy + stdlib `wave` + the `ffmpeg` binary, so it runs in the normal project venv.
SNR is measured on the whole clip: 10*log10(mean(speech^2) / mean(noise^2)), gaps included.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 16000


def make_noise(kind: str, n: int, seed: int) -> np.ndarray:
    """Unit-RMS noise. white = flat spectrum; pink = power ~ 1/f (FFT shaping)."""
    if kind not in ("white", "pink"):
        raise ValueError(f"unknown noise kind {kind!r}")
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    if kind == "pink":
        spec = np.fft.rfft(w)
        f = np.arange(len(spec), dtype=np.float64)
        f[0] = 1.0
        spec = spec / np.sqrt(f)
        spec[0] = 0.0
        w = np.fft.irfft(spec, n)
    w = w - w.mean()
    return (w / np.sqrt(np.mean(w**2))).astype(np.float32)


def add_noise(x: np.ndarray, kind: str, snr_db: float, seed: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    noise = make_noise(kind, len(x), seed)
    p_sig = float(np.mean(x.astype(np.float64) ** 2))
    scale = np.sqrt(p_sig / (10 ** (snr_db / 10)))
    return (x + scale * noise).astype(np.float32)


def peak_normalise(x: np.ndarray, peak: float) -> np.ndarray:
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    if m == 0.0:
        return np.asarray(x, dtype=np.float32)
    return (x * (peak / m)).astype(np.float32)


def concat_turns(
    turns: list[np.ndarray], gap_s: float
) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Join turns with silence between them. Returns audio and (start_s, end_s) per turn."""
    gap = np.zeros(round(gap_s * SR), dtype=np.float32)
    parts, offsets, pos = [], [], 0
    for i, t in enumerate(turns):
        if i:
            parts.append(gap)
            pos += len(gap)
        offsets.append((round(pos / SR, 3), round((pos + len(t)) / SR, 3)))
        parts.append(np.asarray(t, dtype=np.float32))
        pos += len(t)
    return np.concatenate(parts), offsets


def write_wav(path: Path, x: np.ndarray) -> None:
    pcm = np.clip(np.round(np.asarray(x, dtype=np.float64) * 32767), -32768, 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getsampwidth() == 2 and w.getnchannels() == 1, "expected mono PCM16"
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32767


def wav_info(path: Path) -> tuple[int, int, int, int]:
    """(sample rate, channels, sample width bytes, frames)."""
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()


def change_speed(src: Path, dst: Path, factor: float) -> None:
    """Tempo change by `factor` (1.1 = faster/shorter) with ffmpeg atempo; pitch is kept."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-bitexact", "-i", str(src),
        "-filter:a", f"atempo={factor}", "-ar", str(SR), "-ac", "1",
        "-c:a", "pcm_s16le", "-fflags", "+bitexact", "-f", "wav", str(dst),
    ]  # fmt: skip
    subprocess.run(cmd, check=True)  # noqa: S603 (fixed ffmpeg argv, no shell)


def shift_pitch(src: Path, dst: Path, ratio: float) -> None:
    """Pitch x `ratio` at the same duration (asetrate + atempo). ratio < 1 sounds lower/larger.
    This moves pitch and formants together, so it makes a different-sounding voice but NOT a
    different speaker model; callers must say so."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    flt = f"asetrate={SR * ratio:.3f},aresample={SR},atempo={1 / ratio:.6f}"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-bitexact", "-i", str(src),
        "-filter:a", flt, "-ar", str(SR), "-ac", "1",
        "-c:a", "pcm_s16le", "-fflags", "+bitexact", "-f", "wav", str(dst),
    ]  # fmt: skip
    subprocess.run(cmd, check=True)  # noqa: S603 (fixed ffmpeg argv, no shell)
