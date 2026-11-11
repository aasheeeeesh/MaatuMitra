"""Commands behind `python -m m1_data audio-*` and `fleurs` (kept out of cli.py).

Disk rule (orchestrator): never let free space on the drive fall below `--min-free-gb`; every
long loop calls `disk_guard` and stops cleanly (all steps are resumable).
"""

from __future__ import annotations

import hashlib
import json
import shutil
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


def run_tts(root: Path, limit_convs: int | None, min_free_gb: float, threads: int) -> dict:
    items = ab.plan(root)
    if limit_convs:
        order = list(dict.fromkeys(i.conv for i in items))[:limit_convs]
        items = [i for i in items if i.conv in set(order)]
    guard = disk_guard(root, min_free_gb)
    guard()
    from m1_data.tts_model import MmsKannada

    model = MmsKannada(threads=threads)
    rows = ab.build(root, lambda t, s: model(t, s), items, check=guard)
    mrows = ab.write_outputs(root, rows)
    added = ab.append_lock(root, ab.manifest_rows(root, rows))
    return {"audio_files": len(rows), "lock_lines_added": added, "manifest_rows": len(mrows)}


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


def verify(root: Path) -> dict:
    """Compare every audio row of manifest.jsonl with the file on disk (missing = not built here)."""
    rows = [
        json.loads(x)
        for x in (root / "data" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    checked, missing, bad = 0, 0, []
    for r in rows:
        if not r["file"].startswith("data/audio/"):
            continue
        p = root / r["file"]
        if not p.exists():
            missing += 1
            continue
        checked += 1
        if hashlib.sha256(p.read_bytes()).hexdigest() != r["sha256"]:
            bad.append(r["file"])
    return {"checked": checked, "missing": missing, "bad": bad}
