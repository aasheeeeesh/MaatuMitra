"""Settings from environment variables, falling back to the git-ignored repo-root .env.

Secrets are never hard-coded. Missing values stay None; whoever needs them fails closed.
"""

from __future__ import annotations

import dataclasses
import os
import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
PLACEHOLDER_PREFIX = "REPLACE_ME"


def read_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """Minimal KEY=VALUE parser (no interpolation, no quotes magic)."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k.strip()] = v
    return out


@dataclasses.dataclass(frozen=True)
class Settings:
    pg_host: str = "127.0.0.1"
    pg_port: int = 54329
    pg_db: str = "maatumitra"
    owner_user: str = "owner_role"
    owner_password: str | None = None
    api_user: str = "api_login"
    api_password: str | None = None
    bootstrap_user: str | None = None
    bootstrap_password: str | None = None
    jwt_signing_key: str | None = None
    jwt_issuer: str = "maatumitra-mock-issuer"
    jwt_audience: str = "maatumitra-api"
    jwt_ttl_seconds: int = 300
    hmac_key: str | None = None
    mock_login_password: str | None = None
    audio_dir: str | None = None
    transcript_dir: str | None = None
    verifier_spec: str | None = None
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    mode: str = "mock"

    def replace(self, **kw) -> Settings:
        return dataclasses.replace(self, **kw)

    def conninfo(self, who: str, dbname: str | None = None) -> str:
        """libpq conninfo for 'owner', 'api' or 'bootstrap'. Fails closed on a missing password."""
        user, pw = {
            "owner": (self.owner_user, self.owner_password),
            "api": (self.api_user, self.api_password),
            "bootstrap": (self.bootstrap_user, self.bootstrap_password),
        }[who]
        if not user or not pw or pw.startswith(PLACEHOLDER_PREFIX):
            raise RuntimeError(f"database credentials for {who!r} are not configured")
        from psycopg.conninfo import make_conninfo

        return make_conninfo(
            host=self.pg_host,
            port=self.pg_port,
            dbname=dbname or self.pg_db,
            user=user,
            password=pw,
            connect_timeout=5,
            application_name=f"m5_backend_{who}",
        )

    @classmethod
    def for_tests(cls) -> Settings:
        """Random, throw-away secrets for tests that need no database."""
        return cls(
            jwt_signing_key=secrets.token_hex(32),
            hmac_key=secrets.token_hex(32),
            mock_login_password=secrets.token_hex(16),
        )


def load_settings(env_file: Path = ENV_FILE, environ: dict[str, str] | None = None) -> Settings:
    env = read_env_file(env_file)
    env.update(os.environ if environ is None else environ)

    def get(key: str, default=None):
        v = env.get(key)
        return default if v in (None, "") else v

    return Settings(
        pg_host=get("POSTGRES_HOST", "127.0.0.1"),
        pg_port=int(get("POSTGRES_PORT", "54329")),
        pg_db=get("POSTGRES_DB", "maatumitra"),
        owner_user="owner_role",
        # F7: with Docker, POSTGRES_USER/POSTGRES_PASSWORD are the image's BOOTSTRAP superuser and
        # must not double as the owner_role password. Legacy .env files that still say
        # POSTGRES_USER=owner_role keep working (non-Docker path).
        owner_password=get("OWNER_DB_PASSWORD")
        or (
            get("POSTGRES_PASSWORD") if get("POSTGRES_USER", "owner_role") == "owner_role" else None
        ),
        api_user=get("API_DB_USER", "api_login"),
        api_password=get("API_DB_PASSWORD"),
        bootstrap_user=get("PG_BOOTSTRAP_USER"),
        bootstrap_password=get("PG_BOOTSTRAP_PASSWORD"),
        jwt_signing_key=get("JWT_SIGNING_KEY"),
        jwt_issuer=get("JWT_ISSUER", "maatumitra-mock-issuer"),
        jwt_audience=get("JWT_AUDIENCE", "maatumitra-api"),
        jwt_ttl_seconds=int(get("JWT_TTL_SECONDS", "300")),
        hmac_key=get("RESEARCH_PSEUDONYM_HMAC_KEY"),
        mock_login_password=get("MOCK_LOGIN_PASSWORD"),
        audio_dir=get("M5_AUDIO_DIR"),
        transcript_dir=get("M5_TRANSCRIPT_DIR"),
        verifier_spec=get("MAATUMITRA_VERIFIER"),
        api_host=get("API_HOST", "127.0.0.1"),
        api_port=int(get("API_PORT", "8000")),
        mode=get("MODE", "mock"),
    )
