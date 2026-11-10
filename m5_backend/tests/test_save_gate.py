"""F1 + D-80: the server owns the verdict; the save request carries only per-flag resolutions.

SG-1 (audit attempt): a physician sends a hand-made all-pass verdict for a never-approved draft.
It must now be refused. Every test here first failed against the old client-verdict design.
"""

import psycopg
import psycopg.types.json
import pytest
from fastapi.testclient import TestClient

from m5_backend.app.auth import Principal, issue_token
from m5_backend.app.main import create_app
from m5_backend.tests.fakes import base_record, empty_verifier, fake_verifier

pytestmark = pytest.mark.needs_db


def hdr(env, key):
    return {"Authorization": f"Bearer {issue_token(env.settings, env.directory.by_key(key))}"}


@pytest.fixture
def vc(env):
    return TestClient(create_app(env.settings, env.api_db, env.directory, env.audio_dir,
                                 verifier=fake_verifier))  # fmt: skip


def p(env, key):
    u = env.directory.by_key(key)
    return Principal(u.id, u.role, u.facility_id)


def new_record(c, env, marker="", enc="N1", who="N1"):
    r = c.post("/records", headers=hdr(env, who),
               json={"encounter_id": str(env.seed.encounters[enc]), "record": base_record(marker)})  # fmt: skip
    assert r.status_code == 201, r.text
    return r.json()["id"]


def verify(c, env, rid, who="P1"):
    r = c.post(f"/records/{rid}/verify", headers=hdr(env, who), json={})
    assert r.status_code == 201, r.text
    return r.json()


def save(c, env, rid, verdict_id, res, who="P1"):
    return c.post(f"/records/{rid}/save", headers=hdr(env, who),
                  json={"verdict_id": verdict_id, "resolutions": res})  # fmt: skip


def conf(check_id, path):
    return {"check_id": check_id, "field_path": path, "action": "confirmed"}


FLAG = ("C3", "/advice/0/negated")


# ---------------------------------------------------------------- SG-1 and body shape
def test_sg1_hand_made_all_pass_verdict_is_refused(vc, env):
    rid = new_record(vc, env, "FLAGME")
    forged = {"schema_version": "verdict.v1", "record_id": "rec-fx-phys-004",
              "checks": [{"check_id": "C1", "name": "x", "status": "pass", "reason": "ok", "field_path": "/"}],
              "auto_acceptable": True, "verifier_version": "forged"}  # fmt: skip
    r = vc.post(f"/records/{rid}/save", headers=hdr(env, "P1"), json={"verdict": forged})
    assert r.status_code == 422  # client-supplied verdict content is not accepted at all
    r = vc.post(f"/records/{rid}/save", headers=hdr(env, "P1"),
                json={"verdict_id": "00000000-0000-4000-8000-000000000000", "resolutions": [],
                      "verdict": forged})  # fmt: skip
    assert r.status_code == 422
    got = vc.get(f"/records/{rid}", headers=hdr(env, "P1")).json()
    assert got["status"] == "draft" and got["approved_by"] is None


def test_save_without_stored_verdict_is_refused(vc, env):
    rid = new_record(vc, env)
    r = save(vc, env, rid, "00000000-0000-4000-8000-000000000000", [])
    assert r.status_code in (404, 409)
    assert vc.get(f"/records/{rid}", headers=hdr(env, "P1")).json()["status"] == "draft"


@pytest.mark.parametrize("bad", [
    {"verdict_id": "x", "resolutions": []},
    {"resolutions": []},
    {"verdict_id": "00000000-0000-4000-8000-000000000000", "resolutions": [], "resolved_by": "x"},
    {"verdict_id": "00000000-0000-4000-8000-000000000000",
     "resolutions": [{"check_id": "C3", "field_path": "/a", "action": "confirmed", "by": "someone"}]},
    {"verdict_id": "00000000-0000-4000-8000-000000000000",
     "resolutions": [{"check_id": "C3", "field_path": "/a", "action": "overridden"}]},
    {"verdict_id": "00000000-0000-4000-8000-000000000000",
     "resolutions": [{"check_id": "C99", "field_path": "/a", "action": "confirmed"}]},
])  # fmt: skip
def test_save_body_is_strict(vc, env, bad):
    rid = new_record(vc, env)
    assert vc.post(f"/records/{rid}/save", headers=hdr(env, "P1"), json=bad).status_code == 422


# ---------------------------------------------------------------- verify stores the verdict
def test_verify_stores_server_side_verdict_and_audits(vc, env):
    rid = new_record(vc, env, "FLAGME")
    out = verify(vc, env, rid)
    assert out["unresolved"] == [{"check_id": "C3", "field_path": "/advice/0/negated"}]
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        n = c.execute(
            "SELECT count(*) FROM clinic.verdicts WHERE record_id = %s", (rid,)
        ).fetchone()[0]
        a = c.execute("SELECT count(*) FROM clinic.audit_log WHERE action = 'verify' AND row_id = %s",
                      (out["verdict_id"],)).fetchone()[0]  # fmt: skip
    assert n == 1 and a == 1


def test_verify_refuses_empty_verdict_and_is_not_open_to_other_roles(env):
    c = TestClient(
        create_app(env.settings, env.api_db, env.directory, env.audio_dir, verifier=empty_verifier)
    )
    rid = new_record(c, env)
    assert c.post(f"/records/{rid}/verify", headers=hdr(env, "P1"), json={}).status_code == 201
    # an empty verdict is stored but can never be used to save
    with env.owner_conn() as o, o.transaction():
        o.execute("SET LOCAL ROLE maint_role")
        vid = o.execute("SELECT id FROM clinic.verdicts WHERE record_id = %s", (rid,)).fetchone()[0]
    assert save(c, env, rid, str(vid), []).status_code == 409
    for who in ("Ph1", "R1"):
        assert c.post(f"/records/{rid}/verify", headers=hdr(env, who), json={}).status_code == 403
    assert c.post(f"/records/{rid}/verify", headers=hdr(env, "P3"), json={}).status_code == 404
    assert (
        c.post(f"/records/{rid}/verify", headers=hdr(env, "P1"), json={"verdict": {}}).status_code
        == 422
    )


# ---------------------------------------------------------------- resolutions: exact match
def test_flag_needs_exactly_one_matching_confirmed_resolution(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v = verify(vc, env, rid)["verdict_id"]
    assert save(vc, env, rid, v, []).status_code == 409  # missing
    assert save(vc, env, rid, v, [conf("C3", "/advice/9/negated")]).status_code in (
        409,
        422,
    )  # wrong path
    assert save(vc, env, rid, v, [conf("C4", "/advice/0/negated")]).status_code in (
        409,
        422,
    )  # wrong check
    assert save(vc, env, rid, v, [conf(*FLAG), conf(*FLAG)]).status_code == 422  # duplicate
    assert (
        save(vc, env, rid, v, [conf(*FLAG), conf("C5", "/x")]).status_code == 422
    )  # unknown extra
    assert vc.get(f"/records/{rid}", headers=hdr(env, "P1")).json()["status"] == "draft"
    r = save(vc, env, rid, v, [conf(*FLAG)])
    assert r.status_code == 200 and r.json()["status"] == "saved"
    got = vc.get(f"/records/{rid}", headers=hdr(env, "P1")).json()
    assert got["approved_by"] == str(env.seed.users["P1"]) and got["approved_at"]
    with env.owner_conn() as o, o.transaction():
        o.execute("SET LOCAL ROLE maint_role")
        rows = o.execute("SELECT resolved_by, action, check_id, field_path, verdict_id FROM clinic.record_resolutions"
                         " WHERE record_id = %s", (rid,)).fetchall()  # fmt: skip
        acts = o.execute("SELECT count(*) FROM clinic.audit_log WHERE action = 'resolve' AND outcome = 'allow'"
                         " AND user_id = %s", (env.seed.users["P1"],)).fetchone()[0]  # fmt: skip
        rej = o.execute("SELECT count(*) FROM clinic.audit_log WHERE action = 'save_rejected' AND row_id = %s",
                        (rid,)).fetchone()[0]  # fmt: skip
    assert rows == [
        (env.seed.users["P1"], "confirmed", "C3", "/advice/0/negated", __import__("uuid").UUID(v))
    ]
    assert acts >= 1 and rej >= 1
    assert save(vc, env, rid, v, [conf(*FLAG)]).status_code in (404, 409)  # saved is final


def test_clean_verdict_saves_with_no_resolutions(vc, env):
    rid = new_record(vc, env)
    v = verify(vc, env, rid)["verdict_id"]
    r = save(vc, env, rid, v, [])
    assert r.status_code == 200 and r.json()["status"] == "saved"
    # resolutions for a flag that does not exist are refused even on a clean verdict
    rid2 = new_record(vc, env)
    v2 = verify(vc, env, rid2)["verdict_id"]
    assert save(vc, env, rid2, v2, [conf(*FLAG)]).status_code == 422


def test_nurse_asha_cannot_resolve_or_save(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v = verify(vc, env, rid)["verdict_id"]
    for who in ("N1", "A1", "Ph1", "R1"):
        assert save(vc, env, rid, v, [conf(*FLAG)], who=who).status_code == 403, who
    assert vc.get(f"/records/{rid}", headers=hdr(env, "P1")).json()["status"] == "draft"


def test_cross_facility_physician_cannot_save(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v = verify(vc, env, rid)["verdict_id"]
    assert save(vc, env, rid, v, [conf(*FLAG)], who="P3").status_code == 404


def test_verdict_of_another_record_cannot_be_used(vc, env):
    r1 = new_record(vc, env)  # clean
    r2 = new_record(vc, env, "FLAGME")
    v1 = verify(vc, env, r1)["verdict_id"]
    verify(vc, env, r2)
    assert save(vc, env, r2, v1, []).status_code in (404, 409)
    assert vc.get(f"/records/{r2}", headers=hdr(env, "P1")).json()["status"] == "draft"


def test_stale_verdict_after_record_changed_is_refused(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v = verify(vc, env, rid)["verdict_id"]
    r = vc.patch(
        f"/records/{rid}", headers=hdr(env, "N1"), json={"record": base_record("FLAGME changed")}
    )
    assert r.status_code == 200
    assert save(vc, env, rid, v, [conf(*FLAG)]).status_code == 409  # hash changed after the verdict


# ---------------------------------------------------------------- "edited" = re-verified
def test_edited_requires_reverification(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v1 = verify(vc, env, rid)["verdict_id"]
    edit = {"check_id": "C3", "field_path": "/advice/0/negated", "action": "edited"}
    # claims "edited" but the record never changed
    assert save(vc, env, rid, v1, [edit]).status_code == 409
    # record edited (flag removed) but NOT re-verified: no verdict for the new content
    assert (
        vc.patch(
            f"/records/{rid}", headers=hdr(env, "P1"), json={"record": base_record()}
        ).status_code
        == 200
    )
    assert save(vc, env, rid, v1, [edit]).status_code == 409
    assert vc.get(f"/records/{rid}", headers=hdr(env, "P1")).json()["status"] == "draft"
    # re-verified, new verdict clean -> saved
    verify(vc, env, rid)
    r = save(vc, env, rid, v1, [edit])
    assert r.status_code == 200 and r.json()["status"] == "saved"
    with env.owner_conn() as o, o.transaction():
        o.execute("SET LOCAL ROLE maint_role")
        act = o.execute(
            "SELECT action FROM clinic.record_resolutions WHERE record_id = %s", (rid,)
        ).fetchall()
    assert act == [("edited",)]


def test_edited_but_new_verdict_still_flags_is_refused(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v1 = verify(vc, env, rid)["verdict_id"]
    edit = {"check_id": "C3", "field_path": "/advice/0/negated", "action": "edited"}
    # edit introduces a NEW flag (C4) and keeps C3
    assert vc.patch(f"/records/{rid}", headers=hdr(env, "P1"),
                    json={"record": base_record("FLAGME FLAGDOSE")}).status_code == 200  # fmt: skip
    verify(vc, env, rid)
    assert save(vc, env, rid, v1, [edit]).status_code == 409
    # only the NEW flag remains: still refused because the C3 flag is gone but C4 is unresolved
    assert vc.patch(f"/records/{rid}", headers=hdr(env, "P1"),
                    json={"record": base_record("FLAGDOSE")}).status_code == 200  # fmt: skip
    verify(vc, env, rid)
    assert save(vc, env, rid, v1, [edit]).status_code == 409
    assert vc.get(f"/records/{rid}", headers=hdr(env, "P1")).json()["status"] == "draft"


# ---------------------------------------------------------------- DB-level backstop
def test_db_refuses_saved_without_gate_even_for_physician_sql(env):
    ids = env.seed
    pr = p(env, "P1")
    approve = "UPDATE clinic.records SET status = 'saved', approved_by = %s, approved_at = now() WHERE id = %s"
    # draft record P2 (same facility), never verified
    with pytest.raises(psycopg.errors.CheckViolation, match="saved gate"):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute(approve, (pr.user_id, ids.records["P2"]))
    # direct INSERT of a saved record is refused too
    with pytest.raises(psycopg.errors.CheckViolation, match="saved gate"):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute("INSERT INTO clinic.records (encounter_id, json, status, approved_by, approved_at)"
                        " VALUES (%s, %s, 'saved', %s, now())",
                        (ids.encounters["P1"], psycopg.types.json.Jsonb(base_record()), pr.user_id))  # fmt: skip


def test_db_refuses_saved_with_unresolved_flag_and_wrong_resolver(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v = verify(vc, env, rid)["verdict_id"]
    pr = p(env, "P1")
    approve = "UPDATE clinic.records SET status = 'saved', approved_by = %s, approved_at = now() WHERE id = %s"
    with pytest.raises(psycopg.errors.CheckViolation, match="unresolved"):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute(approve, (pr.user_id, rid))
    # a resolution written in somebody else's name is refused by RLS
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute("INSERT INTO clinic.record_resolutions (record_id, verdict_id, record_hash, facility_id,"
                        " check_id, field_path, action, resolved_by)"
                        " SELECT r.id, %s, app.record_hash(r.json), %s, 'C3', '/advice/0/negated', 'confirmed', %s"
                        " FROM clinic.records r WHERE r.id = %s",
                        (v, pr.facility_id, env.seed.users["P2"], rid))  # fmt: skip


def test_verdicts_and_resolutions_are_append_only_and_role_scoped(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v = verify(vc, env, rid)["verdict_id"]
    assert save(vc, env, rid, v, [conf(*FLAG)]).status_code == 200
    for tbl in ("clinic.verdicts", "clinic.record_resolutions"):
        for stmt in (
            f"UPDATE {tbl} SET record_id = record_id",
            f"DELETE FROM {tbl}",
            f"TRUNCATE {tbl}",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with env.api_db.request_tx(p(env, "P1"), commit=False) as cur:
                    cur.execute(stmt)
            # even a superuser is stopped: by the trigger, or (TRUNCATE of a referenced table) by the FK
            with (
                env.bootstrap_conn() as b,
                pytest.raises((psycopg.errors.RaiseException, psycopg.errors.FeatureNotSupported)),
            ):
                b.execute(stmt)
    for role in ("Ph1", "R1"):
        for tbl in ("clinic.verdicts", "clinic.record_resolutions"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with env.api_db.request_tx(p(env, role), commit=False) as cur:
                    cur.execute(f"SELECT 1 FROM {tbl} LIMIT 1")
    # nurse cannot read resolutions, and an other-facility physician sees no verdicts
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with env.api_db.request_tx(p(env, "N1"), commit=False) as cur:
            cur.execute("SELECT 1 FROM clinic.record_resolutions")
    with env.api_db.request_tx(p(env, "P3"), commit=False) as cur:
        assert (
            cur.execute(
                "SELECT count(*) FROM clinic.verdicts WHERE record_id = %s", (rid,)
            ).fetchone()[0]
            == 0
        )
        assert cur.execute("SELECT count(*) FROM clinic.record_resolutions").fetchone()[0] == 0


def test_verdict_insert_must_match_record_and_author(env):
    pr = p(env, "P1")
    rid = env.seed.records["P1"]
    ok = ("INSERT INTO clinic.verdicts (record_id, record_hash, facility_id, verdict, created_by)"
          " VALUES (%s, 'ignored', %s, %s::jsonb, %s)")  # fmt: skip
    good = '{"record_id": "rec-seed-006", "checks": []}'
    # a verdict about a different record_id string is refused by the binding trigger
    with pytest.raises(psycopg.errors.RaiseException, match="does not match"):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute(ok, (rid, pr.facility_id, good.replace("006", "999"), pr.user_id))
    # created_by must be the caller
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute(ok, (rid, pr.facility_id, good, env.seed.users["P2"]))
