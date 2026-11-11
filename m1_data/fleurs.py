"""Kannada FLEURS (google/fleurs, config kn_in, official TEST split) subset: public real speech.

Path that works (the old script loader is not used): direct files from the dataset repo at a
pinned revision: data/kn_in/test.tsv (transcripts) and data/kn_in/audio/test.tar.gz (615 MB).
The tarball is STREAMED and only the chosen files are written, so the 615 MB never sits on disk.
Selection: whole sentences (FLEURS has up to 3 speakers per sentence), seeded; sentences are then
dealt alternately to our `dev` and `test` splits so one sentence never straddles the two.
Source label: public_real. Never pooled with TTS in any reported number.
"""

from __future__ import annotations

import csv
import hashlib
import random
import tarfile
import urllib.request
import wave
from pathlib import Path

from m1_data.split import seed_int

REPO = "google/fleurs"
REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"  # HF dataset sha fetched 2026-11-11
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/data/kn_in/"
TSV_URL = BASE + "test.tsv"
TAR_URL = BASE + "audio/test.tar.gz"
LICENCE = "CC-BY-4.0"
LICENCE_URL = "https://huggingface.co/datasets/google/fleurs"
SEED = 20261112
N_MIN = 250
AUDIO_ROOT = "data/audio/public_real/fleurs_kn_in"
SUBSET_REL = "data/public_real/fleurs_kn_in_test_subset.jsonl"
RETRIEVED_AT = "2026-11-12T00:00:00Z"
VERSION = "m1-fleurs-1.0.0"


def parse_tsv(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(r) != 7:
                raise ValueError(f"unexpected FLEURS tsv row with {len(r)} columns")
            out.append(
                {
                    "sentence_id": r[0],
                    "file_name": r[1],
                    "raw_transcription": r[2],
                    "transcription": r[3],
                    "num_samples": int(r[5]),
                    "gender": r[6],
                }
            )
    return out


def select(rows: list[dict], n_min: int = N_MIN, seed: int = SEED) -> list[dict]:
    """Seeded sentence-level subset with >= n_min utterances (or all). Adds `split`."""
    by_sent: dict[str, list[dict]] = {}
    for r in rows:
        by_sent.setdefault(r["sentence_id"], []).append(r)
    order = sorted(by_sent)
    random.Random(seed_int(seed, "fleurs")).shuffle(order)  # noqa: S311
    chosen, n = [], 0
    for k, sid in enumerate(order):
        if n >= n_min:
            break
        split = ("dev", "test")[k % 2]
        for r in sorted(by_sent[sid], key=lambda x: x["file_name"]):
            chosen.append({**r, "split": split})
            n += 1
    return sorted(chosen, key=lambda r: r["file_name"])


def stream_extract(tar_url: str, wanted: dict[str, str], out_dir: Path) -> list[str]:
    """Stream `tar_url`; write wanted {file_name: split} to out_dir/<split>/<file_name>.
    Every WAV must be 16 kHz mono PCM16 (checked); no tarball is stored."""
    got = []
    with (
        urllib.request.urlopen(tar_url) as resp,  # noqa: S310 (pinned https URL or test file://)
        tarfile.open(fileobj=resp, mode="r|gz") as tf,
    ):
        for m in tf:
            name = Path(m.name).name
            if not m.isfile() or name not in wanted:
                continue
            data = tf.extractfile(m).read()
            dst = out_dir / wanted[name] / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            with wave.open(str(dst), "rb") as w:
                fmt = (w.getframerate(), w.getnchannels(), w.getsampwidth())
            if fmt != (16000, 1, 2):
                dst.unlink()
                raise ValueError(f"{name}: expected 16 kHz mono PCM16, got {fmt}")
            got.append(name)
            if len(got) == len(wanted):
                break
    return got


def manifest_row(rel: str, path: Path, split: str, gender: str, seed: int) -> dict:
    data = path.read_bytes()
    return {
        "schema_version": "manifest.v1",
        "file": rel,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "source": "public_real",
        "split": split,
        "noise_snr_db": None,
        "speed_factor": None,
        "voice_or_speaker": f"fleurs-{gender.lower()}",
        "dialect": "unknown",
        "licence_spdx": LICENCE,
        "licence_url": LICENCE_URL,
        "retrieved_at": RETRIEVED_AT,
        "generator_version": VERSION,
        "seed": seed,
        "parent_id": None,
        "consent_note": "volunteer read speech released by Google under CC-BY-4.0 (FLEURS); "
        "speaker identity not in the data",
        "native_validated": False,
    }
