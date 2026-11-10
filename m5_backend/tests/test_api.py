"""FastAPI end-to-end against the real database: auth, generic errors, saved gate, pharmacist, audio."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from m5_backend.app.auth import issue_token
from m5_backend.app.main import create_app

pytestmark = pytest.mark.needs_db
VERDICTS = Path(__file__).resolve().parents[2] / "fixtures" / "verdict" / "valid"


def hdr(env, key):
    return {"Authorization": f"Bearer {issue_token(env.settings, env.directory.by_key(key))}"}


def audit_rows(env, action):
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        return c.execute(
            "SELECT user_id, app_role, table_name, row_id, outcome FROM clinic.audit_log WHERE action = %s"
            " ORDER BY at", (action,)).fetchall()  # fmt: skip


def test_login_issues_token_and_is_rate_limited(env):
    client = TestClient(create_app(env.settings, env.api_db, env.directory, env.audio_dir))
    uid = str(env.directory.by_key("N1").id)
    r = client.post(
        "/auth/token", json={"username": uid, "password": env.settings.mock_login_password}
    )
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    tok = r.json()["access_token"]
    assert (
        client.get(
            f"/patients/{env.seed.patients['A1']}", headers={"Authorization": f"Bearer {tok}"}
        ).status_code
        == 200
    )
    codes = [
        client.post("/auth/token", json={"username": uid, "password": "wrong"}).status_code
        for _ in range(6)
    ]
    assert codes[:4] == [401] * 4 and codes[-1] == 429


def test_no_token_and_generic_errors(client, env):
    r = client.get(f"/patients/{env.seed.patients['A1']}")
    assert r.status_code == 401 and r.json() == {"error": "unauthorized"}
    r = client.get("/patients/' OR 1=1 --", headers=hdr(env, "N1"))
    assert r.status_code == 422 and r.json() == {"error": "invalid request"}
    body = client.post("/encounters", headers=hdr(env, "N1"),
                       json={"patient_id": "x", "encounter_type": "'; DROP TABLE x; --"}).text  # fmt: skip
    assert "DROP" not in body and "Traceback" not in body and "psycopg" not in body


def test_role_comes_only_from_token(client, env):
    # a nurse claiming physician powers through headers/body cannot create an order
    r = client.post("/medication-orders", headers={**hdr(env, "N1"), "X-Role": "physician"},
                    json={"encounter_id": str(env.seed.encounters["N1"]), "drug": "paracetamol", "dose_value": 500,
                          "dose_unit": "mg", "frequency_per_day": 3, "duration_days": 3})  # fmt: skip
    assert r.status_code == 403


def test_hidden_rows_look_like_not_found(client, env):
    for key in ("A2", "A3", "none"):
        assert (
            client.get(f"/patients/{env.seed.patients[key]}", headers=hdr(env, "A1")).status_code
            == 404
        )
    assert (
        client.get(f"/patients/{env.seed.patients['A3']}", headers=hdr(env, "N1")).status_code
        == 404
    )


def test_asha_creates_household_and_patient_in_her_scope(client, env):
    r = client.post("/households", headers=hdr(env, "A1"), json={})
    assert r.status_code == 201
    hh = r.json()["id"]
    r = client.post("/patients", headers=hdr(env, "A1"),
                    json={"household_id": hh, "name_synthetic": "SYNTHETIC-Api-Test", "age_band": "25-34", "sex": "F"})  # fmt: skip
    assert r.status_code == 201
    r = client.post("/patients", headers=hdr(env, "A1"),
                    json={"household_id": str(env.seed.households["A2"]), "name_synthetic": "SYNTHETIC-Api-Test",
                          "age_band": "25-34", "sex": "F"})  # fmt: skip
    assert r.status_code == 403


def _new_record(client, env, nurse="N1", enc="N1", fixture="rec-fx-phys-004"):
    rec = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "record"
            / "valid"
            / f"{fixture}.json"
        ).read_text(encoding="utf-8")
    )
    r = client.post(
        "/records",
        headers=hdr(env, nurse),
        json={"encounter_id": str(env.seed.encounters[enc]), "record": rec},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"], rec


# The saved-record gate (server-stored verdicts + per-flag resolutions) is tested in test_save_gate.py.


def test_pharmacist_active_patient_flow_is_checked_and_audited(client, env):
    ids, h = env.seed, hdr(env, "Ph1")
    assert client.get("/pharmacist/orders", headers=h).status_code == 404  # nothing active yet
    r = client.post(
        "/pharmacist/active-patient", headers=h, json={"patient_id": str(ids.patients["A1b"])}
    )
    assert r.status_code == 404  # no ready order for that patient
    r = client.post(
        "/pharmacist/active-patient", headers=h, json={"patient_id": str(ids.patients["A3"])}
    )
    assert r.status_code == 404  # other facility
    r = client.post(
        "/pharmacist/active-patient", headers=h, json={"patient_id": str(ids.patients["A1"])}
    )
    assert r.status_code == 200
    orders = r.json()["orders"]
    assert [o["order_id"] for o in orders] == [str(ids.orders["P1"])]  # ready only, not the draft
    assert set(orders[0]) == {"order_id", "patient_ref", "drug", "dose_value", "dose_unit",
                              "frequency_per_day", "duration_days", "status"}  # fmt: skip
    assert client.get("/pharmacist/orders", headers=h).json()[0]["order_id"] == str(
        ids.orders["P1"]
    )
    rows = audit_rows(env, "set_active_patient")
    pid = env.directory.by_key("Ph1").id
    outcomes = {(str(r[3]), r[4]) for r in rows if r[0] == pid}
    assert (str(ids.patients["A1"]), "allow") in outcomes
    assert (str(ids.patients["A1b"]), "deny") in outcomes and (
        str(ids.patients["A3"]),
        "deny",
    ) in outcomes
    # base table still closed to the pharmacist
    assert client.get(f"/medication-orders/{ids.orders['P1']}", headers=h).status_code == 403


def test_audio_served_only_after_encounter_authorisation(client, env):
    e = env.seed.encounters
    r = client.get(f"/encounters/{e['N1']}/audio", headers=hdr(env, "N1"))
    assert r.status_code == 200 and r.content[:4] == b"RIFF"
    assert client.get(f"/encounters/{e['N3']}/audio", headers=hdr(env, "N1")).status_code == 404
    assert client.get(f"/encounters/{e['A2']}/audio", headers=hdr(env, "A1")).status_code == 404
    assert client.get(f"/encounters/{e['A1']}/audio", headers=hdr(env, "Ph1")).status_code == 403
    assert client.get("/encounters/..%2F..%2F.env/audio", headers=hdr(env, "N1")).status_code in (
        404,
        422,
    )


def test_server_binds_localhost_only(env):
    assert env.settings.api_host == "127.0.0.1"
