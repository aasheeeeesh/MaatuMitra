"""Per-request database context: ONE transaction, SET LOCAL ROLE, transaction-local GUCs.

The API logs in as api_login (no table privileges, NOINHERIT). Inside every request:
    BEGIN; SET LOCAL ROLE <app_role>; set_config('app.user_id', ..., true); ...; COMMIT
Only SET LOCAL / set_config(..., true) is used, so nothing leaks to the next transaction on a
pooled connection. The role name comes from a fixed allowlist keyed by the VERIFIED token role.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

from .auth import Principal

DB_ROLE = {
    "asha": "asha_role",
    "nurse": "nurse_role",
    "physician": "physician_role",
    "pharmacist": "pharmacist_role",
    "researcher": "researcher_role",
}


class Database:
    """Tiny LIFO connection pool (enough for a sandbox; lets tests check pool hygiene)."""

    def __init__(self, conninfo: str, pool_size: int = 4):
        self.conninfo = conninfo
        self.pool_size = pool_size
        self._free: list[psycopg.Connection] = []
        self._lock = threading.Lock()

    def _get(self) -> psycopg.Connection:
        with self._lock:
            while self._free:
                c = self._free.pop()
                if not c.closed:
                    return c
        conn = psycopg.connect(self.conninfo, autocommit=True)
        # DISCARD ALL (see _put) also drops server-side prepared statements, so the client must
        # not auto-prepare any (it would otherwise reuse a name the server has forgotten).
        conn.prepare_threshold = None
        return conn

    def _put(self, conn: psycopg.Connection) -> None:
        if conn.closed or conn.info.transaction_status != TransactionStatus.IDLE:
            conn.close()
            return
        # F5: forget EVERYTHING session-level (SET ROLE, SET app.*, temp objects, prepared
        # statements) before the connection is reused. Fails closed: if the reset fails, the
        # connection is thrown away.
        try:
            conn.execute("DISCARD ALL")
        except psycopg.Error:
            conn.close()
            return
        if conn.info.transaction_status != TransactionStatus.IDLE:
            conn.close()
            return
        with self._lock:
            if len(self._free) < self.pool_size:
                self._free.append(conn)
                return
        conn.close()

    def verify_login(self) -> None:
        """F6: refuse to serve requests with a dangerous database login.

        The login must not be a superuser, must not have BYPASSRLS, must not own any table,
        view or function in the app schemas, and must not be able to create roles or databases.
        Raises RuntimeError("unsafe database login: ...") so the API does not start.
        """
        with self.raw_connection() as conn:
            row = conn.execute(
                "SELECT r.rolsuper, r.rolbypassrls, r.rolcreaterole, r.rolcreatedb, r.rolreplication,"
                " (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                "   WHERE n.nspname IN ('clinic', 'research', 'app') AND c.relowner = r.oid),"
                " (SELECT count(*) FROM pg_proc f JOIN pg_namespace n ON n.oid = f.pronamespace"
                "   WHERE n.nspname IN ('clinic', 'research', 'app') AND f.proowner = r.oid),"
                " current_user = session_user"
                " FROM pg_roles r WHERE r.rolname = session_user"
            ).fetchone()
        if row is None:
            raise RuntimeError("unsafe database login: role not found")
        names = ("superuser", "BYPASSRLS", "CREATEROLE", "CREATEDB", "REPLICATION")
        problems = [n for n, v in zip(names, row[:5], strict=True) if v]
        if row[5]:
            problems.append("owns tables")
        if row[6]:
            problems.append("owns functions")
        if not row[7]:
            problems.append("session role differs from login")
        if problems:
            raise RuntimeError("unsafe database login: " + ", ".join(problems))

    def close(self) -> None:
        with self._lock:
            for c in self._free:
                c.close()
            self._free.clear()

    @contextmanager
    def raw_connection(self) -> Iterator[psycopg.Connection]:
        conn = self._get()
        try:
            yield conn
        finally:
            self._put(conn)

    @contextmanager
    def request_tx(
        self,
        principal: Principal,
        *,
        active_patient_id: uuid.UUID | None = None,
        commit: bool = True,
    ) -> Iterator[psycopg.Cursor]:
        role = DB_ROLE[principal.role]  # KeyError -> fail closed
        conn = self._get()
        try:
            with conn.transaction() as tx:
                cur = conn.cursor()
                cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                cur.execute(
                    "SELECT set_config('app.user_id', %s, true),"
                    " set_config('app.facility_id', %s, true),"
                    " set_config('app.active_patient_id', %s, true)",
                    (
                        str(principal.user_id),
                        str(principal.facility_id),
                        str(active_patient_id) if active_patient_id else "",
                    ),
                )
                yield cur
                if not commit:
                    raise psycopg.Rollback(tx)
        finally:
            self._put(conn)


def audit(
    db: Database,
    principal: Principal,
    action: str,
    table: str,
    row_id: uuid.UUID | None,
    outcome: str,
) -> None:
    """Write one audit row in its OWN transaction (used after a denied/failed request)."""
    with db.request_tx(principal) as cur:
        cur.execute("SELECT app.audit_write(%s, %s, %s, %s)", (action, table, row_id, outcome))
