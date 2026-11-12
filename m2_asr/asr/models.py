"""Model registry, pinned downloads, disk checks, cache purge, hardware string.

Facts below come from the Hugging Face model API fetched 2026-11-12 (see README / handoff).
Only safetensors or CTranslate2 files are downloaded; no pickle, no trust_remote_code.
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

MIN_FREE_GB = 1.5

MODELS: dict[str, dict] = {
    "faster-whisper-small": {
        "kind": "ct2",
        "repo": "Systran/faster-whisper-small",
        "revision": "536b0662742c02347bc0e980a01041f333bce120",
        "licence": "MIT",
        "patterns": ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"],
        "kannada": "multilingual Whisper small (kn listed in model language tags); quality UNVERIFIED",
    },
    "whisper-small-vaani-kannada": {
        "kind": "hf_whisper_to_ct2",
        "repo": "ARTPARK-IISc/whisper-small-vaani-kannada",
        "revision": "65a803da247c0727bbd254b3c421046a60dd140b",  # HF API 2026-11-12
        "licence": "Apache-2.0",
        "patterns": [
            "config.json",
            "model.safetensors",
            "preprocessor_config.json",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
            "added_tokens.json",
            "special_tokens_map.json",
            "normalizer.json",
            "generation_config.json",
        ],
        "kannada": "Whisper small fine-tuned on Kannada (Vaani); data and quality UNVERIFIED",
    },
}

# Models that were looked at and NOT run. Reasons are facts from the HF API on 2026-11-12.
NOT_RUN: dict[str, dict] = {
    "ai4bharat-indic-conformer-600m-multilingual": {
        "repo": "ai4bharat/indic-conformer-600m-multilingual",
        "status": "pending",
        "licence": "MIT (API cardData)",
        "reason": "Gated (auto-approval needs a logged-in Hugging Face account; README returned "
        "'Access ... is restricted'). Repo is 2.56 GB (ONNX + custom model_onnx.py, which would need "
        "trust_remote_code review). Lists a Kannada head (joint_post_net_kn.onnx). Does not fit the disk budget.",
    },
    "parrotlet-a-en-5b": {
        "repo": "ekacare/parrotlet-a-en-5b",
        "status": "pending",
        "licence": "MIT (API cardData)",
        "reason": "Gated; card tag language = [en] only, so Kannada is NOT supported; ~10 GB of weights "
        "(decoder 8.6 GB + encoder 1.3 GB) cannot fit 2.9 GB free disk. Negative result by design: "
        "not run; recorded, not hidden.",
    },
    "mms-1b-all": {
        "repo": "facebook/mms-1b-all",
        "status": "pending",
        "licence": "CC-BY-NC-4.0 (API cardData; non-commercial, fine for coursework, must be recorded)",
        "reason": "model.safetensors is 3.86 GB; free disk is 2.9 GB and the floor is 1.5 GB. Needs a "
        "machine with >= 6 GB free (or Colab).",
    },
    "ai4bharat-indicwhisper": {
        "repo": "(no ai4bharat/IndicWhisper repo found)",
        "status": "pending",
        "licence": "UNVERIFIED",
        "reason": "API query for ai4bharat/IndicWhisper returned an auth/not-found error on 2026-11-12. "
        "IndicWhisper weights are, to my recollection, distributed outside this HF path (UNVERIFIED).",
    },
    "vasista22-whisper-kannada-small": {
        "repo": "vasista22/whisper-kannada-small",
        "status": "not_run",
        "licence": "Apache-2.0 (API cardData)",
        "reason": "Weights exist only as pytorch_model.bin (pickle) and flax msgpack; no safetensors. "
        "Rejected by the no-pickle rule.",
    },
    "whisper-large-v3": {
        "repo": "Systran/faster-whisper-large-v3",
        "status": "not_run",
        "licence": "MIT (UNVERIFIED this session)",
        "reason": "~3 GB CT2 weights and needs GPU; no CUDA runtime installed (CUDA torch/cuBLAS too big). Not attempted.",
    },
}


def cpu_name() -> str:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        ) as k:
            return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
    except Exception:
        return platform.processor() or "unknown CPU"


def hardware_string(compute_type: str, threads: int) -> str:
    return f"{cpu_name()}, {os.cpu_count()} logical CPUs, {threads} threads used, CPU only (GPU NOT used), {compute_type}"


def free_gb(path: str = "C:/") -> float:
    return shutil.disk_usage(path).free / 1e9


def require_free(extra_gb: float, path: str = "C:/") -> None:
    """Refuse a download that would leave less than MIN_FREE_GB free."""
    f = free_gb(path)
    if f - extra_gb < MIN_FREE_GB:
        raise RuntimeError(
            f"disk guard: {f:.2f} GB free, need {extra_gb:.2f} GB + floor {MIN_FREE_GB} GB"
        )


def hf_cache_dir() -> Path:
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def fetch(name: str, size_gb: float) -> str:
    """Download the pinned revision (allow-listed files only) into the HF cache; return the path."""
    from huggingface_hub import snapshot_download

    m = MODELS[name]
    try:  # already cached (for example after an interrupted run): nothing new to download
        return snapshot_download(
            m["repo"], revision=m["revision"], allow_patterns=m["patterns"], local_files_only=True
        )
    except Exception:
        require_free(size_gb)
    return snapshot_download(m["repo"], revision=m["revision"], allow_patterns=m["patterns"])


def purge(name: str) -> dict:
    """Delete this model's HF cache folder (only ours: models--org--name) and report the size."""
    repo = MODELS[name]["repo"]
    d = hf_cache_dir() / ("models--" + repo.replace("/", "--"))
    size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.exists() else 0
    if d.exists():
        shutil.rmtree(d)
    return {"deleted": str(d), "bytes": size}
