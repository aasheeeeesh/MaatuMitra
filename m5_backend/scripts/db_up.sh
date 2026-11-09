#!/usr/bin/env bash
# Start a LOCAL PostgreSQL 16 (no Docker, no admin rights), bound to 127.0.0.1 only, then
# create roles, a fresh database, run migrations, load SYNTHETIC seed data and run the export.
#
# Needs in .env (git-ignored): PG_BIN, PGDATA_DIR, POSTGRES_PORT, PG_BOOTSTRAP_USER,
# PG_BOOTSTRAP_PASSWORD, POSTGRES_PASSWORD, API_DB_PASSWORD, ... (see .env.example).
# PG_BIN = bin/ of PostgreSQL 16 (we used the EnterpriseDB 16.15 Windows binaries zip,
# unpacked to %USERPROFILE%/.maatumitra/pg16; see m5_backend/README.md).
# Usage (Git Bash, repo root):  bash m5_backend/scripts/db_up.sh [--no-reset]
set -euo pipefail
cd "$(dirname "$0")/../.."

envget() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true; }
PG_BIN="${PG_BIN:-$(envget PG_BIN)}"
PGDATA_DIR="${PGDATA_DIR:-$(envget PGDATA_DIR)}"
PORT="${POSTGRES_PORT:-$(envget POSTGRES_PORT)}"; PORT="${PORT:-54329}"
BUSER="${PG_BOOTSTRAP_USER:-$(envget PG_BOOTSTRAP_USER)}"
BPASS="${PG_BOOTSTRAP_PASSWORD:-$(envget PG_BOOTSTRAP_PASSWORD)}"

for v in PG_BIN PGDATA_DIR BUSER BPASS; do
  if [ -z "${!v}" ] || [[ "${!v}" == REPLACE_ME* ]]; then echo "db_up: $v is not set in .env" >&2; exit 2; fi
done
EXE=""; [ -x "$PG_BIN/postgres.exe" ] && EXE=".exe"
"$PG_BIN/postgres$EXE" --version | grep -q " 16\." || { echo "db_up: $PG_BIN is not PostgreSQL 16" >&2; exit 2; }

case "$(cd "$(dirname "$PGDATA_DIR")" 2>/dev/null && pwd || echo "$PGDATA_DIR")" in
  "$(pwd)"*) echo "db_up: refusing a data dir inside the repo" >&2; exit 2 ;;
esac

if [ ! -f "$PGDATA_DIR/PG_VERSION" ]; then
  mkdir -p "$PGDATA_DIR"
  PWFILE="$(mktemp)"; trap 'rm -f "$PWFILE"' EXIT
  printf '%s\n' "$BPASS" > "$PWFILE"
  "$PG_BIN/initdb$EXE" -D "$PGDATA_DIR" -U "$BUSER" --pwfile="$PWFILE" \
    --auth=scram-sha-256 --encoding=UTF8 --no-locale >/dev/null
  rm -f "$PWFILE"
  echo "db_up: initialised $PGDATA_DIR (superuser $BUSER, scram-sha-256)"
fi

if "$PG_BIN/pg_ctl$EXE" -D "$PGDATA_DIR" status >/dev/null 2>&1; then
  echo "db_up: already running"
else
  "$PG_BIN/pg_ctl$EXE" -D "$PGDATA_DIR" -l "$PGDATA_DIR/server.log" -w start \
    -o "-p $PORT -c listen_addresses=127.0.0.1 -c password_encryption=scram-sha-256" \
    </dev/null >/dev/null 2>&1  # do not let the server inherit the caller's pipes
  echo "db_up: started on 127.0.0.1:$PORT (log: $PGDATA_DIR/server.log)"
fi
"$PG_BIN/pg_isready$EXE" -h 127.0.0.1 -p "$PORT"

export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$USERPROFILE/.venvs/maatumitra}"
if [ "${1:-}" != "--no-reset" ]; then
  uv run --no-sync python -m m5_backend.scripts.dbtool all
fi
