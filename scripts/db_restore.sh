#!/usr/bin/env bash
# db_restore.sh — recreate db/jobs.db from db/jobs.sql.gz.
#
# Called at the start of the nightly workflow, before scrapers run. If
# db/jobs.sql.gz is present, this rebuilds the DB from it. If not (first
# run on a fresh checkout), creates a fresh empty DB from schema.sql.
#
# Idempotent: if the DB already exists locally, this overwrites it from
# the dump. So local devs can also use this to "reset to last committed
# state" if they want.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DB_PATH="db/jobs.db"
DUMP_PATH="db/jobs.sql.gz"
SCHEMA_PATH="db/schema.sql"

# Fresh start — wipe any existing local DB. Safer than partial restore.
if [ -f "$DB_PATH" ]; then
  rm "$DB_PATH"
fi

mkdir -p "$(dirname "$DB_PATH")"

if [ -f "$DUMP_PATH" ]; then
  echo "→ Restoring $DB_PATH from $DUMP_PATH..."
  gunzip -c "$DUMP_PATH" | sqlite3 "$DB_PATH"
  echo "→ Restored $(sqlite3 "$DB_PATH" 'SELECT COUNT(*) FROM postings WHERE is_active=1') active postings."
else
  if [ ! -f "$SCHEMA_PATH" ]; then
    echo "ERROR: neither $DUMP_PATH nor $SCHEMA_PATH found. Cannot initialize DB."
    exit 1
  fi
  echo "→ No dump found — initializing fresh DB from $SCHEMA_PATH"
  sqlite3 "$DB_PATH" < "$SCHEMA_PATH"
fi

# Run any pending migrations. They're all idempotent so safe to re-apply.
for migration in db/migrate_*.py; do
  if [ -f "$migration" ]; then
    echo "→ Applying $(basename "$migration")"
    python "$migration"
  fi
done
