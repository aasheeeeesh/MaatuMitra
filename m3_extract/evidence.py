"""Evidence spans and the EVIDENCE CHECK (AGENT 4 step 2-3).

An evidence span is a slice of the transcript text: code-point offsets, end exclusive.
check_evidence() confirms transcript[char_start:char_end] == span_text after NFC for EVERY
evidence object in a record. Any failure rejects the whole record (never repaired silently).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from typing import Any


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def evidence_for(transcript: dict[str, Any], start: int, end: int) -> dict[str, Any]:
    """Evidence object for text[start:end]; audio times from word timestamps when ALL words
    inside the span have them, else null."""
    text = transcript["text"]
    inside = [
        w for w in transcript.get("words", []) if w["char_start"] >= start and w["char_end"] <= end
    ]
    a0 = a1 = None
    if inside and all(w.get("start") is not None and w.get("end") is not None for w in inside):
        a0, a1 = inside[0]["start"], inside[-1]["end"]
    return {
        "span_text": text[start:end],
        "char_start": start,
        "char_end": end,
        "audio_start": a0,
        "audio_end": a1,
    }


def iter_evidence(record: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for kind in ("symptoms", "medications", "advice"):
        for i, item in enumerate(record.get(kind) or []):
            yield f"{kind}/{i}", item.get("evidence")
    fu = record.get("follow_up")
    if fu is not None:
        yield "follow_up", fu.get("evidence")
    # record.v2: one span per non-null new field, plus age band and weight
    for i, med in enumerate(record.get("medications") or []):
        for key, ev in (med.get("field_evidence") or {}).items():
            yield f"medications/{i}/field_evidence/{key}", ev
    for key in ("patient_age_band", "weight_kg"):
        if record.get(key) is not None:
            yield key, record[key].get("evidence")


def check_evidence(record: dict[str, Any], transcript_text: str) -> list[str]:
    """Return a list of failures (empty = every span is real). Never trusts the producer."""
    errs: list[str] = []
    text = nfc(transcript_text)
    for path, ev in iter_evidence(record):
        if not isinstance(ev, dict):
            errs.append(f"{path}: missing evidence")
            continue
        cs, ce, span = ev.get("char_start"), ev.get("char_end"), ev.get("span_text")
        if not (isinstance(cs, int) and isinstance(ce, int) and isinstance(span, str)):
            errs.append(f"{path}: evidence offsets/span_text missing or wrong type")
            continue
        if not (0 <= cs < ce <= len(text)):
            errs.append(f"{path}: offsets [{cs}, {ce}) outside transcript of length {len(text)}")
            continue
        if not span.strip():
            errs.append(f"{path}: empty span_text")
            continue
        if text[cs:ce] != nfc(span):
            errs.append(f"{path}: transcript[{cs}:{ce}] = {text[cs:ce]!r} != span_text {span!r}")
        a0, a1 = ev.get("audio_start"), ev.get("audio_end")
        if (a0 is None) != (a1 is None):
            errs.append(f"{path}: only one of audio_start/audio_end is set")
        elif a0 is not None and a1 < a0:
            errs.append(f"{path}: audio_end < audio_start")
    return errs


def locate_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Offsets of an EXACT (NFC) quote in the transcript; only outer whitespace is trimmed.
    The first occurrence is used. No fuzzy repair: a quote that is not verbatim is not evidence."""
    q = nfc(quote or "").strip()
    if not q:
        return None
    i = nfc(text).find(q)
    if i < 0:
        return None
    return i, i + len(q)
