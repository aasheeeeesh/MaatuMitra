"""Server-side save gate client. The UI never decides "saved" by itself.

- MockGate (MODE=mock): mirrors the rules documented in m5_backend/CONTRACT.md for
  `POST /records/{id}/save`: refuse (409) if checks is empty, auto_acceptable is false, or any
  check flags; 422 if the verdict's record_id differs; and (DB CHECK) no save without an
  approval. `force_refuse=True` (env M6_MOCK_GATE_REFUSE=1) refuses every save, for tests/demos.
- HttpGate (MODE=live, API_URL set): calls the m5 API over HTTP. The bearer token is kept in
  server-side Python memory and sent only in the Authorization header, never in a URL.
  Only loopback URLs are accepted (127.0.0.1 / localhost / ::1).
No m5 code is imported.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from contracts.validate import validate_doc

ALL_CODES = (
    "saved",
    "approved",
    "refused_unresolved_flags",
    "refused_no_approval",
    "refused_mismatch",
    "refused_invalid",
    "refused_forced",
    "refused_auth",
    "refused_no_server_id",
    "error_network",
    "error_other",
)


@dataclass(frozen=True)
class GateResult:
    ok: bool
    status: int  # HTTP-like status (0 = no response)
    code: str  # one of ALL_CODES; the UI shows i18n text "gate.code.<code>"
    message: str = ""  # server's own message (shown escaped, as data)


def _unresolved(verdict: dict) -> bool:
    checks = verdict.get("checks") or []
    return (
        not checks
        or not verdict.get("auto_acceptable", False)
        or any(c.get("status") == "flag" for c in checks)
    )


class MockGate:
    def __init__(self, force_refuse: bool = False):
        self.force_refuse = force_refuse
        self._status: dict[str, str] = {}

    def status(self, record_id: str) -> str | None:
        return self._status.get(record_id)

    def approve(self, record_id: str) -> GateResult:
        if self._status.get(record_id) == "saved":
            return GateResult(False, 409, "error_other", "already saved")
        self._status[record_id] = "approved"
        return GateResult(True, 200, "approved")

    def save(self, record_id: str, verdict: dict) -> GateResult:
        if self.force_refuse:
            return GateResult(False, 409, "refused_forced", "mock gate told to refuse")
        if validate_doc("verdict.v1", verdict):
            return GateResult(False, 422, "refused_invalid", "verdict is not valid verdict.v1")
        if self._status.get(record_id) != "approved":
            return GateResult(False, 409, "refused_no_approval", "no approval recorded")
        if verdict.get("record_id") != record_id:
            return GateResult(False, 422, "refused_mismatch", "verdict record_id differs")
        if _unresolved(verdict):
            return GateResult(
                False, 409, "refused_unresolved_flags", "record has unresolved verdict flags"
            )
        self._status[record_id] = "saved"
        return GateResult(True, 200, "saved")


_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class HttpGate:
    """Thin client for m5's API. `server_ids` maps record.v1 record_id -> m5 database UUID."""

    def __init__(
        self,
        base_url: str,
        *,
        username: str,
        password: str,
        server_ids: dict[str, str],
        client: httpx.Client | None = None,
        timeout_s: float = 10.0,
    ):
        host = urlsplit(base_url).hostname
        if host not in _LOOPBACK:
            raise ValueError("API_URL must point to this computer (127.0.0.1)")
        self.force_refuse = False
        self._username = username
        self._password = password
        self._server_ids = dict(server_ids)
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout_s)
        self._token: str | None = None
        self._status: dict[str, str] = {}

    def status(self, record_id: str) -> str | None:
        return self._status.get(record_id)

    def _login(self) -> None:
        r = self._client.post(
            "/auth/token", json={"username": self._username, "password": self._password}
        )
        if r.status_code != 200:
            raise PermissionError(r.status_code)
        self._token = r.json()["access_token"]

    def _post(self, record_id: str, action: str, body: dict | None) -> GateResult:
        sid = self._server_ids.get(record_id)
        if not sid:
            return GateResult(False, 0, "refused_no_server_id", record_id)
        try:
            if self._token is None:
                self._login()
            r = self._client.post(
                f"/records/{sid}/{action}",
                json=body,
                headers={"Authorization": f"Bearer {self._token}"},
            )
        except PermissionError as e:
            return GateResult(
                False, int(e.args[0]) if e.args else 401, "refused_auth", "login refused"
            )
        except httpx.HTTPError as e:
            return GateResult(False, 0, "error_network", type(e).__name__)
        try:
            msg = str(r.json().get("error", ""))
        except (ValueError, AttributeError):
            msg = ""
        if r.status_code == 200:
            code = "saved" if action == "save" else "approved"
            self._status[record_id] = code
            return GateResult(True, 200, code, msg)
        code = {
            409: "refused_unresolved_flags",
            422: "refused_mismatch",
            401: "refused_auth",
            403: "refused_auth",
            404: "refused_no_server_id",
        }.get(r.status_code, "error_other")
        return GateResult(False, r.status_code, code, msg)

    def approve(self, record_id: str) -> GateResult:
        return self._post(record_id, "approve", None)

    def save(self, record_id: str, verdict: dict) -> GateResult:
        return self._post(record_id, "save", {"verdict": verdict})


def make_gate():
    """MODE=live + API_URL -> HttpGate (credentials from env/.env, server-side only); else MockGate."""
    if os.environ.get("MODE", "mock") == "live" and os.environ.get("API_URL"):
        ids_path = os.environ.get("M6_SERVER_IDS", "")
        server_ids = json.loads(Path(ids_path).read_text(encoding="utf-8")) if ids_path else {}
        return HttpGate(
            os.environ["API_URL"],
            username=os.environ.get("M6_API_USER", ""),
            password=os.environ.get("M6_API_PASSWORD", ""),
            server_ids=server_ids,
        )
    return MockGate(force_refuse=os.environ.get("M6_MOCK_GATE_REFUSE") == "1")
