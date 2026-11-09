"""Database setup tool: roles (bootstrap superuser), database, migrations (owner_role), seed, export.

    uv run python -m m5_backend.scripts.dbtool all            # roles + fresh DB + migrate + seed + export
    uv run python -m m5_backend.scripts.dbtool probe
    uv run python -m m5_backend.scripts.dbtool export

The bootstrap superuser is used ONLY here (roles + CREATE/DROP DATABASE). Requests never use it.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from m5_backend.app.config import Settings, load_settings

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
APP_ROLES = ["asha_role", "nurse_role", "physician_role", "pharmacist_role", "researcher_role"]
HELPER_ROLES = ["maint_role", "pharm_view_owner", "audit_writer"]
SAFE = "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"


def probe(s: Settings) -> tuple[bool, str]:
    try:
        ci = s.conninfo("bootstrap", "postgres")
    except RuntimeError as exc:
        return False, str(exc)
    try:
        with psycopg.connect(ci, connect_timeout=3) as c:
            v = c.execute("SHOW server_version_num").fetchone()[0]
        if int(v) // 10000 != 16:
            return False, f"server_version_num={v}, need PostgreSQL 16"
        return True, f"server_version_num={v}"
    except psycopg.Error as exc:
        return False, f"{type(exc).__name__} connecting to {s.pg_host}:{s.pg_port}"


def bootstrap_roles(s: Settings) -> None:
    with psycopg.connect(s.conninfo("bootstrap", "postgres"), autocommit=True) as c:
        existing = {r[0] for r in c.execute("SELECT rolname FROM pg_roles")}

        def ensure(name: str, attrs: str, password: str | None) -> None:
            verb = "ALTER" if name in existing else "CREATE"
            q = sql.SQL(f"{verb} ROLE {{}} {attrs}").format(sql.Identifier(name))
            if password:
                q = q + sql.SQL(" PASSWORD {}").format(sql.Literal(password))
            c.execute(q)

        ensure("owner_role", f"LOGIN INHERIT {SAFE}", s.owner_password)
        ensure("api_login", f"LOGIN NOINHERIT {SAFE}", s.api_password)
        for r in APP_ROLES + HELPER_ROLES:
            ensure(r, f"NOLOGIN NOINHERIT {SAFE}", None)
        for r in APP_ROLES:
            c.execute(
                sql.SQL("GRANT {} TO api_login WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(r)
                )
            )
        for r in HELPER_ROLES:
            c.execute(
                sql.SQL("GRANT {} TO owner_role WITH INHERIT FALSE, SET TRUE").format(
                    sql.Identifier(r)
                )
            )
        # fail closed: nothing we create may be superuser / BYPASSRLS
        bad = c.execute(
            "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s) AND (rolsuper OR rolbypassrls)",
            (["owner_role", "api_login", *APP_ROLES, *HELPER_ROLES],),
        ).fetchall()
        if bad:
            raise RuntimeError(f"refusing: superuser/BYPASSRLS roles found: {bad}")


def recreate_database(s: Settings, dbname: str) -> None:
    with psycopg.connect(s.conninfo("bootstrap", "postgres"), autocommit=True) as c:
        c.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))
        c.execute(
            sql.SQL(
                "CREATE DATABASE {} OWNER owner_role TEMPLATE template0 ENCODING 'UTF8'"
            ).format(sql.Identifier(dbname))
        )
        c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(dbname)))
        c.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO owner_role, api_login").format(
                sql.Identifier(dbname)
            )
        )
    with psycopg.connect(s.conninfo("bootstrap", dbname), autocommit=True) as c:
        c.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")


def migrate(s: Settings, dbname: str) -> list[str]:
    done = []
    with psycopg.connect(s.conninfo("owner", dbname), autocommit=True) as c:
        for f in sorted(SQL_DIR.glob("*.sql")):
            with c.transaction():
                c.execute(f.read_text(encoding="utf-8"))
            done.append(f.name)
    return done


def run_seed(s: Settings, dbname: str, audio_dir: Path | None):
    from m5_backend.seed.seed import seed

    with psycopg.connect(s.conninfo("owner", dbname), autocommit=True) as c:
        return seed(c, audio_dir)


@dataclass
class DbEnv:
    settings: Settings
    dbname: str
    seed: Any
    directory: Any
    api_db: Any
    app: Any
    audio_dir: Path

    def owner_conn(self) -> psycopg.Connection:
        return psycopg.connect(self.settings.conninfo("owner"), autocommit=True)

    def bootstrap_conn(self) -> psycopg.Connection:
        return psycopg.connect(self.settings.conninfo("bootstrap"), autocommit=True)

    def api_raw_conn(self) -> psycopg.Connection:
        return psycopg.connect(self.settings.conninfo("api"), autocommit=True)

    def export(self) -> int:
        from m5_backend.app.export import run_export

        return run_export(self.settings)


def prepare_test_database(s: Settings, dbname: str, audio_dir: Path) -> DbEnv:
    from m5_backend.app.db import Database
    from m5_backend.app.directory import load_directory
    from m5_backend.app.export import run_export
    from m5_backend.app.main import create_app

    s = s.replace(pg_db=dbname, audio_dir=str(audio_dir))
    bootstrap_roles(s)
    recreate_database(s, dbname)
    migrate(s, dbname)
    ids = run_seed(s, dbname, Path(audio_dir))
    run_export(s, dbname)
    directory = load_directory()
    api_db = Database(s.conninfo("api"))
    app = create_app(s, api_db, directory=directory, audio_dir=Path(audio_dir))
    return DbEnv(s, dbname, ids, directory, api_db, app, Path(audio_dir))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dbtool")
    ap.add_argument(
        "cmd", choices=["probe", "bootstrap", "reset", "migrate", "seed", "export", "all"]
    )
    ap.add_argument("--db", default=None, help="database name (default POSTGRES_DB)")
    a = ap.parse_args(argv)
    s = load_settings()
    db = a.db or s.pg_db
    s = s.replace(pg_db=db)
    if a.cmd == "probe":
        ok, why = probe(s)
        print(("OK " if ok else "NOT REACHABLE ") + why)
        return 0 if ok else 1
    if a.cmd in ("bootstrap", "all"):
        bootstrap_roles(s)
        print("roles ok")
    if a.cmd in ("reset", "all"):
        recreate_database(s, db)
        print(f"database {db} recreated")
    if a.cmd in ("migrate", "all"):
        print("migrated:", ", ".join(migrate(s, db)))
    if a.cmd in ("seed", "all"):
        audio = Path(s.audio_dir) if s.audio_dir else None
        ids = run_seed(s, db, audio)
        print(f"seeded {len(ids.patients)} synthetic patients, {len(ids.encounters)} encounters")
    if a.cmd in ("export", "all"):
        from m5_backend.app.export import run_export

        print(f"exported {run_export(s, db)} research rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
