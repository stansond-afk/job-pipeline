"""Migration 002: add interest_level column to postings.

Adds a triage signal independent of fit_score. the user can mark each
posting as not_reviewed (default) / not_interested / interested /
very_interested. The dashboard sort order uses this to push applied
jobs and not_interested postings to the bottom.

Idempotent — checks PRAGMA table_info first, only adds the column if
missing. Safe on a fresh DB (the column exists in schema.sql for new
installs; this script becomes a no-op).

Usage:
    python db/migrate_002_interest_level.py

Output: prints what it did to stdout. Exit 0 on success.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import connect


NEW_COLUMNS = [
    # (column_name, column_definition_sans_name)
    ("interest_level", "TEXT NOT NULL DEFAULT 'not_reviewed'"),
]


def existing_columns(conn, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row["name"] for row in cur.fetchall()}


def main() -> int:
    conn = connect()
    try:
        cols = existing_columns(conn, "postings")
        if not cols:
            print("ERROR: postings table does not exist. Run schema.sql first.")
            return 1

        added = []
        skipped = []
        for col_name, col_def in NEW_COLUMNS:
            if col_name in cols:
                skipped.append(col_name)
                continue
            sql = f"ALTER TABLE postings ADD COLUMN {col_name} {col_def}"
            conn.execute(sql)
            added.append(col_name)

        conn.commit()

        if added:
            print(f"Added columns: {', '.join(added)}")
        if skipped:
            print(f"Skipped (already present): {', '.join(skipped)}")

        # Verify final state
        final_cols = existing_columns(conn, "postings")
        for col_name, _ in NEW_COLUMNS:
            assert col_name in final_cols, f"post-migration check failed: {col_name} missing"

        # Verify default fired on existing rows
        cur = conn.execute("SELECT COUNT(*) c FROM postings WHERE interest_level = 'not_reviewed'")
        unreviewed_count = cur.fetchone()["c"]
        cur = conn.execute("SELECT COUNT(*) c FROM postings")
        total = cur.fetchone()["c"]
        print(f"Postings: {total} total, {unreviewed_count} with interest_level='not_reviewed'")

        print("Migration complete.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
