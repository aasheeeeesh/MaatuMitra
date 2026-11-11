"""Audio variants (noise at a target SNR, speed change, WAV I/O). Pure numpy + ffmpeg."""

from __future__ import annotations

import shutil

import numpy as np
import pytest

from m1_data import audio_dsp as dsp


def _tone(n=16000, f=300.0):
    t = np.arange(n) / dsp.SR
    return (0.4 * np.sin(2 * np.pi * f * t)).astype(np.float32)


@pytest.mark.parametrize("kind", ["white", "pink"])
@pytest.mark.parametrize("snr", [20.0, 10.0, 5.0])
def test_snr_is_exact(kind, snr):
    x = _tone()
    y = dsp.add_noise(x, kind, snr, seed=7)
    noise = y - x
    got = 10 * np.log10(np.mean(x**2) / np.mean(noise**2))
    assert abs(got - snr) < 0.05


def test_noise_is_deterministic_and_seed_dependent():
    x = _tone()
    a, b = dsp.add_noise(x, "pink", 10, seed=1), dsp.add_noise(x, "pink", 10, seed=1)
    c = dsp.add_noise(x, "pink", 10, seed=2)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_pink_has_more_low_frequency_energy_than_white():
    z = np.zeros(16000 * 4, dtype=np.float32)
    ratios = {}
    for kind in ("white", "pink"):
        n = dsp.make_noise(kind, len(z), seed=3)
        sp = np.abs(np.fft.rfft(n)) ** 2
        ratios[kind] = sp[: len(sp) // 8].sum() / sp[len(sp) // 2 :].sum()
    assert ratios["white"] < 1.5
    assert ratios["pink"] > 10 * ratios["white"]


def test_unknown_noise_kind_rejected():
    with pytest.raises(ValueError):
        dsp.add_noise(_tone(), "brown", 10, seed=1)


def test_wav_roundtrip_is_pcm16_16k_mono(tmp_path):
    x = _tone()
    p = tmp_path / "a.wav"
    dsp.write_wav(p, x)
    assert dsp.wav_info(p) == (16000, 1, 2, 16000)
    y = dsp.read_wav(p)
    assert np.max(np.abs(x - y)) < 1 / 16000


def test_wav_write_is_byte_deterministic(tmp_path):
    x = _tone()
    dsp.write_wav(tmp_path / "a.wav", x)
    dsp.write_wav(tmp_path / "b.wav", x)
    assert (tmp_path / "a.wav").read_bytes() == (tmp_path / "b.wav").read_bytes()


def test_concat_inserts_gap():
    a, b = _tone(8000), _tone(4000)
    y, offsets = dsp.concat_turns([a, b], gap_s=0.5)
    assert len(y) == 8000 + 8000 + 4000
    assert offsets == [(0.0, 0.5), (1.0, 1.25)]
    assert np.all(y[8000:16000] == 0)


def test_peak_normalise():
    y = dsp.peak_normalise(_tone() * 2, peak=0.5)
    assert abs(np.max(np.abs(y)) - 0.5) < 1e-6
    assert np.array_equal(dsp.peak_normalise(np.zeros(5, np.float32), 0.5), np.zeros(5, np.float32))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
@pytest.mark.parametrize("factor", [0.9, 1.1])
def test_speed_changes_duration(tmp_path, factor):
    src, dst = tmp_path / "s.wav", tmp_path / "d.wav"
    dsp.write_wav(src, _tone(16000 * 2))
    dsp.change_speed(src, dst, factor)
    assert dsp.wav_info(dst)[:3] == (16000, 1, 2)
    ratio = dsp.wav_info(src)[3] / dsp.wav_info(dst)[3]  # frames old / new
    assert abs(ratio - factor) < 0.01


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_speed_is_deterministic(tmp_path):
    src = tmp_path / "s.wav"
    dsp.write_wav(src, _tone(16000))
    dsp.change_speed(src, tmp_path / "a.wav", 0.9)
    dsp.change_speed(src, tmp_path / "b.wav", 0.9)
    assert (tmp_path / "a.wav").read_bytes() == (tmp_path / "b.wav").read_bytes()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_pitch_shift_lowers_pitch_and_keeps_duration(tmp_path):
    src, dst = tmp_path / "s.wav", tmp_path / "d.wav"
    dsp.write_wav(src, _tone(16000 * 2, f=400.0))
    dsp.shift_pitch(src, dst, 0.8)
    assert abs(dsp.wav_info(dst)[3] - 32000) < 400  # duration kept within 25 ms
    y = dsp.read_wav(dst)
    spec = np.abs(np.fft.rfft(y))
    f_peak = np.argmax(spec) * dsp.SR / len(y)
    assert abs(f_peak - 320.0) < 5.0  # 400 Hz * 0.8
