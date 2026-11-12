"""Server-side save gate client (D-94 flow). The UI never decides "saved" by itself.

Save = approve. The only write the UI makes is `save(record_id, verdict_id, resolutions)`:
exactly one resolution `{check_id, field_path, action}` per flag of the SERVER-stored verdict.
There is no separate /approve call (D-123 F3).

- MockGate (MODE=mock): mirrors the m5 rules (physician only; verdict stored by the "server";
  stale / unknown verdict; one resolution per flag; edited record must be re-verified and clean).
  `locked=True` (env M6_MOCK_GATE_REFUSE=1) means the page can never lower `force_refuse` (F5).
- HttpGate (MODE=live): one instance per browser session. The person logs in with their own m5
  user (`POST /auth/token`); the role is READ FROM THE TOKEN, never from a click (F1). The token
  lives only in this server-side object and is sent only in the Authorization header. The record
  and verdict shown are loaded from m5 by the same id that is saved (F2). Only loopback URLs.
No m5 code is imported.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from contracts.validate import validate_doc

ALL_CODES = (
    "saved",
    "already_saved",
    "refused_unresolved_flags",
    "refused_stale",
    "refused_not_reverified",
    "refused_unacceptable",
    "refused_conflict",
    "refused_bad_request",
    "refused_forbidden",
    "refused_forced",
    "refused_auth",
    "not_found",
    "error_network",
    "error_other",
)
ROLES_KNOWN = ("asha", "nurse", "physician", "pharmacist", "researcher")


@dataclass(frozen=True)
class GateResult:
    ok: bool
    status: int  # HTTP-like status (0 = no response)
    code: str  # one of ALL_CODES; the UI shows i18n text "gate.code.<code>"
    message: str = ""  # server's own message (shown escaped, as data)


@dataclass
class Loaded:
    ok: bool
    data: dict | None = None
    result: GateResult | None = None


def flag_keys(verdict: dict) -> set[tuple[str, str]]:
    return {(c["check_id"], c["field_path"]) for c in verdict["checks"] if c["status"] == "flag"}


def code_for(status: int, message: str) -> str:
    """Map an m5 refusal (status + its generic message) to an i18n code."""
    m = (message or "").lower()
    if status == 409:
        if "unresolved" in m:
            return "refused_unresolved_flags"
        if "stale" in m or "verified again" in m:
            return "refused_stale"
        if "re-verified" in m:
            return "refused_not_reverified"
        if "not acceptable" in m:
            return "refused_unacceptable"
        return "refused_conflict"
    return {
        422: "refused_bad_request",
        401: "refused_auth",
        403: "refused_forbidden",
        404: "not_found",
    }.get(status, "error_other")


class MockGate:
    live = False

    def __init__(self, force_refuse: bool = False, locked: bool = False):
        self.locked = locked
        self._force = force_refuse
        self._status: dict[str, str] = {}
        self._verdicts: dict[str, tuple[str, str, dict]] = {}  # vid -> (record_id, hash, verdict)
        self._latest: dict[str, str] = {}
        self._hash: dict[str, str] = {}

    @property
    def force_refuse(self) -> bool:
        return self._force

    @force_refuse.setter
    def force_refuse(self, value: bool) -> None:
        if self.locked and not value:
            return  # F5: the environment setting cannot be switched off from the page
        self._force = bool(value)

    def status(self, record_id: str) -> str | None:
        return self._status.get(record_id)

    def store_verdict(self, record_id: str, record: dict, verdict: dict) -> str:
        """The mock 'server' stores the (mock-verified) verdict for the current record content."""
        if validate_doc("verdict.v1", verdict):
            raise ValueError("verdict is not valid verdict.v1")
        h = json.dumps(record, sort_keys=True, ensure_ascii=False)
        vid = uuid.uuid4().hex
        self._verdicts[vid] = (record_id, h, verdict)
        self._latest[record_id] = vid
        self._hash[record_id] = h
        return vid

    def save(
        self, record_id: str, verdict_id: str, resolutions: list[dict], role: str | None
    ) -> GateResult:
        def no(status: int, code: str, msg: str = "") -> GateResult:
            return GateResult(False, status, code, msg)

        if self._force:
            return no(409, "refused_forced", "mock gate told to refuse")
        if role != "physician":
            return no(403, "refused_forbidden", "forbidden")
        if self._status.get(record_id) == "saved":
            return no(409, "already_saved", "already saved")
        v = self._verdicts.get(verdict_id)
        if v is None or v[0] != record_id:
            return no(404, "not_found", "not found")
        latest_id = self._latest.get(record_id)
        latest = self._verdicts[latest_id][2] if latest_id else None
        if latest is None or not latest["checks"] or not v[2]["checks"]:
            return no(409, "refused_stale", "record must be verified again")
        flags_v, flags_now = flag_keys(v[2]), flag_keys(latest)
        if not flags_now and not latest["auto_acceptable"]:
            return no(409, "refused_unacceptable", "verdict is not acceptable")
        keys = [(r["check_id"], r["field_path"]) for r in resolutions]
        if len(set(keys)) != len(keys) or not set(keys) <= flags_v:
            return no(422, "refused_bad_request", "invalid request")
        if set(keys) != flags_v:
            return no(409, "refused_unresolved_flags", "record has unresolved verdict flags")
        confirmed = {
            (r["check_id"], r["field_path"]) for r in resolutions if r["action"] == "confirmed"
        }
        if any(r["action"] == "edited" for r in resolutions):
            if v[1] == self._hash[record_id] or not flags_now <= confirmed:
                return no(409, "refused_not_reverified", "edited record is not cleanly re-verified")
        elif v[1] != self._hash[record_id] or latest_id != verdict_id:
            return no(409, "refused_stale", "verdict is stale")
        self._status[record_id] = "saved"
        return GateResult(True, 200, "saved")


_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _role_from_token(token: str) -> str | None:
    """Read the role claim for DISPLAY. m5 verifies the signature on every call and is the
    authority; a forged token here would only change what this page shows, not what m5 allows."""
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except (IndexError, ValueError, UnicodeDecodeError):
        return None
    role = claims.get("role") if isinstance(claims, dict) else None
    return role if role in ROLES_KNOWN else None


def _uuid_ok(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except (ValueError, AttributeError, TypeError):
        return False


class HttpGate:
    live = True

    def __init__(
        self, base_url: str, *, client: httpx.Client | None = None, timeout_s: float = 10.0
    ):
        if urlsplit(base_url).hostname not in _LOOPBACK:
            raise ValueError("API_URL must point to this computer (127.0.0.1)")
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout_s)
        self._token: str | None = None
        self.role: str | None = None
        self.user_id: str | None = None
        self._status: dict[str, str] = {}

    @property
    def logged_in(self) -> bool:
        return self._token is not None and self.role is not None

    def logout(self) -> None:
        self._token, self.role, self.user_id = None, None, None
        self._status.clear()

    def status(self, record_id: str) -> str | None:
        return self._status.get(record_id)

    # -------------------------------------------------------------- calls
    def _call(
        self, method: str, path: str, body: Any = None
    ) -> tuple[httpx.Response | None, GateResult | None]:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            r = self._client.request(method, path, json=body, headers=headers)
        except httpx.HTTPError as e:
            return None, GateResult(False, 0, "error_network", type(e).__name__)
        if r.status_code == 401:
            self.logout()  # expired or refused: the person must log in again
        return r, None

    @staticmethod
    def _refusal(r: httpx.Response) -> GateResult:
        try:
            msg = str(r.json().get("error", ""))
        except (ValueError, AttributeError):
            msg = ""
        return GateResult(False, r.status_code, code_for(r.status_code, msg), msg)

    def login(self, username: str, password: str) -> GateResult:
        self.logout()
        try:
            r = self._client.post("/auth/token", json={"username": username, "password": password})
        except httpx.HTTPError as e:
            return GateResult(False, 0, "error_network", type(e).__name__)
        if r.status_code != 200:
            return GateResult(False, r.status_code, "refused_auth", "login refused")
        try:
            token = r.json()["access_token"]
        except (ValueError, KeyError, TypeError):
            return GateResult(False, r.status_code, "error_other", "bad login answer")
        role = _role_from_token(token)
        if role is None:
            return GateResult(False, r.status_code, "refused_auth", "token has no known role")
        self._token, self.role, self.user_id = token, role, username
        return GateResult(True, 200, "logged_in")

    def patients(self) -> Loaded:
        r, err = self._call("GET", "/patients")
        if err:
            return Loaded(False, result=err)
        if r.status_code != 200:
            return Loaded(False, result=self._refusal(r))
        return Loaded(True, data=r.json())

    def _verify(self, record_id: str) -> Loaded:
        r, err = self._call("POST", f"/records/{record_id}/verify", {})
        if err:
            return Loaded(False, result=err)
        if r.status_code != 201:
            return Loaded(False, result=self._refusal(r))
        j = r.json()
        if validate_doc("verdict.v1", j.get("verdict", {})):
            return Loaded(False, result=GateResult(False, 200, "error_other", "bad verdict"))
        return Loaded(True, data={"verdict_id": j["verdict_id"], "verdict": j["verdict"]})

    def load_record(self, record_id: str) -> Loaded:
        """GET the stored record, then ask the server to verify it. Nothing is read locally."""
        if not _uuid_ok(record_id):
            return Loaded(False, result=GateResult(False, 0, "not_found", "bad record id"))
        r, err = self._call("GET", f"/records/{record_id}")
        if err:
            return Loaded(False, result=err)
        if r.status_code != 200:
            return Loaded(False, result=self._refusal(r))
        j = r.json()
        v = self._verify(record_id)
        if not v.ok:
            return v
        return Loaded(True, data={"record": j["json"], "status": j.get("status"), **v.data})

    def update_record(self, record_id: str, record: dict) -> Loaded:
        """PATCH the edited record, then let the server verify the stored result again."""
        if not _uuid_ok(record_id):
            return Loaded(False, result=GateResult(False, 0, "not_found", "bad record id"))
        r, err = self._call("PATCH", f"/records/{record_id}", {"record": record})
        if err:
            return Loaded(False, result=err)
        if r.status_code != 200:
            return Loaded(False, result=self._refusal(r))
        v = self._verify(record_id)
        return v if not v.ok else Loaded(True, data={"record": record, **v.data})

    def save(
        self, record_id: str, verdict_id: str, resolutions: list[dict], role: str | None = None
    ) -> GateResult:
        if not _uuid_ok(record_id):
            return GateResult(False, 0, "not_found", "bad record id")
        r, err = self._call(
            "POST",
            f"/records/{record_id}/save",
            {"verdict_id": verdict_id, "resolutions": resolutions},
        )
        if err:
            return err
        if r.status_code == 200:
            self._status[record_id] = "saved"
            return GateResult(True, 200, "saved")
        return self._refusal(r)


def make_gate():
    """MODE=live + API_URL -> HttpGate (no shared credentials: each person logs in); else MockGate."""
    if os.environ.get("MODE", "mock") == "live" and os.environ.get("API_URL"):
        return HttpGate(os.environ["API_URL"])
    locked = os.environ.get("M6_MOCK_GATE_REFUSE") == "1"
    return MockGate(force_refuse=locked, locked=locked)
