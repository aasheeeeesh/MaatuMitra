"""Server-side save gate (D-94 flow): mock mirrors m5 rules; HTTP client talks to m5 per user."""

from __future__ import annotations

import copy

import httpx
import pytest

from m6_ui import gate, review
from m6_ui.tests import fake_m5 as fm
from m6_ui.tests.helpers import fixture_triplet


def _stored(g, rid="rec-fx-asha-001"):
    rec, ver, _ = fixture_triplet(rid)
    return rec, ver, g.store_verdict(rid, rec, ver)


def _res(ver, action="confirmed"):
    return [
        {"check_id": c["check_id"], "field_path": c["field_path"], "action": action}
        for c in ver["checks"]
        if c["status"] == "flag"
    ]


# ------------------------------------------------------------------ mock gate (mirrors m5)


def test_mock_saves_clean_record_for_physician_only():
    g = gate.MockGate()
    _, _, vid = _stored(g)
    r = g.save("rec-fx-asha-001", vid, [], role="pharmacist")
    assert not r.ok and r.status == 403 and r.code == "refused_forbidden"
    r = g.save("rec-fx-asha-001", vid, [], role="physician")
    assert r.ok and r.code == "saved" and g.status("rec-fx-asha-001") == "saved"


def test_mock_needs_exactly_one_resolution_per_flag():
    g = gate.MockGate()
    rid = "rec-fx-pharm-003-asr"
    _, ver, vid = _stored(g, rid)
    assert g.save(rid, vid, [], role="physician").code == "refused_unresolved_flags"
    res = _res(ver)
    assert len(res) == 2
    assert g.save(rid, vid, res[:1], role="physician").code == "refused_unresolved_flags"
    assert g.save(rid, vid, [*res, res[0]], role="physician").code == "refused_bad_request"
    ghost = [{"check_id": "C3", "field_path": "/advice/0/negated", "action": "confirmed"}]
    assert g.save(rid, vid, res + ghost, role="physician").code == "refused_bad_request"
    assert g.status(rid) is None
    ok = g.save(rid, vid, res, role="physician")
    assert ok.ok and g.status(rid) == "saved"


def test_mock_refuses_unknown_and_stale_verdict_and_repeat_save():
    g = gate.MockGate()
    rec, ver, vid = _stored(g)
    assert g.save("rec-fx-asha-001", "nope", [], role="physician").code == "not_found"
    vid2 = g.store_verdict("rec-fx-asha-001", rec, ver)
    assert g.save("rec-fx-asha-001", vid, [], role="physician").code == "refused_stale"
    assert g.save("rec-fx-asha-001", vid2, [], role="physician").ok
    again = g.save("rec-fx-asha-001", vid2, [], role="physician")
    assert not again.ok and again.code == "already_saved"


def test_mock_refuses_empty_checks_as_stale():
    g = gate.MockGate()
    rec, ver, _ = _stored(g)
    vid = g.store_verdict("rec-fx-asha-001", rec, {**ver, "checks": [], "auto_acceptable": False})
    assert g.save("rec-fx-asha-001", vid, [], role="physician").code == "refused_stale"


def test_mock_edited_resolution_needs_a_really_edited_and_clean_record():
    g = gate.MockGate()
    rid = "rec-fx-pharm-003-asr"
    rec, ver, vid = _stored(g, rid)
    res = _res(ver, "edited")
    # nothing was edited: m5 says the edited record is not cleanly re-verified
    assert g.save(rid, vid, res, role="physician").code == "refused_not_reverified"
    edited = review.set_pointer(rec, "/medications/0/dose_value", 500)
    clean = {**ver, "checks": [c for c in ver["checks"] if c["status"] != "flag"]}
    clean["auto_acceptable"] = True
    g.store_verdict(rid, edited, clean)
    assert g.save(rid, vid, res, role="physician").ok


def test_mock_edit_that_leaves_a_new_flag_is_not_saved():
    g = gate.MockGate()
    rid = "rec-fx-pharm-003-asr"
    rec, ver, vid = _stored(g, rid)
    res = _res(ver, "edited")
    edited = review.set_pointer(rec, "/medications/0/dose_value", 500)
    new_flag = {
        "check_id": "C2",
        "name": "x",
        "status": "flag",
        "reason": "r",
        "field_path": "/medications/0/dose_value",
    }
    bad = {**ver, "checks": [*ver["checks"][:1], new_flag], "auto_acceptable": False}
    g.store_verdict(rid, edited, bad)
    assert g.save(rid, vid, res, role="physician").code == "refused_not_reverified"


def test_mock_can_be_told_to_refuse_and_env_lock_cannot_be_lowered():
    g = gate.MockGate(force_refuse=True, locked=True)
    _, _, vid = _stored(g)
    assert g.save("rec-fx-asha-001", vid, [], role="physician").code == "refused_forced"
    g.force_refuse = False  # the page tries to switch it off
    assert g.force_refuse is True
    assert g.save("rec-fx-asha-001", vid, [], role="physician").code == "refused_forced"
    free = gate.MockGate(force_refuse=True)
    free.force_refuse = False
    assert free.force_refuse is False


def test_mock_rejects_invalid_verdict():
    g = gate.MockGate()
    rec, ver, _ = _stored(g)
    bad = copy.deepcopy(ver)
    bad["checks"][0]["status"] = "maybe"
    with pytest.raises(ValueError):
        g.store_verdict("rec-fx-asha-001", rec, bad)


# ------------------------------------------------------------------ http gate (per user)


def _http(m5=None):
    m5 = m5 or fm.FakeM5()
    return m5, gate.HttpGate("http://127.0.0.1:8000", client=m5.client())


def test_http_login_takes_role_from_the_token_not_the_caller():
    _, g = _http()
    assert not g.logged_in and g.role is None
    bad = g.login(fm.PHYS, "wrong")
    assert not bad.ok and bad.code == "refused_auth" and g.role is None
    ok = g.login(fm.ASHA1, fm.PASSWORD)
    assert ok.ok and g.role == "asha" and g.logged_in
    g.logout()
    assert g.role is None and not g.logged_in


def test_each_gate_keeps_its_own_token():
    m5 = fm.FakeM5()
    a = gate.HttpGate("http://127.0.0.1:8000", client=m5.client())
    b = gate.HttpGate("http://127.0.0.1:8000", client=m5.client())
    a.login(fm.ASHA1, fm.PASSWORD)
    b.login(fm.PHYS, fm.PASSWORD)
    assert (a.role, b.role) == ("asha", "physician")
    assert len(set(m5.tokens)) == 2


def test_http_load_record_gets_the_stored_record_and_verifies_it():
    m5, g = _http()
    g.login(fm.PHYS, fm.PASSWORD)
    got = g.load_record(fm.RECORD_ID)
    assert got.ok
    assert got.data["record"]["patient_ref"] == fm.SERVER_PATIENT_REF
    assert got.data["verdict_id"] and got.data["verdict"]["checks"]
    assert m5.paths()[-2:] == [
        f"GET /records/{fm.RECORD_ID}",
        f"POST /records/{fm.RECORD_ID}/verify",
    ]


def test_http_load_rejects_path_tricks_without_a_request():
    m5, g = _http()
    g.login(fm.PHYS, fm.PASSWORD)
    n = len(m5.calls)
    r = g.load_record("../../auth/token")
    assert not r.ok and r.result.code == "not_found" and len(m5.calls) == n


def test_http_save_sends_only_verdict_id_and_resolutions_and_never_calls_approve():
    m5, g = _http()
    g.login(fm.PHYS, fm.PASSWORD)
    loaded = g.load_record(fm.RECORD_ID).data
    res = [{"check_id": "C4", "field_path": "/medications/0/dose_value", "action": "confirmed"}]
    r = g.save(fm.RECORD_ID, loaded["verdict_id"], res)
    assert r.ok and r.code == "saved" and g.status(fm.RECORD_ID) == "saved"
    assert m5.save_bodies == [{"verdict_id": loaded["verdict_id"], "resolutions": res}]
    assert not any(p.endswith("/approve") for _, p in m5.calls)


@pytest.mark.parametrize(
    "status,msg,code",
    [
        (409, "record has unresolved verdict flags", "refused_unresolved_flags"),
        (409, "verdict is stale", "refused_stale"),
        (409, "record must be verified again", "refused_stale"),
        (409, "edited record is not cleanly re-verified", "refused_not_reverified"),
        (409, "verdict is not acceptable", "refused_unacceptable"),
        (409, "conflict", "refused_conflict"),
        (422, "invalid request", "refused_bad_request"),
        (403, "forbidden", "refused_forbidden"),
        (404, "not found", "not_found"),
        (401, "unauthorized", "refused_auth"),
        (500, "internal error", "error_other"),
    ],
)
def test_http_save_maps_every_server_refusal(status, msg, code):
    class Forced(fm.FakeM5):
        def handle(self, req):
            if req.url.path.endswith("/save"):
                return httpx.Response(status, json={"error": msg})
            return super().handle(req)

    _, g = _http(Forced())
    g.login(fm.PHYS, fm.PASSWORD)
    r = g.save(fm.RECORD_ID, "x", [])
    assert not r.ok and r.code == code and r.status == status


def test_http_network_error_is_not_a_save():
    def boom(req):
        raise httpx.ConnectError("down")

    g = gate.HttpGate(
        "http://127.0.0.1:8000", client=httpx.Client(transport=httpx.MockTransport(boom))
    )
    assert g.login(fm.PHYS, fm.PASSWORD).code == "error_network"


def test_http_gate_refuses_non_loopback_url():
    with pytest.raises(ValueError):
        gate.HttpGate("http://example.com:8000")


def test_http_patients_come_from_the_server_per_user():
    _, g = _http()
    g.login(fm.ASHA1, fm.PASSWORD)
    got = g.patients()
    assert got.ok and [p["name_synthetic"] for p in got.data] == ["Patient-Own-A1"]


def test_make_gate_from_env(monkeypatch):
    assert isinstance(gate.make_gate(), gate.MockGate)
    assert gate.make_gate().force_refuse is False
    monkeypatch.setenv("M6_MOCK_GATE_REFUSE", "1")
    g = gate.make_gate()
    assert g.force_refuse is True and g.locked
    monkeypatch.setenv("MODE", "live")
    monkeypatch.setenv("API_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("M6_API_USER", "should-be-ignored")
    live = gate.make_gate()
    assert isinstance(live, gate.HttpGate) and not live.logged_in


def test_build_resolutions_empty():
    assert review.build_resolutions([], {}) == []
