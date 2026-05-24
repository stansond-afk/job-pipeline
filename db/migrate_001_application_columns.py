"""Migration 001: add jd_snapshot + tailored_notes columns to applications.

Idempotent — checks PRAGMA table_info first, only adds columns that are missing.
Safe to run multiple times. Safe on a fresh DB (the columns will already exist
from schema.sql, so this script becomes a no-op).

Why this exists:
  schema.sql now defines applications with jd_snapshot and tailored_notes
  inline in CREATE TABLE. New installs get them automatically. But existing
  databases (early DBs) have a CREATE TABLE that ran before
  these columns existed — applying schema.sql to those DBs is a no-op for
  applications because of IF NOT EXISTS. We need ALTER TABLE for the upgrade.

Usage:
    python db/migrate_001_application_columns.py

Output: prints what it did to stdout. Exit 0 on success.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the jobpipeline package importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import connect


NEW_COLUMNS = [
    # (column_name, column_definition_sans_name)
    ("jd_snapshot",    "TEXT"),
    ("tailored_notes", "TEXT"),
]


def existing_columns(conn, table: str) -> set[str]:
    """Return the set of column names currently on `table`."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row["name"] for row in cur.fetchall()}


def main() -> int:
    conn = connect()
    try:
        cols = existing_columns(conn, "applications")
        if not cols:
            print("ERROR: applications table does not exist. Run schema.sql first.")
            return 1

        added = []
        skipped = []
        for col_name, col_def in NEW_COLUMNS:
            if col_name in cols:
                skipped.append(col_name)
                continue
            sql = f"ALTER TABLE applications ADD COLUMN {col_name} {col_def}"
            conn.execute(sql)
            added.append(col_name)

        conn.commit()

        if added:
            print(f"Added columns: {', '.join(added)}")
        if skipped:
            print(f"Skipped (already present): {', '.join(skipped)}")
        if not added and not skipped:
            print("No changes — unexpected state.")
            return 1

        # Verify final state
        final_cols = existing_columns(conn, "applications")
        for col_name, _ in NEW_COLUMNS:
            assert col_name in final_cols, f"post-migration check failed: {col_name} missing"
        print("Migration complete. applications table now has all expected columns.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
