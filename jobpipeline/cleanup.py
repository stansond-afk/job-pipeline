"""Stale-posting cleanup.

Run after each scrape to bound DB growth without losing user state.

Rules:
  - A posting is "stale" if last_seen is older than STALE_DAYS days ago.
  - If stale AND no application row exists → DELETE the posting outright.
  - If stale AND an application exists (any status) → set is_active=0,
    keeping the row for tracker history but hiding it from the dashboard's
    default "active postings" view.
  - Non-stale postings are left alone, regardless of application state.

This naturally cycles old jobs out of the dashboard while preserving every
posting the user actually pursued. The dashboard already filters
WHERE is_active=1 in fetch_postings(), so deactivated rows disappear from
the active view without any UI changes.

Usage:
    from jobpipeline.cleanup import cleanup_stale_postings
    deleted, deactivated = cleanup_stale_postings(conn, stale_days=14)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Tuple


DEFAULT_STALE_DAYS = 14


def cleanup_stale_postings(
    conn: sqlite3.Connection,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> Tuple[int, int]:
    """Apply the stale-cleanup rules. Returns (deleted_count, deactivated_count).

    Caller is responsible for committing.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=stale_days)).isoformat(timespec="seconds")

    # Step 1: deactivate stale postings that have an application row.
    # Use a JOIN-based UPDATE so we touch only rows with associated applications.
    cur = conn.execute(
        """
        UPDATE postings
        SET is_active = 0
        WHERE id IN (
            SELECT p.id
            FROM postings p
            INNER JOIN applications a ON a.posting_id = p.id
            WHERE p.last_seen < ?
              AND p.is_active = 1
        )
        """,
        (cutoff,),
    )
    deactivated = cur.rowcount

    # Step 2: delete stale postings with no application row.
    # Run this AFTER step 1 so the JOIN check is unambiguous.
    #
    # url_telemetry has a FK to postings(id) WITHOUT ON DELETE CASCADE, so
    # SQLite (foreign_keys=ON) blocks deleting any posting that has telemetry
    # rows — this is what was crashing the nightly. NULL those references
    # first (same approach as cleanup_low_fit_postings); the telemetry rows
    # themselves are kept. The predicate must match the DELETE exactly.
    conn.execute(
        """
        UPDATE url_telemetry
        SET posting_id = NULL
        WHERE posting_id IN (
            SELECT id FROM postings
            WHERE last_seen < ?
              AND id NOT IN (SELECT posting_id FROM applications)
        )
        """,
        (cutoff,),
    )
    cur = conn.execute(
        """
        DELETE FROM postings
        WHERE last_seen < ?
          AND id NOT IN (SELECT posting_id FROM applications)
        """,
        (cutoff,),
    )
    deleted = cur.rowcount

    return deleted, deactivated


def cleanup_summary_message(deleted: int, deactivated: int, stale_days: int) -> str:
    """Human-readable summary line for stdout."""
    return (
        f"Stale-cleanup ({stale_days}-day cutoff): "
        f"deleted {deleted} unapplied + deactivated {deactivated} applied = "
        f"{deleted + deactivated} total stale rows handled."
    )


def cleanup_low_fit_postings(
    conn: sqlite3.Connection,
    min_fit_score: float,
) -> int:
    """Delete postings scoring below the fit-score floor.

    Preserves anything the user has touched: applied-to postings and rows
    flagged interested/very_interested stay regardless of score (a low
    score on a flagged row means the scorer is miscalibrated, not that
    the posting is noise).

    Before deleting, NULLs out url_telemetry.posting_id references —
    url_telemetry has a FK to postings(id) without ON DELETE CASCADE,
    so SQLite (with foreign_keys=ON) blocks the delete otherwise.
    Telemetry rows themselves are kept (still tells us the URL was seen).

    Returns deleted_count. Caller is responsible for committing.
    """
    conn.execute(
        """
        UPDATE url_telemetry
        SET posting_id = NULL
        WHERE posting_id IN (
            SELECT id FROM postings
            WHERE fit_score < ?
              AND id NOT IN (SELECT posting_id FROM applications)
              AND (interest_level IS NULL
                   OR interest_level NOT IN ('interested','very_interested'))
        )
        """,
        (min_fit_score,),
    )
    cur = conn.execute(
        """
        DELETE FROM postings
        WHERE fit_score < ?
          AND id NOT IN (SELECT posting_id FROM applications)
          AND (interest_level IS NULL
               OR interest_level NOT IN ('interested','very_interested'))
        """,
        (min_fit_score,),
    )
    return cur.rowcount
