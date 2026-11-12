"""Test helpers for record.v2: build (transcript.v1, record.v2) pairs from turns.

Offsets are COMPUTED with str.find (never typed by hand). Kannada test sentences are written by
an AI agent and are NOT native-validated.
"""

from __future__ import annotations

from m4_verify.tests.helpers import ev, transcript  # noqa: F401  (re-exported)

FE_KEYS = ("route", "strength", "formulation", "as_needed", "food_timing", "status")


def med2(
    turns,
    span,
    turn,
    drug,
    dose=None,
    unit=None,
    freq=None,
    dur=None,
    negated=False,
    *,
    route=None,
    strength=None,
    formulation=None,
    as_needed=None,
    food_timing=None,
    status="prescribed",
    speaker="doctor",
    fe=None,
):
    """fe = {key: (span_text, turn)} for the field_evidence spans (keys in FE_KEYS)."""
    sv, su = strength if strength else (None, None)
    return {
        "drug": drug,
        "dose_value": dose,
        "dose_unit": unit,
        "frequency_per_day": freq,
        "duration_days": dur,
        "negated": negated,
        "evidence": ev(turns, span, turn),
        "route": route,
        "strength_value": sv,
        "strength_unit": su,
        "formulation": formulation,
        "as_needed": as_needed,
        "food_timing": food_timing,
        "status": status,
        "speaker": speaker,
        "field_evidence": {k: ev(turns, s, t) for k, (s, t) in (fe or {}).items()},
    }


def adv2(turns, span, turn, text, negated, speaker="doctor"):
    return {"text": text, "negated": negated, "evidence": ev(turns, span, turn), "speaker": speaker}


def record2(
    turns,
    *,
    meds=(),
    symptoms=(),
    advice=(),
    follow_up=None,
    age=None,
    weight=None,
    patient="pt-test-1",
    audio_id="t-test-1",
    record_id="rec2-test-1",
):
    """age = (band, span_text, turn); weight = (value, span_text, turn)."""
    return {
        "schema_version": "record.v2",
        "record_id": record_id,
        "patient_ref": patient,
        "encounter_type": "physician_consult",
        "source_transcript_id": audio_id,
        "extractor": {"name": "test", "version": "0"},
        "status": "draft",
        "patient_age_band": None
        if age is None
        else {"band": age[0], "evidence": ev(turns, age[1], age[2])},
        "weight_kg": None
        if weight is None
        else {"value": weight[0], "evidence": ev(turns, weight[1], weight[2])},
        "symptoms": list(symptoms),
        "medications": list(meds),
        "advice": list(advice),
        "follow_up": follow_up,
    }


def at(verdict, check_id, path, status="flag"):
    """Entries of one check at one field_path with one status."""
    return [
        c
        for c in verdict["checks"]
        if c["check_id"] == check_id and c["field_path"] == path and c["status"] == status
    ]
