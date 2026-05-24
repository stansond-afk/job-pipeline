"""Scrape job postings from Lever API for verified target companies.

Reads slugs from data/lever_slugs.csv (produced by discover_lever_slugs.py).
Upserts postings into the SQLite DB using the shared persistence layer.

Usage:
    python scripts/scrape_lever.py
"""

import csv
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from jobpipeline.persistence import upsert_posting, log_run, format_summary
from jobpipeline.models import Posting, SourceRun, utcnow_iso
from jobpipeline.db import connect

SLUGS_PATH = Path(__file__).parent.parent / "data" / "lever_slugs.csv"
BASE_URL = "https://api.lever.co/v0/postings/{}?mode=json"
HEADERS = {"User-Agent": "Mozilla/5.0 (job search research tool)"}
SOURCE = "lever"


def fetch_postings(slug: str) -> list[dict]:
    try:
        r = requests.get(BASE_URL.format(slug), headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  Error fetching {slug}: {e}")
        return []


def parse_posting(raw: dict, company: str) -> Posting:
    created_at = raw.get("createdAt")
    if created_at:
        try:
            created_at = datetime.fromtimestamp(
                int(created_at) / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            created_at = None

    categories = raw.get("categories") or {}
    description = raw.get("descriptionPlain") or raw.get("description") or ""

    return Posting(
        source=SOURCE,
        source_job_id=raw.get("id", ""),
        company=company,
        role=raw.get("text", ""),
        location=categories.get("location") or categories.get("city") or None,
        department=categories.get("department") or categories.get("team") or None,
        url=raw.get("hostedUrl") or raw.get("applyUrl") or "",
        jd_text=description,
        posted_at=created_at,
    )


def load_slugs() -> list[dict]:
    if not SLUGS_PATH.exists():
        print(f"Slug file not found: {SLUGS_PATH}")
        print("Run discover_lever_slugs.py first.")
        return []
    with open(SLUGS_PATH) as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("slug")]


def main():
    slugs = load_slugs()
    if not slugs:
        print("No verified Lever slugs found. Exiting.")
        return

    print(f"Scraping {len(slugs)} Lever companies...\n")
    conn = connect()
    total_new = total_updated = total_errors = 0

    for row in slugs:
        company = row["company"]
        slug = row["slug"]
        print(f"  {company} ({slug})")
        now = utcnow_iso()

        raw_postings = fetch_postings(slug)
        new_count = updated_count = error_count = 0

        for raw in raw_postings:
            try:
                posting = parse_posting(raw, company)
                is_new = upsert_posting(conn, posting, now)
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                print(f"    Error parsing posting: {e}")
                error_count += 1

        conn.commit()

        run = SourceRun(
            source=SOURCE,
            company=company,
            postings_found=len(raw_postings),
            postings_new=new_count,
            postings_updated=updated_count,
            error_message=None,
            status="success" if error_count == 0 else "partial",
        )
        log_run(conn, run)
        conn.commit()

        print(f"    {len(raw_postings)} fetched — {new_count} new, {updated_count} updated, {error_count} errors")
        total_new += new_count
        total_updated += updated_count
        total_errors += error_count
        time.sleep(1)

    conn.close()
    print(f"\nLever total: {total_new} new, {total_updated} updated, {total_errors} errors")


if __name__ == "__main__":
    main()
