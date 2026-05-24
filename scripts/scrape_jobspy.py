"""scrape_jobspy.py — multi-board scraper via JobSpy.

Wraps `python-jobspy` (https://github.com/cullenwatson/JobSpy) to pull postings
from Indeed, LinkedIn, Glassdoor, ZipRecruiter, and Google Jobs in a single
library call per search term. Replaces the failed Indeed RSS / direct-scrape
attempts from session 8.

Source tagging:
    Each posting is tagged source='jobspy:<site>' (e.g., 'jobspy:indeed',
    'jobspy:linkedin'). Dashboard can filter per-site; source_log gets one
    row per (search × site) combination.

Source ID synthesis:
    JobSpy does not return a stable ATS-native ID. We use f"{site}:{jobspy_id}"
    as source_job_id, which is unique within source='jobspy:<site>'.

Per-site error isolation:
    JobSpy can fail on one site (e.g., Glassdoor 400s, LinkedIn rate limits)
    without taking down the run. We call scrape_jobs() once per site so a
    failure on one site doesn't poison the others. Failures are logged to
    source_log with status='error'.

Search config lives in config/search_queries.csv so non-coders can edit
without touching code.

Cross-source dedup note:
    A Brattle Group posting may now exist in postings twice — once under
    source='greenhouse' (via direct scrape) and once under source='jobspy:indeed'.
    The (source, source_job_id) upsert key in persistence.py keys per source,
    so this is by design. Cross-source dedup is a separate concern handled
    elsewhere (or in a future cleanup pass).

Setup:
    pip install python-jobspy

Run:
    python scripts/scrape_jobspy.py
"""

from __future__ import annotations

import csv
import logging
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

# Make sibling package importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import DB_PATH, connect
from jobpipeline.models import Posting, SourceRun, utcnow_iso
from jobpipeline.persistence import format_summary, log_run, upsert_posting

REPO_ROOT = Path(__file__).resolve().parent.parent

# Personal config takes precedence; fall back to the .example file so the
# script still runs (with placeholder queries) before the wizard runs.
_PERSONAL_SEARCHES = REPO_ROOT / "config" / "search_queries.csv"
_EXAMPLE_SEARCHES = REPO_ROOT / "config" / "search_queries.example.csv"
SEARCHES_CSV = _PERSONAL_SEARCHES if _PERSONAL_SEARCHES.exists() else _EXAMPLE_SEARCHES

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SITES = ["indeed", "linkedin", "glassdoor", "zip_recruiter", "google"]

# Per-site flags. linkedin_fetch_description=True costs an extra request per
# LinkedIn job but gives us full JD text for scoring/enrichment.
JOBSPY_KWARGS: dict[str, Any] = {
    "country_indeed": "USA",
    "linkedin_fetch_description": True,
    "hours_old": 168,  # last 7 days; tighten on later runs once we're current
    "verbose": 1,
}

INTER_SEARCH_DELAY_SEC = 0.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scrape_jobspy")


# ---------------------------------------------------------------------------
# Search config loading
# ---------------------------------------------------------------------------

def load_searches(path: Path) -> list[dict[str, Any]]:
    """Read enabled search rows from the config CSV."""
    if not path.exists():
        raise FileNotFoundError(f"Search config not found: {path}")
    rows: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("enabled", "1").strip() != "1":
                continue
            rows.append({
                "search_term": row["search_term"].strip(),
                "location": row["location"].strip(),
                "google_search_term": (row.get("google_search_term") or "").strip() or None,
                "results_wanted": int(row.get("results_wanted") or 50),
            })
    return rows


# ---------------------------------------------------------------------------
# DataFrame -> Posting mapping
# ---------------------------------------------------------------------------

def best_url(row: pd.Series) -> str:
    """Prefer job_url_direct (deep link to employer ATS) over job_url (aggregator)."""
    direct = row.get("job_url_direct")
    if isinstance(direct, str) and direct.startswith("http"):
        return direct
    fallback = row.get("job_url")
    return fallback if isinstance(fallback, str) else ""


def parse_date(val: Any) -> str | None:
    """JobSpy returns date_posted as a date or NaT. Normalize to ISO string or None."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, str):
        return val
    try:
        return val.isoformat()
    except Exception:
        return None


def row_to_posting(row: pd.Series) -> Posting | None:
    """Map a JobSpy DataFrame row to our Posting dataclass. Returns None if invalid."""
    title = row.get("title")
    company = row.get("company")
    site = row.get("site")
    if not (isinstance(title, str) and isinstance(company, str) and isinstance(site, str)):
        return None
    url = best_url(row)
    if not url:
        return None
    jobspy_id = row.get("id")
    if not isinstance(jobspy_id, str) or not jobspy_id:
        # Fall back to URL as id if JobSpy didn't give one
        jobspy_id = url
    location_val = row.get("location")
    location = location_val.strip() if isinstance(location_val, str) else None
    desc = row.get("description")
    jd_text = desc.strip() if isinstance(desc, str) and desc.strip() else None
    posted_at = parse_date(row.get("date_posted"))

    return Posting(
        source=f"jobspy:{site}",
        source_job_id=f"{site}:{jobspy_id}",
        company=company.strip(),
        role=title.strip(),
        url=url,
        location=location,
        department=None,  # JobSpy doesn't provide a department/team field
        jd_text=jd_text,
        posted_at=posted_at,
    )


# ---------------------------------------------------------------------------
# Per-site scrape
# ---------------------------------------------------------------------------

def scrape_one_site(
    conn,
    site: str,
    search: dict[str, Any],
    now: str,
) -> SourceRun:
    """Run one JobSpy search against one site. Returns a SourceRun (committed)."""
    from jobspy import scrape_jobs  # imported lazily so module loads even if jobspy is missing

    label = f"{search['search_term']} @ {search['location']}"
    run = SourceRun(source=f"jobspy:{site}", company=label)
    start = time.monotonic()

    try:
        kwargs = dict(JOBSPY_KWARGS)
        if site == "google" and search.get("google_search_term"):
            kwargs["google_search_term"] = search["google_search_term"]
        df = scrape_jobs(
            site_name=[site],
            search_term=search["search_term"],
            location=search["location"],
            results_wanted=search["results_wanted"],
            **kwargs,
        )

        if df is None or len(df) == 0:
            run.postings_found = 0
            run.status = "success"
        else:
            run.postings_found = len(df)
            for _, row in df.iterrows():
                posting = row_to_posting(row)
                if posting is None or not posting.source_job_id:
                    continue
                try:
                    was_new = upsert_posting(conn, posting, now)
                    if was_new:
                        run.postings_new += 1
                    else:
                        run.postings_updated += 1
                except Exception as e:
                    # Don't let one bad row blow up the whole search
                    log.warning(
                        "  upsert failed for %s @ %s: %s",
                        posting.role, posting.company, e,
                    )
            run.status = "success"
    except Exception as e:
        run.status = "error"
        run.error_message = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        run.duration_ms = int((time.monotonic() - start) * 1000)
        log_run(conn, run)
        conn.commit()

    return run


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    searches = load_searches(SEARCHES_CSV)
    log.info("Loaded %d enabled searches from %s", len(searches), SEARCHES_CSV)
    log.info("Targeting %d sites: %s", len(SITES), ", ".join(SITES))
    log.info("DB: %s", DB_PATH)
    print()

    conn = connect()
    try:
        all_runs: list[SourceRun] = []
        for i, search in enumerate(searches, 1):
            now = utcnow_iso()
            print(f"[{i}/{len(searches)}] {search['search_term']!r} @ {search['location']!r} "
                  f"(results_wanted={search['results_wanted']})")
            for site in SITES:
                run = scrape_one_site(conn, site, search, now)
                all_runs.append(run)
                print(format_summary(run))
                time.sleep(0.1)  # tiny breath between sites
            if i < len(searches):
                time.sleep(INTER_SEARCH_DELAY_SEC)

        print()
        # Per-site totals
        site_totals: dict[str, dict[str, int]] = {}
        for r in all_runs:
            site = r.source.split(":", 1)[1] if ":" in r.source else r.source
            d = site_totals.setdefault(site, {"new": 0, "updated": 0, "errors": 0, "found": 0})
            d["new"] += r.postings_new
            d["updated"] += r.postings_updated
            d["found"] += r.postings_found
            if r.status == "error":
                d["errors"] += 1

        total_new = sum(d["new"] for d in site_totals.values())
        total_updated = sum(d["updated"] for d in site_totals.values())
        total_errors = sum(d["errors"] for d in site_totals.values())

        print(f"Summary: {total_new} new, {total_updated} updated across "
              f"{len(all_runs) - total_errors} successful runs, {total_errors} errors.")
        print()
        print("Per-site breakdown:")
        for site, d in site_totals.items():
            print(f"  {site:<14} new={d['new']:>4}  updated={d['updated']:>4}  "
                  f"found={d['found']:>4}  errors={d['errors']:>2}")

        # Top companies in jobspy postings — useful for spotting target-list gaps
        print()
        print("Top companies in JobSpy postings (this run + prior):")
        rows = conn.execute("""
            SELECT company, COUNT(*) AS n
            FROM postings
            WHERE source LIKE 'jobspy:%'
            GROUP BY company
            ORDER BY n DESC
            LIMIT 15;
        """).fetchall()
        for r in rows:
            print(f"  {r['n']:>4}  {r['company']}")

        return 0 if total_errors == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
