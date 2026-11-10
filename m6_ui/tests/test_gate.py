"""Server-side save gate: mock mirrors m5 rules; HTTP client maps refusals; token never in URL."""

from __future__ import annotations

import copy
import json

import httpx
import pytest

from m6_ui import gate
from m6_ui.tests.helpers import fixture_triplet


def _clean():
    return fixture_triplet("rec-fx-asha-001")[1]


def _flagged():
    return fixture_triplet("rec-fx-pharm-003-asr")[1]


def test_mock_refuses_save_without_approval():
    g = gate.MockGate()
    r = g.save("rec-fx-asha-001", _clean())
    assert not r.ok and r.code == "refused_no_approval"


def test_mock_saves_clean_approved_record():
    g = gate.MockGate()
    assert g.approve("rec-fx-asha-001").ok
    r = g.save("rec-fx-asha-001", _clean())
    assert r.ok and r.code == "saved" and g.status("rec-fx-asha-001") == "saved"


def test_mock_refuses_unresolved_flags_like_m5_409():
    g = gate.MockGate()
    g.approve("rec-fx-pharm-003-asr")
    r = g.save("rec-fx-pharm-003-asr", _flagged())
    assert not r.ok and r.status == 409 and r.code == "refused_unresolved_flags"
    assert g.status("rec-fx-pharm-003-asr") == "approved"


def test_mock_refuses_empty_checks_and_mismatch():
    g = gate.MockGate()
    g.approve("rec-fx-asha-001")
    empty = {**_clean(), "checks": [], "auto_acceptable": False}
    assert g.save("rec-fx-asha-001", empty).code == "refused_unresolved_flags"
    assert g.save("other-id", _clean()).code == "refused_no_approval"
    g.approve("other-id")
    assert g.save("other-id", _clean()).code == "refused_mismatch"


def test_mock_refuses_invalid_verdict():
    g = gate.MockGate()
    g.approve("rec-fx-asha-001")
    bad = copy.deepcopy(_clean())
    bad["checks"][0]["status"] = "maybe"
    assert g.save("rec-fx-asha-001", bad).code == "refused_invalid"


def test_mock_can_be_told_to_refuse():
    g = gate.MockGate(force_refuse=True)
    g.approve("rec-fx-asha-001")
    r = g.save("rec-fx-asha-001", _clean())
    assert not r.ok and r.code == "refused_forced"


SERVER_ID = "11111111-1111-1111-1111-111111111111"


def _http_gate(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:8000")
    return gate.HttpGate(
        "http://127.0.0.1:8000",
        username="u",
        password="secret-pw",
        server_ids={"rec-1": SERVER_ID},
        client=client,
    )


def test_http_gate_maps_409_and_keeps_token_out_of_url():
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        if req.url.path == "/auth/token":
            return httpx.Response(200, json={"access_token": "TOKEN123", "token_type": "bearer"})
        if req.url.path.endswith("/approve"):
            return httpx.Response(200, json={"id": SERVER_ID, "status": "approved"})
        return httpx.Response(409, json={"error": "record has unresolved verdict flags"})

    g = _http_gate(handler)
    assert g.approve("rec-1").ok
    r = g.save("rec-1", {"record_id": "rec-1"})
    assert r.code == "refused_unresolved_flags" and r.status == 409
    assert "unresolved" in r.message
    for req in seen:
        assert "TOKEN123" not in str(req.url)
        assert "secret-pw" not in str(req.url)
    assert seen[-1].url.path == f"/records/{SERVER_ID}/save"
    assert seen[-1].headers["authorization"] == "Bearer TOKEN123"
    assert json.loads(seen[-1].content) == {"verdict": {"record_id": "rec-1"}}


@pytest.mark.parametrize(
    "status,code",
    [(401, "refused_auth"), (403, "refused_auth"), (422, "refused_mismatch"), (500, "error_other")],
)
def test_http_gate_maps_statuses(status, code):
    def handler(req):
        if req.url.path == "/auth/token":
            return httpx.Response(200, json={"access_token": "T"})
        return httpx.Response(status, json={"error": "e"})

    assert _http_gate(handler).save("rec-1", {}).code == code


def test_http_gate_network_error_and_unknown_record():
    def handler(req):
        raise httpx.ConnectError("boom")

    g = _http_gate(handler)
    assert g.save("rec-1", {}).code == "error_network"
    assert g.save("rec-unknown", {}).code == "refused_no_server_id"


def test_http_gate_refuses_non_loopback_url():
    with pytest.raises(ValueError):
        gate.HttpGate("http://example.com:8000", username="u", password="p", server_ids={})


def test_make_gate_from_env(monkeypatch):
    assert isinstance(gate.make_gate(), gate.MockGate)
    assert gate.make_gate().force_refuse is False
    monkeypatch.setenv("M6_MOCK_GATE_REFUSE", "1")
    assert gate.make_gate().force_refuse is True
