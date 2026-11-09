#!/usr/bin/env bash
# Stop the local PostgreSQL started by db_up.sh. Data stays in PGDATA_DIR (outside the repo).
set -euo pipefail
cd "$(dirname "$0")/../.."
envget() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true; }
PG_BIN="${PG_BIN:-$(envget PG_BIN)}"
PGDATA_DIR="${PGDATA_DIR:-$(envget PGDATA_DIR)}"
EXE=""; [ -x "$PG_BIN/pg_ctl.exe" ] && EXE=".exe"
if "$PG_BIN/pg_ctl$EXE" -D "$PGDATA_DIR" status >/dev/null 2>&1; then
  "$PG_BIN/pg_ctl$EXE" -D "$PGDATA_DIR" -m fast -w stop
else
  echo "db_down: not running"
fi
