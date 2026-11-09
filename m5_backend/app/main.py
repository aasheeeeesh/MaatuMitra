"""MaatuMitra sandbox API (FastAPI). Binds to 127.0.0.1 only. All data is synthetic.

Access control lives in the DATABASE (forced RLS). The API's jobs: verify the token, open ONE
transaction per request as the token's app role, run parameterised SQL, audit, and return
generic errors. Rows hidden by RLS look like "not found" (no existence oracle).

Run: uv run python -m m5_backend.app.main     (needs a reachable Postgres, see README)
"""

from __future__ import annotations

import hmac
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from psycopg.types.json import Jsonb
from starlette.exceptions import HTTPException as StarletteHTTPException

from contracts.validate import validate_doc

from . import models
from .auth import AuthError, Principal, issue_token, verify_token
from .config import Settings, load_settings
from .db import Database, audit
from .directory import Directory, load_directory
from .ratelimit import LoginRateLimiter

GENERIC = {
    400: "bad request",
    401: "unauthorized",
    403: "forbidden",
    404: "not found",
    405: "method not allowed",
    409: "conflict",
    422: "invalid request",
    429: "too many requests",
    500: "internal error",
}
ACTIVE_PATIENT_TTL_S = 600


class ApiError(Exception):
    def __init__(self, status: int, message: str | None = None):
        self.status = status
        self.message = message or GENERIC.get(status, "error")


def _err(status: int, message: str | None = None, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        {"error": message or GENERIC.get(status, "error")}, status_code=status, headers=headers
    )


def _status_for_db_error(exc: psycopg.Error) -> int:
    if isinstance(exc, psycopg.errors.InsufficientPrivilege):  # grants AND RLS WITH CHECK (42501)
        return 403
    if isinstance(
        exc,
        psycopg.errors.IntegrityError | psycopg.errors.DataError,
    ):
        return 422
    return 500


def _row(cur: psycopg.Cursor, r: tuple | None) -> dict[str, Any] | None:
    if r is None:
        return None
    return {d.name: v for d, v in zip(cur.description, r, strict=True)}


def principal(request: Request) -> Principal:
    """Bearer token -> verified Principal. The role comes ONLY from the verified token."""
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer ") or len(h) > 4200:
        raise ApiError(401)
    try:
        return verify_token(request.app.state.settings, h[7:].strip(), request.app.state.directory)
    except (AuthError, ValueError) as exc:
        raise ApiError(401) from exc


Auth = Annotated[Principal, Depends(principal)]


def create_app(
    settings: Settings | None = None,
    db: Database | None = None,
    directory: Directory | None = None,
    audio_dir: Path | None = None,
    rate_limiter: LoginRateLimiter | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    directory = directory or load_directory()
    if db is None:
        db = Database(settings.conninfo("api"))
    audio_root = Path(audio_dir or settings.audio_dir or ".").resolve()
    limiter = rate_limiter or LoginRateLimiter(max_attempts=5, window_s=60)
    ip_limiter = LoginRateLimiter(max_attempts=30, window_s=60)
    active: dict[uuid.UUID, tuple[uuid.UUID, float]] = {}
    active_lock = threading.Lock()

    app = FastAPI(title="MaatuMitra sandbox API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db = db

    # ------------------------------------------------------------ errors: generic only
    @app.exception_handler(RequestValidationError)
    async def _validation(_req, _exc):
        return _err(422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_req, exc: StarletteHTTPException):
        return _err(exc.status_code if exc.status_code in GENERIC else 400)

    @app.exception_handler(ApiError)
    async def _api(_req, exc: ApiError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return _err(exc.status, exc.message, headers)

    @app.exception_handler(Exception)
    async def _any(_req, _exc):
        return _err(500)

    @app.middleware("http")
    async def _headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ------------------------------------------------------------ auth
    app.state.settings = settings
    app.state.directory = directory

    def run(
        p: Principal,
        action: str,
        table: str,
        row_id: uuid.UUID | None,
        fn: Callable[[psycopg.Cursor], Any],
        active_patient_id: uuid.UUID | None = None,
    ) -> Any:
        """One request = one transaction as the token's role. Audited allow/deny/error."""
        try:
            with db.request_tx(p, active_patient_id=active_patient_id) as cur:
                out = fn(cur)
                cur.execute(
                    "SELECT app.audit_write(%s, %s, %s, %s)", (action, table, row_id, "allow")
                )
                return out
        except ApiError as exc:
            _safe_audit(p, action, table, row_id, "deny")
            raise exc
        except psycopg.Error as exc:
            status = _status_for_db_error(exc)
            _safe_audit(p, action, table, row_id, "deny" if status in (403, 404) else "error")
            raise ApiError(status) from None

    def _safe_audit(p, action, table, row_id, outcome) -> None:
        try:
            audit(db, p, action, table, row_id, outcome)
        except psycopg.Error:
            pass  # the request already failed closed; never leak details

    def one(cur: psycopg.Cursor, query: str, params: tuple) -> dict[str, Any]:
        r = _row(cur, cur.execute(query, params).fetchone())
        if r is None:
            raise ApiError(404)
        return r

    def all_rows(cur: psycopg.Cursor, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        rows = cur.execute(query, params).fetchall()
        return [_row(cur, r) for r in rows]

    # ------------------------------------------------------------ mock issuer (sandbox only)
    @app.post("/auth/token")
    def login(body: models.LoginIn, request: Request):
        if settings.mode == "production":
            raise ApiError(404)
        ip = request.client.host if request.client else "unknown"
        if not ip_limiter.allow(ip) or not limiter.allow(f"{ip}|{body.username}"):
            raise ApiError(429)
        expected = settings.mock_login_password or ""
        try:
            user = directory.get(uuid.UUID(body.username))
        except ValueError:
            user = None
        ok_pw = bool(expected) and hmac.compare_digest(
            body.password.encode("utf-8"), expected.encode("utf-8")
        )
        if user is None or not ok_pw:
            raise ApiError(401)
        return {"access_token": issue_token(settings, user), "token_type": "bearer"}

    # ------------------------------------------------------------ households (ASHA)
    @app.get("/households")
    def list_households(p: Auth):
        return run(p, "list", "households", None, lambda c: all_rows(
            c, "SELECT id, facility_id, assigned_asha_id FROM clinic.households ORDER BY id"))  # fmt: skip

    @app.post("/households", status_code=201)
    def create_household(body: models.HouseholdIn, p: Auth):
        return run(p, "insert", "households", None, lambda c: one(
            c, "INSERT INTO clinic.households (facility_id, assigned_asha_id) VALUES (%s, %s) RETURNING id",
            (p.facility_id, p.user_id)))  # fmt: skip

    # ------------------------------------------------------------ patients

    @app.get("/patients")
    def list_patients(p: Auth, household_id: uuid.UUID | None = None):
        if household_id is None:
            q, args = (
                "SELECT id, household_id, facility_id, name_synthetic, age_band, sex FROM clinic.patients ORDER BY id",
                (),
            )
        else:
            q, args = (
                "SELECT id, household_id, facility_id, name_synthetic, age_band, sex FROM clinic.patients WHERE household_id = %s ORDER BY id",
                (household_id,),
            )
        return run(p, "list", "patients", None, lambda c: all_rows(c, q, args))

    @app.get("/patients/{patient_id}")
    def get_patient(patient_id: uuid.UUID, p: Auth):
        return run(p, "select", "patients", patient_id, lambda c: one(
            c, "SELECT id, household_id, facility_id, name_synthetic, age_band, sex FROM clinic.patients WHERE id = %s", (patient_id,)))  # fmt: skip

    @app.post("/patients", status_code=201)
    def create_patient(body: models.PatientIn, p: Auth):
        return run(p, "insert", "patients", None, lambda c: one(
            c, "INSERT INTO clinic.patients (household_id, facility_id, name_synthetic, age_band, sex)"
               " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (body.household_id, p.facility_id, body.name_synthetic, body.age_band, body.sex)))  # fmt: skip

    @app.patch("/patients/{patient_id}")
    def update_patient(patient_id: uuid.UUID, body: models.PatientUpdate, p: Auth):
        return run(p, "update", "patients", patient_id, lambda c: one(
            c, "UPDATE clinic.patients SET name_synthetic = COALESCE(%s, name_synthetic),"
               " age_band = COALESCE(%s, age_band), sex = COALESCE(%s, sex) WHERE id = %s RETURNING id",
            (body.name_synthetic, body.age_band, body.sex, patient_id)))  # fmt: skip

    # ------------------------------------------------------------ encounters + audio

    @app.get("/encounters/{encounter_id}")
    def get_encounter(encounter_id: uuid.UUID, p: Auth):
        return run(p, "select", "encounters", encounter_id, lambda c: one(
            c, "SELECT id, patient_id, author_id, facility_id, encounter_type, created_at FROM clinic.encounters WHERE id = %s", (encounter_id,)))  # fmt: skip

    @app.post("/encounters", status_code=201)
    def create_encounter(body: models.EncounterIn, p: Auth):
        return run(p, "insert", "encounters", None, lambda c: one(
            c, "INSERT INTO clinic.encounters (patient_id, author_id, facility_id, encounter_type)"
               " VALUES (%s, %s, %s, %s) RETURNING id",
            (body.patient_id, p.user_id, p.facility_id, body.encounter_type)))  # fmt: skip

    @app.patch("/encounters/{encounter_id}")
    def update_encounter(encounter_id: uuid.UUID, body: models.EncounterUpdate, p: Auth):
        return run(p, "update", "encounters", encounter_id, lambda c: one(
            c, "UPDATE clinic.encounters SET encounter_type = %s WHERE id = %s RETURNING id",
            (body.encounter_type, encounter_id)))  # fmt: skip

    @app.get("/encounters/{encounter_id}/audio")
    def get_audio(encounter_id: uuid.UUID, p: Auth):
        # Authorisation FIRST: the encounter must be visible to this caller under RLS.
        run(p, "audio", "audio", encounter_id, lambda c: one(
            c, "SELECT id FROM clinic.encounters WHERE id = %s", (encounter_id,)))  # fmt: skip
        path = (audio_root / f"{encounter_id}.wav").resolve()  # name built from a parsed UUID only
        if path.parent != audio_root or not path.is_file():
            raise ApiError(404)
        return FileResponse(path, media_type="audio/wav")

    # ------------------------------------------------------------ records + saved gate

    def _check_record(rec: dict) -> None:
        if validate_doc("record.v1", rec) or rec.get("status") not in ("draft", "flagged"):
            raise ApiError(422)

    @app.get("/records/{record_id}")
    def get_record(record_id: uuid.UUID, p: Auth):
        return run(p, "select", "records", record_id, lambda c: one(
            c, "SELECT id, encounter_id, json, status, approved_by, approved_at FROM clinic.records WHERE id = %s", (record_id,)))  # fmt: skip

    @app.post("/records", status_code=201)
    def create_record(body: models.RecordIn, p: Auth):
        _check_record(body.record)
        return run(p, "insert", "records", None, lambda c: one(
            c, "INSERT INTO clinic.records (encounter_id, json, status) VALUES (%s, %s, %s) RETURNING id",
            (body.encounter_id, Jsonb(body.record), body.record["status"])))  # fmt: skip

    @app.patch("/records/{record_id}")
    def update_record(record_id: uuid.UUID, body: models.RecordUpdate, p: Auth):
        _check_record(body.record)
        return run(p, "update", "records", record_id, lambda c: one(
            c, "UPDATE clinic.records SET json = %s, status = %s"
               " WHERE id = %s AND status IN ('draft', 'flagged') RETURNING id",
            (Jsonb(body.record), body.record["status"], record_id)))  # fmt: skip

    @app.post("/records/{record_id}/approve")
    def approve_record(record_id: uuid.UUID, p: Auth):
        return run(p, "approve", "records", record_id, lambda c: one(
            c, "UPDATE clinic.records SET status = 'approved', approved_by = %s, approved_at = now()"
               " WHERE id = %s AND status IN ('draft', 'flagged') RETURNING id, status",
            (p.user_id, record_id)))  # fmt: skip

    @app.post("/records/{record_id}/save")
    def save_record(record_id: uuid.UUID, body: models.SaveIn, p: Auth):
        verdict = body.verdict
        if validate_doc("verdict.v1", verdict):
            raise ApiError(422)
        unresolved = (
            not verdict["checks"]
            or not verdict["auto_acceptable"]
            or any(ch["status"] == "flag" for ch in verdict["checks"])
        )

        def do(c: psycopg.Cursor):
            r = one(
                c,
                "SELECT json->>'record_id' AS rid FROM clinic.records WHERE id = %s",
                (record_id,),
            )
            if r["rid"] != verdict["record_id"]:
                raise ApiError(422)
            if unresolved:
                raise ApiError(409, "record has unresolved verdict flags")
            return one(
                c,
                "UPDATE clinic.records SET status = 'saved', approved_by = %s, approved_at = now()"
                " WHERE id = %s AND status <> 'saved' RETURNING id, status",
                (p.user_id, record_id),
            )

        try:
            return run(p, "save", "records", record_id, do)
        except ApiError as exc:
            if exc.status == 409:
                _safe_audit(p, "save_rejected", "records", record_id, "deny")
            raise

    # ------------------------------------------------------------ medication orders

    @app.get("/medication-orders/{order_id}")
    def get_order(order_id: uuid.UUID, p: Auth):
        return run(p, "select", "medication_orders", order_id, lambda c: one(
            c, "SELECT id, encounter_id, patient_id, facility_id, drug, dose_value, dose_unit, frequency_per_day, duration_days, status FROM clinic.medication_orders WHERE id = %s", (order_id,)))  # fmt: skip

    @app.post("/medication-orders", status_code=201)
    def create_order(body: models.OrderIn, p: Auth):
        # patient and facility are taken from the (RLS-visible) encounter, never from the body
        return run(p, "insert", "medication_orders", None, lambda c: one(
            c, "INSERT INTO clinic.medication_orders (encounter_id, patient_id, facility_id, drug,"
               " dose_value, dose_unit, frequency_per_day, duration_days, status)"
               " SELECT e.id, e.patient_id, e.facility_id, %s, %s, %s, %s, %s, %s"
               " FROM clinic.encounters e WHERE e.id = %s RETURNING id",
            (body.drug, body.dose_value, body.dose_unit, body.frequency_per_day, body.duration_days,
             body.status, body.encounter_id)))  # fmt: skip

    @app.patch("/medication-orders/{order_id}")
    def update_order(order_id: uuid.UUID, body: models.OrderUpdate, p: Auth):
        return run(p, "update", "medication_orders", order_id, lambda c: one(
            c, "UPDATE clinic.medication_orders SET drug = COALESCE(%s, drug),"
               " dose_value = COALESCE(%s, dose_value), dose_unit = COALESCE(%s, dose_unit),"
               " frequency_per_day = COALESCE(%s, frequency_per_day),"
               " duration_days = COALESCE(%s, duration_days), status = COALESCE(%s, status)"
               " WHERE id = %s RETURNING id",
            (body.drug, body.dose_value, body.dose_unit, body.frequency_per_day, body.duration_days,
             body.status, order_id)))  # fmt: skip

    # ------------------------------------------------------------ pharmacist

    @app.post("/pharmacist/active-patient")
    def set_active_patient(body: models.ActivePatientIn, p: Auth):
        """Checks a ready order exists for this patient at HER facility (through the view),
        then remembers the active patient server-side for a short time. Always audited.
        Limit: this cannot prove the patient is physically present."""

        def do(c):
            rows = all_rows(
                c,
                "SELECT order_id, patient_ref, drug, dose_value, dose_unit, frequency_per_day, duration_days, status FROM clinic.pharmacist_orders_v ORDER BY order_id",
            )
            if not rows:
                raise ApiError(404)
            return rows

        rows = run(p, "set_active_patient", "pharmacist_orders_v", body.patient_id, do,
                   active_patient_id=body.patient_id)  # fmt: skip
        with active_lock:
            active[p.user_id] = (body.patient_id, time.monotonic() + ACTIVE_PATIENT_TTL_S)
        return {"orders": rows}

    @app.get("/pharmacist/orders")
    def pharmacist_orders(p: Auth):
        with active_lock:
            a = active.get(p.user_id)
        if a is None or a[1] < time.monotonic():
            raise ApiError(404)
        return run(p, "list", "pharmacist_orders_v", a[0], lambda c: all_rows(
            c, "SELECT order_id, patient_ref, drug, dose_value, dose_unit, frequency_per_day, duration_days, status FROM clinic.pharmacist_orders_v ORDER BY order_id"),
            active_patient_id=a[0])  # fmt: skip

    # ------------------------------------------------------------ research
    @app.get("/research/encounters")
    def research_rows(p: Auth):
        return run(p, "list", "research_export", None, lambda c: all_rows(
            c, "SELECT pseudonym, age_band, sex, encounter_type, encounter_month, record_status,"
               " symptoms_present, symptoms_absent, medications FROM research.encounters_deid"
               " ORDER BY pseudonym, encounter_month, encounter_type"))  # fmt: skip

    return app


def main() -> int:
    import uvicorn

    s = load_settings()
    if s.api_host != "127.0.0.1":
        raise SystemExit("refusing to bind anywhere except 127.0.0.1 (constraint 4)")
    uvicorn.run(create_app(s), host="127.0.0.1", port=s.api_port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
