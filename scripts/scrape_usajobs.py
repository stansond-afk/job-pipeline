"""USAJobs scraper.

Hits data.usajobs.gov/api/Search for each of a configured list of search queries
(location + keyword combinations), paginates through all results, upserts postings
into the SQLite database.

Why query-based rather than agency-based:
    Agency subelement codes are fiddly and change. For v1, it's simpler and
    higher-recall to search the whole DC metro area by keyword. The OrganizationName
    comes back in every posting, so downstream we can filter to our target
    agencies OR surface non-target agencies we'd want to add to the list.

Setup:
    1. Get an API key from https://developer.usajobs.gov/apirequest/
    2. Create a .env file at the repo root with:
         USAJOBS_API_KEY=<your key>
         USAJOBS_USER_AGENT=<your email>
       (.env is gitignored — never committed)

Run:
    python scripts/scrape_usajobs.py

Rate limits:
    USAJobs allows a few requests per second. We rate-limit to ~0.5s between
    requests to stay polite.
"""

from __future__ import annotations

import html
import os
import re
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
ENV_PATH = REPO_ROOT / ".env"

USAJOBS_API = "https://data.usajobs.gov/api/Search"
REQUEST_TIMEOUT_SEC = 30
RATE_LIMIT_DELAY_SEC = 0.5
PAGE_SIZE = 500  # max allowed per USAJobs docs
MAX_PAGES = 20   # safety cap — 20 pages × 500 = 10k postings per query


# ---------------------------------------------------------------------------
# Search queries — read from config/usajobs_queries.csv
# ---------------------------------------------------------------------------
#
# Each row in the CSV defines one USAJobs API call:
#   label     — human-readable name (shows up in scrape logs)
#   keywords  — free-text; USAJobs does OR on space-separated terms
#   locations — semicolon-separated list of city names (USAJobs format)
#   remote    — "true" → adds RemoteIndicator=True instead of LocationName
#   enabled   — "true" → run this query; "false" → skip
#
# Falls back to config/usajobs_queries.example.csv if the personal file
# doesn't exist yet (typical pre-wizard state).
#
# Philosophy: err toward recall. Dedup via (source, source_job_id) upsert
# means a posting showing up in 3 different queries only lands once.

import csv as _csv

def _load_search_queries() -> list[tuple[str, dict]]:
    """Read config/usajobs_queries.csv and return [(label, params), ...]."""
    repo_root = Path(__file__).resolve().parent.parent
    personal = repo_root / "config" / "usajobs_queries.csv"
    example = repo_root / "config" / "usajobs_queries.example.csv"
    path = personal if personal.exists() else example
    if not path.exists():
        return []

    out = []
    with path.open() as f:
        for row in _csv.DictReader(f):
            if (row.get("enabled") or "").strip().lower() != "true":
                continue
            label = (row.get("label") or "").strip()
            keywords = (row.get("keywords") or "").strip()
            locations = (row.get("locations") or "").strip()
            remote = (row.get("remote") or "").strip().lower() == "true"
            params: dict = {"Keyword": keywords} if keywords else {}
            if remote:
                params["RemoteIndicator"] = "True"
            elif locations:
                params["LocationName"] = locations
            if not params:
                continue  # nothing usable
            out.append((label, params))
    return out


SEARCH_QUERIES = _load_search_queries()


# ---------------------------------------------------------------------------
# Environment / credentials
# ---------------------------------------------------------------------------

def load_env() -> dict[str, str]:
    """Minimal .env reader — avoids adding python-dotenv as a dep.

    Reads KEY=VALUE lines, ignores blank lines and lines starting with #.
    Does NOT do shell-style quoting or variable substitution; keep values simple.
    """
    env = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_credentials() -> tuple[str, str]:
    env = load_env()
    api_key = env.get("USAJOBS_API_KEY") or os.environ.get("USAJOBS_API_KEY")
    user_agent = env.get("USAJOBS_USER_AGENT") or os.environ.get("USAJOBS_USER_AGENT")

    missing = []
    if not api_key:
        missing.append("USAJOBS_API_KEY")
    if not user_agent:
        missing.append("USAJOBS_USER_AGENT")

    if missing:
        print("ERROR: missing required credentials: " + ", ".join(missing))
        print()
        print("Create a .env file in the repo root with:")
        print("  USAJOBS_API_KEY=<your key from https://developer.usajobs.gov/apirequest/>")
        print("  USAJOBS_USER_AGENT=<your email address>")
        print()
        print("(.env is gitignored — it will never be committed.)")
        sys.exit(1)

    return api_key, user_agent


# ---------------------------------------------------------------------------
# USAJobs API
# ---------------------------------------------------------------------------

def fetch_page(session: requests.Session, params: dict, page: int) -> dict:
    """Fetch one page of USAJobs search results. Raises on HTTP errors."""
    params = dict(params)
    params["ResultsPerPage"] = str(PAGE_SIZE)
    params["Page"] = str(page)
    resp = session.get(USAJOBS_API, params=params, timeout=REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json()


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(s: str) -> str:
    if not s:
        return ""
    no_tags = _HTML_TAG_RE.sub(" ", s)
    decoded = html.unescape(no_tags)
    return _WHITESPACE_RE.sub(" ", decoded).strip()


def item_to_posting(item: dict) -> Posting:
    """Transform one USAJobs SearchResultItem into our Posting shape.

    USAJobs has a deeply nested structure. We pull what we need:
      MatchedObjectId               → source_job_id (the UsaJobs job control number)
      MatchedObjectDescriptor:
        PositionTitle               → role
        OrganizationName            → company (which federal agency)
        DepartmentName              → department (parent dept, for cabinet-level orgs)
        PositionURI                 → url
        PositionLocation[0].LocationName → location (first office if multiple)
        QualificationSummary        → jd_text
        PublicationStartDate        → posted_at
    """
    descriptor = item.get("MatchedObjectDescriptor", {})
    locations = descriptor.get("PositionLocation") or []
    location_str = None
    if locations:
        names = [loc.get("LocationName") for loc in locations if loc.get("LocationName")]
        if names:
            # If multiple, keep the first but note the count so downstream sees it
            location_str = names[0] if len(names) == 1 else f"{names[0]} (+{len(names) - 1} more)"

    # Qualification summary can be long and HTML-ish
    qual = descriptor.get("QualificationSummary") or ""
    duties = descriptor.get("UserArea", {}).get("Details", {}).get("MajorDuties", "")
    # Sometimes duties come back as a list
    if isinstance(duties, list):
        duties = " ".join(str(d) for d in duties)
    jd_text = strip_html((qual + "\n\n" + duties).strip())

    return Posting(
        source="usajobs",
        source_job_id=str(item.get("MatchedObjectId") or descriptor.get("PositionID") or ""),
        company=descriptor.get("OrganizationName") or descriptor.get("DepartmentName") or "(unknown agency)",
        role=descriptor.get("PositionTitle") or "(untitled)",
        url=descriptor.get("PositionURI") or "",
        location=location_str,
        department=descriptor.get("DepartmentName"),
        jd_text=jd_text or None,
        posted_at=descriptor.get("PublicationStartDate"),
    )


# ---------------------------------------------------------------------------
# Scrape logic
# ---------------------------------------------------------------------------

def scrape_query(conn, session: requests.Session, label: str, params: dict) -> SourceRun:
    """Run one search query against USAJobs, paginating through all results."""
    run = SourceRun(source="usajobs", company=label)
    start = time.monotonic()

    try:
        now = utcnow_iso()
        total_found = 0
        for page in range(1, MAX_PAGES + 1):
            data = fetch_page(session, params, page)
            search_result = data.get("SearchResult", {})
            items = search_result.get("SearchResultItems") or []
            if not items:
                break
            for item in items:
                posting = item_to_posting(item)
                if not posting.source_job_id:
                    continue  # defensive — skip malformed items
                was_new = upsert_posting(conn, posting, now)
                if was_new:
                    run.postings_new += 1
                else:
                    run.postings_updated += 1
            total_found += len(items)
            # If we got less than a full page, we're done
            if len(items) < PAGE_SIZE:
                break
            time.sleep(RATE_LIMIT_DELAY_SEC)
        run.postings_found = total_found
        run.status = "success"
    except requests.HTTPError as e:
        run.status = "error"
        body_preview = (e.response.text or "")[:200] if e.response is not None else "(no body)"
        run.error_message = f"HTTP {e.response.status_code if e.response else '??'}: {body_preview}"
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    api_key, user_agent = get_credentials()

    session = requests.Session()
    session.headers.update({
        "Host": "data.usajobs.gov",
        "User-Agent": user_agent,
        "Authorization-Key": api_key,
        "Accept": "application/json",
    })

    print(f"Running {len(SEARCH_QUERIES)} USAJobs searches into {DB_PATH}")
    print()

    conn = connect()
    try:
        runs: list[SourceRun] = []
        for i, (label, params) in enumerate(SEARCH_QUERIES):
            run = scrape_query(conn, session, label, params)
            runs.append(run)
            print(format_summary(run))
            if i < len(SEARCH_QUERIES) - 1:
                time.sleep(RATE_LIMIT_DELAY_SEC)

        print()
        total_new = sum(r.postings_new for r in runs)
        total_updated = sum(r.postings_updated for r in runs)
        errors = [r for r in runs if r.status == "error"]
        print(f"Summary: {total_new} new, {total_updated} updated across "
              f"{len(runs) - len(errors)} successful queries, {len(errors)} errors.")

        # Show a breakdown of which agencies the postings came from —
        # useful for spotting non-target agencies we might want to add.
        print()
        print("Top agencies in new postings (this run + prior runs combined):")
        rows = conn.execute("""
            SELECT company AS agency, COUNT(*) AS n
            FROM postings
            WHERE source = 'usajobs'
            GROUP BY agency
            ORDER BY n DESC
            LIMIT 15;
        """).fetchall()
        for r in rows:
            print(f"  {r['n']:>4}  {r['agency']}")

        return 0 if not errors else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
