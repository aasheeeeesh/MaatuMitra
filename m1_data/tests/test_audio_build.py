"""TTS audio plan, build (with a fake synthesiser), manifest rows and the lock-append rule."""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

import numpy as np
import pytest

from contracts.validate import validate_doc
from m1_data import audio_build as ab
from m1_data import audio_dsp as dsp

from .conftest import DATA, ROOT

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def fake_synth(text_kn: str, seed: int) -> np.ndarray:
    rng = random.Random(seed)
    n = 4000 + 40 * len(text_kn)
    t = np.arange(n) / dsp.SR
    return (0.3 * np.sin(2 * np.pi * (200 + rng.random() * 50) * t)).astype(np.float32)


def _mini_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "data" / "gold").mkdir(parents=True)
    (root / "data" / "splits").mkdir(parents=True)
    (root / "data" / "lexicon").mkdir(parents=True)
    shutil.copy(DATA / "lexicon" / "drugs.csv", root / "data" / "lexicon" / "drugs.csv")
    for s, ids in {"dev": ["m1-x-000", "m1-x-001"], "test": ["m1-y-000", "m1-y-001"]}.items():
        (root / "data" / "splits" / f"{s}.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
        for cid in ids:
            gold = {
                "conversation_id": cid,
                "turns": [
                    {"speaker_role": "asha", "text": "ಮಗುವಿಗೆ ಜ್ವರ ಇದೆ?"},
                    {"speaker_role": "caregiver", "text": "Paracetamol 500 mg ಕೊಟ್ಟಿದ್ದೇವೆ."},
                ],
            }
            (root / "data" / "gold" / f"{cid}.json").write_text(
                json.dumps(gold, ensure_ascii=False), encoding="utf-8"
            )
    (root / "data" / "splits" / "test.lock").write_text("# header\n", encoding="utf-8")
    (root / "data" / "manifest.jsonl").write_text("", encoding="utf-8")
    return root


def test_variant_table_is_complete():
    names = [v.name for v in ab.VARIANTS]
    assert len(names) == 9 and names[0] == "clean"
    assert {(v.noise, v.snr) for v in ab.VARIANTS if v.noise} == {
        (k, s) for k in ("white", "pink") for s in (20.0, 10.0, 5.0)
    }
    assert sorted(v.speed for v in ab.VARIANTS if v.speed) == [0.9, 1.1]


def test_plan_on_real_data_respects_the_split_rules():
    items = ab.plan(ROOT)
    split_of = {
        cid: s
        for s in ("dev", "test")
        for cid in (DATA / "splits" / f"{s}.txt").read_text(encoding="utf-8").split()
    }
    assert all(split_of[i.conv] == i.split for i in items)
    assert len({i.audio_id for i in items}) == len(items)
    test_ids = set((DATA / "splits" / "test.txt").read_text(encoding="utf-8").split())
    # every test conversation has the held-out voice with ALL variants
    held = {(i.conv, i.variant.name) for i in items if i.voice == ab.HELD_OUT_VOICE}
    assert held == {(c, v.name) for c in test_ids for v in ab.VARIANTS}
    # the held-out voice never appears in dev
    assert not [i for i in items if i.voice == ab.HELD_OUT_VOICE and i.split == "dev"]
    # dev: only the base voice, a seeded subset
    dev_convs = {i.conv for i in items if i.split == "dev"}
    assert len(dev_convs) == ab.DEV_SUBSET_N
    assert {i.voice for i in items if i.split == "dev"} == {ab.BASE_VOICE}
    assert ab.plan(ROOT) == items  # deterministic


def test_build_is_deterministic_and_rows_validate(tmp_path):
    root = _mini_root(tmp_path)
    items = ab.plan(root, dev_n=1)
    rows1 = ab.build(root, fake_synth, items, log=lambda *_: None)
    hashes1 = {r["file"]: r["sha256"] for r in ab.manifest_rows(root, rows1)}
    for p in (root / "data" / "audio" / "tts").rglob("*.wav"):
        p.unlink()
    shutil.rmtree(root / "data" / "audio" / "_turns")
    rows2 = ab.build(root, fake_synth, items, log=lambda *_: None)
    assert hashes1 == {r["file"]: r["sha256"] for r in ab.manifest_rows(root, rows2)}
    rows = ab.manifest_rows(root, rows2)
    assert len(rows) == len(items)
    for r in rows:
        assert validate_doc("manifest.v1", r) == [], r
        assert r["source"] == "tts"
    f = root / rows[0]["file"]
    assert dsp.wav_info(f)[:3] == (16000, 1, 2)


def test_noise_rows_record_snr_noise_type_and_speed(tmp_path):
    root = _mini_root(tmp_path)
    rows = ab.build(root, fake_synth, ab.plan(root, dev_n=1), log=lambda *_: None)
    pink5 = next(r for r in rows if r["variant"] == "pink_snr5")
    assert (pink5["noise_type"], pink5["snr_db"], pink5["speed_factor"]) == ("pink", 5.0, None)
    sp = next(r for r in rows if r["variant"] == "speed1.1")
    assert sp["speed_factor"] == 1.1 and sp["noise_type"] is None
    clean = next(r for r in rows if r["variant"] == "clean" and r["conv_id"] == sp["conv_id"])
    assert sp["duration_s"] < clean["duration_s"]


def test_append_lock_only_adds_lines(tmp_path):
    root = _mini_root(tmp_path)
    lock = root / "data" / "splits" / "test.lock"
    lock.write_text("# header\n" + "a" * 64 + "  data/gold/m1-y-000.json\n", encoding="utf-8")
    before = lock.read_bytes()
    rows = ab.build(root, fake_synth, ab.plan(root, dev_n=1), log=lambda *_: None)
    ab.append_lock(root, ab.manifest_rows(root, rows))
    after = lock.read_bytes()
    assert after.startswith(before)
    new = after[len(before) :].decode().splitlines()
    assert all("data/audio/" in ln for ln in new if ln and not ln.startswith("#"))
    assert not any("/dev/" in ln for ln in new)  # dev audio is never locked
    n = len([ln for ln in new if ln and not ln.startswith("#")])
    ab.append_lock(root, ab.manifest_rows(root, rows))  # idempotent
    assert len(lock.read_bytes()) == len(after) and n == sum(
        1 for r in rows if r["split"] == "test"
    )
