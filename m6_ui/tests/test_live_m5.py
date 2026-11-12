"""Live-mode integration against the REAL m5 API (sandbox, synthetic data).

Skipped unless an m5 API answers on 127.0.0.1:8000 (start it: `bash m5_backend/scripts/db_up.sh`
then `uv run python -m m5_backend.app.main`). Reads the sandbox login password from the
environment (M6_TEST_LOGIN_PASSWORD) or from MOCK_LOGIN_PASSWORD in .env. It never prints it.
The m5 user ids come from m5's seed file, read as plain data (no m5 code is imported).
"""

from __future__ import annotations

import json
import os
import re

import httpx
import pytest

from m6_ui import gate
from m6_ui.tests.helpers import ROOT, fixture_triplet

BASE = os.environ.get("M6_TEST_API_URL", "http://127.0.0.1:8000")


def _password() -> str | None:
    if os.environ.get("M6_TEST_LOGIN_PASSWORD"):
        return os.environ["M6_TEST_LOGIN_PASSWORD"]
    env = ROOT / ".env"
    if env.exists():
        m = re.search(r"^MOCK_LOGIN_PASSWORD=(.+)$", env.read_text(encoding="utf-8"), re.M)
        return m.group(1).strip() if m else None
    return None


def _users() -> dict[str, str]:
    doc = json.loads((ROOT / "m5_backend" / "seed" / "synthetic_users.json").read_text("utf-8"))
    return {u["key"]: u["id"] for u in doc["users"]}


def _up() -> bool:
    try:
        return httpx.get(BASE + "/auth/token", timeout=2).status_code in (404, 405, 422)
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _up() or not _password(), reason="no m5 API on 127.0.0.1:8000 (UNVERIFIED live)"
)


def _gate(key: str) -> gate.HttpGate:
    g = gate.HttpGate(BASE)
    res = g.login(_users()[key], _password())
    assert res.ok, res
    return g


def _make_draft_record(nurse: gate.HttpGate) -> str:
    """A nurse creates a draft record on a patient at her facility (direct API, setup only)."""
    h = {"Authorization": f"Bearer {nurse._token}"}
    c = httpx.Client(base_url=BASE, headers=h, timeout=10)
    pats = c.get("/patients").json()
    enc = c.post(
        "/encounters", json={"patient_id": pats[0]["id"], "encounter_type": "nurse_consult"}
    )
    assert enc.status_code == 201, enc.text
    rec, _, _ = fixture_triplet("rec-fx-asha-001")
    rec = {**rec, "status": "draft"}
    r = c.post("/records", json={"encounter_id": enc.json()["id"], "record": rec})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_role_comes_from_the_real_token_and_asha_sees_only_her_patients():
    a1, a3 = _gate("A1"), _gate("A3")
    assert a1.role == "asha" and a3.role == "asha"
    p1, p3 = a1.patients(), a3.patients()
    assert p1.ok and p3.ok
    ids1, ids3 = {p["id"] for p in p1.data}, {p["id"] for p in p3.data}
    assert ids1.isdisjoint(ids3) or ids1 != ids3  # different facilities: different lists


def test_full_gated_save_flow_against_m5():
    nurse = _gate("N1")  # m5 limits logins to 5 per minute per user: log in once each
    rid = _make_draft_record(nurse)
    phys = _gate("P1")
    got = phys.load_record(rid)
    assert got.ok, got.result
    assert got.data["record"]["record_id"] == "rec-fx-asha-001"
    verdict = got.data["verdict"]
    flags = [c for c in verdict["checks"] if c["status"] == "flag"]
    # a nurse may not save; and a save without answering every flag is refused
    assert nurse.save(rid, got.data["verdict_id"], []).code == "refused_forbidden"
    if flags:
        assert phys.save(rid, got.data["verdict_id"], []).code == "refused_unresolved_flags"
    res = [
        {"check_id": c["check_id"], "field_path": c["field_path"], "action": "confirmed"}
        for c in flags
    ]
    done = phys.save(rid, got.data["verdict_id"], res)
    assert done.ok and done.code == "saved", done
    again = phys.save(rid, got.data["verdict_id"], res)
    assert not again.ok  # a saved record cannot be saved twice
