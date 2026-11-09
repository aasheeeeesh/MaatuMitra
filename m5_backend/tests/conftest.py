"""Shared fixtures. DB tests skip with a clear message when no PostgreSQL 16 is reachable."""

from __future__ import annotations

import pytest

from m5_backend.app.config import Settings, load_settings

TEST_DB = "maatumitra_test"


@pytest.fixture(scope="session")
def settings_nodb() -> Settings:
    return Settings.for_tests()


@pytest.fixture(scope="session")
def env(tmp_path_factory):
    """Fresh test database: roles (bootstrap), migrations (owner_role), seed + export (maint_role)."""
    from m5_backend.scripts import dbtool

    s = load_settings()
    ok, why = dbtool.probe(s)
    if not ok:
        pytest.skip(
            f"needs_db: PostgreSQL 16 not reachable ({why}). Start it with "
            "`bash m5_backend/scripts/db_up.sh` (or the CI postgres:16 service)."
        )
    audio_dir = tmp_path_factory.mktemp("audio_synthetic")
    return dbtool.prepare_test_database(s, TEST_DB, audio_dir)


@pytest.fixture
def client(env):
    from fastapi.testclient import TestClient

    return TestClient(env.app)
