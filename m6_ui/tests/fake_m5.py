"""A tiny in-memory stand-in for the m5 API (httpx.MockTransport), used only by tests.

It mirrors the m5 rules that matter to the UI: one mock token per user (role inside the token),
RLS-like filtering of /patients, GET /records/{id}, PATCH + /verify (server-owned verdicts),
/save with {verdict_id, resolutions}, and 403 for non-physicians. It logs every call.
No m5 code is imported.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import uuid

import httpx

from m6_ui.tests.helpers import fixture_triplet

PASSWORD = "sandbox-pw"
USERS = {
    "11111111-0000-4000-8000-000000000001": ("asha", "SYNTHETIC-ASHA-A1"),
    "11111111-0000-4000-8000-000000000002": ("asha", "SYNTHETIC-ASHA-A2"),
    "11111111-0000-4000-8000-000000000003": ("physician", "SYNTHETIC-PHYS-P1"),
    "11111111-0000-4000-8000-000000000004": ("pharmacist", "SYNTHETIC-PHARM-1"),
}
ASHA1, ASHA2, PHYS, PHARM = list(USERS)
PATIENTS = {ASHA1: ["Patient-Own-A1"], ASHA2: ["Patient-Other-A2"]}
RECORD_ID = "22222222-0000-4000-8000-000000000001"
SERVER_PATIENT_REF = "pt-server-only-999"


def b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


def fake_jwt(role: str, sub: str) -> str:
    return f"{b64({'alg': 'HS256'})}.{b64({'sub': sub, 'role': role})}.sig"


def _h(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()


class FakeM5:
    def __init__(
        self,
        base_record_id: str = "rec-fx-pharm-003-asr",
        patient_ref: str = SERVER_PATIENT_REF,
        c4_reason: str = "out_of_range [CR-DOSE]: dose 50 mg is below the range",
    ):
        self.c4_reason = c4_reason
        rec, _ver, _tr = fixture_triplet(base_record_id)
        rec = copy.deepcopy(rec)
        rec["patient_ref"] = patient_ref
        self.record = rec
        self.status = "flagged"
        self.verdicts: dict[str, dict] = {}
        self.latest: str | None = None
        self.calls: list[tuple[str, str]] = []
        self.tokens: dict[str, tuple[str, str]] = {}
        self.save_bodies: list[dict] = []
        self.fail_with: int | None = None  # force /save to answer this status

    # ------------------------------------------------------------- verifier (server side)
    def _verdict(self) -> dict:
        dose = self.record["medications"][0]["dose_value"]
        checks = [
            {"check_id": "C1", "name": "span", "status": "pass", "reason": "ok", "field_path": "/"}
        ]
        if dose == 50:
            checks.append(
                {
                    "check_id": "C4",
                    "name": "dose-range",
                    "status": "flag",
                    "reason": self.c4_reason,
                    "field_path": "/medications/0/dose_value",
                }
            )
        flags = any(c["status"] == "flag" for c in checks)
        return {
            "schema_version": "verdict.v1",
            "record_id": self.record["record_id"],
            "checks": checks,
            "auto_acceptable": not flags,
            "verifier_version": "fake-m5-1",
        }

    def _flag_keys(self, v: dict) -> set[tuple[str, str]]:
        return {(c["check_id"], c["field_path"]) for c in v["checks"] if c["status"] == "flag"}

    # ------------------------------------------------------------- transport
    def client(self) -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(self.handle), base_url="http://127.0.0.1:8000"
        )

    def paths(self) -> list[str]:
        return [f"{m} {p}" for m, p in self.calls]

    def handle(self, req: httpx.Request) -> httpx.Response:
        path, method = req.url.path, req.method
        self.calls.append((method, path))
        if path == "/auth/token":
            body = json.loads(req.content)
            u = USERS.get(body.get("username", ""))
            if u is None or body.get("password") != PASSWORD:
                return httpx.Response(401, json={"error": "unauthorized"})
            tok = fake_jwt(u[0], body["username"]) + "." + uuid.uuid4().hex[:6]
            self.tokens[tok] = (body["username"], u[0])
            return httpx.Response(200, json={"access_token": tok, "token_type": "bearer"})
        auth = req.headers.get("authorization", "")
        who = self.tokens.get(auth[7:]) if auth.startswith("Bearer ") else None
        if who is None:
            return httpx.Response(401, json={"error": "unauthorized"})
        uid, role = who
        if path == "/patients":
            names = (
                PATIENTS.get(uid, [])
                if role == "asha"
                else [n for v in PATIENTS.values() for n in v]
            )
            return httpx.Response(
                200, json=[{"id": str(i), "name_synthetic": n} for i, n in enumerate(names)]
            )
        if path == f"/records/{RECORD_ID}" and method == "GET":
            if role == "pharmacist":
                return httpx.Response(404, json={"error": "not found"})
            return httpx.Response(
                200, json={"id": RECORD_ID, "json": self.record, "status": self.status}
            )
        if path == f"/records/{RECORD_ID}" and method == "PATCH":
            self.record = json.loads(req.content)["record"]
            return httpx.Response(200, json={"id": RECORD_ID})
        if path == f"/records/{RECORD_ID}/verify":
            v = self._verdict()
            vid = str(uuid.uuid4())
            self.verdicts[vid] = {"verdict": v, "hash": _h(self.record)}
            self.latest = vid
            unresolved = [{"check_id": c, "field_path": p} for c, p in sorted(self._flag_keys(v))]
            return httpx.Response(
                201,
                json={
                    "verdict_id": vid,
                    "record_id": RECORD_ID,
                    "record_hash": _h(self.record),
                    "verdict": v,
                    "unresolved": unresolved,
                },
            )
        if path == f"/records/{RECORD_ID}/save":
            body = json.loads(req.content)
            self.save_bodies.append(body)
            if self.fail_with:
                return httpx.Response(self.fail_with, json={"error": "forced"})
            if role != "physician":
                return httpx.Response(403, json={"error": "forbidden"})
            if set(body) != {"verdict_id", "resolutions"}:
                return httpx.Response(422, json={"error": "invalid request"})
            if self.status == "saved":
                return httpx.Response(409, json={"error": "conflict"})
            v = self.verdicts.get(body["verdict_id"])
            if v is None:
                return httpx.Response(404, json={"error": "not found"})
            keys = [(r["check_id"], r["field_path"]) for r in body["resolutions"]]
            flags = self._flag_keys(v["verdict"])
            if len(set(keys)) != len(keys) or not set(keys) <= flags:
                return httpx.Response(422, json={"error": "invalid request"})
            if set(keys) != flags:
                return httpx.Response(409, json={"error": "record has unresolved verdict flags"})
            if body["verdict_id"] != self.latest:
                return httpx.Response(409, json={"error": "verdict is stale"})
            self.status = "saved"
            return httpx.Response(
                200, json={"id": RECORD_ID, "status": "saved", "resolved": len(keys)}
            )
        return httpx.Response(404, json={"error": "not found"})
