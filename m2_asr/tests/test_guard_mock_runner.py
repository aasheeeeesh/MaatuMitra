import json
import wave
from pathlib import Path

import pytest

from contracts import validate
from m2_asr.asr import guard, mock, runner
from m2_asr.asr.base import build_transcript

ROOT = Path(__file__).resolve().parents[2]


def _wav(p: Path, seconds: float = 1.0) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return p


def test_guard_refuses_test_split_audio(tmp_path):
    g = guard.DevGuard(ROOT)
    test_ids = [x.strip() for x in (ROOT / "data/splits/test.txt").read_text().split() if x.strip()]
    assert test_ids, "test.txt must list conversations"
    with pytest.raises(guard.TestSplitRefused):
        g.check(f"data/audio/tts/test/mms_kan_base/clean/{test_ids[0]}.wav")  # folder 'test'
    with pytest.raises(guard.TestSplitRefused):
        g.check(tmp_path / "dev" / "x" / f"{test_ids[0]}.wav")  # test conversation id in a dev path
    with pytest.raises(guard.TestSplitRefused):
        g.check("data/audio/tts/dev/mms_kan_pitch084/clean/m1-a1-007.wav")  # held-out voice
    with pytest.raises(guard.TestSplitRefused):
        g.check("data/audio/public_real/fleurs_kn_in/test/1.wav")
    lock_line = next(
        ln
        for ln in (ROOT / "data/splits/test.lock").read_text().splitlines()
        if not ln.startswith("#") and "  " in ln
    )
    with pytest.raises(guard.TestSplitRefused):
        g.check(lock_line.split("  ", 1)[1])
    dev_ids = [x.strip() for x in (ROOT / "data/splits/dev.txt").read_text().split() if x.strip()]
    g.check(f"data/audio/tts/dev/mms_kan_base/clean/{dev_ids[0]}.wav")  # fine


def test_runner_refuses_test_audio_before_transcribing(tmp_path):
    calls = []

    class Spy(mock.MockAdapter):
        def transcribe(self, audio_path, **kw):
            calls.append(audio_path)
            return super().transcribe(audio_path, **kw)

    bad = _wav(tmp_path / "test" / "a.wav")
    entries = [{"audio_id": "a", "path": str(bad), "source": "tts", "voice": "v"}]
    with pytest.raises(guard.TestSplitRefused):
        runner.run_entries(Spy({}), entries, tmp_path / "out", guard.DevGuard(ROOT))
    assert calls == []


def test_mock_adapter_needs_no_model_and_emits_valid_transcripts(tmp_path):
    wav = _wav(tmp_path / "dev" / "m1-a1-007__mms_kan_base__clean.wav", 2.0)
    ad = mock.MockAdapter({"m1-a1-007__mms_kan_base__clean": "ನೆಗಡಿ ಇಲ್ಲಾ"})
    t = ad.transcribe(wav)
    assert t["text"] == "ನೆಗಡಿ ಇಲ್ಲಾ" and t["model"]["name"] == "mock"
    assert t["audio_duration_s"] == 2.0
    assert [w["w"] for w in t["words"]] == ["ನೆಗಡಿ", "ಇಲ್ಲಾ"]
    assert t["text"][t["words"][1]["char_start"] : t["words"][1]["char_end"]] == "ಇಲ್ಲಾ"
    assert validate.validate_doc("transcript.v1", t) == []


def test_build_transcript_normalises_text():
    t = build_transcript("x", "tts", "m", "r", "﻿ ಕಿ​  ಕ ", 1.0, 1.0, "hw")
    assert t["text"] == "ಕಿ ಕ" and "​" not in t["text"]


def test_runner_resume_and_outputs(tmp_path):
    wavs = [_wav(tmp_path / "dev" / f"c{i}.wav") for i in range(3)]
    entries = [
        {"audio_id": f"c{i}", "path": str(w), "source": "tts", "voice": "v"}
        for i, w in enumerate(wavs)
    ]
    out = tmp_path / "out"
    ad = mock.MockAdapter({"c0": "ಒಂದು"})
    r1 = runner.run_entries(ad, entries, out, guard.DevGuard(ROOT))
    assert (r1["done"], r1["skipped"], r1["failed"]) == (3, 0, 0)
    r2 = runner.run_entries(ad, entries, out, guard.DevGuard(ROOT))
    assert (r2["done"], r2["skipped"]) == (0, 3)  # resume: nothing redone
    files = sorted(out.glob("*.json"))
    assert len(files) == 3
    assert json.loads(files[0].read_text(encoding="utf-8"))["schema_version"] == "transcript.v1"
    agg_path = tmp_path / "agg" / "dev" / "transcripts.jsonl"
    assert runner.aggregate(out, agg_path) == 3
    assert len(agg_path.read_text(encoding="utf-8").splitlines()) == 3


def test_subset_is_deterministic_and_dev_only():
    from m2_asr.asr import subset

    idx = [
        {
            "audio_id": f"{c}__v__{v}",
            "conv_id": c,
            "voice": "v",
            "variant": v,
            "split": "dev",
            "storage": "stored",
            "file": f"data/audio/tts/dev/v/{v}/{c}.wav",
            "duration_s": 5.0,
        }
        for c in [f"c{i}" for i in range(10)]
        for v in ("clean", "white_snr5")
    ]
    a = subset.pick_conversations(idx, n=4, seed=7)
    assert a == subset.pick_conversations(idx, n=4, seed=7)
    assert len(a) == 4 and len(set(a)) == 4
    assert a != subset.pick_conversations(idx, n=4, seed=8)
