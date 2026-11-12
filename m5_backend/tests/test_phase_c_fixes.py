"""Phase C fix pass: (a) verdicts tied to content, (b) read-only reopen, (c) verifier gets the
DB encounter + transcript, (d) trigger gates every final status."""

from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from m5_backend.app.auth import issue_token
from m5_backend.app.db import Principal
from m5_backend.app.main import create_app
from m5_backend.tests.fakes import base_record, fake_verifier

pytestmark = pytest.mark.needs_db
FLAG = ("C3", "/advice/0/negated")


def hdr(env, key):
    return {"Authorization": f"Bearer {issue_token(env.settings, env.directory.by_key(key))}"}


def princ(env, key):
    u = env.directory.by_key(key)
    return Principal(u.id, u.role, u.facility_id)


@pytest.fixture
def vc(env):
    return TestClient(
        create_app(env.settings, env.api_db, env.directory, env.audio_dir, verifier=fake_verifier)
    )


def new_record(c, env, marker="", enc="N1", who="N1"):
    r = c.post("/records", headers=hdr(env, who),
               json={"encounter_id": str(env.seed.encounters[enc]), "record": base_record(marker)})  # fmt: skip
    assert r.status_code == 201, r.text
    return r.json()["id"]


def verify(c, env, rid, who="P1"):
    r = c.post(f"/records/{rid}/verify", headers=hdr(env, who), json={})
    assert r.status_code == 201, r.text
    return r.json()


def save(c, env, rid, vid, res, who="P1"):
    return c.post(f"/records/{rid}/save", headers=hdr(env, who),
                  json={"verdict_id": vid, "resolutions": res})  # fmt: skip


def conf(check_id, path):
    return {"check_id": check_id, "field_path": path, "action": "confirmed"}


# ------------------------------------------------------------------ (a) verdict tied to content
def test_a_second_verify_of_same_content_does_not_invalidate_first_verdict(vc, env):
    rid = new_record(vc, env, "FLAGME")
    first = verify(vc, env, rid, "P1")
    second = verify(vc, env, rid, "P2")  # another physician, same unchanged content
    assert second["verdict_id"] == first["verdict_id"]
    r = save(vc, env, rid, first["verdict_id"], [conf(*FLAG)], "P1")
    assert r.status_code == 200 and r.json()["status"] == "saved", r.text


def test_a_verdict_for_old_content_stays_refused_after_edit(vc, env):
    rid = new_record(vc, env, "FLAGME")
    old = verify(vc, env, rid)["verdict_id"]
    assert vc.patch(f"/records/{rid}", headers=hdr(env, "P1"),
                    json={"record": base_record("FLAGME changed")}).status_code == 200  # fmt: skip
    verify(vc, env, rid)  # new content has its own verdict
    assert save(vc, env, rid, old, [conf(*FLAG)]).status_code == 409
    # content goes back to the original text: the ORIGINAL verdict is valid again (same hash)
    assert vc.patch(f"/records/{rid}", headers=hdr(env, "P1"),
                    json={"record": base_record("FLAGME")}).status_code == 200  # fmt: skip
    assert save(vc, env, rid, old, [conf(*FLAG)]).status_code == 200


def test_a_db_allows_one_verdict_per_record_content(vc, env):
    rid = new_record(vc, env, "FLAGME")
    verify(vc, env, rid)
    pr = princ(env, "P1")
    with pytest.raises(psycopg.errors.UniqueViolation):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute(
                "INSERT INTO clinic.verdicts (record_id, record_hash, facility_id, verdict, created_by)"
                " SELECT record_id, 'x', facility_id, verdict, %s FROM clinic.verdicts WHERE record_id = %s",
                (pr.user_id, rid),
            )


# ------------------------------------------------------------------ (b) reopen a saved record
def test_b_review_of_saved_record_is_read_only_with_verdict_and_resolutions(vc, env):
    rid = new_record(vc, env, "FLAGME")
    v = verify(vc, env, rid)
    assert save(vc, env, rid, v["verdict_id"], [conf(*FLAG)]).status_code == 200
    n_before = _count(env, rid)
    r = vc.get(f"/records/{rid}/review", headers=hdr(env, "P1"))
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "saved" and b["verdict_id"] == v["verdict_id"]
    assert b["verdict"] == v["verdict"] and b["unresolved"] == []
    assert [(x["check_id"], x["field_path"], x["action"]) for x in b["resolutions"]] == [
        (*FLAG, "confirmed")
    ]
    assert _count(env, rid) == n_before  # nothing written
    # RLS unchanged
    assert vc.get(f"/records/{rid}/review", headers=hdr(env, "P3")).status_code == 404
    assert vc.get(f"/records/{rid}/review", headers=hdr(env, "N1")).status_code == 404
    assert vc.get(f"/records/{rid}/review").status_code == 401
    assert vc.get(f"/records/{rid}/review", headers=hdr(env, "Ph1")).status_code in (403, 404)
    # verify on the saved record still cannot change it
    assert vc.post(f"/records/{rid}/verify", headers=hdr(env, "P1"), json={}).status_code == 404


def test_b_review_of_unverified_draft_has_null_verdict(vc, env):
    rid = new_record(vc, env, "FLAGME")
    b = vc.get(f"/records/{rid}/review", headers=hdr(env, "N1")).json()
    assert b["verdict"] is None and b["verdict_id"] is None and b["resolutions"] == []


def _count(env, rid):
    with env.owner_conn() as o, o.transaction():
        o.execute("SET LOCAL ROLE maint_role")
        return o.execute(
            "SELECT (SELECT count(*) FROM clinic.verdicts WHERE record_id = %s),"
            " (SELECT count(*) FROM clinic.record_resolutions WHERE record_id = %s)",
            (rid, rid),
        ).fetchone()


# ------------------------------------------------------------------ (c) verifier hook input
def _tr_path(env, enc):
    return Path(env.audio_dir) / "transcripts" / f"{env.seed.encounters[enc]}.json"


def test_c_hook_receives_db_encounter_and_its_transcript(env):
    seen = {}

    def hook(record, *, encounter_id, transcript):
        seen.update(encounter_id=encounter_id, transcript=transcript)
        return fake_verifier(record)

    c = TestClient(
        create_app(env.settings, env.api_db, env.directory, env.audio_dir, verifier=hook)
    )
    rec = base_record()
    rec["source_transcript_id"] = str(env.seed.encounters["A3"])  # forged, editable field
    rid = new_record(c, env, enc="N1", who="N1")
    assert (
        c.patch(f"/records/{rid}", headers=hdr(env, "N1"), json={"record": rec}).status_code == 200
    )
    verify(c, env, rid, "P1")
    mine = json.loads(_tr_path(env, "N1").read_text(encoding="utf-8"))
    assert seen["encounter_id"] == str(env.seed.encounters["N1"])
    assert seen["transcript"] == mine


def test_c_missing_transcript_is_passed_as_none_and_old_one_arg_hook_still_works(env):
    seen = {}

    def hook(record, *, encounter_id, transcript):
        seen["t"] = transcript
        return fake_verifier(record)

    c = TestClient(
        create_app(env.settings, env.api_db, env.directory, env.audio_dir, verifier=hook)
    )
    p = _tr_path(env, "N2")
    saved = p.read_bytes() if p.exists() else None
    try:
        if saved is not None:
            p.unlink()
        rid = new_record(c, env, enc="N2", who="N1")
        verify(c, env, rid)
        assert seen["t"] is None
    finally:
        if saved is not None:
            p.write_bytes(saved)
    # legacy hook fn(record) keeps working (vc fixtures elsewhere use it); kwargs-only hooks too
    c2 = TestClient(create_app(env.settings, env.api_db, env.directory, env.audio_dir,
                               verifier=lambda r: fake_verifier(r)))  # fmt: skip
    rid2 = new_record(c2, env, enc="N1", who="N1")
    assert verify(c2, env, rid2)["verdict"]["verifier_version"] == "fake-test"


# ------------------------------------------------------------------ (d) every final status gated
@pytest.mark.parametrize("final", ["approved", "saved"])
def test_d_physician_sql_cannot_reach_any_final_status_with_open_flags(vc, env, final):
    rid = new_record(vc, env, "FLAGME")
    pr = princ(env, "P1")
    q = "UPDATE clinic.records SET status = %s, approved_by = %s, approved_at = now() WHERE id = %s"
    with pytest.raises(psycopg.errors.CheckViolation, match="gate"):  # never verified
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute(q, (final, pr.user_id, rid))
    verify(vc, env, rid)
    with pytest.raises(psycopg.errors.CheckViolation, match="unresolved"):  # verified, not resolved
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute(q, (final, pr.user_id, rid))
    # approved record cannot be INSERTed directly either
    with pytest.raises(psycopg.errors.CheckViolation, match="gate"):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute("INSERT INTO clinic.records (encounter_id, json, status, approved_by, approved_at)"
                        " VALUES (%s, %s, %s, %s, now())",
                        (env.seed.encounters["P1"], psycopg.types.json.Jsonb(base_record()), final, pr.user_id))  # fmt: skip


def test_d_final_record_content_cannot_be_rewritten_by_sql(vc, env):
    pr = princ(env, "P1")
    rewrite = (
        "UPDATE clinic.records SET json = jsonb_set(json, '{advice,0,text}', '\"x\"') WHERE id = %s"
    )
    # a saved record is protected by RLS (0 rows) ...
    with env.api_db.request_tx(pr, commit=False) as cur:
        assert cur.execute(rewrite, (env.seed.records["P1_saved"],)).rowcount == 0
    # ... and an 'approved' one (RLS lets the approver touch it) by the trigger
    rid = new_record(vc, env, "FLAGME")
    v = verify(vc, env, rid)
    with env.api_db.request_tx(pr) as cur:
        cur.execute("INSERT INTO clinic.record_resolutions (record_id, verdict_id, record_hash, facility_id,"
                    " check_id, field_path, action, resolved_by)"
                    " SELECT r.id, %s, app.record_hash(r.json), %s, 'C3', '/advice/0/negated', 'confirmed', %s"
                    " FROM clinic.records r WHERE r.id = %s",
                    (v["verdict_id"], pr.facility_id, pr.user_id, rid))  # fmt: skip
        cur.execute("UPDATE clinic.records SET status = 'approved', approved_by = %s, approved_at = now()"
                    " WHERE id = %s", (pr.user_id, rid))  # fmt: skip
    with pytest.raises(psycopg.errors.CheckViolation, match="gate"):
        with env.api_db.request_tx(pr, commit=False) as cur:
            cur.execute(rewrite, (rid,))
