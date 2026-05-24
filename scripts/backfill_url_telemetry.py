"""Backfill url_telemetry from existing postings (D32).

Walks every row in the postings table and writes a corresponding url_telemetry
row using its url + source + company. Idempotent thanks to the (url, source)
unique index — running this twice produces the same result as running it once.

When to run:
  - Once, right after migrate_003_url_telemetry.py, to populate historical data.
  - Optionally again later if telemetry was accidentally deleted; the unique
    index makes it safe.

Performance note:
  All inserts happen in a single transaction. On a ~5k posting DB this takes
  a couple seconds and is well within SQLite's comfort zone. If the DB grows
  to 100k+ postings we'd want to batch-commit every N rows; not needed yet.

Usage:
    python scripts/backfill_url_telemetry.py
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import DB_PATH, connect
from jobpipeline.url_telemetry import URL_TELEMETRY_INSERT_SQL, parse


def main() -> int:
    print(f"Backfilling url_telemetry from {DB_PATH}")
    conn = connect()
    try:
        # Sanity: telemetry table must exist
        check = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='url_telemetry'"
        ).fetchone()
        if check is None:
            print("ERROR: url_telemetry table not found. Run db/migrate_003_url_telemetry.py first.")
            return 1

        # Snapshot before
        before = conn.execute("SELECT COUNT(*) c FROM url_telemetry").fetchone()["c"]
        total_postings = conn.execute("SELECT COUNT(*) c FROM postings").fetchone()["c"]
        print(f"Before: {before} telemetry rows, {total_postings} postings to walk.")
        print()

        start = time.monotonic()
        ats_counts: Counter[str] = Counter()
        unknown_domains: Counter[str] = Counter()
        rows_processed = 0

        # Stream postings to avoid materializing all of them at once.
        cursor = conn.execute(
            "SELECT id, source, company, url, first_seen FROM postings ORDER BY id"
        )
        for row in cursor:
            telemetry = parse(row["url"])
            ats_counts[telemetry.ats_guess] += 1
            if telemetry.ats_guess == "unknown" and telemetry.domain:
                unknown_domains[telemetry.domain] += 1
            conn.execute(
                URL_TELEMETRY_INSERT_SQL,
                {
                    "url": row["url"],
                    "domain": telemetry.domain,
                    "ats_guess": telemetry.ats_guess,
                    "ats_slug": telemetry.ats_slug,
                    "company_name": row["company"],
                    "source": row["source"],
                    "added_at": row["first_seen"],
                    "posting_id": row["id"],
                },
            )
            rows_processed += 1

        conn.commit()
        duration = time.monotonic() - start

        after = conn.execute("SELECT COUNT(*) c FROM url_telemetry").fetchone()["c"]
        added = after - before

        print(f"Processed {rows_processed} postings in {duration:.2f}s.")
        print(f"Telemetry rows: {before} -> {after} (added {added}, skipped {rows_processed - added} as duplicates).")
        print()
        print("ATS distribution across processed postings:")
        for ats, n in ats_counts.most_common():
            print(f"  {n:>5}  {ats}")

        if unknown_domains:
            print()
            print("Top 20 unrecognized domains (candidates for future parser additions):")
            for domain, n in unknown_domains.most_common(20):
                print(f"  {n:>5}  {domain}")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
