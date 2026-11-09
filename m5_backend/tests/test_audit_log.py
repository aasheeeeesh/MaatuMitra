"""audit_log is append-only: UPDATE / DELETE / TRUNCATE fail for every role, owner and superuser."""

import psycopg
import pytest

from m5_backend.app.auth import Principal

pytestmark = pytest.mark.needs_db
ROLE_KEYS = {
    "asha": "A1",
    "nurse": "N1",
    "physician": "P1",
    "pharmacist": "Ph1",
    "researcher": "R1",
}
STMTS = [
    "UPDATE clinic.audit_log SET outcome = 'deny'",
    "DELETE FROM clinic.audit_log",
    "TRUNCATE clinic.audit_log",
]


def p(env, key):
    u = env.directory.by_key(key)
    return Principal(u.id, u.role, u.facility_id)


@pytest.mark.parametrize("role", list(ROLE_KEYS))
@pytest.mark.parametrize("stmt", STMTS)
def test_app_roles_cannot_modify_audit_log(env, role, stmt):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with env.api_db.request_tx(p(env, ROLE_KEYS[role]), commit=False) as cur:
            cur.execute(stmt)


@pytest.mark.parametrize("role", list(ROLE_KEYS))
def test_app_roles_cannot_read_or_insert_audit_log_directly(env, role):
    for stmt in ["SELECT 1 FROM clinic.audit_log LIMIT 1",
                 "INSERT INTO clinic.audit_log (app_role, action, table_name, outcome) VALUES ('nurse','select','patients','allow')"]:  # fmt: skip
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with env.api_db.request_tx(p(env, ROLE_KEYS[role]), commit=False) as cur:
                cur.execute(stmt)


@pytest.mark.parametrize("stmt", STMTS)
def test_owner_cannot_modify_audit_log(env, stmt):
    with env.owner_conn() as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute(stmt)


@pytest.mark.parametrize("stmt", STMTS)
def test_even_superuser_hits_the_trigger(env, stmt):
    with env.bootstrap_conn() as c:
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            c.execute(stmt)


def test_audit_write_takes_user_from_context_not_arguments(env):
    a1 = p(env, "A1")
    with env.api_db.request_tx(a1) as cur:
        cur.execute("SELECT app.audit_write('select', 'patients', NULL, 'allow')")
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        row = c.execute(
            "SELECT user_id, app_role FROM clinic.audit_log WHERE action = 'select' AND table_name = 'patients'"
            " ORDER BY at DESC LIMIT 1"
        ).fetchone()
    assert row == (a1.user_id, "asha")


def test_audit_log_refuses_free_text(env):
    with pytest.raises(psycopg.errors.CheckViolation):
        with env.api_db.request_tx(p(env, "N1"), commit=False) as cur:
            cur.execute(
                "SELECT app.audit_write('patient said she is pregnant', 'patients', NULL, 'allow')"
            )


def test_audit_write_without_context_fails(env):
    with env.owner_conn() as c, c.transaction() as tx:
        c.execute("SET LOCAL ROLE maint_role")
        with pytest.raises(psycopg.errors.RaiseException):
            c.execute("SELECT app.audit_write('select', 'patients', NULL, 'allow')")
        raise psycopg.Rollback(tx)
