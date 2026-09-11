#!/usr/bin/env bash
# Optional native PostgreSQL for macOS/Linux. Use this OR compose.yaml.
set -euo pipefail
cd "$(dirname "$0")/.."
megan_pgdata="$PWD/.local/pgdata"
case "${1:-start}" in
  start)
    mkdir -p .local
    if [[ ! -f "$megan_pgdata/PG_VERSION" ]]; then
      # Local development cluster, password matches the .env examples.
      umask 077
      megan_pwfile="$(mktemp)"
      trap 'rm -f "$megan_pwfile"' EXIT
      printf '%s\n' megan > "$megan_pwfile"
      initdb -D "$megan_pgdata" -U megan -A scram-sha-256 --pwfile="$megan_pwfile" --encoding=UTF8 --locale=C
    fi
    if ! pg_ctl -D "$megan_pgdata" status >/dev/null 2>&1; then
      pg_ctl -D "$megan_pgdata" -l "$PWD/.local/postgres.log" -o '-h 127.0.0.1 -p 54329 -k /tmp -c max_connections=30' start
    fi
    for megan_db in megan megan_test; do
      if [[ "$(PGPASSWORD=megan psql -h 127.0.0.1 -p 54329 -U megan -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$megan_db'")" != 1 ]]; then
        PGPASSWORD=megan createdb -h 127.0.0.1 -p 54329 -U megan "$megan_db"
      fi
    done
    ;;
  stop) pg_ctl -D "$megan_pgdata" -m fast stop ;;
  status) pg_ctl -D "$megan_pgdata" status ;;
  *) echo 'Usage: bash scripts/local_postgres.sh start|stop|status' >&2; exit 2 ;;
esac
