"""Research export job: base tables -> schema `research` (de-identified, consent-filtered).

- pseudonym = first 20 hex chars (80 bits) of HMAC-SHA256(RESEARCH_PSEUDONYM_HMAC_KEY, patient_id)
- dates coarsened to month ("YYYY-MM"); no names, no ids, no free text (advice, follow-up and
  evidence spans are dropped); structured strings must be in a closed allowlist (fail closed)
- only patients with consents.research_ok = true AT EXPORT TIME; every export is a full
  refresh. A consent withdrawal ALSO deletes that patient's rows at once (DB trigger, F4; it uses
  research.pseudonym_map, which only the export job and the trigger can read).
- small-cell suppression (F3): a cell = (age_band, sex, month, encounter_type). Cells with fewer
  than K_MIN (5) distinct patients are DROPPED (not generalised). This is a basic safeguard, not
  proof of anonymity: symptoms/medications are not part of the cell, and the pseudonym links one
  patient's visits.

Run: uv run python -m m5_backend.app.export   (uses owner_role credentials -> SET LOCAL ROLE maint_role)
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import uuid
from datetime import datetime
from functools import cache
from typing import Any

from .config import REPO_ROOT, Settings

PSEUDONYM_HEX = 20
K_MIN = 5
SYMPTOM_VOCAB = frozenset(
    {
        "fever", "cough", "cold", "headache", "vomiting", "nausea", "diarrhoea", "diarrhea",
        "rash", "breathlessness", "abdominal pain", "sore throat", "body ache", "fatigue",
        "dizziness", "chest pain", "swelling", "bleeding", "loss of appetite", "weakness",
    }
)  # fmt: skip
UNIT_VOCAB = frozenset(
    {"mg", "g", "mcg", "ml", "tablet", "capsule", "sachet", "drop", "teaspoon", "IU"}
)
LEXICON_FILES = (
    REPO_ROOT / "data" / "lexicon" / "drugs.csv",
    REPO_ROOT / "fixtures" / "lexicon" / "drugs_fixture.csv",
)


@cache
def drug_vocab() -> frozenset[str]:
    names: set[str] = set()
    for p in LEXICON_FILES:
        if p.is_file():
            with p.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    g = (row.get("generic_en") or "").strip().lower()
                    if g:
                        names.add(g)
    return frozenset(names)


def pseudonym(key: bytes, patient_id: uuid.UUID) -> str:
    if len(key) < 16:
        raise ValueError("HMAC key too short")
    mac = hmac.new(key, str(patient_id).encode("ascii"), hashlib.sha256).hexdigest()
    return mac[:PSEUDONYM_HEX]


def hmac_key_bytes(settings: Settings) -> bytes:
    k = settings.hmac_key
    if not k or k.startswith("REPLACE_ME") or len(k) < 32:
        raise RuntimeError("RESEARCH_PSEUDONYM_HMAC_KEY missing or too short")
    return k.encode("utf-8")


def month_of(ts: datetime) -> str:
    return f"{ts.year:04d}-{ts.month:02d}"


def suppress_small_cells(rows: list[tuple], k_min: int = K_MIN) -> list[tuple]:
    """Keep only rows whose cell (age_band, sex, month, encounter_type) has >= k_min DISTINCT
    patients. Row layout = EXPORT_SELECT: (patient_id, age_band, sex, type, created_at, json, status)."""
    if k_min < 1:
        raise ValueError("k_min must be >= 1")
    members: dict[tuple, set] = {}
    for pid, band, sex, etype, created, _j, _s in rows:
        members.setdefault((band, sex, month_of(created), etype), set()).add(pid)
    return [r for r in rows if len(members[(r[1], r[2], month_of(r[4]), r[3])]) >= k_min]


def _num(v: Any) -> float | int | None:
    if isinstance(v, bool) or not isinstance(v, int | float):
        return None
    return v


def deidentify_record(rec: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only allowlisted structured values. Everything else is dropped."""
    rec = rec or {}
    present, absent, meds = [], [], []
    for s in rec.get("symptoms") or []:
        name = s.get("name") if isinstance(s, dict) else None
        if isinstance(name, str) and name in SYMPTOM_VOCAB and isinstance(s.get("present"), bool):
            (present if s["present"] else absent).append(name)
    vocab = drug_vocab()
    for m in rec.get("medications") or []:
        if not isinstance(m, dict) or m.get("drug") not in vocab:
            continue
        unit = m.get("dose_unit")
        meds.append(
            {
                "drug": m["drug"],
                "dose_value": _num(m.get("dose_value")),
                "dose_unit": unit if unit in UNIT_VOCAB else None,
                "frequency_per_day": _num(m.get("frequency_per_day")),
                "duration_days": _num(m.get("duration_days")),
                "negated": m.get("negated") if isinstance(m.get("negated"), bool) else None,
            }
        )
    return {
        "symptoms_present": sorted(present),
        "symptoms_absent": sorted(absent),
        "medications": meds,
    }


EXPORT_SELECT = """
SELECT p.id, p.age_band, p.sex, e.encounter_type, e.created_at, r.json, r.status
FROM clinic.patients p
JOIN clinic.consents c ON c.patient_id = p.id AND c.research_ok
JOIN clinic.encounters e ON e.patient_id = p.id
LEFT JOIN clinic.records r ON r.encounter_id = e.id
"""

EXPORT_INSERT = """
INSERT INTO research.encounters_deid
  (pseudonym, age_band, sex, encounter_type, encounter_month, record_status,
   symptoms_present, symptoms_absent, medications)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def run_export(settings: Settings, dbname: str | None = None, k_min: int = K_MIN) -> int:
    """Full refresh of research.encounters_deid. Returns the number of exported rows."""
    import psycopg
    from psycopg.types.json import Jsonb

    key = hmac_key_bytes(settings)
    with psycopg.connect(settings.conninfo("owner", dbname), autocommit=True) as conn:
        with conn.transaction():
            cur = conn.cursor()
            cur.execute("SET LOCAL ROLE maint_role")
            cur.execute("DELETE FROM research.encounters_deid")
            cur.execute("DELETE FROM research.pseudonym_map")
            rows = suppress_small_cells(cur.execute(EXPORT_SELECT).fetchall(), k_min)
            n = 0
            mapped: set = set()
            for pid, age_band, sex, etype, created, rec_json, status in rows:
                d = deidentify_record(rec_json)
                if pid not in mapped:
                    mapped.add(pid)
                    cur.execute(
                        "INSERT INTO research.pseudonym_map (patient_id, pseudonym) VALUES (%s, %s)",
                        (pid, pseudonym(key, pid)),
                    )
                cur.execute(
                    EXPORT_INSERT,
                    (
                        pseudonym(key, pid),
                        age_band,
                        sex,
                        etype,
                        month_of(created),
                        status,
                        d["symptoms_present"],
                        d["symptoms_absent"],
                        Jsonb(d["medications"]),
                    ),
                )
                n += 1
            cur.execute("SELECT app.audit_write('export', 'research_export', NULL, 'allow')")
    return n


def main() -> int:
    from .config import load_settings

    n = run_export(load_settings())
    out = {"exported_rows": n}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
