"""Test helpers: build a (transcript.v1, record.v1) pair from turns and items.

Offsets are COMPUTED with str.find inside the given turn (never typed by hand).
Kannada test sentences are written by an AI agent and are NOT native-validated.
"""

from __future__ import annotations

from pathlib import Path

import regex

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures"
TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")


def _words(text: str, conf: dict[str, float] | None):
    out = []
    for i, m in enumerate(TOKEN.finditer(text)):
        c = None
        if conf is not None:
            c = conf.get(m.group(), 0.95)
        out.append(
            {
                "w": m.group(),
                "char_start": m.start(),
                "char_end": m.end(),
                "start": None if conf is None else round(0.3 + i * 0.5, 2),
                "end": None if conf is None else round(0.7 + i * 0.5, 2),
                "conf": c,
            }
        )
    return out


def transcript(turns: list[str], *, audio_id: str = "t-test-1", conf: dict | None = None):
    """conf=None -> gold-style transcript (no confidences). conf={} -> all words 0.95."""
    text = "\n".join(turns)
    return {
        "schema_version": "transcript.v1",
        "audio_id": audio_id,
        "source": "template_text" if conf is None else "tts",
        "model": {"name": "gold", "revision": "test"}
        if conf is None
        else {"name": "asr-test", "revision": "test"},
        "text": text,
        "words": _words(text, conf),
        "latency_ms": None,
        "audio_duration_s": None,
        "hardware": None,
        "created_at": "2026-11-09T12:00:00Z",
    }


def ev(turns: list[str], span: str, turn: int, occurrence: int = 0):
    offset = sum(len(t) + 1 for t in turns[:turn])
    local = -1
    for _ in range(occurrence + 1):
        local = turns[turn].find(span, local + 1)
    assert local >= 0, (span, turns[turn])
    cs = offset + local
    return {
        "span_text": span,
        "char_start": cs,
        "char_end": cs + len(span),
        "audio_start": None,
        "audio_end": None,
    }


def med(turns, span, turn, drug, dose=None, unit=None, freq=None, dur=None, negated=False):
    return {
        "drug": drug,
        "dose_value": dose,
        "dose_unit": unit,
        "frequency_per_day": freq,
        "duration_days": dur,
        "negated": negated,
        "evidence": ev(turns, span, turn),
    }


def sym(turns, span, turn, name, present):
    return {"name": name, "present": present, "evidence": ev(turns, span, turn)}


def adv(turns, span, turn, text, negated):
    return {"text": text, "negated": negated, "evidence": ev(turns, span, turn)}


def record(
    turns,
    *,
    meds=(),
    symptoms=(),
    advice=(),
    follow_up=None,
    patient="pt-test-1",
    audio_id="t-test-1",
    record_id="rec-test-1",
):
    return {
        "schema_version": "record.v1",
        "record_id": record_id,
        "patient_ref": patient,
        "encounter_type": "physician_consult",
        "source_transcript_id": audio_id,
        "extractor": {"name": "test", "version": "0"},
        "status": "draft",
        "symptoms": list(symptoms),
        "medications": list(meds),
        "advice": list(advice),
        "follow_up": follow_up,
    }


def statuses(verdict, check_id):
    return [c["status"] for c in verdict["checks"] if c["check_id"] == check_id]


def flags(verdict, check_id=None):
    return [
        c
        for c in verdict["checks"]
        if c["status"] == "flag" and (check_id is None or c["check_id"] == check_id)
    ]
