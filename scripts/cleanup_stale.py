"""CLI: clean up stale postings from the DB.

Run after scraping + before scoring to bound DB size over time.

Usage:
    python scripts/cleanup_stale.py                    # 14-day default
    python scripts/cleanup_stale.py --stale-days 7     # custom cutoff
    python scripts/cleanup_stale.py --dry-run          # show what would happen, change nothing

Exit code is always 0 on a clean run, even if zero rows were affected.
Non-zero only on actual error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the package is importable when invoked from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.cleanup import (
    DEFAULT_RETIRE_LOOKBACK_HOURS,
    DEFAULT_STALE_DAYS,
    cleanup_low_fit_postings,
    cleanup_stale_postings,
    cleanup_summary_message,
    retire_closed_postings,
    retire_summary_message,
)
from jobpipeline.db import connect


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stale-days", type=int, default=DEFAULT_STALE_DAYS,
        help=f"Days since last_seen before posting is stale (default: {DEFAULT_STALE_DAYS})",
    )
    parser.add_argument(
        "--min-fit-score", type=float, default=None,
        help="If set, also delete unapplied + unflagged postings with fit_score below this floor (e.g. 0.05)",
    )
    parser.add_argument(
        "--retire-lookback-hours", type=int, default=DEFAULT_RETIRE_LOOKBACK_HOURS,
        help=("Retire postings that dropped off a board scraped successfully within "
              f"this many hours (default: {DEFAULT_RETIRE_LOOKBACK_HOURS})"),
    )
    parser.add_argument(
        "--no-retire", action="store_true",
        help="Skip closed-posting retirement (only run time-based staleness)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without modifying the DB",
    )
    args = parser.parse_args()

    conn = connect()
    try:
        if args.dry_run:
            from datetime import datetime, timedelta, timezone
            print("DRY RUN — no changes will be made.")

            if not args.no_retire:
                r_del, r_deact = retire_closed_postings(
                    conn, args.retire_lookback_hours, dry_run=True
                )
                print(retire_summary_message(r_del, r_deact))
            cutoff = (datetime.now(timezone.utc) - timedelta(days=args.stale_days)).isoformat(timespec="seconds")

            would_deactivate = conn.execute(
                """SELECT COUNT(*) FROM postings p
                   INNER JOIN applications a ON a.posting_id = p.id
                   WHERE p.last_seen < ? AND p.is_active = 1""",
                (cutoff,),
            ).fetchone()[0]

            would_delete = conn.execute(
                """SELECT COUNT(*) FROM postings
                   WHERE last_seen < ?
                     AND id NOT IN (SELECT posting_id FROM applications)""",
                (cutoff,),
            ).fetchone()[0]

            print(cleanup_summary_message(would_delete, would_deactivate, args.stale_days))

            if args.min_fit_score is not None:
                would_low_fit = conn.execute(
                    """SELECT COUNT(*) FROM postings
                       WHERE fit_score < ?
                         AND id NOT IN (SELECT posting_id FROM applications)
                         AND (interest_level IS NULL
                              OR interest_level NOT IN ('interested','very_interested'))""",
                    (args.min_fit_score,),
                ).fetchone()[0]
                print(f"Low-fit cleanup (<{args.min_fit_score} floor): would delete {would_low_fit} rows.")
            return 0

        if not args.no_retire:
            r_deleted, r_deactivated = retire_closed_postings(conn, args.retire_lookback_hours)
            conn.commit()
            print(retire_summary_message(r_deleted, r_deactivated))

        deleted, deactivated = cleanup_stale_postings(conn, args.stale_days)
        conn.commit()
        print(cleanup_summary_message(deleted, deactivated, args.stale_days))

        if args.min_fit_score is not None:
            low_fit_deleted = cleanup_low_fit_postings(conn, args.min_fit_score)
            conn.commit()
            print(f"Low-fit cleanup (<{args.min_fit_score} floor): deleted {low_fit_deleted} rows.")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
