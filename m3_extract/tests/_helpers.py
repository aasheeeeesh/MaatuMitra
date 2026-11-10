"""Shared helpers for m3_extract tests. Fixtures only (never dev/test data)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures"
FIX_LEXICON = FIX / "lexicon" / "drugs_fixture.csv"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def fixture_pairs():
    """(gold doc, gold transcript doc) for every valid gold fixture."""
    out = []
    for gp in sorted((FIX / "gold" / "valid").glob("*.json")):
        g = load_json(gp)
        tp = FIX / "transcript" / "valid" / f"{g['conversation_id']}__gold.json"
        out.append((g, load_json(tp)))
    return out


def make_transcript(text: str, audio_id: str = "unit-001") -> dict:
    """A gold-style transcript.v1 for an ad-hoc unit-test sentence."""
    import regex

    words = [
        {
            "w": m.group(),
            "char_start": m.start(),
            "char_end": m.end(),
            "start": None,
            "end": None,
            "conf": None,
        }
        for m in regex.finditer(r"[\p{L}\p{M}\p{N}]+", text)
    ]
    return {
        "schema_version": "transcript.v1",
        "audio_id": audio_id,
        "source": "template_text",
        "model": {"name": "gold", "revision": "unit-test"},
        "text": text,
        "words": words,
        "latency_ms": None,
        "audio_duration_s": None,
        "hardware": None,
        "created_at": "2026-11-10T00:00:00Z",
    }


CTX = {"patient_ref": "pt-unit-0001", "encounter_type": "nurse_consult"}
