"""NEOGOV / GovernmentJobs.com RSS scraper.

Reads config/targets.csv, filters to ATS == 'neogov', hits each jurisdiction's
public RSS job feed at governmentjobs.com, parses the XML, and upserts postings
into the SQLite database.

Feed URL patterns:
    https://www.governmentjobs.com/SearchEngine/JobsFeed?agency=<slug>
    https://www.governmentjobs.com/careers/<slug>/jobsfeed          (older, may still work)

We use the newer SearchEngine URL per NEOGOV's July 2025 deprecation notice.

Design notes:
  - RSS 2.0 feeds. Each <item> has title/link/description/pubDate/guid. We use
    guid as the stable job ID (stripping the URL base if present). If guid is
    missing, we fall back to a hash of title+link.
  - Descriptions contain HTML. We strip tags the same way as other scrapers.
  - No auth, no rate limit documented. We pace at 1 request/sec to be polite.
  - Some jurisdictions may return an empty feed (no current postings). That's
    a success with postings_found=0, not an error.

Run:
    python scripts/scrape_neogov.py

Input:
    config/targets.csv rows where ats == 'neogov'. Each row's ats_identifier is
    the agency slug (e.g. 'fairfaxcounty').
"""

from __future__ import annotations

import csv
import hashlib
import html
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import DB_PATH, connect
from jobpipeline.models import Posting, SourceRun, utcnow_iso
from jobpipeline.persistence import format_summary, log_run, upsert_posting

REPO_ROOT = Path(__file__).resolve().parent.parent
_PERSONAL_TARGETS = REPO_ROOT / "config" / "targets.csv"
_EXAMPLE_TARGETS = REPO_ROOT / "config" / "targets.example.csv"
TARGETS_CSV = REPO_ROOT / "config" / ("targets.csv" if _PERSONAL_TARGETS.exists() else "targets.example.csv")

NEOGOV_FEED_URL = "https://www.governmentjobs.com/SearchEngine/JobsFeed?agency={slug}"
REQUEST_TIMEOUT_SEC = 30
DELAY_BETWEEN_AGENCIES_SEC = 1.0


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def read_neogov_targets() -> list[dict]:
    """Load config/targets.csv, return rows where ats == 'neogov'."""
    if not TARGETS_CSV.exists():
        raise FileNotFoundError(f"Target list not found: {TARGETS_CSV}")
    rows = []
    with TARGETS_CSV.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            if (r.get("ats") or "").strip().lower() == "neogov":
                rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# HTML / XML helpers
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(s: str) -> str:
    if not s:
        return ""
    no_tags = _HTML_TAG_RE.sub(" ", s)
    decoded = html.unescape(no_tags)
    return _WHITESPACE_RE.sub(" ", decoded).strip()


def extract_location_from_description(description_text: str) -> Optional[str]:
    """NEOGOV RSS descriptions often include location info in a predictable place.

    The description HTML typically looks like:
        <p>Salary: $50,000 - $80,000<br/>
        Location: Fairfax, VA<br/>
        Department: ...<br/>
        Description: ...</p>

    We look for an explicit 'Location:' line and return what follows.
    Falls back to None if the pattern doesn't match — scoring can still work
    without location metadata.
    """
    if not description_text:
        return None
    m = re.search(r"Location\s*:\s*([^\r\n<]+?)(?:<|\r|\n|$)", description_text, re.I)
    if m:
        return m.group(1).strip().rstrip(" ,;")
    return None


def stable_job_id(item: dict) -> str:
    """Return a stable ID for a posting across scrape runs.

    Prefer guid → link → hash(title+link). NEOGOV's guid is usually a full URL
    with the numeric job ID at the end; we keep it intact rather than parsing
    out the number, since URL-as-ID is unambiguous.
    """
    if item.get("guid"):
        return item["guid"]
    if item.get("link"):
        return item["link"]
    blob = (item.get("title", "") + "|" + item.get("link", "")).encode("utf-8")
    return "hash:" + hashlib.sha1(blob).hexdigest()


# ---------------------------------------------------------------------------
# RSS fetch + parse
# ---------------------------------------------------------------------------

def fetch_feed(slug: str) -> bytes:
    """Fetch the raw RSS XML bytes for one NEOGOV agency. Raises on HTTP errors."""
    url = NEOGOV_FEED_URL.format(slug=slug)
    resp = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SEC,
        headers={
            "User-Agent": "job-pipeline/0.1 (personal job search tooling)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    resp.raise_for_status()
    return resp.content


def parse_feed(xml_bytes: bytes) -> list[dict]:
    """Parse RSS 2.0 XML into a list of raw item dicts.

    Intentionally uses only stdlib xml.etree — no lxml/feedparser dependencies.
    Falls back gracefully if a field is missing.
    """
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"invalid XML: {e}") from e

    # RSS 2.0 structure: <rss><channel><item>...</item>...</channel></rss>
    # Find the <channel> and then all <item>s.
    channel = root.find("channel")
    if channel is None:
        # Some feeds are atom or have odd roots — try finding items anywhere
        item_nodes = root.findall(".//item")
    else:
        item_nodes = channel.findall("item")

    for node in item_nodes:
        item: dict = {}
        for tag in ("title", "link", "description", "pubDate", "guid", "category"):
            el = node.find(tag)
            if el is not None and el.text:
                item[tag] = el.text.strip()
        items.append(item)
    return items


def item_to_posting(agency_name: str, item: dict) -> Optional[Posting]:
    """Transform an RSS item dict into our Posting shape.

    Returns None if the item is too malformed to use (no title and no link).
    """
    title = item.get("title")
    link = item.get("link")
    if not title and not link:
        return None

    job_id = stable_job_id(item)
    description_raw = item.get("description", "")
    location = extract_location_from_description(description_raw)

    return Posting(
        source="neogov",
        source_job_id=job_id,
        company=agency_name,
        role=title or "(untitled)",
        url=link or "",
        location=location,
        department=None,  # NEOGOV RSS doesn't consistently expose department
        jd_text=strip_html(description_raw) or None,
        posted_at=item.get("pubDate"),
    )


# ---------------------------------------------------------------------------
# Scrape logic
# ---------------------------------------------------------------------------

def scrape_one(conn, target: dict) -> SourceRun:
    """Scrape one NEOGOV agency feed. Returns the SourceRun (already logged)."""
    agency_name = target["company"]
    slug = target["ats_identifier"].strip()
    run = SourceRun(source="neogov", company=agency_name)
    start = time.monotonic()

    try:
        xml_bytes = fetch_feed(slug)
        items = parse_feed(xml_bytes)
        run.postings_found = len(items)
        now = utcnow_iso()
        for item in items:
            posting = item_to_posting(agency_name, item)
            if posting is None:
                continue
            was_new = upsert_posting(conn, posting, now)
            if was_new:
                run.postings_new += 1
            else:
                run.postings_updated += 1
        run.status = "success"
    except requests.HTTPError as e:
        run.status = "error"
        code = e.response.status_code if e.response is not None else "??"
        body_preview = (e.response.text or "")[:200] if e.response is not None else ""
        run.error_message = f"HTTP {code}: {body_preview}"
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
    targets = read_neogov_targets()
    if not targets:
        print("No NEOGOV-tagged jurisdictions in config/targets.csv. Nothing to do.")
        print("To add one, edit config/targets.csv with a row like:")
        print("  Fairfax County Government,government-state-local,B,neogov,fairfaxcounty")
        return 0

    print(f"Scraping {len(targets)} NEOGOV agency feeds into {DB_PATH}")
    print()

    conn = connect()
    try:
        runs: list[SourceRun] = []
        for i, target in enumerate(targets):
            run = scrape_one(conn, target)
            runs.append(run)
            print(format_summary(run))
            if i < len(targets) - 1:
                time.sleep(DELAY_BETWEEN_AGENCIES_SEC)

        print()
        total_new = sum(r.postings_new for r in runs)
        total_updated = sum(r.postings_updated for r in runs)
        errors = [r for r in runs if r.status == "error"]
        print(f"Summary: {total_new} new, {total_updated} updated across "
              f"{len(runs) - len(errors)} successful feeds, {len(errors)} errors.")
        return 0 if not errors else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
