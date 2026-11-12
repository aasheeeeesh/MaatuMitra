"""Commands behind `python -m m1_data audio-*` and `fleurs` (kept out of cli.py).

Disk rule (orchestrator): never let free space on the drive fall below `--min-free-gb`; every
long loop calls `disk_guard` and stops cleanly (all steps are resumable).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

from m1_data import audio_build as ab
from m1_data import fleurs as fl

AVG_CONV_SECONDS = (
    14.0  # measured on the gold text length: ~3.2 turns x ~4 s; UNVERIFIED until built
)
BYTES_PER_SECOND = 32000


class DiskLow(RuntimeError):
    pass


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def disk_guard(path: Path, min_free_gb: float) -> Callable[[], None]:
    def _check() -> None:
        f = free_gb(path)
        if f < min_free_gb:
            raise DiskLow(
                f"free disk {f:.2f} GB < floor {min_free_gb:.2f} GB: stopping (resumable)"
            )

    return _check


def estimate(root: Path) -> dict:
    items = ab.plan(root)
    convs = {(i.split, i.conv) for i in items}
    gb = len(items) * AVG_CONV_SECONDS * BYTES_PER_SECOND / 1e9
    return {
        "items": len(items),
        "test_conversations": sum(1 for s, _ in convs if s == "test"),
        "dev_conversations": sum(1 for s, _ in convs if s == "dev"),
        "tts_gb_estimate": round(gb, 2),
        "assumed_seconds_per_conversation": AVG_CONV_SECONDS,
    }


def load_index(root: Path) -> dict[str, dict]:
    idx = root / ab.INDEX_REL
    if not idx.exists():
        return {}
    return {r["audio_id"]: r for r in map(json.loads, idx.read_text(encoding="utf-8").splitlines())}


def run_tts(root: Path, limit_convs: int | None, min_free_gb: float, threads: int) -> dict:
    items = ab.plan(root)
    if limit_convs:
        order = list(dict.fromkeys(i.conv for i in items))[:limit_convs]
        items = [i for i in items if i.conv in set(order)]
    guard = disk_guard(root, min_free_gb)
    guard()
    from m1_data.tts_model import MmsKannada

    model = MmsKannada(threads=threads)
    done = set(load_index(root))
    got: list[dict] = []
    added = 0

    def flush(crows: list[dict]) -> None:  # after EVERY conversation, so a stop loses nothing
        nonlocal added
        got.extend(crows)
        ab.write_outputs(root, crows)
        added += ab.append_lock(root, ab.manifest_rows(root, crows))

    ab.build(root, lambda t, s: model(t, s), items, check=guard, done=done, on_conv=flush)
    return {
        "audio_rows_new": len(got),
        "lock_lines_added": added,
        "index_rows": len(load_index(root)),
        "not_reproducible_kept": sum(1 for r in got if not r["reproducible"]),
    }


def run_fleurs(root: Path, min_free_gb: float) -> dict:
    guard = disk_guard(root, min_free_gb)
    guard()
    tsv = root / "data" / "audio" / "_fleurs_test.tsv"
    tsv.parent.mkdir(parents=True, exist_ok=True)
    if not tsv.exists():
        urllib.request.urlretrieve(fl.TSV_URL, tsv)  # noqa: S310 (pinned https URL)
    chosen = fl.select(fl.parse_tsv(tsv))
    out_dir = root / fl.AUDIO_ROOT
    want = {r["file_name"]: r["split"] for r in chosen}
    todo = {k: v for k, v in want.items() if not (out_dir / v / k).exists()}
    if todo:
        fl.stream_extract(fl.TAR_URL, todo, out_dir)
    guard()
    rows, mrows = [], []
    for r in chosen:
        rel = f"{fl.AUDIO_ROOT}/{r['split']}/{r['file_name']}"
        m = fl.manifest_row(rel, root / rel, r["split"], r["gender"], fl.SEED)
        mrows.append(m)
        rows.append(
            {
                "audio_id": f"fleurs-kn_in-{Path(r['file_name']).stem}",
                "file": rel,
                "split": r["split"],
                "sentence_id": r["sentence_id"],
                "gender": r["gender"],
                "raw_transcription": r["raw_transcription"],
                "transcription": r["transcription"],
                "duration_s": round(r["num_samples"] / 16000, 3),
                "sha256": m["sha256"],
            }
        )
    sub = root / fl.SUBSET_REL
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text(ab._jsonl(rows), encoding="utf-8", newline="")
    ab.merge_manifest(root, mrows)
    added = ab.append_lock(root, mrows)
    return {
        "utterances": len(rows),
        "dev": sum(r["split"] == "dev" for r in rows),
        "lock_lines_added": added,
    }


def _is_audio_row(r: dict) -> bool:
    return r["file"].startswith("data/audio/")


def verify(root: Path, materialise_sample: int = 0, seed: int = 20261112) -> dict:
    """Compare every audio row of manifest.jsonl with the file on disk. Rows whose index entry says
    `on_demand` are not missing, they are counted separately. With `materialise_sample` N, N on-demand
    variants are rebuilt into a temp dir, compared with the manifest hash and deleted
    (TEST variants only when ALLOW_TEST=1)."""
    rows = [
        json.loads(x)
        for x in (root / "data" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    index = {r["file"]: r for r in load_index(root).values()}
    checked, missing, on_demand, bad = 0, 0, 0, []
    for r in rows:
        if not _is_audio_row(r):
            continue
        p = root / r["file"]
        if not p.exists():
            if index.get(r["file"], {}).get("storage") == "on_demand":
                on_demand += 1
            else:
                missing += 1
            continue
        checked += 1
        if hashlib.sha256(p.read_bytes()).hexdigest() != r["sha256"]:
            bad.append(r["file"])
    res = {"checked": checked, "on_demand": on_demand, "missing": missing, "bad": bad}
    if materialise_sample:
        mrow = {r["file"]: r["sha256"] for r in rows}
        pool = sorted(
            (r for r in index.values() if r["storage"] == "on_demand"),
            key=lambda r: r["audio_id"],
        )
        if os.environ.get("ALLOW_TEST") != "1":
            pool = [r for r in pool if r["split"] != "test"]
        pick = random.Random(seed).sample(pool, min(materialise_sample, len(pool)))  # noqa: S311
        ok, fail = 0, []
        with tempfile.TemporaryDirectory(prefix="m1_mat_") as td:
            for r in pick:
                dst = Path(td) / f"{r['audio_id']}.wav"
                try:
                    got = ab.materialise_row(root, r, dst)
                    if got != mrow.get(r["file"]):
                        raise ValueError("index and manifest disagree")
                    ok += 1
                except (ValueError, OSError) as e:
                    fail.append(f"{r['audio_id']}: {e}")
                dst.unlink(missing_ok=True)
        res["materialised_ok"] = ok
        res["materialise_failed"] = fail
        res["materialise_pool"] = len(pool)
        if fail:
            res["bad"] = bad + fail
    return res


def materialise(
    root: Path, ids: str, split: str, variants: str, out: Path, environ: dict | None = None
) -> dict:
    """Re-create variant WAVs from the stored clean file and verify each sha256 (mismatch = error).
    The test split is refused unless ALLOW_TEST=1."""
    env = os.environ if environ is None else environ
    if split == "test" and env.get("ALLOW_TEST") != "1":
        raise PermissionError(
            "refusing --split test: set ALLOW_TEST=1 (the test run happens once, in Phase C)"
        )
    want_ids = None
    if ids != "all":
        want_ids = set(Path(ids).read_text(encoding="utf-8").split())
    want_var = None if variants == "all" else set(variants.split(","))
    index = load_index(root)
    pick = [
        r
        for r in index.values()
        if r["split"] == split
        and (want_ids is None or r["conv_id"] in want_ids)
        and (want_var is None or r["variant"] in want_var)
    ]
    if not pick:
        raise ValueError("no audio rows match --ids/--split/--variants")
    out_n = 0
    for r in sorted(pick, key=lambda r: r["audio_id"]):
        ab.materialise_row(root, r, out / r["voice"] / r["variant"] / f"{r['conv_id']}.wav")
        out_n += 1
    return {"materialised": out_n, "verified_sha256": out_n, "out": str(out)}
