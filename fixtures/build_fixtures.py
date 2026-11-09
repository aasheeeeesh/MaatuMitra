"""Regenerate every contract fixture deterministically.

    uv run python fixtures/build_fixtures.py

Why a script: span offsets must be exactly right, so they are COMPUTED from the
text (str.find), never typed by hand. All content is FIXTURE ONLY:
- Kannada sentences were written by an AI (architect agent) and are NOT
  native-validated.
- ASR timings/confidences are hand-made numbers; no model was run.
- URLs use example.org (reserved for documentation, RFC 2606) because no real
  source was fetched for fixtures. Never cite them.
- Doses are illustrative only and UNVERIFIED.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import regex

ROOT = Path(__file__).resolve().parent
TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")
CREATED = "2026-11-09T12:00:00Z"
GEN = "fixtures-v1"

# --------------------------------------------------------------------------- conversations
# (conversation_id, family, encounter_type, patient_ref, turns, items, tags)
# items: list of (kind, fields, turn_index, span_text)

CONVS = [
    dict(
        cid="fx-asha-001",
        family="a_fever_cough_duration",
        enc="asha_household_visit",
        patient="pt-fx-0001",
        turns=[
            ("asha", "ಮಗುವಿಗೆ ಎಷ್ಟು ದಿನದಿಂದ ಜ್ವರ ಇದೆ?"),
            ("caregiver", "ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ, ಕೆಮ್ಮು ಇಲ್ಲ."),
        ],
        items=[
            ("symptoms", {"name": "fever", "present": True}, 1, "ಮೂರು ದಿನದಿಂದ ಜ್ವರ ಇದೆ"),
            ("symptoms", {"name": "cough", "present": False}, 1, "ಕೆಮ್ಮು ಇಲ್ಲ"),
        ],
        follow_up=None,
        tags=dict(
            has_negation=True, trap_tokens=[], code_switched=False, cross_turn_negation=False
        ),
        status="draft",
    ),
    dict(
        cid="fx-asha-002",
        family="b_cross_turn_negation",
        enc="asha_household_visit",
        patient="pt-fx-0002",
        turns=[
            ("asha", "ಮಗು ನಿನ್ನೆ ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್ ಕುಡಿಯಿತಾ?"),
            ("caregiver", "ಇಲ್ಲ."),
        ],
        items=[
            (
                "medications",
                {
                    "drug": "paracetamol",
                    "dose_value": None,
                    "dose_unit": None,
                    "frequency_per_day": None,
                    "duration_days": None,
                    "negated": True,
                },
                0,
                "ಪ್ಯಾರಸಿಟಮಾಲ್ ಸಿರಪ್",
            ),
        ],
        follow_up=None,
        tags=dict(has_negation=True, trap_tokens=[], code_switched=False, cross_turn_negation=True),
        status="flagged",
    ),
    dict(
        cid="fx-pharm-003",
        family="e_pharmacist_dispensing",
        enc="pharmacist_dispensing",
        patient="pt-fx-0003",
        turns=[
            ("pharmacist", "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."),
            ("patient", "ಸರಿ, ಊಟದ ನಂತರ ತೆಗೆದುಕೊಳ್ಳಬೇಕಾ?"),
            ("pharmacist", "ಹೌದು, ಊಟದ ನಂತರ. ಎಲ್ಲ ಮಾತ್ರೆ ಮುಗಿಸಿ."),
        ],
        items=[
            (
                "medications",
                {
                    "drug": "amoxicillin",
                    "dose_value": 500,
                    "dose_unit": "mg",
                    "frequency_per_day": 3,
                    "duration_days": 5,
                    "negated": False,
                },
                0,
                "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 500 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ",
            ),
            ("advice", {"text": "take after food", "negated": False}, 2, "ಊಟದ ನಂತರ"),
            ("advice", {"text": "finish all tablets", "negated": False}, 2, "ಎಲ್ಲ ಮಾತ್ರೆ ಮುಗಿಸಿ"),
        ],
        follow_up=None,
        tags=dict(
            has_negation=False,
            trap_tokens=["ಮಾತ್ರೆ", "ಎಲ್ಲ"],
            code_switched=True,
            cross_turn_negation=False,
        ),
        status="approved",
    ),
    dict(
        cid="fx-phys-004",
        family="g_physician_code_switch",
        enc="physician_consult",
        patient="pt-fx-0004",
        turns=[
            ("physician", "Azithromycin 500 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಮೂರು ದಿನ ತೆಗೆದುಕೊಳ್ಳಿ."),
            ("physician", "ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು."),
        ],
        items=[
            (
                "medications",
                {
                    "drug": "azithromycin",
                    "dose_value": 500,
                    "dose_unit": "mg",
                    "frequency_per_day": 1,
                    "duration_days": 3,
                    "negated": False,
                },
                0,
                "Azithromycin 500 mg ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ ಮೂರು ದಿನ",
            ),
            (
                "advice",
                {"text": "do not take antibiotics for a cold", "negated": True},
                1,
                "ನೆಗಡಿಗೆ antibiotic ತೆಗೆದುಕೊಳ್ಳಬಾರದು",
            ),
        ],
        follow_up=None,
        tags=dict(has_negation=True, trap_tokens=[], code_switched=True, cross_turn_negation=False),
        status="draft",
    ),
    dict(
        cid="fx-nurse-005",
        family="f_nurse_multi_symptom",
        enc="nurse_consult",
        patient="pt-fx-0005",
        turns=[
            ("nurse", "ತಲೆನೋವು ಇದೆಯಾ? ವಾಂತಿ ಆಗುತ್ತಿದೆಯಾ?"),
            ("patient", "ತಲೆನೋವು ಇದೆ, ಆದರೆ ವಾಂತಿ ಆಗಿಲ್ಲ."),
            ("nurse", "ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಎರಡು ದಿನದಲ್ಲಿ ಮತ್ತೆ ಬನ್ನಿ."),
        ],
        items=[
            ("symptoms", {"name": "headache", "present": True}, 1, "ತಲೆನೋವು ಇದೆ"),
            ("symptoms", {"name": "vomiting", "present": False}, 1, "ವಾಂತಿ ಆಗಿಲ್ಲ"),
        ],
        follow_up=(
            {"text": "if the fever does not come down, come back in two days"},
            2,
            "ಜ್ವರ ಕಡಿಮೆ ಆಗದಿದ್ದರೆ ಎರಡು ದಿನದಲ್ಲಿ ಮತ್ತೆ ಬನ್ನಿ",
        ),
        tags=dict(
            has_negation=True, trap_tokens=[], code_switched=False, cross_turn_negation=False
        ),
        status="draft",
    ),
    dict(
        cid="fx-trap-006",
        family="i_trap_sentences",
        enc="physician_consult",
        patient="pt-fx-0006",
        turns=[
            ("physician", "ಪ್ಯಾರಸಿಟಮಾಲ್ ೫೦೦ mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ ಮಾತ್ರ ತೆಗೆದುಕೊಳ್ಳಿ."),
            ("patient", "ಎಲ್ಲಾ ಮಾತ್ರೆ ಇಲ್ಲಿ ಇವೆ, ಅಲ್ವಾ?"),
        ],
        items=[
            (
                "medications",
                {
                    "drug": "paracetamol",
                    "dose_value": 500,
                    "dose_unit": "mg",
                    "frequency_per_day": 2,
                    "duration_days": None,
                    "negated": False,
                },
                0,
                "ಪ್ಯಾರಸಿಟಮಾಲ್ ೫೦೦ mg ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ",
            ),
        ],
        follow_up=None,
        tags=dict(
            has_negation=False,
            trap_tokens=["ಮಾತ್ರ", "ಎಲ್ಲಾ", "ಮಾತ್ರೆ", "ಇಲ್ಲಿ", "ಅಲ್ವಾ"],
            code_switched=True,
            cross_turn_negation=False,
        ),
        status="draft",
    ),
]


def conv_text(turns):
    return "\n".join(t for _, t in turns)


def locate(turns, turn_index, span):
    """Return (char_start, char_end) of span inside turn turn_index of the conversation text."""
    offset = sum(len(t) + 1 for _, t in turns[:turn_index])
    local = turns[turn_index][1].find(span)
    assert local >= 0, (span, turns[turn_index][1])
    return offset + local, offset + local + len(span)


def words(text, timed=False, low_conf=()):
    out = []
    t = 0.30
    for i, m in enumerate(TOKEN.finditer(text)):
        w = {"w": m.group(), "char_start": m.start(), "char_end": m.end()}
        if timed:
            dur = round(0.12 + 0.06 * len(m.group()), 2)
            w.update(start=round(t, 2), end=round(t + dur, 2))
            w["conf"] = 0.41 if m.group() in low_conf else round(0.97 - 0.01 * (i % 5), 2)
            t += dur + 0.08
        else:
            w.update(start=None, end=None, conf=None)
        out.append(w)
    return out, round(t + 0.3, 2)


def gold_doc(c):
    gr = {
        "patient_ref": c["patient"],
        "encounter_type": c["enc"],
        "symptoms": [],
        "medications": [],
        "advice": [],
        "follow_up": None,
    }
    for kind, fields, ti, span in c["items"]:
        cs, ce = locate(c["turns"], ti, span)
        gr[kind].append(
            {
                **fields,
                "gold_span": {
                    "turn_index": ti,
                    "span_text": span,
                    "char_start": cs,
                    "char_end": ce,
                },
            }
        )
    if c["follow_up"]:
        fields, ti, span = c["follow_up"]
        cs, ce = locate(c["turns"], ti, span)
        gr["follow_up"] = {
            **fields,
            "gold_span": {"turn_index": ti, "span_text": span, "char_start": cs, "char_end": ce},
        }
    return {
        "schema_version": "gold.v1",
        "conversation_id": c["cid"],
        "template_family_id": c["family"],
        "turns": [{"speaker_role": r, "text": t} for r, t in c["turns"]],
        "gold_record": gr,
        "tags": c["tags"],
    }


def transcript_doc(audio_id, text, *, gold, source, low_conf=()):
    ws, dur = words(text, timed=not gold, low_conf=low_conf)
    return {
        "schema_version": "transcript.v1",
        "audio_id": audio_id,
        "source": source,
        "model": (
            {"name": "gold", "revision": GEN}
            if gold
            else {"name": "faster-whisper-small", "revision": "FIXTURE-no-model-run"}
        ),
        "text": text,
        "words": ws,
        "latency_ms": None if gold else 1834.0,
        "audio_duration_s": None if gold else dur,
        "hardware": None if gold else "FIXTURE: hand-made values, no model was run",
        "created_at": CREATED,
    }


def record_doc(record_id, transcript, c, *, overrides=None, status=None, timed=False):
    text = transcript["text"]
    wmap = transcript["words"]
    rec = {
        "schema_version": "record.v1",
        "record_id": record_id,
        "patient_ref": c["patient"],
        "encounter_type": c["enc"],
        "source_transcript_id": transcript["audio_id"],
        "extractor": {"name": "fixture-hand-made", "version": GEN},
        "status": status or c["status"],
        "symptoms": [],
        "medications": [],
        "advice": [],
        "follow_up": None,
    }
    overrides = overrides or {}

    lines = text.split(chr(10))

    def ev(span, ti):
        offset = sum(len(t) + 1 for t in lines[:ti])
        local = lines[ti].find(span)
        assert local >= 0, (span, lines[ti])
        cs = offset + local
        ce = cs + len(span)
        a0 = a1 = None
        if timed:
            inside = [w for w in wmap if w["char_start"] >= cs and w["char_end"] <= ce]
            a0, a1 = inside[0]["start"], inside[-1]["end"]
        return {
            "span_text": span,
            "char_start": cs,
            "char_end": ce,
            "audio_start": a0,
            "audio_end": a1,
        }

    for kind, fields, ti, span in c["items"]:
        span = overrides.get(span, span)
        f = dict(fields)
        f.update(overrides.get((kind, fields.get("drug") or fields.get("name")), {}))
        rec[kind].append({**f, "evidence": ev(span, ti)})
    if c["follow_up"]:
        fields, ti, span = c["follow_up"]
        rec["follow_up"] = {**fields, "evidence": ev(span, ti)}
    return rec


ALL_CHECKS = [
    ("C1", "span-exists"),
    ("C2", "span-supports-value"),
    ("C3", "negation-consistency"),
    ("C4", "dose-range"),
    ("C5", "frequency-duration-parse"),
    ("C6", "unsupported-addition"),
    ("C7", "asr-risk"),
    ("C8", "ambiguity"),
]


def verdict_doc(record_id, special=None, auto=None):
    special = special or {}
    checks = []
    for cid, name in ALL_CHECKS:
        status, reason, path = special.get(cid, ("pass", "ok", "/"))
        checks.append(
            {"check_id": cid, "name": name, "status": status, "reason": reason, "field_path": path}
        )
    flagged = any(c["status"] == "flag" for c in checks)
    return {
        "schema_version": "verdict.v1",
        "record_id": record_id,
        "checks": checks,
        "auto_acceptable": (not flagged) if auto is None else auto,
        "verifier_version": "fixture-v1",
    }


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def manifest_rows():
    base = {
        "schema_version": "manifest.v1",
        "noise_snr_db": None,
        "speed_factor": None,
        "dialect": "unknown",
        "retrieved_at": CREATED,
        "generator_version": GEN,
        "seed": 1234,
        "parent_id": None,
        "native_validated": False,
    }
    rows = [
        dict(
            file="data/audio/tts/fx-pharm-003__v1__clean.wav",
            source="tts",
            split="dev",
            voice_or_speaker="tts-voice-A",
            licence_spdx="UNVERIFIED",
            licence_url="UNVERIFIED",
            consent_note="synthetic TTS voice; no human speaker",
        ),
        dict(
            file="data/audio/tts/fx-pharm-003__v1__snr10_white.wav",
            source="tts",
            split="dev",
            voice_or_speaker="tts-voice-A",
            noise_snr_db=10.0,
            parent_id="data/audio/tts/fx-pharm-003__v1__clean.wav",
            licence_spdx="UNVERIFIED",
            licence_url="UNVERIFIED",
            consent_note="synthetic TTS voice; no human speaker",
        ),
        dict(
            file="data/audio/tts/fx-phys-004__v2__speed1.1.wav",
            source="tts",
            split="test",
            voice_or_speaker="tts-voice-B-heldout",
            speed_factor=1.1,
            licence_spdx="UNVERIFIED",
            licence_url="UNVERIFIED",
            consent_note="synthetic TTS voice; no human speaker",
        ),
        dict(
            file="data/audio/public/fleurs_kn_fixture_0001.wav",
            source="public_real",
            split="test",
            voice_or_speaker="fleurs-speaker-fixture-17",
            seed=None,
            generator_version="loader-fixture-v1",
            licence_spdx="CC-BY-4.0",
            licence_url="https://example.org/fixture/licence-page",
            consent_note="public dataset; consent per dataset card (fixture, UNVERIFIED)",
        ),
        dict(
            file="data/gold/fx-nurse-005.json",
            source="template_text",
            split="dev",
            voice_or_speaker="none",
            licence_spdx="NOASSERTION",
            licence_url="UNVERIFIED",
            consent_note="template-generated synthetic text; no person involved",
        ),
    ]
    out = []
    for r in rows:
        d = {**base, **r}
        d["sha256"] = sha(d["file"])
        d["bytes"] = 1000 + len(d["file"]) * 37
        out.append(
            {
                k: d[k]
                for k in [
                    "schema_version",
                    "file",
                    "sha256",
                    "bytes",
                    "source",
                    "split",
                    "noise_snr_db",
                    "speed_factor",
                    "voice_or_speaker",
                    "dialect",
                    "licence_spdx",
                    "licence_url",
                    "retrieved_at",
                    "generator_version",
                    "seed",
                    "parent_id",
                    "consent_note",
                    "native_validated",
                ]
            }
        )
    return out


U = [
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
    "33333333-3333-4333-8333-333333333333",
    "44444444-4444-4444-8444-444444444444",
    "55555555-5555-4555-8555-555555555555",
]


def access_cases():
    rows = [
        (
            "ac-asha-households-select-own",
            "asha",
            U[0],
            "households",
            "select",
            "own",
            None,
            "allow",
        ),
        (
            "ac-asha-patients-select-other-fac",
            "asha",
            U[0],
            "patients",
            "select",
            "other_facility",
            None,
            "deny",
        ),
        (
            "ac-pharm-orders-view-select-own",
            "pharmacist",
            U[3],
            "pharmacist_orders_v",
            "select",
            "own",
            None,
            "allow",
        ),
        (
            "ac-researcher-records-select-alg-none",
            "researcher",
            U[4],
            "records",
            "select",
            "none",
            "alg_none",
            "deny",
        ),
        (
            "ac-nurse-records-update-sqli",
            "nurse",
            U[1],
            "records",
            "update",
            "same_facility_other",
            "sqli",
            "allow",
        ),
        (
            "ac-physician-audit-delete",
            "physician",
            U[2],
            "audit_log",
            "delete",
            "none",
            None,
            "deny",
        ),
    ]
    keys = ["case_id", "role", "user_id", "resource", "action", "ownership", "attack", "expected"]
    return [{"schema_version": "access_case.v1", **dict(zip(keys, r, strict=True))} for r in rows]


def cards():
    rows = [
        (
            "card-cold-no-antibiotic",
            "antibiotics do not treat colds",
            "ನೆಗಡಿ ಮತ್ತು ಸಾಮಾನ್ಯ ಶೀತಕ್ಕೆ ಆಂಟಿಬಯಾಟಿಕ್ ಬೇಡ. ಸಂದೇಹವಿದ್ದರೆ ವೈದ್ಯರನ್ನು ಕೇಳಿ.",
            "FIXTURE: Antibiotics are not needed for a common cold. If unsure, ask a doctor.",
        ),
        (
            "card-finish-prescribed",
            "take only what the doctor prescribed",
            "ವೈದ್ಯರು ಹೇಳಿದಷ್ಟು ದಿನ ಮಾತ್ರ ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳಿ. ಉಳಿದ ಮಾತ್ರೆಗಳನ್ನು ಬೇರೆಯವರಿಗೆ ಕೊಡಬೇಡಿ.",
            "FIXTURE: Take medicine only for as many days as the doctor said. Do not give "
            "leftover tablets to others.",
        ),
        (
            "card-hand-hygiene",
            "hand hygiene",
            "ಊಟದ ಮೊದಲು ಮತ್ತು ಶೌಚಾಲಯದ ನಂತರ ಸೋಪಿನಿಂದ ಕೈ ತೊಳೆಯಿರಿ.",
            "FIXTURE: Wash hands with soap before eating and after using the toilet.",
        ),
        (
            "card-ors-diarrhoea",
            "ORS for diarrhoea",
            "ಭೇದಿ ಆದಾಗ ಓ.ಆರ್.ಎಸ್ ದ್ರಾವಣ ಕುಡಿಸಿ.",
            "FIXTURE: Give ORS solution during diarrhoea.",
        ),
        (
            "card-when-see-doctor",
            "when to see a doctor",
            "ಜ್ವರ ಮೂರು ದಿನಕ್ಕಿಂತ ಹೆಚ್ಚು ಇದ್ದರೆ ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ.",
            "FIXTURE: If fever lasts more than three days, see a doctor.",
        ),
    ]
    return [
        {
            "schema_version": "card.v1",
            "id": cid,
            "topic": topic,
            "kn_text": kn,
            "en_text": en,
            "source_url": f"https://example.org/fixture/{cid}",
            "source_retrieved_at": CREATED,
            "version": 1,
            "status": "machine_drafted_not_native_validated",
            "clinician_reviewed": False,
        }
        for cid, topic, kn, en in rows
    ]


def review_reports():
    def finding(i, sev, conf, urls=()):
        return {
            "id": f"F{i}",
            "severity": sev,
            "item": f"fixture item {i}",
            "problem": "FIXTURE: example problem text",
            "suggested_fix": "FIXTURE: example fix text",
            "evidence": "FIXTURE: model knowledge only, low confidence",
            "source_urls": list(urls),
            "confidence": conf,
        }

    specs = [
        (
            "rv-m1-kn-fixture",
            "kannada-language-reviewer",
            "m1_data",
            30,
            [finding(1, "major", "low"), finding(2, "minor", "medium")],
        ),
        (
            "rv-m1-clin-fixture",
            "clinical-reviewer",
            "m1_data",
            8,
            [finding(1, "critical", "medium", ["https://example.org/fixture/source"])],
        ),
        ("rv-m4-integrity-fixture", "scientific-integrity-auditor", "m4_verify", 12, []),
        (
            "rv-m5-sec-fixture",
            "security-auditor",
            "m5_backend",
            20,
            [finding(1, "major", "high"), finding(2, "major", "high"), finding(3, "minor", "low")],
        ),
        ("rv-int-qa-fixture", "integration-qa", "integration", 10, [finding(1, "minor", "high")]),
    ]
    return [
        {
            "schema_version": "review_report.v1",
            "review_id": rid,
            "reviewer_agent": agent,
            "target": target,
            "date": "2026-11-09",
            "sample_size": n,
            "findings": f,
            "summary": "FIXTURE: example summary. Simulated review, not human validation.",
            "label": "ai_simulated_review",
        }
        for rid, agent, target, n, f in specs
    ]


# --------------------------------------------------------------------------- invalid fixtures


def build_invalid(valid):
    inv = {}
    t = copy.deepcopy(valid["transcript"][0])
    t["words"][1]["char_start"] += 1
    inv.setdefault("transcript", {})["word_offset_mismatch.json"] = (
        t,
        "words[1].char_start shifted by one: text slice no longer equals w",
    )
    t = copy.deepcopy(valid["transcript"][0])
    t["source"] = "youtube"
    inv["transcript"]["source_not_in_enum.json"] = (t, "source 'youtube' is not an allowed value")
    t = copy.deepcopy(valid["transcript"][0])
    del t["model"]["revision"]
    inv["transcript"]["model_missing_revision.json"] = (t, "model.revision is required (pinning)")
    t = copy.deepcopy(valid["transcript"][0])
    t["text"] = t["text"].replace("ಮಗುವಿಗೆ", "ಮಗುವಿಗೆ") + " ಕ\u0cbf\u0cd5"
    inv["transcript"]["text_not_nfc.json"] = (t, "text contains decomposed U+0CBF U+0CD5 (not NFC)")

    r = copy.deepcopy(valid["record"][2])
    del r["medications"][0]["evidence"]
    inv.setdefault("record", {})["medication_missing_evidence.json"] = (
        r,
        "a medication without evidence (every field must have evidence)",
    )
    r = copy.deepcopy(valid["record"][0])
    r["status"] = "final"
    inv["record"]["status_not_in_enum.json"] = (
        r,
        "status 'final' not in draft|flagged|approved|saved",
    )
    r = copy.deepcopy(valid["record"][0])
    r["symptoms"][0]["evidence"]["char_end"] = r["symptoms"][0]["evidence"]["char_start"]
    inv["record"]["evidence_end_not_after_start.json"] = (r, "evidence char_end == char_start")
    r = copy.deepcopy(valid["record"][0])
    r["symptoms"][0]["evidence"]["span_text"] += "X"
    inv["record"]["span_length_mismatch.json"] = (
        r,
        "char_end - char_start differs from len(span_text)",
    )
    r = copy.deepcopy(valid["record"][2])
    r["approved_by"] = "physician-fx-1"
    inv["record"]["extra_property_approved_by.json"] = (
        r,
        "record.v1 has no approver field; extra properties are forbidden (gate lives in m5)",
    )

    v = copy.deepcopy(valid["verdict"][0])
    v["checks"][3]["status"] = "flag"
    v["auto_acceptable"] = True
    inv.setdefault("verdict", {})["flag_but_auto_acceptable.json"] = (
        v,
        "a check flags but auto_acceptable is true",
    )
    v = copy.deepcopy(valid["verdict"][0])
    v["checks"][0]["check_id"] = "C9"
    inv["verdict"]["check_id_c9.json"] = (v, "check_id C9 does not exist (C1..C8 only)")
    v = copy.deepcopy(valid["verdict"][0])
    v["checks"][2]["reason"] = "check_error: KeyError 'negated'"
    v["checks"][2]["status"] = "pass"
    inv["verdict"]["check_error_marked_pass.json"] = (
        v,
        "a check that errored must be 'flag' (fail-closed), not 'pass'",
    )
    v = copy.deepcopy(valid["verdict"][0])
    v["checks"] = []
    v["auto_acceptable"] = True
    inv["verdict"]["no_checks_but_auto_acceptable.json"] = (
        v,
        "no checks ran but auto_acceptable is true",
    )

    g = copy.deepcopy(valid["gold"][0])
    g["gold_record"]["symptoms"][0]["gold_span"]["char_start"] += 1
    g["gold_record"]["symptoms"][0]["gold_span"]["char_end"] += 1
    inv.setdefault("gold", {})["gold_span_offset_mismatch.json"] = (
        g,
        "gold span offsets shifted: slice no longer equals span_text",
    )
    g = copy.deepcopy(valid["gold"][0])
    sp = g["gold_record"]["symptoms"][0]["gold_span"]
    sp["turn_index"] = 0
    inv["gold"]["span_outside_its_turn.json"] = (
        g,
        "gold span lies in turn 1 but says turn_index 0",
    )
    g = copy.deepcopy(valid["gold"][0])
    g["tags"]["has_negation"] = False
    inv["gold"]["negated_item_but_has_negation_false.json"] = (
        g,
        "cough present=false but tags.has_negation is false",
    )
    g = copy.deepcopy(valid["gold"][0])
    g["turns"][0]["text"] = "ಮಗುವಿಗೆ\nಜ್ವರ ಇದೆ?"
    inv["gold"]["turn_text_contains_newline.json"] = (
        g,
        "turn text may not contain a newline (newline is the turn separator)",
    )

    m = copy.deepcopy(valid["manifest"][0])
    m["sha256"] = m["sha256"].upper()
    inv.setdefault("manifest", {})["sha256_uppercase.json"] = (m, "sha256 must be lower-case hex")
    m = copy.deepcopy(valid["manifest"][0])
    m["split"] = "train"
    inv["manifest"]["split_train.json"] = (m, "split must be dev or test")
    m = copy.deepcopy(valid["manifest"][0])
    del m["native_validated"]
    inv["manifest"]["missing_native_validated.json"] = (m, "native_validated is required")
    m = copy.deepcopy(valid["manifest"][0])
    m["file"] = "C:\\data\\audio\\x.wav"
    inv["manifest"]["windows_absolute_path.json"] = (m, "file must be a relative POSIX path")

    a = copy.deepcopy(valid["access_case"][0])
    a["action"] = "drop"
    inv.setdefault("access_case", {})["action_drop.json"] = (a, "action 'drop' not allowed")
    a = copy.deepcopy(valid["access_case"][3])
    a["expected"] = "allow"
    inv["access_case"]["alg_none_expected_allow.json"] = (
        a,
        "an alg=none token attack must always expect deny",
    )
    a = copy.deepcopy(valid["access_case"][0])
    a["user_id"] = "42"
    inv["access_case"]["user_id_not_uuid.json"] = (a, "user ids are UUIDs, never sequential ids")

    c = copy.deepcopy(valid["card"][0])
    c["kn_text"] = "Antibiotics are not needed for a cold."
    inv.setdefault("card", {})["kn_text_without_kannada.json"] = (
        c,
        "kn_text has no Kannada script",
    )
    c = copy.deepcopy(valid["card"][0])
    c["status"] = "native_validated"
    inv["card"]["status_native_validated.json"] = (
        c,
        "status 'native_validated' is not allowed by card.v1",
    )
    c = copy.deepcopy(valid["card"][0])
    c["version"] = 0
    inv["card"]["version_zero.json"] = (c, "version must be >= 1")

    rr = copy.deepcopy(valid["review_report"][0])
    rr["label"] = "native_validated"
    inv.setdefault("review_report", {})["label_not_ai_simulated.json"] = (
        rr,
        "label must be 'ai_simulated_review'",
    )
    rr = copy.deepcopy(valid["review_report"][0])
    rr["findings"][0]["severity"] = "blocker"
    inv["review_report"]["severity_blocker.json"] = (rr, "severity must be critical|major|minor")
    rr = copy.deepcopy(valid["review_report"][3])
    rr["findings"][1]["id"] = rr["findings"][0]["id"]
    inv["review_report"]["duplicate_finding_ids.json"] = (rr, "two findings share the id F1")
    rr = copy.deepcopy(valid["review_report"][0])
    del rr["findings"][0]["confidence"]
    inv["review_report"]["finding_missing_confidence.json"] = (rr, "confidence is required")
    return inv


# --------------------------------------------------------------------------- main


def write(path: Path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    valid: dict[str, list] = {
        k: []
        for k in [
            "transcript",
            "record",
            "verdict",
            "gold",
            "manifest",
            "access_case",
            "card",
            "review_report",
        ]
    }
    names: dict[str, list] = {k: [] for k in valid}

    by_id = {c["cid"]: c for c in CONVS}
    for c in CONVS:
        g = gold_doc(c)
        valid["gold"].append(g)
        names["gold"].append(c["cid"])
        tr = transcript_doc(c["cid"], conv_text(c["turns"]), gold=True, source="template_text")
        valid["transcript"].append(tr)
        names["transcript"].append(f"{c['cid']}__gold")
        rec = record_doc(f"rec-{c['cid']}", tr, c)
        valid["record"].append(rec)
        names["record"].append(f"rec-{c['cid']}")

    # Two ASR-like transcripts (hand-made, no model run). fx-pharm-003: ASR heard "50" not "500".
    c3 = by_id["fx-pharm-003"]
    asr_text = conv_text(c3["turns"]).replace("500 mg", "50 mg")
    tr3 = transcript_doc("fx-pharm-003-asr", asr_text, gold=False, source="tts", low_conf=("50",))
    valid["transcript"].append(tr3)
    names["transcript"].append("fx-pharm-003__asr_digit_error")
    c3_asr = copy.deepcopy(c3)
    c3_asr["items"][0] = (
        "medications",
        {**c3["items"][0][1], "dose_value": 50},
        0,
        "ಅಮಾಕ್ಸಿಸಿಲಿನ್ 50 mg ಮಾತ್ರೆ ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ ಐದು ದಿನ",
    )
    rec3 = record_doc("rec-fx-pharm-003-asr", tr3, c3_asr, status="flagged", timed=True)
    valid["record"].append(rec3)
    names["record"].append("rec-fx-pharm-003-asr")
    c4 = by_id["fx-phys-004"]
    tr4 = transcript_doc("fx-phys-004-asr", conv_text(c4["turns"]), gold=False, source="tts")
    valid["transcript"].append(tr4)
    names["transcript"].append("fx-phys-004__asr_clean")

    valid["verdict"] = [
        verdict_doc("rec-fx-asha-001", {"C7": ("n/a", "no ASR confidence (gold transcript)", "/")}),
        verdict_doc(
            "rec-fx-asha-002",
            {
                "C7": ("n/a", "no ASR confidence (gold transcript)", "/"),
                "C4": ("n/a", "no dose stated", "/medications/0"),
            },
        ),
        verdict_doc(
            "rec-fx-pharm-003-asr",
            {
                "C4": (
                    "flag",
                    "dose 50 mg is below the lexicon range for amoxicillin "
                    "(fixture range, UNVERIFIED)",
                    "/medications/0/dose_value",
                ),
                "C7": (
                    "flag",
                    "critical token '50' has confidence 0.41 < dev threshold",
                    "/medications/0/dose_value",
                ),
            },
        ),
        verdict_doc(
            "rec-fx-phys-004",
            {
                "C3": (
                    "flag",
                    "check_error: ValueError in clause splitter (fail-closed)",
                    "/advice/0/negated",
                ),
            },
        ),
        verdict_doc(
            "rec-fx-trap-006",
            {
                "C7": ("n/a", "no ASR confidence (gold transcript)", "/"),
                "C8": ("pass", "trap tokens ಮಾತ್ರ/ಎಲ್ಲಾ/ಇಲ್ಲಿ/ಅಲ್ವಾ are not negation cues", "/"),
            },
        ),
        verdict_doc(
            "rec-fx-nurse-005",
            {
                "C8": (
                    "flag",
                    "two clauses with negation near each other; please confirm",
                    "/symptoms/1/present",
                ),
            },
        ),
    ]
    names["verdict"] = [v["record_id"] for v in valid["verdict"]]
    valid["manifest"] = manifest_rows()
    names["manifest"] = [
        f"row{i + 1}_{r['source']}_{r['split']}" for i, r in enumerate(valid["manifest"])
    ]
    valid["access_case"] = access_cases()
    names["access_case"] = [a["case_id"] for a in valid["access_case"]]
    valid["card"] = cards()
    names["card"] = [c["id"] for c in valid["card"]]
    valid["review_report"] = review_reports()
    names["review_report"] = [r["review_id"] for r in valid["review_report"]]

    invalid = build_invalid(valid)

    for contract in valid:
        d = ROOT / contract
        if d.exists():
            shutil.rmtree(d)
        for name, doc in zip(names[contract], valid[contract], strict=True):
            write(d / "valid" / f"{name}.json", doc)
        lines = [
            f"# Invalid {contract} fixtures",
            "",
            "Each file must be REJECTED by `contracts/validate.py`. Reason per file:",
            "",
            "| file | why it is invalid |",
            "|---|---|",
        ]
        for fname, (doc, why) in sorted(invalid[contract].items()):
            write(d / "invalid" / fname, doc)
            lines.append(f"| {fname} | {why} |")
        (d / "invalid" / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (d / "README.md").write_text(
            f"# fixtures/{contract}\n\nExamples of `{contract}.v1` (schema: "
            f"contracts/schemas/{contract}.v1.schema.json). Generated by "
            "fixtures/build_fixtures.py. FIXTURE ONLY: Kannada not native-validated, "
            "numbers hand-made.\n",
            encoding="utf-8",
        )
        (d / "valid" / "README.md").write_text(
            f"Every file here must PASS `uv run python -m contracts.validate {contract} "
            f"fixtures/{contract}/valid`.\n",
            encoding="utf-8",
        )
    print("fixtures written:", {k: len(v) for k, v in valid.items()})


if __name__ == "__main__":
    main()
