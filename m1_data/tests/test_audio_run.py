"""Disk guard, plan estimate and manifest verification of the audio commands."""

from __future__ import annotations

import json

import pytest

from m1_data import audio_build as ab
from m1_data import audio_run as ar

from .conftest import ROOT


def test_disk_guard_stops_below_the_floor(monkeypatch):
    monkeypatch.setattr(ar, "free_gb", lambda p: 3.9)
    with pytest.raises(ar.DiskLow):
        ar.disk_guard(ROOT, 4.0)()
    monkeypatch.setattr(ar, "free_gb", lambda p: 5.0)
    ar.disk_guard(ROOT, 4.0)()  # no raise


def test_estimate_counts_and_stays_under_the_cap():
    e = ar.estimate(ROOT)
    assert e["items"] == len(ab.plan(ROOT))
    assert e["test_conversations"] == 264 and e["dev_conversations"] == ab.DEV_SUBSET_N
    assert e["tts_gb_estimate"] < 2.5


def test_verify_reports_changed_and_missing_audio(tmp_path):
    (tmp_path / "data").mkdir()
    f = tmp_path / "data" / "audio" / "tts" / "test" / "v" / "clean" / "c.wav"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"abc")
    import hashlib

    good = {
        "file": "data/audio/tts/test/v/clean/c.wav",
        "sha256": hashlib.sha256(b"abc").hexdigest(),
        "bytes": 3,
    }
    gone = {"file": "data/audio/tts/test/v/clean/d.wav", "sha256": "0" * 64, "bytes": 1}
    text = "".join(json.dumps(r) + "\n" for r in (good, gone))
    (tmp_path / "data" / "manifest.jsonl").write_text(text, encoding="utf-8")
    res = ar.verify(tmp_path)
    assert res["checked"] == 1 and res["missing"] == 1 and res["bad"] == []
    f.write_bytes(b"abd")
    assert ar.verify(tmp_path)["bad"] == ["data/audio/tts/test/v/clean/c.wav"]
