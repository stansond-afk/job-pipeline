"""Lightweight dataclasses shared by scrapers and downstream code.

Kept deliberately simple. SQLite rows are tuples; these dataclasses give
scrapers a type-checked shape to build before insertion, and give downstream
code a clean object to pass around.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Status enum for applications (kept in sync with schema.sql comment)
# ---------------------------------------------------------------------------

APPLICATION_STATUSES = (
    "new",
    "reviewing",
    "tailored",
    "submitted",
    "interviewing",
    "offered",
    "rejected",
    "withdrawn",
    "closed",
)

# ---------------------------------------------------------------------------
# Interest level enum for postings (D27 — separate axis from fit_score and
# from application status). Default is 'not_reviewed' for every freshly-
# scraped posting; the user updates via the per-row dropdown on the dashboard.
# ---------------------------------------------------------------------------

INTEREST_LEVELS = (
    "not_reviewed",       # default — user hasn't looked yet
    "not_interested",     # explicitly rejected — pushes to bottom of dashboard
    "interested",         # keeping it on the radar
    "very_interested",    # priority — pushes to top of dashboard
)

# Display labels for UI rendering. Keep keys in sync with INTEREST_LEVELS.
INTEREST_LEVEL_LABELS = {
    "not_reviewed":    "—",
    "not_interested":  "Not interested",
    "interested":      "Interested",
    "very_interested": "Very interested",
}


def utcnow_iso() -> str:
    """Return current UTC time as ISO-8601 string (what we store in the DB)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Posting:
    """A job posting as pulled from a source. Pre-insertion shape."""

    source: str                     # 'greenhouse', 'lever', ...
    source_job_id: str              # the ATS's native ID
    company: str                    # canonical company name
    role: str                       # role title
    url: str                        # link to posting
    location: Optional[str] = None
    department: Optional[str] = None
    jd_text: Optional[str] = None
    posted_at: Optional[str] = None  # ISO-8601 UTC if available from source

    def as_insert_params(self, now: str) -> dict:
        """Return dict suitable for the INSERT parameters in scrapers."""
        return {
            "source": self.source,
            "source_job_id": self.source_job_id,
            "company": self.company,
            "role": self.role,
            "url": self.url,
            "location": self.location,
            "department": self.department,
            "jd_text": self.jd_text,
            "posted_at": self.posted_at,
            "first_seen": now,
            "last_seen": now,
            "is_active": 1,
        }


@dataclass
class Application:
    """An application the user has decided to pursue for a posting.

    Pre-insertion shape. Mirrors Posting's pattern. The id is assigned by
    SQLite on insert; created_at/updated_at default to "now" if not provided.
    """

    posting_id: int                 # FK to postings.id
    status: str = "submitted"       # see APPLICATION_STATUSES
    submitted_at: Optional[str] = None     # ISO-8601 UTC, when applied
    resume_path: Optional[str] = None      # path to tailored resume .docx
    cover_letter_path: Optional[str] = None  # path to cover letter .docx
    notes: Optional[str] = None            # freeform notes
    jd_snapshot: Optional[str] = None      # JD text as edited at Apply time (D18)
    tailored_notes: Optional[str] = None   # paste-back from tailoring chat

    def as_insert_params(self, now: str) -> dict:
        """Return dict suitable for the INSERT parameters."""
        if self.status not in APPLICATION_STATUSES:
            raise ValueError(
                f"Invalid status {self.status!r}. "
                f"Must be one of: {', '.join(APPLICATION_STATUSES)}"
            )
        return {
            "posting_id":        self.posting_id,
            "status":            self.status,
            "submitted_at":      self.submitted_at,
            "resume_path":       self.resume_path,
            "cover_letter_path": self.cover_letter_path,
            "notes":             self.notes,
            "jd_snapshot":       self.jd_snapshot,
            "tailored_notes":    self.tailored_notes,
            "created_at":        now,
            "updated_at":        now,
        }


@dataclass
class SourceRun:
    """Tracks one scraper invocation for one source (optionally one company)."""

    source: str
    company: Optional[str] = None
    run_at: str = field(default_factory=utcnow_iso)
    status: str = "success"          # 'success', 'error', 'skipped'
    postings_found: int = 0
    postings_new: int = 0
    postings_updated: int = 0
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None

    def as_insert_params(self) -> dict:
        return {
            "source": self.source,
            "company": self.company,
            "run_at": self.run_at,
            "status": self.status,
            "postings_found": self.postings_found,
            "postings_new": self.postings_new,
            "postings_updated": self.postings_updated,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }
