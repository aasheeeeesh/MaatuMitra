"""Fix pass F2-F8 (security audit 2026-11-10). Each test reproduces the audit attempt first."""

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from m5_backend.app.auth import Principal
from m5_backend.app.config import load_settings
from m5_backend.app.db import Database
from m5_backend.app.export import hmac_key_bytes, pseudonym, suppress_small_cells

REPO = Path(__file__).resolve().parents[2]


def p(env, key):
    u = env.directory.by_key(key)
    return Principal(u.id, u.role, u.facility_id)


# ------------------------------------------------------------------ F7 (no database needed)
def test_f7_env_example_has_no_owner_role_as_bootstrap_user():
    text = (REPO / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^POSTGRES_USER=owner_role\s*$", text, re.M) is None
    assert re.search(r"^POSTGRES_USER=mm_bootstrap\s*$", text, re.M)
    assert re.search(r"^OWNER_DB_PASSWORD=REPLACE_ME", text, re.M)
    for line in text.splitlines():
        if not line.startswith("#") and ("PASSWORD" in line or "KEY" in line):
            assert line.split("=", 1)[1].startswith("REPLACE_ME"), line


def test_f7_owner_password_is_separate_from_docker_bootstrap_password():
    env = {"POSTGRES_USER": "mm_bootstrap", "POSTGRES_PASSWORD": "bootstrap-pw"}
    assert load_settings(env_file=Path("nonexistent.env"), environ=env).owner_password is None
    env["OWNER_DB_PASSWORD"] = "owner-pw"
    assert load_settings(env_file=Path("nonexistent.env"), environ=env).owner_password == "owner-pw"
    legacy = {"POSTGRES_USER": "owner_role", "POSTGRES_PASSWORD": "legacy"}
    assert (
        load_settings(env_file=Path("nonexistent.env"), environ=legacy).owner_password == "legacy"
    )


# ------------------------------------------------------------------ F3 (pure)
def _row(pid, band="25-34", sex="F", month=10, et="nurse_consult"):
    return (pid, band, sex, et, datetime(2026, month, 3, tzinfo=UTC), {}, "draft")


def test_f3_small_cells_are_suppressed_pure():
    rows = [_row(uuid.uuid4()) for _ in range(5)] + [
        _row(uuid.uuid4(), band="0-4") for _ in range(4)
    ]
    kept = suppress_small_cells(rows, 5)
    assert len(kept) == 5 and all(r[1] == "25-34" for r in kept)
    # one patient with 5 visits is ONE patient, not a cell of 5
    same = uuid.uuid4()
    assert suppress_small_cells([_row(same) for _ in range(5)], 5) == []
    assert len(suppress_small_cells([_row(same)], 1)) == 1
    with pytest.raises(ValueError):
        suppress_small_cells(rows, 0)


# ------------------------------------------------------------------ F3 / F4 (database)
@pytest.mark.needs_db
def test_f3_default_export_has_only_cells_of_five_or_more(env):
    n = env.export()
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        cells = c.execute("SELECT age_band, sex, encounter_month, encounter_type, count(DISTINCT pseudonym)"
                          " FROM research.encounters_deid GROUP BY 1,2,3,4").fetchall()  # fmt: skip
    assert n >= 5 and cells and all(cnt >= 5 for *_, cnt in cells), cells
    key, ids = hmac_key_bytes(env.settings), env.seed.patients
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        ps = {r[0] for r in c.execute("SELECT pseudonym FROM research.encounters_deid")}
    # the three original consented patients are alone in their cells -> suppressed
    for k in ("A1", "A2", "A3"):
        assert pseudonym(key, ids[k]) not in ps
    # with k=1 nothing is suppressed (shows the filter, not missing data, is what hides them)
    from m5_backend.app.export import run_export

    run_export(env.settings, env.dbname, k_min=1)
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        ps1 = {r[0] for r in c.execute("SELECT pseudonym FROM research.encounters_deid")}
    assert pseudonym(key, ids["A1"]) in ps1
    env.export()


@pytest.mark.needs_db
def test_f4_withdrawal_removes_research_rows_immediately(env):
    key, pid = hmac_key_bytes(env.settings), env.seed.patients["C1"]
    ps_c1 = pseudonym(key, pid)
    env.export()

    def exported():
        with env.owner_conn() as c, c.transaction():
            c.execute("SET LOCAL ROLE maint_role")
            return {r[0] for r in c.execute("SELECT pseudonym FROM research.encounters_deid")}

    assert ps_c1 in exported()
    try:
        with env.owner_conn() as c, c.transaction():
            c.execute("SET LOCAL ROLE maint_role")
            c.execute(
                "UPDATE clinic.consents SET research_ok = false, updated_at = now() WHERE patient_id = %s",
                (pid,),
            )
        after = exported()  # NO re-export in between
        assert ps_c1 not in after
        with env.owner_conn() as c, c.transaction():
            c.execute("SET LOCAL ROLE maint_role")
            assert (
                c.execute(
                    "SELECT count(*) FROM research.pseudonym_map WHERE patient_id = %s", (pid,)
                ).fetchone()[0]
                == 0
            )
        # the other cohort members are untouched by the trigger
        assert pseudonym(key, env.seed.patients["C2"]) in after
    finally:
        with env.owner_conn() as c, c.transaction():
            c.execute("SET LOCAL ROLE maint_role")
            c.execute("UPDATE clinic.consents SET research_ok = true WHERE patient_id = %s", (pid,))
        env.export()


@pytest.mark.needs_db
def test_f4_researcher_cannot_read_pseudonym_map(env):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with env.api_db.request_tx(p(env, "R1"), commit=False) as cur:
            cur.execute("SELECT * FROM research.pseudonym_map")


# ------------------------------------------------------------------ F2
@pytest.mark.needs_db
def test_f2_researcher_cannot_write_an_audit_row_as_physician(env):
    ph = env.seed.users["P1"]
    with pytest.raises(psycopg.errors.RaiseException):
        with env.api_db.request_tx(p(env, "R1"), commit=False) as cur:
            cur.execute("SELECT set_config('app.role', 'physician', true),"
                        " set_config('app.user_id', %s, true)", (str(ph),))  # fmt: skip
            cur.execute("SELECT app.audit_write('approve', 'records', NULL, 'allow')")
    # a nurse session cannot borrow a physician's user id either
    with pytest.raises(psycopg.errors.RaiseException):
        with env.api_db.request_tx(p(env, "N1"), commit=False) as cur:
            cur.execute("SELECT set_config('app.user_id', %s, true)", (str(ph),))
            cur.execute("SELECT app.audit_write('approve', 'records', NULL, 'allow')")
    # a session with NO valid role / user cannot write at all
    with env.api_raw_conn() as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT app.audit_write('select', 'patients', NULL, 'allow')")
    # a legitimate request still records the real role and user
    with env.api_db.request_tx(p(env, "R1")) as cur:
        cur.execute("SELECT set_config('app.role', 'physician', true)")  # ignored now
        cur.execute("SELECT app.audit_write('list', 'research_export', NULL, 'allow')")
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        row = c.execute("SELECT user_id, app_role FROM clinic.audit_log WHERE action = 'list' AND table_name = 'research_export'"
                        " ORDER BY at DESC LIMIT 1").fetchone()  # fmt: skip
    assert row == (env.seed.users["R1"], "researcher")


# ------------------------------------------------------------------ F5
@pytest.mark.needs_db
def test_f5_injected_session_level_set_role_does_not_reach_next_request(env):
    db = Database(env.settings.conninfo("api"), pool_size=1)
    try:
        # the audit attempt G-2: a committed request ends with SESSION-level SET ROLE / set_config
        with db.request_tx(p(env, "N1")) as cur:
            cur.connection.execute("SET ROLE physician_role")
            cur.execute(
                "SELECT set_config('app.facility_id', %s, false)", (str(env.seed.facilities["F2"]),)
            )
        with db.raw_connection() as conn:
            assert conn.execute("SELECT current_user, session_user").fetchone() == (
                "api_login",
                "api_login",
            )
            assert conn.execute("SELECT current_setting('app.facility_id', true)").fetchone()[
                0
            ] in (None, "")
        # and through raw_connection as well
        with db.raw_connection() as conn:
            conn.execute("SET ROLE physician_role")
        with db.raw_connection() as conn:
            assert conn.execute("SELECT current_user").fetchone()[0] == "api_login"
    finally:
        db.close()


# ------------------------------------------------------------------ F6
@pytest.mark.needs_db
def test_f6_api_refuses_to_start_with_unsafe_login(env):
    from m5_backend.app.main import create_app

    s = env.settings
    for who in ("bootstrap", "owner"):  # superuser / table owner
        with pytest.raises(RuntimeError, match="unsafe database login"):
            create_app(s, Database(s.conninfo(who)), env.directory, env.audio_dir)
    # BYPASSRLS login
    with env.bootstrap_conn() as b:
        b.execute("DROP ROLE IF EXISTS tmp_bypass_login")
        b.execute("CREATE ROLE tmp_bypass_login LOGIN BYPASSRLS PASSWORD 'tmp-pw-synthetic'")
        b.execute(f"GRANT CONNECT ON DATABASE {env.dbname} TO tmp_bypass_login")
    try:
        ci = make_conninfo(host=s.pg_host, port=s.pg_port, dbname=env.dbname, user="tmp_bypass_login",
                           password="tmp-pw-synthetic")  # fmt: skip
        with pytest.raises(RuntimeError, match="unsafe database login"):
            create_app(s, Database(ci), env.directory, env.audio_dir)
    finally:
        with env.bootstrap_conn() as b:
            b.execute("DROP OWNED BY tmp_bypass_login")
            b.execute("DROP ROLE tmp_bypass_login")
    # the real login passes
    create_app(s, Database(s.conninfo("api")), env.directory, env.audio_dir)


# ------------------------------------------------------------------ F8 (partial)
@pytest.mark.needs_db
def test_f8_patient_ref_is_not_a_uuid_prefix(client, env):
    from m5_backend.app.auth import issue_token

    h = {"Authorization": f"Bearer {issue_token(env.settings, env.directory.by_key('Ph1'))}"}
    pid = env.seed.patients["A1"]
    r = client.post("/pharmacist/active-patient", headers=h, json={"patient_id": str(pid)})
    assert r.status_code == 200
    ref = r.json()["orders"][0]["patient_ref"]
    assert re.fullmatch(r"[0-9a-f]{10,}", ref)
    assert ref != str(pid).replace("-", "")[: len(ref)] and not str(pid).replace(
        "-", ""
    ).startswith(ref[:6])
    # stable for the same patient, different for another patient
    again = client.get("/pharmacist/orders", headers=h).json()[0]["patient_ref"]
    assert again == ref
    with env.owner_conn() as c, c.transaction():
        c.execute("SET LOCAL ROLE maint_role")
        refs = [x[0] for x in c.execute("SELECT ref FROM clinic.patients")]
    assert len(set(refs)) == len(refs)
