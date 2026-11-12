"""Start/stop the m5 API as a subprocess on 127.0.0.1 with the m4 adapter wired in."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
USERS_FILE = REPO / "m5_backend" / "seed" / "synthetic_users.json"


def env_value(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    f = REPO / ".env"
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return None


def db_up() -> tuple[bool, str]:
    """True if PostgreSQL answers AND the app database is migrated (probe only, no changes)."""
    try:
        from m5_backend.app.config import load_settings
        from m5_backend.scripts import dbtool

        return dbtool.probe(load_settings())
    except Exception as exc:  # no .env, no psycopg ...
        return False, type(exc).__name__


@contextlib.contextmanager
def api(port: int, transcript_dirs: list[Path], m5_transcript_dir: Path, log: Path):
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO),
        "API_HOST": HOST,
        "API_PORT": str(port),
        "MAATUMITRA_VERIFIER": "integration.verifier_adapter:verify_record",
        "MAATUMITRA_TRANSCRIPT_DIRS": os.pathsep.join(str(d) for d in transcript_dirs),
        "M5_TRANSCRIPT_DIR": str(m5_transcript_dir),
        "PYTHONIOENCODING": "utf-8",
    }
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-m", "m5_backend.app.main"],
            cwd=REPO,
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
        try:
            base = f"http://{HOST}:{port}"
            for _ in range(60):
                if proc.poll() is not None:
                    raise RuntimeError(f"API exited early, see {log}")
                try:
                    if httpx.get(base + "/auth/token", timeout=1).status_code in (404, 405, 422):
                        break
                except httpx.HTTPError:
                    time.sleep(0.5)
            else:
                raise RuntimeError("API did not start in 30 s")
            yield base
        finally:
            if sys.platform == "win32":  # the venv launcher spawns a child: kill the whole tree
                subprocess.run(  # noqa: S603
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],  # noqa: S607
                    capture_output=True,
                    check=False,
                )
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
