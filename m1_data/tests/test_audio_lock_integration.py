"""The text generator must coexist with audio rows: it keeps them in manifest.jsonl and keeps the
appended audio tail of test.lock byte for byte; the lock check tolerates missing (git-ignored) audio."""

from __future__ import annotations

import json
import shutil

from m1_data.audio_build import LOCK_COMMENT
from m1_data.generate import generate
from m1_data.split import split_audio_tail, verify_lock

from .conftest import DATA


def _copy_data(dst):
    for sub in ("lexicon", "splits"):
        shutil.copytree(DATA / sub, dst / "data" / sub)
    shutil.copy(DATA / "manifest.jsonl", dst / "data" / "manifest.jsonl")


def test_split_audio_tail():
    head, tail = split_audio_tail(
        "# h\nabc  data/gold/x.json\n" + LOCK_COMMENT + "\nff  data/audio/a.wav\n"
    )
    assert head == "# h\nabc  data/gold/x.json\n"
    assert tail.startswith(LOCK_COMMENT) and tail.endswith("data/audio/a.wav\n")
    assert split_audio_tail("# h\n") == ("# h\n", "")


def test_generate_preserves_audio_rows_and_lock_tail(tmp_path):
    _copy_data(tmp_path)
    lock = tmp_path / "data" / "splits" / "test.lock"
    tail = LOCK_COMMENT + "\n" + "0" * 64 + "  data/audio/tts/test/v/clean/m1-a5-000.wav\n"
    lock.write_bytes(lock.read_bytes() + tail.encode())
    row = {
        "schema_version": "manifest.v1",
        "file": "data/audio/tts/test/v/clean/m1-a5-000.wav",
        "sha256": "0" * 64,
        "bytes": 1,
        "source": "tts",
        "split": "test",
    }
    mp = tmp_path / "data" / "manifest.jsonl"
    mp.write_text(mp.read_text(encoding="utf-8") + json.dumps(row) + "\n", encoding="utf-8")
    before = lock.read_bytes()
    generate(out_root=tmp_path)
    assert lock.read_bytes() == before
    rows = [json.loads(x) for x in mp.read_text(encoding="utf-8").splitlines()]
    assert row in rows
    assert [r["file"] for r in rows] == sorted(r["file"] for r in rows)


def test_missing_ignored_audio_is_not_a_lock_failure(tmp_path):
    (tmp_path / "data" / "splits").mkdir(parents=True)
    lock = tmp_path / "data" / "splits" / "test.lock"
    lock.write_text("1" * 64 + "  data/audio/tts/test/v/clean/x.wav\n", encoding="utf-8")
    assert verify_lock(lock, tmp_path) == []
    f = tmp_path / "data/audio/tts/test/v/clean/x.wav"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"edited")
    assert any("CHANGED" in p for p in verify_lock(lock, tmp_path))
