"""Merge D1 events into the local SQLite DB.

Runs as a step in the nightly Actions workflow. Pulls all events from
the Cloudflare D1 events table where applied_at IS NULL, applies them
to the local jobs.db (which has just been restored from jobs.sql.gz),
then marks each event as applied.

Authentication uses a Cloudflare API token stored as a GitHub Actions secret
(CLOUDFLARE_API_TOKEN). The token needs D1 read+write permissions for
your Cloudflare account.

Session 20 addition (D31): handles the new 'add_job' event type, which
creates a new posting from a Worker-side manual entry. Routes through
upsert_posting() so url_telemetry (D32) fires automatically.

Usage (from repo root):
    python scripts/merge_d1_events.py

Required env vars:
    CLOUDFLARE_API_TOKEN     — API token with D1:Edit permission
    CLOUDFLARE_ACCOUNT_ID    — your Cloudflare account ID
    D1_DATABASE_ID           — the events DB UUID

Exit codes:
    0 — success (merge applied or no events to apply)
    1 — error (network, auth, or merge failure)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# Make sibling package importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "jobs.db"


# ─────────────────────────────────────────────────────────────────────────
# Cloudflare D1 API helpers
# ─────────────────────────────────────────────────────────────────────────

def d1_query(sql: str, params: list | None = None) -> dict:
    """Execute a SQL statement against D1 via the Cloudflare API.

    Returns the parsed JSON response. Raises on HTTP errors or non-success
    response bodies.
    """
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    db_id = os.environ["D1_DATABASE_ID"]
    token = os.environ["CLOUDFLARE_API_TOKEN"]

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{db_id}/query"
    body = json.dumps({"sql": sql, "params": params or []}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"D1 API HTTP {e.code}: {body}") from e

    if not data.get("success"):
        raise RuntimeError(f"D1 API error: {data.get('errors')}")
    return data


# ─────────────────────────────────────────────────────────────────────────
# Event handlers — one per event_type
# ─────────────────────────────────────────────────────────────────────────

def apply_interest(conn: sqlite3.Connection, event: dict) -> None:
    """Apply an 'interest' event to the local DB."""
    payload = json.loads(event["payload"])
    posting_id = event["posting_id"]
    new_level = payload["interest_level"]
    conn.execute(
        "UPDATE postings SET interest_level = ? WHERE id = ?",
        (new_level, posting_id),
    )


def apply_status(conn: sqlite3.Connection, event: dict) -> None:
    """Apply a 'status' event to the local DB."""
    from jobpipeline.models import utcnow_iso
    payload = json.loads(event["payload"])
    application_id = event["application_id"]
    new_status = payload["status"]
    conn.execute(
        "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, utcnow_iso(), application_id),
    )


def apply_apply(conn: sqlite3.Connection, event: dict) -> int:
    """Apply an 'apply' event — creates a new application row.

    Returns the new application's id (used for logging only; D1 doesn't
    need it back since the event is merged regardless).
    """
    from jobpipeline.models import utcnow_iso
    payload = json.loads(event["payload"])
    posting_id = event["posting_id"]
    now = utcnow_iso()

    cur = conn.execute("""
        INSERT INTO applications (
            posting_id, status, submitted_at, resume_path, cover_letter_path,
            notes, jd_snapshot, tailored_notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        posting_id,
        payload.get("status", "submitted"),
        payload.get("submitted_at"),
        payload.get("resume_path"),
        payload.get("cover_letter_path"),
        payload.get("notes"),
        payload.get("jd_snapshot"),
        payload.get("tailored_notes"),
        now,
        now,
    ))
    return cur.lastrowid


def apply_add_job(conn: sqlite3.Connection, event: dict) -> int | None:
    """Apply an 'add_job' event — creates a new posting from a manual entry
    submitted via the deployed dashboard (D31, session 20).

    The payload from the Worker contains the full posting shape:
        source, source_job_id, company, role, url, location, department,
        jd_text, posted_at

    Routing through upsert_posting() rather than raw INSERT gives us two
    things for free:
      1. The (source, source_job_id) UNIQUE constraint deduplicates if
         the same manual entry is submitted twice.
      2. url_telemetry (D32) fires automatically via the side effect in
         upsert_posting — same as every other scraper.

    After upsert, attempts to score the posting via score_postings.score_posting.
    Scoring failures are logged as warnings but don't fail the merge — the
    posting still ends up in the DB at NULL fit_score and shows up at the
    bottom of the dashboard until the next full scoring pass.

    Returns the posting_id on success, or None on failure.
    """
    from jobpipeline.models import Posting, utcnow_iso
    from jobpipeline.persistence import upsert_posting

    payload = json.loads(event["payload"])
    now = utcnow_iso()

    posting = Posting(
        source=payload["source"],
        source_job_id=payload["source_job_id"],
        company=payload["company"],
        role=payload["role"],
        url=payload["url"],
        location=payload.get("location"),
        department=payload.get("department"),
        jd_text=payload.get("jd_text"),
        posted_at=payload.get("posted_at"),
    )

    # upsert_posting writes both the postings row and (via side effect) a
    # url_telemetry row. INSERT OR IGNORE on telemetry's (url, source) makes
    # the second-attempt case idempotent.
    upsert_posting(conn, posting, now)

    # Look up the resulting posting_id for scoring + logging
    row = conn.execute(
        "SELECT id FROM postings WHERE source = ? AND source_job_id = ?",
        (posting.source, posting.source_job_id),
    ).fetchone()
    if not row:
        # Shouldn't happen, but defensively avoid crashing the merge
        print(f"  ⚠ add_job event {event['id']}: posting not found after upsert", file=sys.stderr)
        return None
    posting_id = row["id"]

    # Score the new posting inline (mirrors scripts/manual_entry_server.py
    # behavior). Score failures are non-fatal — the posting still gets
    # ingested; it just shows up with NULL fit_score until the next pass.
    try:
        from scripts.score_postings import score_posting  # type: ignore
        fit_score, score_notes = score_posting(
            posting.role, posting.jd_text or "", posting.location
        )
        conn.execute(
            "UPDATE postings SET fit_score = ?, score_notes = ? WHERE id = ?",
            (fit_score, score_notes, posting_id),
        )
    except Exception as e:
        print(
            f"  ⚠ add_job event {event['id']}: scoring failed: {type(e).__name__}: {e}",
            file=sys.stderr,
        )

    return posting_id


HANDLERS = {
    "interest": apply_interest,
    "status": apply_status,
    "apply": apply_apply,
    "add_job": apply_add_job,
}


# ─────────────────────────────────────────────────────────────────────────
# Main flow
# ─────────────────────────────────────────────────────────────────────────

def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: local DB not found at {DB_PATH}", file=sys.stderr)
        print("Run scripts/db_restore.sh first.", file=sys.stderr)
        return 1

    print(f"→ Pulling unapplied D1 events…")
    response = d1_query("""
        SELECT id, event_type, posting_id, application_id, payload, user_email, created_at
        FROM events
        WHERE applied_at IS NULL
        ORDER BY created_at ASC
    """)
    rows = response["result"][0].get("results", [])

    if not rows:
        print("→ No pending events to merge. Done.")
        return 0

    print(f"→ Applying {len(rows)} event(s) to local DB…")

    applied_ids = []
    failed = []

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        for row in rows:
            handler = HANDLERS.get(row["event_type"])
            if not handler:
                print(f"  ✗ event {row['id']}: unknown event_type {row['event_type']!r}", file=sys.stderr)
                failed.append(row["id"])
                continue
            try:
                handler(conn, row)
                applied_ids.append(row["id"])
                print(f"  ✓ event {row['id']}: {row['event_type']} (by {row['user_email']})")
            except Exception as e:
                print(f"  ✗ event {row['id']}: {type(e).__name__}: {e}", file=sys.stderr)
                failed.append(row["id"])
        conn.commit()
    finally:
        conn.close()

    # Mark successful events as applied in D1
    if applied_ids:
        ids_csv = ",".join(str(i) for i in applied_ids)
        d1_query(
            f"UPDATE events SET applied_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id IN ({ids_csv})"
        )
        print(f"→ Marked {len(applied_ids)} event(s) as applied in D1.")

    if failed:
        print(f"⚠ {len(failed)} event(s) failed to apply: {failed}", file=sys.stderr)
        # Don't exit non-zero — let the rest of the pipeline run with partial data

    return 0


if __name__ == "__main__":
    sys.exit(main())
