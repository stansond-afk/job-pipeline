"""Persistence helpers shared by all scrapers.

Previously lived in scripts/scrape_greenhouse.py. Extracted so every new scraper
uses the same upsert + logging code, not a copy.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .models import Application, Posting, SourceRun, utcnow_iso
from .url_telemetry import record_url_telemetry

log = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO postings (
    source, source_job_id, company, role, url, location, department,
    jd_text, posted_at, first_seen, last_seen, is_active
) VALUES (
    :source, :source_job_id, :company, :role, :url, :location, :department,
    :jd_text, :posted_at, :first_seen, :last_seen, :is_active
)
ON CONFLICT(source, source_job_id) DO UPDATE SET
    company    = excluded.company,
    role       = excluded.role,
    url        = excluded.url,
    location   = excluded.location,
    department = excluded.department,
    jd_text    = excluded.jd_text,
    posted_at  = excluded.posted_at,
    last_seen  = excluded.last_seen,
    is_active  = 1;
"""

EXISTS_SQL = "SELECT 1 FROM postings WHERE source = ? AND source_job_id = ? LIMIT 1;"

POSTING_ID_SQL = (
    "SELECT id FROM postings WHERE source = ? AND source_job_id = ? LIMIT 1;"
)


def upsert_posting(conn: sqlite3.Connection, posting: Posting, now: str) -> bool:
    """Insert or update a posting. Return True if newly inserted, False if updated.

    We check for existence first (rather than relying on RETURNING tricks) because
    RETURNING can't reliably distinguish insert-vs-update when timestamps collide
    at second precision — two fast upserts within the same second would otherwise
    both look "new".

    Side effect: writes a row to url_telemetry (D32). This is idempotent at the
    SQL layer (INSERT OR IGNORE on the (url, source) unique key), so calling
    upsert_posting() on the same posting twice produces exactly one telemetry
    row. Telemetry failures are caught and logged — they must NOT block the
    posting insert, since telemetry is instrumentation and the posting is the
    primary write.
    """
    existed = conn.execute(
        EXISTS_SQL, (posting.source, posting.source_job_id)
    ).fetchone() is not None
    conn.execute(UPSERT_SQL, posting.as_insert_params(now))

    # Telemetry (D32) — record the URL even on updates. The INSERT OR IGNORE
    # in record_url_telemetry makes the update case a cheap no-op.
    try:
        posting_id_row = conn.execute(
            POSTING_ID_SQL, (posting.source, posting.source_job_id)
        ).fetchone()
        posting_id = posting_id_row["id"] if posting_id_row else None
        record_url_telemetry(
            conn,
            url=posting.url,
            source=posting.source,
            company_name=posting.company,
            added_at=now,
            posting_id=posting_id,
        )
    except Exception as e:
        # Never let telemetry break the scraper. Log and move on.
        log.warning(
            "url_telemetry write failed for %s (%s): %s",
            posting.url, posting.source, e,
        )

    return not existed


SOURCE_LOG_INSERT_SQL = """
INSERT INTO source_log (
    source, company, run_at, status, postings_found, postings_new,
    postings_updated, error_message, duration_ms
) VALUES (
    :source, :company, :run_at, :status, :postings_found, :postings_new,
    :postings_updated, :error_message, :duration_ms
);
"""


def log_run(conn: sqlite3.Connection, run: SourceRun) -> None:
    conn.execute(SOURCE_LOG_INSERT_SQL, run.as_insert_params())


def format_summary(run: SourceRun) -> str:
    """Pretty-print one SourceRun as a single line for stdout."""
    label = run.company or run.source
    if run.status == "success":
        return (f"  ✓ {label:<45} "
                f"found={run.postings_found:>4}  new={run.postings_new:>4}  "
                f"updated={run.postings_updated:>4}  ({run.duration_ms}ms)")
    return f"  ✗ {label:<45} {run.status}: {run.error_message} ({run.duration_ms}ms)"


# ---------------------------------------------------------------------------
# Applications — Phase 1B (tracker UI)
# ---------------------------------------------------------------------------
#
# Convention: there is at most ONE application row per posting_id. The Apply
# button on the dashboard is idempotent — calling it twice on the same posting
# updates the existing row (refreshes jd_snapshot, bumps updated_at) rather
# than creating a duplicate. This matches the user's mental model: "I already
# applied to this; let me update my notes" not "I applied twice."
#
# The schema doesn't enforce uniqueness on posting_id (no UNIQUE constraint)
# because Phase 2 may want to allow re-applying after a rejection. For now
# Phase 1B treats it as 1-to-1 in code.

APPLICATION_INSERT_SQL = """
INSERT INTO applications (
    posting_id, status, submitted_at, resume_path, cover_letter_path,
    notes, jd_snapshot, tailored_notes, created_at, updated_at
) VALUES (
    :posting_id, :status, :submitted_at, :resume_path, :cover_letter_path,
    :notes, :jd_snapshot, :tailored_notes, :created_at, :updated_at
);
"""

APPLICATION_UPDATE_SQL = """
UPDATE applications SET
    status            = :status,
    submitted_at      = :submitted_at,
    resume_path       = :resume_path,
    cover_letter_path = :cover_letter_path,
    notes             = :notes,
    jd_snapshot       = :jd_snapshot,
    tailored_notes    = :tailored_notes,
    updated_at        = :updated_at
WHERE id = :id;
"""


def insert_application(conn: sqlite3.Connection, app: Application, now: str) -> int:
    """Insert a new application row. Returns the new row's id.

    Caller is responsible for committing. Caller is responsible for first
    checking that no application already exists for the posting_id (use
    upsert_application for the idempotent variant).
    """
    cur = conn.execute(APPLICATION_INSERT_SQL, app.as_insert_params(now))
    return cur.lastrowid


def upsert_application(conn: sqlite3.Connection, app: Application, now: str) -> tuple[int, bool]:
    """Insert or update the application for app.posting_id.

    Returns (application_id, is_new). is_new=True means we inserted a fresh
    row; is_new=False means we updated an existing one.
    """
    existing = get_application_by_posting_id(conn, app.posting_id)
    if existing is None:
        new_id = insert_application(conn, app, now)
        return new_id, True

    # Update path: preserve created_at, refresh updated_at, take new values
    # for the rest. The Application dataclass we received is what the user
    # just submitted via the modal, so its fields win.
    params = app.as_insert_params(now)
    params["id"] = existing["id"]
    # created_at is set by as_insert_params from `now`, but on UPDATE we want
    # to leave the original created_at alone — the SQL doesn't touch it.
    params.pop("created_at", None)
    conn.execute(APPLICATION_UPDATE_SQL, params)
    return existing["id"], False


def update_application_status(
    conn: sqlite3.Connection,
    application_id: int,
    new_status: str,
    now: Optional[str] = None,
) -> bool:
    """Update just the status field. Returns True if a row was changed.

    Validates new_status against APPLICATION_STATUSES. Caller commits.
    """
    from .models import APPLICATION_STATUSES
    if new_status not in APPLICATION_STATUSES:
        raise ValueError(
            f"Invalid status {new_status!r}. "
            f"Must be one of: {', '.join(APPLICATION_STATUSES)}"
        )
    now = now or utcnow_iso()
    cur = conn.execute(
        "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, now, application_id),
    )
    return cur.rowcount > 0


def get_application_by_posting_id(
    conn: sqlite3.Connection, posting_id: int
) -> Optional[sqlite3.Row]:
    """Return the application row for a posting, or None."""
    return conn.execute(
        "SELECT * FROM applications WHERE posting_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (posting_id,),
    ).fetchone()


def get_application_by_id(
    conn: sqlite3.Connection, application_id: int
) -> Optional[sqlite3.Row]:
    """Return the application row by its id, or None."""
    return conn.execute(
        "SELECT * FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()


def get_posting_by_id(
    conn: sqlite3.Connection, posting_id: int
) -> Optional[sqlite3.Row]:
    """Return the posting row by its id, or None.

    Used by the Apply modal's pre-fill endpoint — it pulls jd_text,
    role, company, etc. so the modal can render with editable values.
    """
    return conn.execute(
        "SELECT * FROM postings WHERE id = ?",
        (posting_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# Interest level — D27 (per-posting triage signal, separate from fit_score)
# ---------------------------------------------------------------------------


def update_posting_interest(
    conn: sqlite3.Connection,
    posting_id: int,
    new_interest: str,
) -> bool:
    """Update postings.interest_level for one posting. Returns True if changed.

    Validates new_interest against INTEREST_LEVELS. Caller commits.

    Mirrors update_application_status — interest is a triage signal that
    the user updates frequently from the dashboard via inline dropdown.
    Independent of application status.
    """
    from .models import INTEREST_LEVELS
    if new_interest not in INTEREST_LEVELS:
        raise ValueError(
            f"Invalid interest_level {new_interest!r}. "
            f"Must be one of: {', '.join(INTEREST_LEVELS)}"
        )
    # Also bump interest_updated_at — feeds the daily-streak computation
    # (any interest change counts as "showing up" for that day).
    # Column added by migrate_004; guard with PRAGMA so this still works
    # against an un-migrated DB.
    has_ts = any(
        row["name"] == "interest_updated_at"
        for row in conn.execute("PRAGMA table_info(postings)").fetchall()
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    if has_ts:
        cur = conn.execute(
            "UPDATE postings SET interest_level = ?, interest_updated_at = ? WHERE id = ?",
            (new_interest, now_iso, posting_id),
        )
    else:
        cur = conn.execute(
            "UPDATE postings SET interest_level = ? WHERE id = ?",
            (new_interest, posting_id),
        )
    return cur.rowcount > 0
