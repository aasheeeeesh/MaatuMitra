"""Synthetic tone fixture and 'play this part' cutting."""

from __future__ import annotations

import io
import wave

import pytest

from m6_ui import audio
from m6_ui.tests.helpers import M6


def test_fixture_wav_exists_is_synthetic_and_reproducible():
    p = M6 / "fixtures" / "audio" / "tone_fx.wav"
    assert p.exists()
    assert p.read_bytes() == audio.make_tone_wav()
    assert audio.wav_duration(p.read_bytes()) >= 11.08  # longest fixture transcript


def test_cut_has_the_requested_length():
    wav = audio.make_tone_wav()
    clip = audio.cut_wav(wav, 0.3, 4.66)
    assert clip is not None
    assert audio.wav_duration(clip) == pytest.approx(4.36, abs=0.01)
    with wave.open(io.BytesIO(clip)) as w:
        assert w.getframerate() == audio.SAMPLE_RATE


@pytest.mark.parametrize("start,end", [(None, 1.0), (1.0, None), (None, None), (5.0, 4.0), (-1, 2)])
def test_no_timing_returns_none(start, end):
    assert audio.cut_wav(audio.make_tone_wav(), start, end) is None


def test_cut_is_clamped_to_audio_length():
    wav = audio.make_tone_wav()
    clip = audio.cut_wav(wav, 11.5, 50.0)
    assert clip is not None and audio.wav_duration(clip) <= audio.wav_duration(wav) - 11.5 + 0.01


def test_garbage_audio_returns_none():
    assert audio.cut_wav(b"not a wav", 0.0, 1.0) is None
