"""Clean on disk, variants on demand: only clean WAVs stay; variants are re-made from the stored
clean file, byte-identical, and verified against the manifest hash."""

from __future__ import annotations

import hashlib
import shutil

import pytest

from contracts.validate import validate_doc
from m1_data import audio_build as ab
from m1_data import audio_run as ar

from .test_audio_build import _mini_root, fake_synth

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")


def _built(tmp_path):
    root = _mini_root(tmp_path)
    items = ab.plan(root, dev_n=1)
    got: list[dict] = []

    def flush(crows):
        got.extend(crows)
        ab.write_outputs(root, crows)
        ab.append_lock(root, ab.manifest_rows(root, crows))

    ab.build(root, fake_synth, items, log=lambda *_: None, on_conv=flush)
    return root, got


def test_only_clean_files_stay_on_disk(tmp_path):
    root, rows = _built(tmp_path)
    on_disk = {p.relative_to(root).as_posix() for p in (root / "data/audio/tts").rglob("*.wav")}
    assert on_disk == {r["file"] for r in rows if r["variant"] == "clean"}
    assert {r["storage"] for r in rows if r["variant"] != "clean"} == {"on_demand"}
    assert not (root / "data/audio/_tmp").exists()
    for r in ab.manifest_rows(root, rows):
        assert validate_doc("manifest.v1", r) == []


def test_materialise_twice_is_byte_identical_and_matches_manifest(tmp_path):
    root, rows = _built(tmp_path)
    ids = "all"
    a, b = tmp_path / "a", tmp_path / "b"
    env = {"ALLOW_TEST": "1"}
    for split in ("dev", "test"):
        ar.materialise(root, ids, split, "all", a, env)
        ar.materialise(root, ids, split, "all", b, env)
    fa = sorted(a.rglob("*.wav"))
    assert len(fa) == len(rows)
    man = {r["file"]: r["sha256"] for r in ab.manifest_rows(root, rows)}
    for p in fa:
        q = b / p.relative_to(a)
        assert p.read_bytes() == q.read_bytes()
    by_id = {r["audio_id"]: r["sha256"] for r in rows}
    assert {hashlib.sha256(p.read_bytes()).hexdigest() for p in fa} == set(by_id.values())
    assert set(man.values()) == set(by_id.values())


def test_materialise_refuses_test_without_allow_test(tmp_path):
    root, _ = _built(tmp_path)
    with pytest.raises(PermissionError):
        ar.materialise(root, "all", "test", "all", tmp_path / "o", {})
    assert not (tmp_path / "o").exists()
    out = ar.materialise(root, "all", "dev", "white_snr10,speed1.1", tmp_path / "o2", {})
    assert out["materialised"] == 2


def test_materialise_mismatch_is_an_error(tmp_path):
    root, rows = _built(tmp_path)
    idx = root / ab.INDEX_REL
    text = idx.read_text(encoding="utf-8")
    victim = next(r for r in rows if r["variant"] == "pink_snr5" and r["split"] == "dev")
    idx.write_text(text.replace(victim["sha256"], "0" * 64), encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        ar.materialise(root, "all", "dev", "pink_snr5", tmp_path / "o", {})


def test_verify_counts_on_demand_and_sample(tmp_path):
    root, rows = _built(tmp_path)
    res = ar.verify(root, materialise_sample=5)
    assert res["bad"] == [] and res["missing"] == 0
    assert res["on_demand"] == sum(1 for r in rows if r["variant"] != "clean")
    assert res["materialised_ok"] == 5 and res["materialise_failed"] == []


def test_leftover_files_deleted_when_identical_kept_when_different(tmp_path):
    """Older runs stored every variant. Identical re-render -> delete; different -> keep the
    original and record its hash, flagged non reproducible."""
    root, rows = _built(tmp_path)
    items = ab.plan(root, dev_n=1)
    leftovers = {}
    for r in rows:
        if r["variant"] == "clean":
            continue
        it = next(i for i in items if i.audio_id == r["audio_id"])
        dst = root / r["file"]
        ab.render(root, it, dst)
        leftovers[r["audio_id"]] = dst
    odd = next(a for a in leftovers if a.endswith("white_snr20") and "__mms_kan_base__" in a)
    leftovers[odd].write_bytes(leftovers[odd].read_bytes() + b"\0\0")  # simulate drift
    again = ab.build(root, fake_synth, items, log=lambda *_: None)
    by = {r["audio_id"]: r for r in again}
    for aid, p in leftovers.items():
        if aid == odd:
            assert p.exists() and by[aid]["storage"] == "stored" and not by[aid]["reproducible"]
            assert by[aid]["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
            assert by[aid]["materialised_sha256"] != by[aid]["sha256"]
        else:
            assert not p.exists() and by[aid]["storage"] == "on_demand"


def test_manifest_merge_keeps_old_order(tmp_path):
    root = _mini_root(tmp_path)
    mp = root / "data/manifest.jsonl"
    mp.write_text('{"file": "b"}\n{"file": "a"}\n', encoding="utf-8")
    ab.merge_manifest(root, [{"file": "c"}, {"file": "b", "x": 1}])
    lines = mp.read_text(encoding="utf-8").splitlines()
    assert [__import__("json").loads(x)["file"] for x in lines] == ["b", "a", "c"]
