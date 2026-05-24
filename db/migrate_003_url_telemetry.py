"""Migration 003: add url_telemetry table (D32).

Creates the url_telemetry table + indexes on existing databases. Idempotent —
uses CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS, so safe to run
multiple times. Safe on a fresh DB (the table also exists in schema.sql for
new installs; this script becomes a no-op in that case).

What this table is for:
  Every URL we see (from scrapers, JobSpy, or manual entries) gets logged with
  its domain, detected ATS, and tenant slug. analyze_telemetry.py reads from
  this table to surface "scraper-coverage gaps" — e.g., Greenhouse slugs that
  JobSpy is finding but our direct Greenhouse scraper doesn't have configured.

What this script does:
  1. Verifies the postings table exists (FK target).
  2. Creates url_telemetry + 5 indexes if absent.
  3. Reports current row counts.

Usage:
    python db/migrate_003_url_telemetry.py

Output: prints what it did to stdout. Exit 0 on success.

Note: This script creates the table but does NOT backfill existing postings
into it. Run scripts/backfill_url_telemetry.py afterward to populate historical
data. The migration and the backfill are kept separate so you can run the
migration as part of CI without paying the backfill cost on every commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import connect


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS url_telemetry (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL,
    domain          TEXT NOT NULL,
    ats_guess       TEXT NOT NULL,
    ats_slug        TEXT,
    company_name    TEXT,
    source          TEXT NOT NULL,
    added_at        TEXT NOT NULL,
    posting_id      INTEGER,

    FOREIGN KEY (posting_id) REFERENCES postings(id),
    UNIQUE (url, source)
);
"""

CREATE_INDEX_SQLS = [
    "CREATE INDEX IF NOT EXISTS idx_url_telemetry_domain    ON url_telemetry(domain);",
    "CREATE INDEX IF NOT EXISTS idx_url_telemetry_ats_guess ON url_telemetry(ats_guess);",
    "CREATE INDEX IF NOT EXISTS idx_url_telemetry_ats_slug  ON url_telemetry(ats_slug);",
    "CREATE INDEX IF NOT EXISTS idx_url_telemetry_source    ON url_telemetry(source);",
    "CREATE INDEX IF NOT EXISTS idx_url_telemetry_added_at  ON url_telemetry(added_at);",
]


def table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def main() -> int:
    conn = connect()
    try:
        # Sanity: postings table must exist (it's our FK target)
        if not table_exists(conn, "postings"):
            print("ERROR: postings table does not exist. Run scripts/init_db.py first.")
            return 1

        was_present = table_exists(conn, "url_telemetry")

        conn.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEX_SQLS:
            conn.execute(idx_sql)
        conn.commit()

        if was_present:
            print("url_telemetry table already existed — verified indexes are in place.")
        else:
            print("Created url_telemetry table + 5 indexes.")

        # Report current state
        cur = conn.execute("SELECT COUNT(*) c FROM url_telemetry")
        telemetry_count = cur.fetchone()["c"]
        cur = conn.execute("SELECT COUNT(*) c FROM postings")
        postings_count = cur.fetchone()["c"]
        print(f"Postings: {postings_count} total. url_telemetry: {telemetry_count} rows.")

        if postings_count > 0 and telemetry_count == 0:
            print()
            print("NOTE: telemetry is empty but you have postings.")
            print("Run: python scripts/backfill_url_telemetry.py")
            print("to populate historical data.")

        print("Migration complete.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
