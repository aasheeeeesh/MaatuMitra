"""Common subset: the SAME dev files for every model (never compare on different data).

TTS: a seeded sample of N dev conversations, ALL nine variants of each (clean, white/pink x
SNR 20/10/5, speed 0.9/1.1). Public real: every FLEURS kn_IN dev clip. Dev only.
Variants with storage 'on_demand' are rebuilt by `m1_data audio-materialise` at run time.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20261109


def pick_conversations(index_rows: list[dict], n: int, seed: int = SEED) -> list[str]:
    """Seeded choice of n distinct dev conversations that have a clean row."""
    convs = sorted(
        {r["conv_id"] for r in index_rows if r["split"] == "dev" and r["variant"] == "clean"}
    )
    return sorted(random.Random(seed).sample(convs, min(n, len(convs))))  # noqa: S311


def build(root: Path, n_conv: int, seed: int = SEED) -> list[dict]:
    """Subset entries: audio_id, path (repo-relative), source, voice, variant, conv, duration."""
    idx = [
        json.loads(ln)
        for ln in (root / "data/audio_index/tts_index.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    idx = [r for r in idx if r["split"] == "dev"]
    chosen = set(pick_conversations(idx, n_conv, seed))
    out = []
    for r in sorted(idx, key=lambda r: r["audio_id"]):
        if r["conv_id"] in chosen:
            out.append(
                {
                    "audio_id": r["audio_id"],
                    "path": r["file"],
                    "source": "tts",
                    "voice": r["voice"],
                    "variant": r["variant"],
                    "conv": r["conv_id"],
                    "storage": r["storage"],
                    "duration_s": r["duration_s"],
                }
            )
    fl = (
        root / "data/public_real/fleurs_kn_in_test_subset.jsonl"
    )  # file name says test; rows carry split
    for ln in fl.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        if r["split"] != "dev":
            continue
        out.append(
            {
                "audio_id": Path(r["file"]).stem,
                "path": r["file"],
                "source": "public_real",
                "voice": "fleurs",
                "variant": "clean",
                "conv": None,
                "storage": "stored",
                "duration_s": r["duration_s"],
                "reference": r["transcription"],
            }
        )
    return out


def write(entries: list[dict], results_dir: Path, seed: int, n_conv: int) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "common_subset.txt").write_text(
        "# m2 common subset (dev only). One audio_id per line; every model is run and scored on exactly these.\n"
        f"# seed={seed} tts_conversations={n_conv} (all 9 variants each) + all FLEURS kn_IN dev clips\n"
        + "".join(e["audio_id"] + "\n" for e in entries),
        encoding="utf-8",
        newline="\n",
    )
    (results_dir / "common_subset.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=0) + "\n", encoding="utf-8", newline="\n"
    )


def load(results_dir: Path) -> list[dict]:
    return json.loads((results_dir / "common_subset.json").read_text(encoding="utf-8"))
