"""Greenhouse scraper.

Reads config/targets.csv, filters to ATS == 'greenhouse', hits each company's
public jobs endpoint, and upserts postings into the SQLite database.

Design notes:
  - Each company is independent. One company failing (404, HTML response, whatever)
    does not abort the whole run — we log the error to source_log and continue.
  - Upsert logic: (source, source_job_id) is the dedup key. On repeat runs,
    existing postings get their last_seen bumped and is_active flipped back to 1
    if needed. This makes "did this posting disappear?" queryable later via
    last_seen < today's run time.
  - We stash the full job description (as cleaned text) in jd_text so the scoring
    module can operate on it without re-hitting the API. Greenhouse returns HTML;
    we strip tags naively — enough for keyword matching. No BeautifulSoup dep to
    keep requirements.txt minimal.

Run:
    python scripts/scrape_greenhouse.py
"""

from __future__ import annotations

import csv
import html
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterator

import requests

# Make sibling package importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import DB_PATH, connect
from jobpipeline.models import Posting, SourceRun, utcnow_iso
from jobpipeline.persistence import format_summary, log_run, upsert_posting

REPO_ROOT = Path(__file__).resolve().parent.parent
_PERSONAL_TARGETS = REPO_ROOT / "config" / "targets.csv"
_EXAMPLE_TARGETS = REPO_ROOT / "config" / "targets.example.csv"
TARGETS_CSV = REPO_ROOT / "config" / ("targets.csv" if _PERSONAL_TARGETS.exists() else "targets.example.csv")

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

# Polite defaults. Greenhouse doesn't publish a rate limit but we don't want
# to hammer them — nightly pulls against a few dozen companies is well under any
# reasonable threshold.
REQUEST_TIMEOUT_SEC = 30
DELAY_BETWEEN_COMPANIES_SEC = 1.0


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def read_greenhouse_targets() -> list[dict]:
    """Load config/targets.csv and return rows where ats == 'greenhouse'."""
    if not TARGETS_CSV.exists():
        raise FileNotFoundError(f"Target list not found: {TARGETS_CSV}")

    rows = []
    with TARGETS_CSV.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            if (r.get("ats") or "").strip().lower() == "greenhouse":
                rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Greenhouse API
# ---------------------------------------------------------------------------

def fetch_greenhouse_jobs(slug: str) -> list[dict]:
    """Fetch all jobs for a Greenhouse board. Raises on HTTP / JSON errors."""
    url = GREENHOUSE_API.format(slug=slug)
    resp = requests.get(url, timeout=REQUEST_TIMEOUT_SEC,
                        headers={"Accept": "application/json",
                                 "User-Agent": "job-pipeline/0.1 (personal job search tooling)"})
    resp.raise_for_status()
    data = resp.json()
    if "jobs" not in data:
        raise ValueError(f"Unexpected response shape (no 'jobs' key): {data!r}")
    return data["jobs"]


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(s: str) -> str:
    """Turn Greenhouse's HTML job content into plain-ish text.

    Not perfect — doesn't handle nested entities or weird HTML — but good enough
    for keyword matching and for displaying a few lines in the dashboard.
    """
    if not s:
        return ""
    no_tags = _HTML_TAG_RE.sub(" ", s)
    decoded = html.unescape(no_tags)
    return _WHITESPACE_RE.sub(" ", decoded).strip()


def job_to_posting(company: str, job: dict) -> Posting:
    """Transform a Greenhouse job dict into our Posting shape."""
    loc = (job.get("location") or {}).get("name") or None

    # Department: Greenhouse can return an empty list or multiple. Take the first's name.
    departments = job.get("departments") or []
    dept = departments[0]["name"] if departments and departments[0].get("name") else None

    return Posting(
        source="greenhouse",
        source_job_id=str(job["id"]),
        company=company,
        role=job.get("title") or "(untitled)",
        url=job.get("absolute_url") or "",
        location=loc,
        department=dept,
        jd_text=strip_html(job.get("content") or ""),
        posted_at=job.get("updated_at"),  # ISO-8601 from Greenhouse
    )


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape_one(conn: sqlite3.Connection, target: dict) -> SourceRun:
    """Scrape one company; return a SourceRun (already logged to DB on return)."""
    company = target["company"]
    slug = target["ats_identifier"].strip()
    run = SourceRun(source="greenhouse", company=company)
    start = time.monotonic()

    try:
        jobs = fetch_greenhouse_jobs(slug)
        run.postings_found = len(jobs)
        now = utcnow_iso()
        for job in jobs:
            posting = job_to_posting(company, job)
            was_new = upsert_posting(conn, posting, now)
            if was_new:
                run.postings_new += 1
            else:
                run.postings_updated += 1
        run.status = "success"
    except requests.HTTPError as e:
        run.status = "error"
        run.error_message = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except requests.RequestException as e:
        run.status = "error"
        run.error_message = f"request failed: {e}"
    except Exception as e:
        run.status = "error"
        run.error_message = f"{type(e).__name__}: {e}"
    finally:
        run.duration_ms = int((time.monotonic() - start) * 1000)
        log_run(conn, run)
        conn.commit()

    return run


def main() -> int:
    targets = read_greenhouse_targets()
    if not targets:
        print("No Greenhouse-tagged companies in config/targets.csv. Nothing to do.")
        return 0

    print(f"Scraping {len(targets)} Greenhouse boards into {DB_PATH}")
    print()

    conn = connect()
    try:
        runs: list[SourceRun] = []
        for i, target in enumerate(targets):
            run = scrape_one(conn, target)
            runs.append(run)
            print(format_summary(run))
            if i < len(targets) - 1:
                time.sleep(DELAY_BETWEEN_COMPANIES_SEC)

        print()
        total_new = sum(r.postings_new for r in runs)
        total_updated = sum(r.postings_updated for r in runs)
        errors = [r for r in runs if r.status == "error"]
        print(f"Summary: {total_new} new, {total_updated} updated across "
              f"{len(runs) - len(errors)} successful boards, {len(errors)} errors.")
        return 0 if not errors else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
