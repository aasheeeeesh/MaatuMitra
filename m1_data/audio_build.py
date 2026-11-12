"""TTS audio: plan, synthesise (resumable), variants, index, manifest rows, test.lock append.

One WAV per conversation per voice per variant (turns joined with 0.5 s of silence).
Voices (honest naming): `mms_kan_base` is the real MMS-TTS output; `mms_kan_pitch084` is the SAME
synthetic speaker with pitch x0.84 (ffmpeg), i.e. a different-sounding voice but NOT a different
speaker model. It is the TEST-ONLY (held-out) voice. See the decision entry D-? (TTS model).
Splits: audio of a conversation inherits its split; TTS and public_real are never mixed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from m1_data import audio_dsp as dsp
from m1_data.split import read_lock, seed_int
from m1_data.tts_pronounce import build_table, kannadify

AUDIO_VERSION = "m1-audio-1.0.0"
AUDIO_SEED = 20261112
RETRIEVED_AT = "2026-11-12T00:00:00Z"
GAP_S = 0.5
PEAK = 0.5
BASE_VOICE = "mms_kan_base"
HELD_OUT_VOICE = "mms_kan_pitch084"  # TEST ONLY
PITCH_RATIO = 0.84
DEV_SUBSET_N = 80
TTS_MODEL = "facebook/mms-tts-kan"
TTS_REVISION = "30e3c5d533e8c559c10bf0d25637fea51b95bd7c"
TTS_LICENCE = "CC-BY-NC-4.0"
TTS_LICENCE_URL = "https://huggingface.co/facebook/mms-tts-kan"
CONSENT = "synthetic speech from a text-to-speech model; no person was recorded"
AUDIO_DIR = "data/audio/tts"
INDEX_REL = "data/audio_index/tts_index.jsonl"


@dataclass(frozen=True)
class Variant:
    name: str
    noise: str | None = None
    snr: float | None = None
    speed: float | None = None


VARIANTS = (
    Variant("clean"),
    *(Variant(f"{k}_snr{int(s)}", k, s) for k in ("white", "pink") for s in (20.0, 10.0, 5.0)),
    Variant("speed0.9", speed=0.9),
    Variant("speed1.1", speed=1.1),
)
CLEAN = VARIANTS[0]


@dataclass(frozen=True)
class Item:
    conv: str
    split: str
    voice: str
    variant: Variant

    @property
    def audio_id(self) -> str:
        return f"{self.conv}__{self.voice}__{self.variant.name}"

    @property
    def rel_path(self) -> str:
        return f"{AUDIO_DIR}/{self.split}/{self.voice}/{self.variant.name}/{self.conv}.wav"


def _ids(root: Path, split: str) -> list[str]:
    p = root / "data" / "splits" / f"{split}.txt"
    return sorted(x for x in p.read_text(encoding="utf-8").split() if not x.startswith("#"))


def plan(root: Path, dev_n: int = DEV_SUBSET_N) -> list[Item]:
    """Test: held-out voice x ALL variants, base voice clean only, for EVERY test conversation.
    Dev: base voice x ALL variants for a seeded subset of `dev_n` conversations."""
    items: list[Item] = []
    for cid in _ids(root, "test"):
        items += [Item(cid, "test", HELD_OUT_VOICE, v) for v in VARIANTS]
        items.append(Item(cid, "test", BASE_VOICE, CLEAN))
    dev = _ids(root, "dev")
    pick = sorted(
        __import__("random")
        .Random(seed_int(AUDIO_SEED, "dev_subset"))
        .sample(dev, min(dev_n, len(dev)))
    )
    for cid in pick:
        items += [Item(cid, "dev", BASE_VOICE, v) for v in VARIANTS]
    return items


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _turn_seed(conv: str, k: int) -> int:
    return seed_int(AUDIO_SEED, "turn", conv, k)


def clean_item(it: Item) -> Item:
    return Item(it.conv, it.split, it.voice, CLEAN)


def render(root: Path, it: Item, dst: Path) -> None:
    """Make the file of a non-clean item from the STORED clean file of the same voice.
    This is the single definition of a variant (used by build and by audio-materialise)."""
    src = root / clean_item(it).rel_path
    v = it.variant
    if v.noise:
        seed = seed_int(AUDIO_SEED, it.audio_id)
        dsp.write_wav(dst, dsp.add_noise(dsp.read_wav(src), v.noise, v.snr, seed))
    elif v.speed:
        dsp.change_speed(src, dst, v.speed)
    else:
        raise ValueError("clean is stored, not rendered")


def build(
    root: Path,
    synth: Callable[[str, int], np.ndarray],
    items: list[Item],
    log=print,
    check: Callable[[], None] | None = None,
    done: set[str] | None = None,
    on_conv: Callable[[list[dict]], None] | None = None,
) -> list[dict]:
    """Make the items ("clean on disk, variants on demand"). Per conversation: the clean file(s)
    stay on disk; every other variant is rendered to a scratch file, hashed (sha256 of the exact
    bytes) and deleted. A variant file left over from an older run is compared byte-for-byte with
    the fresh render: equal -> deleted; different -> the ORIGINAL is kept and its hash recorded
    (`reproducible` false). Conversations whose items are all in `done` are skipped.
    Returns one index row per item; `on_conv` is called with each conversation's rows."""
    table = build_table(root / "data" / "lexicon" / "drugs.csv")
    turns_dir = root / "data" / "audio" / "_turns"
    tmp_dir = root / "data" / "audio" / "_tmp"
    done = done or set()
    by_conv: dict[str, list[Item]] = {}
    for it in items:
        by_conv.setdefault(it.conv, []).append(it)
    rows: list[dict] = []
    for n, (conv, its) in enumerate(sorted(by_conv.items()), 1):
        if all(i.audio_id in done for i in its):
            continue
        if check:
            check()  # e.g. the free-disk guard; raises to stop cleanly (the build is resumable)
        its = sorted(its, key=lambda i: i.variant != CLEAN)  # clean files first
        gold = json.loads((root / "data" / "gold" / f"{conv}.json").read_text(encoding="utf-8"))
        kn_texts = [kannadify(t["text"], table) for t in gold["turns"]]
        arrs = []
        for k, txt in enumerate(kn_texts):
            tp = turns_dir / f"{conv}_{k}.wav"
            if not tp.exists():
                dsp.write_wav(tp, synth(txt, _turn_seed(conv, k)))
            arrs.append(dsp.read_wav(tp))
        base, offsets = dsp.concat_turns(arrs, GAP_S)
        base = dsp.peak_normalise(base, PEAK)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        crows: list[dict] = []
        for it in its:
            dst = root / it.rel_path
            v = it.variant
            seed = seed_int(AUDIO_SEED, it.audio_id)
            extra: dict = {}
            if v == CLEAN:
                if not dst.exists():
                    if it.voice == BASE_VOICE:
                        dsp.write_wav(dst, base)
                    else:
                        a, b = tmp_dir / f"{conv}_a.wav", tmp_dir / f"{conv}_b.wav"
                        dsp.write_wav(a, base)
                        dsp.shift_pitch(a, b, PITCH_RATIO)
                        dsp.write_wav(dst, dsp.read_wav(b))
                sha, size, frames = _sha_file(dst), dst.stat().st_size, dsp.wav_info(dst)[3]
                storage, repro = "stored", True
            else:
                scratch = tmp_dir / f"{it.audio_id}.wav"
                render(root, it, scratch)
                sha, size = _sha_file(scratch), scratch.stat().st_size
                frames = dsp.wav_info(scratch)[3]
                storage, repro = "on_demand", True
                if dst.exists():  # leftover from the older "store everything" run
                    old = _sha_file(dst)
                    if old == sha:
                        dst.unlink()
                    else:
                        extra = {"materialised_sha256": sha, "materialised_bytes": size}
                        sha, size, frames = old, dst.stat().st_size, dsp.wav_info(dst)[3]
                        storage, repro = "stored", False
                scratch.unlink()
            scale = 1.0 / v.speed if v.speed else 1.0
            crows.append(
                {
                    "audio_id": it.audio_id,
                    "file": it.rel_path,
                    "conv_id": conv,
                    "split": it.split,
                    "voice": it.voice,
                    "variant": v.name,
                    "noise_type": v.noise,
                    "snr_db": v.snr,
                    "speed_factor": v.speed,
                    "seed": seed,
                    "sha256": sha,
                    "bytes": size,
                    "storage": storage,  # stored = file on disk; on_demand = audio-materialise
                    "reproducible": repro,
                    "clean_file": clean_item(it).rel_path,
                    "duration_s": round(frames / dsp.SR, 3),
                    "turn_offsets_s": [
                        [round(a * scale, 3), round(b * scale, 3)] for a, b in offsets
                    ],
                    "tts_input": kn_texts,
                    "tts_model": TTS_MODEL,
                    "tts_revision": TTS_REVISION,
                    **extra,
                }
            )
        rows += crows
        if on_conv:
            on_conv(crows)
        if n % 20 == 0:
            log(f"{n}/{len(by_conv)} conversations")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return rows


def materialise_row(root: Path, row: dict, dst: Path) -> str:
    """Re-create the WAV of one index row at `dst` and verify its sha256. Raises on mismatch."""
    variant = next(v for v in VARIANTS if v.name == row["variant"])
    it = Item(row["conv_id"], row["split"], row["voice"], variant)
    if row["storage"] == "stored" or row["variant"] == "clean":
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / row["file"], dst)
    else:
        render(root, it, dst)
    got = _sha_file(dst)
    if got != row["sha256"]:
        dst.unlink(missing_ok=True)
        raise ValueError(f"sha256 mismatch for {row['audio_id']}: {got} != {row['sha256']}")
    return got


def manifest_row(root: Path, r: dict) -> dict:
    return {
        "schema_version": "manifest.v1",
        "file": r["file"],
        "sha256": r["sha256"],
        "bytes": r["bytes"],
        "source": "tts",
        "split": r["split"],
        "noise_snr_db": r["snr_db"],
        "speed_factor": r["speed_factor"],
        "voice_or_speaker": r["voice"],
        "dialect": "unknown",
        "licence_spdx": TTS_LICENCE,
        "licence_url": TTS_LICENCE_URL,
        "retrieved_at": RETRIEVED_AT,
        "generator_version": AUDIO_VERSION,
        "seed": r["seed"],
        "parent_id": r["conv_id"]
        if r["variant"] == "clean"
        else f"{r['conv_id']}__{r['voice']}__clean",
        "consent_note": CONSENT,
        "native_validated": False,
    }


def manifest_rows(root: Path, index_rows: list[dict]) -> list[dict]:
    return [manifest_row(root, r) for r in index_rows]


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def write_outputs(root: Path, index_rows: list[dict]) -> list[dict]:
    """Write the tracked index and merge the audio rows into data/manifest.jsonl (rows of other
    files are kept as they are; rows with the same `file` are replaced)."""
    idx = root / INDEX_REL
    idx.parent.mkdir(parents=True, exist_ok=True)
    keep = {}
    if idx.exists():
        keep = {
            r["audio_id"]: r for r in map(json.loads, idx.read_text(encoding="utf-8").splitlines())
        }
    keep.update({r["audio_id"]: r for r in index_rows})
    idx.write_text(_jsonl([keep[k] for k in sorted(keep)]), encoding="utf-8", newline="")
    return merge_manifest(root, manifest_rows(root, index_rows))


def merge_manifest(root: Path, new_rows: list[dict]) -> list[dict]:
    """New files are appended; a row with an existing `file` is replaced IN PLACE (order kept)."""
    mp = root / "data" / "manifest.jsonl"
    old = [json.loads(x) for x in mp.read_text(encoding="utf-8").splitlines() if x.strip()]
    pos = {r["file"]: i for i, r in enumerate(old)}
    for r in new_rows:
        if r["file"] in pos:
            old[pos[r["file"]]] = r
        else:
            pos[r["file"]] = len(old)
            old.append(r)
    mp.write_text(_jsonl(old), encoding="utf-8", newline="")
    return old


LOCK_COMMENT = (
    "# audio files of the test split (appended by m1_data audio-lock; lines are only ever added)"
)


def append_lock(root: Path, mrows: list[dict]) -> int:
    """Append `<sha256>  <path>` for every TEST audio file not yet locked. Existing bytes are
    never touched. A file that is already locked but now hashes differently is an ERROR (the
    frozen test audio changed). Returns the number of lines added."""
    lock = root / "data" / "splits" / "test.lock"
    have = read_lock(lock)
    test = [(r["file"], r["sha256"]) for r in mrows if r["split"] == "test"]
    changed = [p for p, s in test if p in have and have[p] != s]
    if changed:
        raise RuntimeError(f"locked test audio changed: {changed[:3]}")
    add = [(p, s) for p, s in test if p not in have]
    if not add:
        return 0
    text = lock.read_bytes().decode("utf-8")
    prefix = "" if text.endswith("\n") else "\n"
    head = "" if LOCK_COMMENT in text else LOCK_COMMENT + "\n"
    body = "".join(f"{sha}  {path}\n" for path, sha in sorted(add))
    lock.write_bytes((text + prefix + head + body).encode("utf-8"))
    return len(add)
