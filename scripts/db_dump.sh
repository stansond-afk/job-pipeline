#!/usr/bin/env bash
# db_dump.sh — export db/jobs.db to db/jobs.sql.gz for git commit.
#
# The binary db/jobs.db stays gitignored. We commit the gzipped SQL dump
# instead, which:
#   - Compresses the 22 MB binary down to ~4-5 MB
#   - Diffs cleanly in git (text deltas instead of opaque binary blobs)
#   - Roundtrips perfectly (db_restore.sh recreates an identical DB)
#
# Called automatically by deploy.sh and the nightly Actions workflow.
# Safe to run manually: produces deterministic output.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DB_PATH="db/jobs.db"
DUMP_PATH="db/jobs.sql.gz"

if [ ! -f "$DB_PATH" ]; then
  echo "→ No DB at $DB_PATH — nothing to dump."
  exit 0
fi

# .dump produces a textual SQL representation that fully reconstructs the DB.
# gzip -9 trades a small amount of dump time for max compression — worth it
# since the dump is what hits git.
sqlite3 "$DB_PATH" .dump | gzip -9 > "$DUMP_PATH"

echo "→ Dumped $DB_PATH → $DUMP_PATH ($(du -h "$DUMP_PATH" | cut -f1))"
