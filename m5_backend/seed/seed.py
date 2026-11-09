"""Synthetic seed data (all fake; names start with SYNTHETIC-). Loaded through maint_role.

Layout (facility F1 = actor facility, F2 = other facility):
  households  A1 (F1, ASHA A1)  A2 (F1, ASHA A2)  A3 (F2, ASHA A3)  none (F1, unassigned)
  patients    one per household + one more per household WITHOUT a consent row ("<key>b")
  encounters  asha/nurse/physician encounters for A1/A2/A3 chains + nurse/physician for 'none'
  records     one draft record per encounter (record.v1 fixtures as JSON) + one SAVED record
  orders      ready_to_dispense for P1/P2/P3/none chains + one DRAFT order for the A1 chain
  consents    research_ok: A1, A2, A3 true; none false; "<key>b" patients have no consent row
"""

from __future__ import annotations

import json
import secrets
import struct
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from m5_backend.app.directory import Directory, load_directory

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORD_FIXTURES = REPO_ROOT / "fixtures" / "record" / "valid"
IST = timezone(timedelta(hours=5, minutes=30))
FAKE_NAMES = [
    "Kaveri",
    "Tunga",
    "Sharavati",
    "Hemavati",
    "Netravati",
    "Kabini",
    "Bhadra",
    "Malaprabha",
]


@dataclass
class SeedIds:
    facilities: dict[str, uuid.UUID] = field(default_factory=dict)
    users: dict[str, uuid.UUID] = field(default_factory=dict)
    households: dict[str, uuid.UUID] = field(default_factory=dict)
    patients: dict[str, uuid.UUID] = field(default_factory=dict)
    encounters: dict[str, uuid.UUID] = field(default_factory=dict)
    records: dict[str, uuid.UUID] = field(default_factory=dict)
    orders: dict[str, uuid.UUID] = field(default_factory=dict)
    audit: dict[str, uuid.UUID] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    record_json: dict[str, dict] = field(default_factory=dict)
    encounter_times: dict[str, datetime] = field(default_factory=dict)


def _wav_silence(seconds: float = 0.1, rate: int = 8000) -> bytes:
    n = int(seconds * rate)
    data = b"\x00\x00" * n
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
    hdr += (
        struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(data))
    )
    return hdr + data


def _fixture_records() -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(RECORD_FIXTURES.glob("*.json"))
    ]


def seed(
    conn: psycopg.Connection, audio_dir: Path | None = None, directory: Directory | None = None
) -> SeedIds:
    """`conn` must be an owner_role connection (autocommit). Everything runs as maint_role."""
    d = directory or load_directory()
    ids = SeedIds()
    fixtures = _fixture_records()
    with conn.transaction():
        cur = conn.cursor()
        cur.execute("SET LOCAL ROLE maint_role")
        cur.execute("SELECT set_config('app.role', 'maint', true)")
        for k, f in d.facilities.items():
            fid = uuid.UUID(f["id"])
            cur.execute(
                "INSERT INTO clinic.facilities (id, name) VALUES (%s, %s)", (fid, f["name"])
            )
            ids.facilities[k] = fid
        for u in d.users:
            cur.execute(
                "INSERT INTO clinic.users (id, role, facility_id, display_name) VALUES (%s, %s, %s, %s)",
                (u.id, u.role, u.facility_id, u.display_name),
            )
            ids.users[u.key] = u.id
        F1, F2 = ids.facilities["F1"], ids.facilities["F2"]
        U = ids.users

        hh = {"A1": (F1, U["A1"]), "A2": (F1, U["A2"]), "A3": (F2, U["A3"]), "none": (F1, None)}
        for k, (fac, asha) in hh.items():
            ids.households[k] = cur.execute(
                "INSERT INTO clinic.households (facility_id, assigned_asha_id) VALUES (%s, %s) RETURNING id",
                (fac, asha),
            ).fetchone()[0]

        bands = ["25-34", "15-24", "35-44", "45-59", "0-4", "60+", "5-14", "25-34"]
        for i, key in enumerate(["A1", "A2", "A3", "none", "A1b", "A2b", "A3b", "noneb"]):
            hk = key.rstrip("b") if key != "noneb" else "none"
            fac = hh[hk][0]
            name = f"SYNTHETIC-{FAKE_NAMES[i]}-{secrets.token_hex(3)}"
            ids.names[key] = name
            ids.patients[key] = cur.execute(
                "INSERT INTO clinic.patients (household_id, facility_id, name_synthetic, age_band, sex)"
                " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (ids.households[hk], fac, name, bands[i], "F" if i % 3 else "M"),
            ).fetchone()[0]

        enc = {
            "A1": ("A1", "A1", "asha_household_visit"),
            "A2": ("A2", "A2", "asha_household_visit"),
            "A3": ("A3", "A3", "asha_household_visit"),
            "N1": ("A1", "N1", "nurse_consult"),
            "N2": ("A2", "N2", "nurse_consult"),
            "N3": ("A3", "N3", "nurse_consult"),
            "P1": ("A1", "P1", "physician_consult"),
            "P2": ("A2", "P2", "physician_consult"),
            "P3": ("A3", "P3", "physician_consult"),
            "none": ("none", "N2", "nurse_consult"),
            "none_p": ("none", "P2", "physician_consult"),
        }
        base_t = datetime(2026, 10, 3, 9, 30, tzinfo=IST)
        for i, (ek, (pk, author, etype)) in enumerate(enc.items()):
            fac = hh[pk][0]
            t = base_t + timedelta(days=3 * i, hours=i)
            ids.encounter_times[ek] = t
            ids.encounters[ek] = cur.execute(
                "INSERT INTO clinic.encounters (patient_id, author_id, facility_id, encounter_type, created_at)"
                " VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (ids.patients[pk], U[author], fac, etype, t),
            ).fetchone()[0]

        for i, ek in enumerate(enc):
            rec = json.loads(json.dumps(fixtures[i % len(fixtures)]))
            rec["record_id"] = f"rec-seed-{i:03d}"
            rec["patient_ref"] = f"pt-seed-{i:03d}"
            rec["status"] = "draft"
            ids.record_json[ek] = rec
            ids.records[ek] = cur.execute(
                "INSERT INTO clinic.records (encounter_id, json, status) VALUES (%s, %s, 'draft') RETURNING id",
                (ids.encounters[ek], Jsonb(rec)),
            ).fetchone()[0]
        saved = json.loads(json.dumps(fixtures[0]))
        saved["record_id"], saved["patient_ref"], saved["status"] = (
            "rec-seed-saved",
            "pt-seed-saved",
            "saved",
        )
        ids.record_json["P1_saved"] = saved
        ids.records["P1_saved"] = cur.execute(
            "INSERT INTO clinic.records (encounter_id, json, status, approved_by, approved_at)"
            " VALUES (%s, %s, 'saved', %s, %s) RETURNING id",
            (ids.encounters["P1"], Jsonb(saved), U["P1"], base_t + timedelta(days=1)),
        ).fetchone()[0]

        orders = {
            "P1": ("P1", "A1", "ready_to_dispense", "paracetamol"),
            "P1_draft": ("P1", "A1", "draft", "amoxicillin"),
            "P2": ("P2", "A2", "ready_to_dispense", "azithromycin"),
            "P3": ("P3", "A3", "ready_to_dispense", "paracetamol"),
            "none": ("none_p", "none", "ready_to_dispense", "cefixime"),
        }
        for ok, (ek, pk, status, drug) in orders.items():
            ids.orders[ok] = cur.execute(
                "INSERT INTO clinic.medication_orders (encounter_id, patient_id, facility_id, drug, dose_value,"
                " dose_unit, frequency_per_day, duration_days, status)"
                " VALUES (%s, %s, %s, %s, 500, 'mg', 3, 5, %s) RETURNING id",
                (ids.encounters[ek], ids.patients[pk], hh[pk][0], drug, status),
            ).fetchone()[0]

        for pk, ok_ in (("A1", True), ("A2", True), ("A3", True), ("none", False)):
            cur.execute(
                "INSERT INTO clinic.consents (patient_id, research_ok) VALUES (%s, %s)",
                (ids.patients[pk], ok_),
            )

        # one seeded audit row per directory user + one without a user (targets for the matrix)
        for key in [*ids.users, None]:
            cur.execute(
                "SELECT set_config('app.user_id', %s, true)", ("" if key is None else str(U[key]),)
            )
            cur.execute("SELECT app.audit_write('seed', 'audit_log', NULL, 'allow')")
            ids.audit[key or "none"] = cur.execute(
                "SELECT id FROM clinic.audit_log ORDER BY at DESC, id LIMIT 1"
            ).fetchone()[0]
        cur.execute("SELECT set_config('app.user_id', '', true)")

    if audio_dir is not None:
        audio_dir = Path(audio_dir)
        audio_dir.mkdir(parents=True, exist_ok=True)
        wav = _wav_silence()
        for eid in ids.encounters.values():
            (audio_dir / f"{eid}.wav").write_bytes(wav)
    return ids
