"""FLEURS kn_in subset: seeded, sentence-grouped selection and streamed extraction."""

from __future__ import annotations

import io
import tarfile
import wave

import pytest

from contracts.validate import validate_doc
from m1_data import fleurs as fl


def _rows(n_sent=60, per=3):
    rows = []
    for s in range(n_sent):
        for k in range(per):
            rows.append(
                {
                    "sentence_id": str(1000 + s),
                    "file_name": f"{s}_{k}.wav",
                    "raw_transcription": f"sentence {s}",
                    "transcription": f"sentence {s}",
                    "num_samples": 160000,
                    "gender": "FEMALE" if k else "MALE",
                }
            )
    return rows


def test_selection_is_seeded_grouped_and_big_enough():
    a, b = fl.select(_rows(), n_min=100, seed=5), fl.select(_rows(), n_min=100, seed=5)
    assert a == b and len(a) >= 100
    assert a != fl.select(_rows(), n_min=100, seed=6)
    sent_split = {}
    for r in a:
        assert sent_split.setdefault(r["sentence_id"], r["split"]) == r["split"]  # no straddling
    assert {r["split"] for r in a} == {"dev", "test"}


def test_selection_takes_everything_if_fewer_than_n_min():
    assert len(fl.select(_rows(2, 2), n_min=200, seed=1)) == 4


def test_parse_tsv_real_layout(tmp_path):
    p = tmp_path / "t.tsv"
    p.write_text("1\ta.wav\tರಾ\tನೋ\tp h\t100\tMALE\n", encoding="utf-8")
    r = fl.parse_tsv(p)[0]
    assert (r["sentence_id"], r["file_name"], r["num_samples"], r["gender"]) == (
        "1",
        "a.wav",
        100,
        "MALE",
    )


def _wav_bytes(n=1600, channels=1):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x01\x00" * n * channels)
    return buf.getvalue()


def _tar(path, names, channels=1):
    with tarfile.open(path, "w:gz") as tf:
        for name in names:
            data = _wav_bytes(channels=channels)
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))


def test_stream_extract_only_wanted_files(tmp_path):
    tar_path = tmp_path / "t.tar.gz"
    _tar(tar_path, ["test/a.wav", "test/b.wav", "test/c.wav"])
    out = tmp_path / "out"
    got = fl.stream_extract(tar_path.as_uri(), {"a.wav": "dev", "c.wav": "test"}, out)
    assert sorted(got) == ["a.wav", "c.wav"]
    assert (out / "dev" / "a.wav").exists() and (out / "test" / "c.wav").exists()
    assert not (out / "dev" / "b.wav").exists()


def test_stream_extract_rejects_wrong_format(tmp_path):
    tar_path = tmp_path / "t.tar.gz"
    _tar(tar_path, ["a.wav"], channels=2)
    with pytest.raises(ValueError):
        fl.stream_extract(tar_path.as_uri(), {"a.wav": "dev"}, tmp_path / "o")


def test_manifest_row_validates(tmp_path):
    f = tmp_path / "x.wav"
    f.write_bytes(_wav_bytes())
    row = fl.manifest_row("data/audio/public_real/fleurs_kn_in/dev/x.wav", f, "dev", "FEMALE", 7)
    assert validate_doc("manifest.v1", row) == []
    assert row["source"] == "public_real" and row["licence_spdx"] == "CC-BY-4.0"


def _float_wav_bytes(samples, sr=16000):
    import struct

    data = struct.pack(f"<{len(samples)}f", *samples)
    fmt = struct.pack("<HHIIHHH", 3, 1, sr, sr * 4, 4, 32, 0)  # IEEE float, 18-byte fmt chunk
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"fact" + struct.pack("<II", 4, len(samples)) + b"data" + struct.pack("<I", len(data))
    return b"RIFF" + struct.pack("<I", len(body) + len(data)) + body + data


def test_float32_wav_is_converted_to_pcm16_deterministically(tmp_path):
    raw = _float_wav_bytes([0.0, 0.5, -0.5, 1.0, -1.0, 2.0, 1 / 32767])
    out = fl.float_wav_to_pcm16(raw)
    assert out == fl.float_wav_to_pcm16(raw)
    p = tmp_path / "x.wav"
    p.write_bytes(out)
    with wave.open(str(p), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        pcm = w.readframes(w.getnframes())
    import numpy as np

    assert list(np.frombuffer(pcm, dtype="<i2")) == [0, 16384, -16384, 32767, -32767, 32767, 1]
    assert fl.float_wav_to_pcm16(_wav_bytes()) == _wav_bytes()  # PCM16 passes through unchanged


def test_stream_extract_converts_float_wavs(tmp_path):
    tar_path = tmp_path / "t.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        d = _float_wav_bytes([0.1] * 800)
        ti = tarfile.TarInfo("test/f.wav")
        ti.size = len(d)
        tf.addfile(ti, io.BytesIO(d))
    got = fl.stream_extract(tar_path.as_uri(), {"f.wav": "dev"}, tmp_path / "o")
    assert got == ["f.wav"]
    with wave.open(str(tmp_path / "o" / "dev" / "f.wav"), "rb") as w:
        assert w.getsampwidth() == 2 and w.getnframes() == 800
