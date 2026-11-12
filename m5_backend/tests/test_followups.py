"""Phase C follow-ups: /approve removed (save is the only approval path), GET /records list,
GET /records/{id}/transcript, verifier loaded by import path, record.v2 bodies."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from m5_backend.app.auth import issue_token
from m5_backend.app.main import create_app
from m5_backend.tests.fakes import REPO, base_record, fake_verifier

V2 = REPO / "fixtures" / "record.v2" / "valid" / "rec2-fx-child-007.json"
FAKE_MOD = "m5_backend.tests.fake_verifier_mod"


def hdr(env, key):
    return {"Authorization": f"Bearer {issue_token(env.settings, env.directory.by_key(key))}"}


@pytest.fixture
def vc(env):
    return TestClient(
        create_app(env.settings, env.api_db, env.directory, env.audio_dir, verifier=fake_verifier)
    )


def new_rec(c, env, record, who="N1", enc="N1"):
    r = c.post(
        "/records",
        headers=hdr(env, who),
        json={"encounter_id": str(env.seed.encounters[enc]), "record": record},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ------------------------------------------------------------------ 1. /approve
@pytest.mark.needs_db
def test_handcrafted_approve_with_unresolved_flags_is_refused(vc, env):
    rid = new_rec(vc, env, base_record("FLAGME"))
    v = vc.post(f"/records/{rid}/verify", headers=hdr(env, "P1"), json={}).json()
    assert v["unresolved"], "precondition: the record has an open flag"
    for body in (None, {}, {"status": "approved"}):
        r = vc.post(f"/records/{rid}/approve", headers=hdr(env, "P1"), json=body)
        assert r.status_code in (404, 405), r.text
    got = vc.get(f"/records/{rid}", headers=hdr(env, "P1")).json()
    assert got["status"] == "draft" and got["approved_by"] is None and got["approved_at"] is None


# ------------------------------------------------------------------ 2. list + transcript
@pytest.mark.needs_db
def test_list_records_is_scoped_by_rls(vc, env):
    s = env.seed
    asha = vc.get("/records", headers=hdr(env, "A1"))
    assert asha.status_code == 200
    ids = {i["id"] for i in asha.json()["items"]}
    assert str(s.records["A1"]) in ids and str(s.records["A2"]) not in ids
    assert str(s.records["A3"]) not in ids and str(s.records["P3"]) not in ids
    nurse = {i["id"] for i in vc.get("/records?limit=100", headers=hdr(env, "N1")).json()["items"]}
    assert str(s.records["N1"]) in nurse and str(s.records["N2"]) in nurse
    assert str(s.records["N3"]) not in nurse and str(s.records["P3"]) not in nurse
    assert str(s.records["P1_saved"]) not in nurse  # nurses cannot read saved records
    phys = {i["id"] for i in vc.get("/records?limit=100", headers=hdr(env, "P1")).json()["items"]}
    assert str(s.records["P1_saved"]) in phys and str(s.records["P3"]) not in phys


@pytest.mark.needs_db
def test_list_records_fields_and_flag_count(vc, env):
    rid = new_rec(vc, env, base_record("FLAGME"))
    body = vc.get("/records?limit=100", headers=hdr(env, "P1")).json()
    mine = next(i for i in body["items"] if i["id"] == rid)
    assert set(mine) == {"id", "record_id", "encounter_id", "patient_id", "status", "flagged_count"}
    assert mine["flagged_count"] is None  # not verified yet
    vc.post(f"/records/{rid}/verify", headers=hdr(env, "P1"), json={})
    body = vc.get("/records?limit=100", headers=hdr(env, "P1")).json()
    assert next(i for i in body["items"] if i["id"] == rid)["flagged_count"] == 1
    assert "name_synthetic" not in json.dumps(body)


@pytest.mark.needs_db
def test_list_records_pagination_and_bad_params(vc, env):
    h = hdr(env, "P1")
    allp = vc.get("/records?limit=100", headers=h).json()
    assert allp["limit"] == 100 and allp["offset"] == 0
    page1 = vc.get("/records?limit=2&offset=0", headers=h).json()
    page2 = vc.get("/records?limit=2&offset=2", headers=h).json()
    assert len(page1["items"]) == 2 and page1["next_offset"] == 2
    ids = [i["id"] for i in allp["items"]]
    assert [i["id"] for i in page1["items"] + page2["items"]] == ids[:4]
    for q in ("limit=0", "limit=101", "limit=-1", "offset=-1", "limit=abc", "offset=' OR 1=1 --"):
        assert vc.get(f"/records?{q}", headers=h).status_code == 422, q


@pytest.mark.needs_db
@pytest.mark.parametrize("who", ["Ph1", "R1"])
def test_pharmacist_and_researcher_cannot_list_records(vc, env, who):
    r = vc.get("/records", headers=hdr(env, who))
    assert r.status_code in (403, 404) and "items" not in r.text
    r = vc.get(f"/records/{env.seed.records['P1']}/transcript", headers=hdr(env, who))
    assert r.status_code in (403, 404)


@pytest.mark.needs_db
def test_transcript_follows_record_visibility(vc, env):
    s = env.seed
    ok = vc.get(f"/records/{s.records['A1']}/transcript", headers=hdr(env, "A1"))
    assert ok.status_code == 200
    assert ok.json()["schema_version"] == "transcript.v1" and ok.json()["text"]
    assert (
        vc.get(f"/records/{s.records['P1']}/transcript", headers=hdr(env, "P1")).status_code == 200
    )
    for who, rec in (("A1", "A2"), ("A1", "A3"), ("N1", "N3"), ("P1", "P3"), ("N1", "P1_saved")):
        r = vc.get(f"/records/{s.records[rec]}/transcript", headers=hdr(env, who))
        assert r.status_code == 404 and r.json() == {"error": "not found"}, (who, rec)
    r = vc.get("/records/..%2F..%2Fetc/transcript", headers=hdr(env, "P1"))
    assert r.status_code in (404, 422)
    assert vc.get(f"/records/{s.records['P1']}/transcript").status_code == 401


@pytest.mark.needs_db
def test_transcript_name_comes_from_database_not_from_record_json(env):
    """A record whose JSON names another transcript id cannot read that transcript (IDOR)."""
    tdir = Path(env.audio_dir) / "transcripts"
    victim = env.seed.encounters["A3"]
    assert re.fullmatch(r"[0-9a-f-]{36}", str(victim)) and (tdir / f"{victim}.json").is_file()
    c = TestClient(create_app(env.settings, env.api_db, env.directory, env.audio_dir))
    rec = base_record()
    rec["source_transcript_id"] = str(victim)
    rid = new_rec(c, env, rec, who="A1", enc="A1")
    got = c.get(f"/records/{rid}/transcript", headers=hdr(env, "A1")).json()
    mine = json.loads((tdir / f"{env.seed.encounters['A1']}.json").read_text(encoding="utf-8"))
    other = json.loads((tdir / f"{victim}.json").read_text(encoding="utf-8"))
    assert got["audio_id"] == mine["audio_id"] != other["audio_id"]


# ------------------------------------------------------------------ 3. verifier by import path
def test_load_verifier_default_and_by_path():
    from m5_backend.app.verifier import load_verifier, manual_review_verifier

    assert load_verifier(None) is manual_review_verifier
    assert load_verifier("") is manual_review_verifier
    fn = load_verifier(f"{FAKE_MOD}:always_flag_c4")
    assert fn({"record_id": "r1"})["verifier_version"] == "fake-module-v1"


@pytest.mark.parametrize(
    "spec",
    [
        "nocolon",
        f"{FAKE_MOD}:",
        ":fn",
        "os:system;ls",
        "a b:c",
        "no_such_module_zzz:fn",
        f"{FAKE_MOD}:missing",
        f"{FAKE_MOD}:NOT_CALLABLE",
        "../x:fn",
        f"{FAKE_MOD}:__doc__",
    ],
)
def test_load_verifier_rejects_bad_specs_and_fails_closed(spec):
    from m5_backend.app.verifier import load_verifier

    with pytest.raises(RuntimeError) as e:
        load_verifier(spec)
    assert "Traceback" not in str(e.value)


def test_settings_reads_verifier_env():
    from m5_backend.app.config import load_settings

    nofile = Path("nonexistent.env")
    s = load_settings(environ={"MAATUMITRA_VERIFIER": "a.b:c"}, env_file=nofile)
    assert s.verifier_spec == "a.b:c"
    assert load_settings(environ={}, env_file=nofile).verifier_spec is None


@pytest.mark.needs_db
def test_app_uses_verifier_from_settings(env):
    s = env.settings.replace(verifier_spec=f"{FAKE_MOD}:always_flag_c4")
    c = TestClient(create_app(s, env.api_db, env.directory, env.audio_dir))
    rid = new_rec(c, env, base_record())
    v = c.post(f"/records/{rid}/verify", headers=hdr(env, "P1"), json={}).json()
    assert v["verdict"]["verifier_version"] == "fake-module-v1"
    assert v["unresolved"] == [{"check_id": "C4", "field_path": "/medications/0/dose_value"}]
    bad = s.replace(verifier_spec="no_such_module_zzz:fn")
    with pytest.raises(RuntimeError):
        create_app(bad, env.api_db, env.directory, env.audio_dir)


@pytest.mark.needs_db
def test_default_verifier_still_flags_everything(env):
    c = TestClient(create_app(env.settings, env.api_db, env.directory, env.audio_dir))
    rid = new_rec(c, env, base_record())
    v = c.post(f"/records/{rid}/verify", headers=hdr(env, "P1"), json={}).json()
    assert v["verdict"]["verifier_version"] == "m5-manual-review-v1" and v["unresolved"]


# ------------------------------------------------------------------ 4. record.v2
def v2_record() -> dict:
    rec = json.loads(V2.read_text(encoding="utf-8"))
    rec["status"] = "draft"
    return rec


@pytest.mark.needs_db
def test_record_v2_accepted_and_stored_as_jsonb(vc, env):
    rec = v2_record()
    rid = new_rec(vc, env, rec)
    got = vc.get(f"/records/{rid}", headers=hdr(env, "N1")).json()["json"]
    assert got == rec and got["schema_version"] == "record.v2"
    assert vc.post(f"/records/{rid}/verify", headers=hdr(env, "P1"), json={}).status_code == 201
    upd = vc.patch(f"/records/{rid}", headers=hdr(env, "N1"), json={"record": rec})
    assert upd.status_code == 200


@pytest.mark.needs_db
def test_record_v2_invalid_or_bidi_or_unknown_version_is_refused(vc, env):
    enc = str(env.seed.encounters["N1"])

    def post(rec):
        return vc.post(
            "/records", headers=hdr(env, "N1"), json={"encounter_id": enc, "record": rec}
        ).status_code

    bad = v2_record()
    bad["medications"][0]["route"] = "by_magic"
    assert post(bad) == 422
    bidi = v2_record()
    bidi["medications"][0]["drug"] = "para‮cetamol"
    assert post(bidi) == 422
    unknown = base_record()
    unknown["schema_version"] = "record.v3"
    assert post(unknown) == 422
    saved = v2_record()
    saved["status"] = "saved"
    assert post(saved) == 422
