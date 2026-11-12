"""Runner: one transcript.v1 JSON per audio file, resumable, test-split guarded."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import traceback
from pathlib import Path

from contracts import validate

from .base import ASRAdapter
from .guard import DevGuard


def out_name(audio_id: str) -> str:
    """Short file name (Windows MAX_PATH is 260 and this repo sits in a deep folder). The real
    audio_id is inside the JSON. 8 hex chars of sha1 over ~450 ids: collisions are checked."""
    return hashlib.sha1(audio_id.encode("utf-8")).hexdigest()[:8] + ".json"  # noqa: S324


def _valid_existing(p: Path) -> bool:
    try:
        return not validate.validate_doc("transcript.v1", json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return False


def run_entries(
    adapter: ASRAdapter, entries: list[dict], out_dir: Path, guard: DevGuard, log=print
) -> dict:
    """Transcribe every entry (path must be dev audio). Existing valid outputs are skipped.
    The guard checks ALL paths first, so a test path stops the run before any model work."""
    for e in entries:
        guard.check(e["path"])
    names = [out_name(e["audio_id"]) for e in entries]
    if len(set(names)) != len(names):
        raise RuntimeError("output file name collision; widen out_name()")
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {"done": 0, "skipped": 0, "failed": 0, "errors": []}
    for i, e in enumerate(entries, 1):
        dst = out_dir / out_name(e["audio_id"])
        if dst.exists() and _valid_existing(dst):
            res["skipped"] += 1
            continue
        try:
            t = adapter.transcribe(e["path"], audio_id=e["audio_id"], source=e["source"])
            errs = validate.validate_doc("transcript.v1", t)
            if errs:
                raise ValueError(f"invalid transcript.v1: {errs[:3]}")
            tmp = dst.with_name(dst.name + ".tmp")
            tmp.write_text(
                json.dumps(t, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
            )
            tmp.replace(dst)
            res["done"] += 1
        except Exception as ex:
            res["failed"] += 1
            res["errors"].append({"audio_id": e["audio_id"], "error": f"{type(ex).__name__}: {ex}"})
            log(traceback.format_exc())
        if i % 25 == 0:
            log(
                f"[{i}/{len(entries)}] done={res['done']} skipped={res['skipped']} failed={res['failed']}"
            )
    return res


def aggregate(per_file_dir: Path, jsonl_path: Path) -> int:
    """Concatenate per-file JSONs into one JSONL (the layout m7 reads); returns the line count."""
    files = sorted(per_file_dir.glob("*.json"))
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as fh:
        for f in files:
            fh.write(
                json.dumps(json.loads(f.read_text(encoding="utf-8")), ensure_ascii=False) + "\n"
            )
    return len(files)


def materialise(root: Path, entries: list[dict], scratch: Path) -> dict[str, str]:
    """Rebuild on-demand variants with m1's CLI (sha256-verified) into scratch; returns
    {audio_id: path}. Called per batch; the caller deletes the batch afterwards."""
    need = [e for e in entries if not (root / e["path"]).exists()]
    if not need:
        return {}
    ids = scratch / "ids.txt"
    ids.parent.mkdir(parents=True, exist_ok=True)
    ids.write_text("\n".join(sorted({e["conv"] for e in need})) + "\n", encoding="utf-8")
    variants = ",".join(sorted({e["variant"] for e in need}))
    out = scratch / "mat"
    subprocess.run(  # noqa: S603 (fixed argv, our own CLI)
        [
            sys.executable,
            "-m",
            "m1_data",
            "audio-materialise",
            "--ids",
            str(ids),
            "--split",
            "dev",
            "--variants",
            variants,
            "--out",
            str(out),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return {e["audio_id"]: str(out / e["voice"] / e["variant"] / f"{e['conv']}.wav") for e in need}
