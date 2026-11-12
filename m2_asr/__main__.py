"""CLI: python -m m2_asr {subset,run,summarise,mock,fetch,purge,status} ...

All commands work on DEV audio only (guard.DevGuard). The Phase C test run uses the same code
with a separate, human-approved wrapper (see README); nothing here reads test audio.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
import wave
from datetime import UTC, datetime
from pathlib import Path

from contracts import validate

from .asr import guard as G
from .asr import models, runner, subset, summary
from .asr.mock import MockAdapter

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "m2_asr"
DEFAULT_SCRATCH = Path(tempfile.gettempdir()) / "m2scratch"
N_CONV = 36


def _entries(limit: int | None) -> list[dict]:
    es = subset.load(RES)
    return es[:limit] if limit else es


def cmd_subset(a) -> int:
    es = subset.build(ROOT, a.n_conv)
    subset.write(es, RES, subset.SEED, a.n_conv)
    tts = [e for e in es if e["source"] == "tts"]
    pr = [e for e in es if e["source"] == "public_real"]
    print(
        f"common subset: {len(tts)} TTS files ({len({e['conv'] for e in tts})} conversations), "
        f"{len(pr)} public_real files; audio {sum(e['duration_s'] for e in es):.0f} s"
    )
    return 0


def build_adapter(name: str, scratch: Path, language: str, threads: int):
    from .asr.whisper_ct2 import FasterWhisperAdapter, convert_hf_to_ct2

    m = models.MODELS[name]
    if m["kind"] == "ct2":
        path = models.fetch(name, 0.5)
        scratch.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(path) / "tokenizer.json", scratch / "tokenizer.json")  # reused later
        rev = m["revision"]
    else:
        out = scratch / "ct2" / name
        if not (out / "model.bin").exists():  # converted copy from an earlier run is reused
            hf = models.fetch(name, 1.0)
            out = convert_hf_to_ct2(
                hf,
                out,
                scratch / "tokenizer.json",
                after_load=lambda: print("source weights purged:", models.purge(name), flush=True),
            )
        path, rev = out, m["revision"] + "+ct2-int8"
    return FasterWhisperAdapter(path, name, rev, language=language, cpu_threads=threads)


def cmd_run(a) -> int:
    scratch = Path(a.scratch)
    entries = _entries(a.limit)
    dev = G.DevGuard(ROOT)
    for e in entries:
        dev.check(e["path"])  # fail fast, before any download
    print(f"free disk before: {models.free_gb():.2f} GB")
    t_start = time.time()
    ad = build_adapter(a.model, scratch, a.language, a.threads)
    print("adapter ready:", ad.name, ad.revision, "|", ad.hardware)
    out = RES / "dev" / a.model
    tot = {"done": 0, "skipped": 0, "failed": 0, "errors": []}
    stored = [e for e in entries if (ROOT / e["path"]).exists()]
    pending = [e for e in entries if not (ROOT / e["path"]).exists()]
    first = next((e for e in stored), None)
    if first:  # warm-up (not saved) so the first file's latency is not model-load noise
        ad.transcribe(ROOT / first["path"], audio_id="warmup", source=first["source"])
    batches = [([{**e, "path": str(ROOT / e["path"])} for e in stored], None)]
    for i in range(0, len(pending), a.batch):
        batches.append((pending[i : i + a.batch], scratch / "mat"))
    for items, tmp in batches:
        todo = (
            [e for e in items if not (out / runner.out_name(e["audio_id"])).exists()]
            if tmp
            else items
        )
        if tmp is not None:
            if not todo:
                continue
            if models.free_gb() < models.MIN_FREE_GB + 0.2:
                print("disk guard: stopping before materialising a batch")
                break
            paths = runner.materialise(ROOT, todo, scratch)
            items = [{**e, "path": paths[e["audio_id"]]} for e in todo]
        r = runner.run_entries(ad, items, out, dev)
        for k in ("done", "skipped", "failed"):
            tot[k] += r[k]
        tot["errors"] += r["errors"]
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        print(
            f"batch ok: {r['done']} done, {r['skipped']} skipped, {r['failed']} failed; "
            f"free {models.free_gb():.2f} GB",
            flush=True,
        )
    n = runner.aggregate(out, RES / a.model / "dev" / "transcripts.jsonl")
    status = "ran" if tot["failed"] == 0 and n == len(entries) else "partial"
    run = {
        "model": a.model,
        "revision": ad.revision,
        "licence": models.MODELS[a.model]["licence"],
        "status": status,
        "hardware": ad.hardware,
        "settings": ad.settings(),
        "files_expected": len(entries),
        "files_written": n,
        **{k: tot[k] for k in ("done", "skipped", "failed")},
        "errors": tot["errors"][:20],
        "split": "dev",
        "wall_seconds": round(time.time() - t_start),
        "finished_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "latency = decode + inference per file, model load and one warm-up file excluded",
    }
    rj = RES / a.model / "run.json"
    if tot["done"] == 0 and rj.exists():  # pure resume check: keep the record of the real run
        prev = json.loads(rj.read_text(encoding="utf-8"))
        prev.setdefault("resume_checks", []).append(
            {"at": run["finished_at"], "skipped": tot["skipped"], "failed": tot["failed"]}
        )
        run = prev
    rj.write_text(json.dumps(run, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: run[k] for k in ("status", "files_written", "failed", "wall_seconds")}))
    return 0 if status == "ran" else 1


def cmd_summarise(a) -> int:
    entries = subset.load(RES)
    ran = [
        p.name for p in sorted((RES / "dev").iterdir()) if p.is_dir() and p.name in models.MODELS
    ]
    rows = summary.summarise(ROOT, ran, entries, RES / "summary.csv")
    if len(ran) >= 2:
        summary.paired(ROOT, ran[0], ran[1], entries, RES / "paired_cer.csv")
    print(f"summary.csv: {len(rows)} rows; models with outputs: {ran}")
    return 0


def cmd_mock(a) -> int:
    """Mock run on fixtures only: no model, no repo audio. Output goes to a temp folder."""
    fx = json.loads((ROOT / "m2_asr/fixtures/mock_transcripts.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        entries = []
        for aid in fx:
            p = tdp / "dev" / f"{aid}.wav"
            p.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
                w.writeframes(b"\x00\x00" * 16000)
            entries.append({"audio_id": aid, "path": str(p), "source": "tts", "voice": "mock"})
        out = tdp / "out"
        r = runner.run_entries(MockAdapter(fx), entries, out, G.DevGuard(ROOT))
        bad = validate.validate_path("transcript.v1", out)
        errs = {k: v for k, v in bad.items() if v}
        print(f"mock: {r['done']} transcripts written, schema errors: {len(errs)}")
        return 0 if r["failed"] == 0 and not errs else 1


def cmd_fetch_status(a) -> int:
    print(
        json.dumps(
            {
                "free_gb": round(models.free_gb(), 2),
                "models": list(models.MODELS),
                "not_run": {k: v["status"] for k, v in models.NOT_RUN.items()},
            },
            indent=1,
        )
    )
    return 0


def cmd_purge(a) -> int:
    print(json.dumps(models.purge(a.model)))
    if a.scratch_dir:
        shutil.rmtree(a.scratch_dir, ignore_errors=True)
    print(f"free disk after: {models.free_gb():.2f} GB")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="m2_asr")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("subset")
    s.add_argument("--n-conv", type=int, default=N_CONV)
    s.set_defaults(f=cmd_subset)
    r = sp.add_parser("run")
    r.add_argument("--model", required=True, choices=list(models.MODELS))
    r.add_argument("--limit", type=int)
    r.add_argument("--batch", type=int, default=48)
    r.add_argument("--language", default="kn")
    r.add_argument("--threads", type=int, default=8)
    r.add_argument("--scratch", default=str(DEFAULT_SCRATCH))
    r.set_defaults(f=cmd_run)
    sp.add_parser("summarise").set_defaults(f=cmd_summarise)
    sp.add_parser("mock").set_defaults(f=cmd_mock)
    sp.add_parser("status").set_defaults(f=cmd_fetch_status)
    p = sp.add_parser("purge")
    p.add_argument("--model", required=True, choices=list(models.MODELS))
    p.add_argument("--scratch-dir")
    p.set_defaults(f=cmd_purge)
    a = ap.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
