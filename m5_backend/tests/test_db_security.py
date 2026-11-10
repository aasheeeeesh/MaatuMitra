"""Database-level security properties (needs PostgreSQL 16)."""

import psycopg
import pytest

from m5_backend.app.auth import Principal

pytestmark = pytest.mark.needs_db

OURS = ["owner_role", "api_login", "asha_role", "nurse_role", "physician_role", "pharmacist_role",
        "researcher_role", "maint_role", "pharm_view_owner", "audit_writer"]  # fmt: skip
APP = ["asha_role", "nurse_role", "physician_role", "pharmacist_role", "researcher_role"]


def p(env, key):
    u = env.directory.by_key(key)
    return Principal(u.id, u.role, u.facility_id)


def test_no_role_is_superuser_or_bypassrls(env):
    with env.bootstrap_conn() as c:
        rows = c.execute(
            "SELECT rolname, rolsuper, rolbypassrls, rolcanlogin, rolinherit FROM pg_roles WHERE rolname = ANY(%s)",
            (OURS,),
        ).fetchall()
    assert len(rows) == len(OURS)
    for name, sup, byp, login, inherit in rows:
        assert not sup and not byp, name
        assert login == (name in ("owner_role", "api_login")), name
        if name == "api_login":
            assert inherit is False


def test_api_login_memberships_are_set_only(env):
    with env.bootstrap_conn() as c:
        rows = c.execute(
            "SELECT r.rolname, m.inherit_option, m.set_option FROM pg_auth_members m"
            " JOIN pg_roles r ON r.oid = m.roleid JOIN pg_roles u ON u.oid = m.member"
            " WHERE u.rolname = 'api_login'"
        ).fetchall()
    assert sorted(r[0] for r in rows) == sorted(APP)
    assert all(inh is False and st is True for _, inh, st in rows)


def test_every_table_has_rls_enabled_and_forced(env):
    with env.owner_conn() as c:
        rows = c.execute(
            "SELECT n.nspname || '.' || c.relname, c.relrowsecurity, c.relforcerowsecurity"
            " FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE c.relkind = 'r' AND n.nspname IN ('clinic', 'research')"
        ).fetchall()
    assert len(rows) == 13
    assert all(r[1] and r[2] for r in rows), rows


def test_ids_are_uuid_and_no_public_policies(env):
    with env.owner_conn() as c:
        types = c.execute(
            "SELECT table_name, data_type FROM information_schema.columns"
            " WHERE table_schema IN ('clinic','research') AND column_name = 'id'"
        ).fetchall()
        public = c.execute(
            "SELECT count(*) FROM pg_policies WHERE 'public' = ANY(roles)"
        ).fetchone()[0]
    assert types and all(t == "uuid" for _, t in types)
    assert public == 0


def test_api_login_has_no_table_privileges_of_its_own(env):
    with env.api_raw_conn() as c:
        for t in [
            "clinic.patients",
            "clinic.records",
            "clinic.audit_log",
            "research.encounters_deid",
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(f"SELECT 1 FROM {t} LIMIT 1")


def test_table_owner_with_no_policy_sees_zero_rows(env):
    # FORCE RLS binds the owner too: owner_role has no policy -> 0 rows although rows exist.
    with env.owner_conn() as c:
        for t in ["facilities", "users", "households", "patients", "encounters", "records",
                  "medication_orders", "consents", "audit_log"]:  # fmt: skip
            assert c.execute(f"SELECT count(*) FROM clinic.{t}").fetchone()[0] == 0, t
        assert c.execute("SELECT count(*) FROM research.encounters_deid").fetchone()[0] == 0
        with c.transaction():
            c.execute("SET LOCAL ROLE maint_role")
            assert c.execute("SELECT count(*) FROM clinic.patients").fetchone()[0] >= 8


def test_role_with_grants_but_no_policy_sees_zero_rows(env):
    with env.bootstrap_conn() as c, c.transaction() as tx:
        c.execute("CREATE ROLE m5_probe_nopolicy NOLOGIN")
        c.execute("GRANT USAGE ON SCHEMA clinic, app TO m5_probe_nopolicy")
        c.execute("GRANT SELECT ON ALL TABLES IN SCHEMA clinic TO m5_probe_nopolicy")
        c.execute("SET LOCAL ROLE m5_probe_nopolicy")
        for t in [
            "households",
            "patients",
            "encounters",
            "records",
            "medication_orders",
            "consents",
        ]:
            assert c.execute(f"SELECT count(*) FROM clinic.{t}").fetchone()[0] == 0, t
        raise psycopg.Rollback(tx)  # the probe role disappears again


def test_pharmacist_and_researcher_have_no_base_table_grants(env):
    with env.bootstrap_conn() as c:
        for t in ["households", "patients", "encounters", "records", "medication_orders",
                  "consents", "audit_log", "users", "facilities"]:  # fmt: skip
            for r in ("pharmacist_role", "researcher_role"):
                got = c.execute(
                    "SELECT has_table_privilege(%s, %s, 'SELECT,INSERT,UPDATE,DELETE')",
                    (r, f"clinic.{t}"),
                ).fetchone()[0]
                assert got is False, (r, t)
        assert c.execute(
            "SELECT has_table_privilege('pharmacist_role','clinic.pharmacist_orders_v','SELECT')"
        ).fetchone()[0]
        assert c.execute(
            "SELECT has_table_privilege('researcher_role','research.encounters_deid','SELECT')"
        ).fetchone()[0]


def test_pharmacist_view_is_security_barrier_owned_by_narrow_role(env):
    with env.owner_conn() as c:
        opts, owner = c.execute(
            "SELECT c.reloptions, pg_get_userbyid(c.relowner) FROM pg_class c"
            " WHERE c.oid = 'clinic.pharmacist_orders_v'::regclass"
        ).fetchone()
    assert "security_barrier=true" in opts and owner == "pharm_view_owner"


def test_no_role_or_guc_leaks_to_next_transaction_on_pooled_connection(env):
    from m5_backend.app.db import Database

    db = Database(env.settings.conninfo("api"), pool_size=1)
    try:
        with db.request_tx(p(env, "A1")) as cur:
            assert cur.execute("SELECT current_user").fetchone()[0] == "asha_role"
        with db.raw_connection() as conn:
            row = conn.execute(
                "SELECT current_user, current_setting('app.user_id', true),"
                " current_setting('app.facility_id', true), current_setting('app.active_patient_id', true)"
            ).fetchone()
        assert row[0] == "api_login"
        assert all(v in (None, "") for v in row[1:]), row
    finally:
        db.close()


def test_reset_role_leaves_no_privileges(env):
    with env.api_db.request_tx(p(env, "N1"), commit=False) as cur:
        cur.execute("RESET ROLE")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT 1 FROM clinic.patients LIMIT 1")


def test_residual_raw_api_credentials_can_set_gucs(env):
    """DOCUMENTS THE RESIDUAL LIMIT (not a pass condition of the matrix): whoever holds the
    raw api_login password can SET ROLE to any app role and forge app.user_id. Mitigation:
    only the API process holds that credential (.env, git-ignored, 127.0.0.1 only)."""
    ids = env.seed
    with env.api_raw_conn() as c, c.transaction() as tx:
        c.execute("SET LOCAL ROLE asha_role")
        c.execute("SELECT set_config('app.user_id', %s, true)", (str(ids.users["A2"]),))
        seen = c.execute(
            "SELECT id FROM clinic.households WHERE id = %s", (ids.households["A2"],)
        ).fetchall()
        raise psycopg.Rollback(tx)
    assert len(seen) == 1  # forged context works at the DB level -> credentials must stay secret


def test_saved_check_constraint(env):
    ids = env.seed
    # For a physician the RLS WITH CHECK refuses first (42501); the CHECK constraint is the
    # second layer, proven below with maint_role, which has a permissive policy.
    with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.CheckViolation)):
        with env.api_db.request_tx(p(env, "P1"), commit=False) as cur:
            cur.execute(
                "UPDATE clinic.records SET status = 'saved', approved_by = NULL, approved_at = NULL WHERE id = %s",
                (ids.records["P1"],),
            )
    with env.owner_conn() as c, c.transaction() as tx:
        c.execute("SET LOCAL ROLE maint_role")
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute(
                "INSERT INTO clinic.records (encounter_id, json, status) VALUES (%s, '{}', 'saved')",
                (ids.encounters["P1"],),
            )
        raise psycopg.Rollback(tx)


def test_nurse_cannot_approve_or_see_saved_records(env):
    ids = env.seed
    with env.api_db.request_tx(p(env, "N1"), commit=False) as cur:
        assert (
            cur.execute(
                "SELECT 1 FROM clinic.records WHERE id = %s", (ids.records["P1_saved"],)
            ).fetchall()
            == []
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with env.api_db.request_tx(p(env, "N1"), commit=False) as cur:
            cur.execute(
                "UPDATE clinic.records SET status = 'approved', approved_by = %s, approved_at = now() WHERE id = %s",
                (ids.users["N1"], ids.records["N1"]),
            )


def test_physician_cannot_approve_in_someone_elses_name(env):
    ids = env.seed
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with env.api_db.request_tx(p(env, "P1"), commit=False) as cur:
            cur.execute(
                "UPDATE clinic.records SET status = 'approved', approved_by = %s, approved_at = now() WHERE id = %s",
                (ids.users["P2"], ids.records["P1"]),
            )


def test_saved_record_is_immutable(env):
    ids = env.seed
    with env.api_db.request_tx(p(env, "P1"), commit=False) as cur:
        cur.execute(
            "UPDATE clinic.records SET json = json WHERE id = %s", (ids.records["P1_saved"],)
        )
        assert cur.rowcount == 0
