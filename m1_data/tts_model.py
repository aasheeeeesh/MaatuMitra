"""Meta MMS-TTS Kannada (facebook/mms-tts-kan) through transformers VitsModel, CPU.

Why this model: the brief's first choice, ai4bharat/indic-parler-tts, is a gated Hugging Face
repo (HTTP 401 without a logged-in account that accepted its terms; checked 2026-11-11) and the
team has no token. MMS-TTS is the brief's named fallback. Licence CC-BY-NC-4.0 (non-commercial;
fine for coursework, UNVERIFIED for the synthesised audio itself). It has ONE speaker.
Weights are loaded from safetensors only; no trust_remote_code.
"""

from __future__ import annotations

import numpy as np

MODEL_ID = "facebook/mms-tts-kan"
REVISION = "30e3c5d533e8c559c10bf0d25637fea51b95bd7c"  # HF repo sha, fetched 2026-11-11
SR = 16000  # MMS-TTS native sampling rate


class MmsKannada:
    def __init__(self, threads: int = 4) -> None:
        import torch
        from transformers import AutoTokenizer, VitsModel

        torch.set_num_threads(threads)
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION)
        self.model = VitsModel.from_pretrained(MODEL_ID, revision=REVISION, use_safetensors=True)
        self.model.eval()
        assert self.model.config.sampling_rate == SR

    def __call__(self, text_kn: str, seed: int) -> np.ndarray:
        """Kannada-script text -> float32 mono at 16 kHz. One torch seed per utterance."""
        inputs = self.tok(text_kn, return_tensors="pt")
        self.torch.manual_seed(seed)
        with self.torch.no_grad():
            wav = self.model(**inputs).waveform[0]
        return wav.float().cpu().numpy().astype(np.float32)
