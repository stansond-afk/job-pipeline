"""GreenJobs.com RSS scraper.

Fetches the public RSS feed from greenjobsearch.org (the public-facing domain
of Green Jobs Network's job board, running on the JobRoller WordPress plugin)
and upserts postings into the SQLite database.

This is a single-feed source — unlike Greenhouse / Lever / NEOGOV which
iterate over per-company targets, GreenJobs is one aggregated feed across
many employers. Each <item> in the feed is a single job posting.

Coverage: sustainability, climate, environmental, conservation, clean energy,
renewable energy, and adjacent roles. Strong match for the user's interests.

Feed URL: https://greenjobs.greenjobsearch.org/feed/?post_type=job_listing
  - The feed returns up to ~10-25 recent job listings (WordPress default).
  - For more, we'd need to scrape additional pages — but this is the standard
    JobRoller behavior and the included items cover the most recent postings,
    which is what nightly polling cares about.

Design notes:
  - RSS 2.0 with WordPress-extension fields. Each <item> has the usual
    title/link/description/pubDate/guid. Company name lives in the description
    HTML (a JobRoller convention) and we extract it via regex.
  - source_job_id: GUID from the feed (typically the post permalink).
  - Strip HTML from description for jd_text, same convention as other scrapers.
  - One employer with multiple postings will appear as multiple items with
    different GUIDs, so the dedup constraint (source, source_job_id) handles
    repeat companies naturally.
  - Source label: 'greenjobs' (lowercase, slug-style, consistent with other
    scrapers).

Run:
    python scripts/scrape_greenjobs.py

No inputs required — single hardcoded feed URL.
"""

from __future__ import annotations

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


FEED_URL = "https://greenjobs.greenjobsearch.org/feed/?post_type=job_listing"
SOURCE_NAME = "greenjobs"
REQUEST_TIMEOUT_SEC = 30
USER_AGENT = "job-pipeline/0.1 (personal job search tooling)"

# Delay between per-posting page fetches to be polite. 0.5s × 20 items = ~10s
# extra per scrape, well within the workflow's 3-minute timeout for this step.
DELAY_BETWEEN_PAGES_SEC = 0.5


# ---------------------------------------------------------------------------
# HTML / XML helpers
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(s: str) -> str:
    """Strip HTML tags and collapse whitespace. Same pattern as other scrapers."""
    if not s:
        return ""
    no_tags = _HTML_TAG_RE.sub(" ", s)
    decoded = html.unescape(no_tags)
    return _WHITESPACE_RE.sub(" ", decoded).strip()


# JobRoller posting pages have predictable structure:
#
#   <title>Executive Director - Pacific Education Institute - greenjobsearch.org</title>
#   <strong class="job-location"><i ...></i>Olympia</strong>, <span>Washington, United States</span>
#
# We extract from both. The <title> split is reliable across every posting
# we've inspected; the location HTML is JobRoller's standard markup.

_TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)

# Location element: captures the city (group 1) and state-country (group 2).
# JobRoller wraps city in <strong class="job-location"> with an icon element
# inside that we skip via [^<]* before the city text.
_JOB_LOCATION_RE = re.compile(
    r'<strong\s+class="job-location"[^>]*>'   # opening strong tag
    r'(?:<i[^>]*>[^<]*</i>)?'                 # optional icon element
    r'\s*([^<]+?)\s*</strong>'                # group 1: city
    r'(?:,\s*<span[^>]*>\s*([^<]+?)\s*</span>)?',  # group 2: ", State, Country" via <span>
    re.IGNORECASE | re.DOTALL,
)


def extract_company_from_title(page_title: str) -> Optional[str]:
    """Parse the page's <title> tag for the company name.

    Expected format: "<role> - <company> - greenjobsearch.org"
    We take the middle part. Returns None if the title doesn't follow the
    pattern.
    """
    if not page_title:
        return None
    parts = [p.strip() for p in page_title.split(" - ")]
    # Need at least 3 parts: role, company, "greenjobsearch.org"
    if len(parts) < 3:
        return None
    # If the trailing part isn't the site name, the format is unexpected
    if "greenjobsearch.org" not in parts[-1].lower():
        return None
    # Middle parts are company (sometimes a multi-dash company name yields
    # parts[1] + parts[2] etc, so join everything between role and site name)
    company = " - ".join(parts[1:-1]).strip()
    return company or None


def extract_location_from_page(html_text: str) -> Optional[str]:
    """Extract location from the page's <strong class="job-location"> element.

    Returns a string like "Olympia, Washington, United States" or just "Olympia"
    if the trailing <span> isn't present. Returns None if the element isn't
    found.
    """
    if not html_text:
        return None
    m = _JOB_LOCATION_RE.search(html_text)
    if not m:
        return None
    city = (m.group(1) or "").strip()
    state_country = (m.group(2) or "").strip() if m.group(2) else ""
    if not city:
        return None
    if state_country:
        return f"{city}, {state_country}"
    return city


def fetch_posting_page(url: str) -> Optional[str]:
    """Fetch a single posting page HTML. Returns None on any failure.

    Graceful degradation: a failed fetch shouldn't kill the whole batch.
    The caller falls back to RSS-only data if this returns None.
    """
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SEC,
            headers={
                "Accept": "text/html",
                "User-Agent": USER_AGENT,
            },
        )
        if resp.status_code != 200:
            return None
        return resp.text
    except requests.RequestException:
        return None


def _title_text(html_text: str) -> Optional[str]:
    """Pull the <title> tag's text content, or None."""
    if not html_text:
        return None
    m = _TITLE_RE.search(html_text)
    if not m:
        return None
    return html.unescape(m.group(1).strip())


# ---------------------------------------------------------------------------
# Feed fetching + parsing
# ---------------------------------------------------------------------------

def fetch_feed() -> str:
    """Fetch the RSS feed and return raw XML text. Raises on HTTP errors."""
    resp = requests.get(
        FEED_URL,
        timeout=REQUEST_TIMEOUT_SEC,
        headers={
            "Accept": "application/rss+xml, application/xml, text/xml",
            "User-Agent": USER_AGENT,
        },
    )
    resp.raise_for_status()
    return resp.text


def parse_feed(xml_text: str) -> list[dict]:
    """Parse the RSS XML and return a list of item dicts.

    Each returned dict has keys: title, link, description, pub_date, guid.
    """
    root = ET.fromstring(xml_text)
    # RSS 2.0 has <rss><channel><item>...</item>...</channel></rss>
    channel = root.find("channel")
    if channel is None:
        return []

    items = []
    for item in channel.findall("item"):
        items.append({
            "title": _text_of(item, "title"),
            "link": _text_of(item, "link"),
            "description": _text_of(item, "description"),
            "pub_date": _text_of(item, "pubDate"),
            "guid": _text_of(item, "guid"),
        })
    return items


def _text_of(element: ET.Element, tag: str) -> str:
    """Helper: get the text content of a child element, or empty string."""
    child = element.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text


# ---------------------------------------------------------------------------
# Item → Posting transform
# ---------------------------------------------------------------------------

def item_to_posting(item: dict) -> Optional[Posting]:
    """Transform a feed item into our Posting shape. Returns None if invalid.

    Two-stage extraction:
      1. From the RSS item itself: title (= role), link (= url), guid (= id),
         description (= jd_text after HTML strip), pub_date.
      2. From the linked posting page (via fetch_posting_page): company name
         (from <title>), location (from <strong class="job-location">).

    If the page fetch fails, we fall back to "Green Jobs Network" + None for
    company/location respectively — better than dropping the posting entirely,
    since the role and link still let the user investigate.
    """
    title = (item.get("title") or "").strip()
    link = (item.get("link") or "").strip()
    description_html = item.get("description") or ""
    guid = (item.get("guid") or "").strip()

    if not title or not link:
        return None

    source_job_id = guid or link

    # Default fallbacks (used if page fetch fails)
    company: str = "Green Jobs Network"
    location: Optional[str] = None

    page_html = fetch_posting_page(link)
    if page_html:
        page_title = _title_text(page_html)
        if page_title:
            extracted_company = extract_company_from_title(page_title)
            if extracted_company:
                company = extracted_company
        extracted_location = extract_location_from_page(page_html)
        if extracted_location:
            location = extracted_location

    jd_text = strip_html(description_html)
    posted_at = (item.get("pub_date") or "").strip() or None

    return Posting(
        source=SOURCE_NAME,
        source_job_id=source_job_id,
        company=company,
        role=title,
        url=link,
        location=location,
        department=None,
        jd_text=jd_text,
        posted_at=posted_at,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape(conn) -> SourceRun:
    """Run the full scrape; return the SourceRun (already logged on return)."""
    run = SourceRun(source=SOURCE_NAME, company="GreenJobs.com (aggregated)")
    start = time.monotonic()

    try:
        xml_text = fetch_feed()
        items = parse_feed(xml_text)
        run.postings_found = len(items)

        now = utcnow_iso()
        for i, item in enumerate(items):
            posting = item_to_posting(item)
            if posting is None:
                continue
            was_new = upsert_posting(conn, posting, now)
            if was_new:
                run.postings_new += 1
            else:
                run.postings_updated += 1
            # Be polite: brief pause between page fetches. Last item doesn't
            # need it since we're done after.
            if i < len(items) - 1:
                time.sleep(DELAY_BETWEEN_PAGES_SEC)
        run.status = "success"
    except requests.HTTPError as e:
        run.status = "error"
        run.error_message = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except requests.RequestException as e:
        run.status = "error"
        run.error_message = f"request failed: {e}"
    except ET.ParseError as e:
        run.status = "error"
        run.error_message = f"XML parse error: {e}"
    except Exception as e:
        run.status = "error"
        run.error_message = f"{type(e).__name__}: {e}"
    finally:
        run.duration_ms = int((time.monotonic() - start) * 1000)
        log_run(conn, run)
        conn.commit()

    return run


def main() -> int:
    print(f"Scraping GreenJobs.com RSS feed into {DB_PATH}")
    print(f"  Source: {FEED_URL}")
    print()

    conn = connect()
    try:
        run = scrape(conn)
        print(format_summary(run))
        print()
        if run.status == "success":
            print(
                f"Summary: {run.postings_new} new, {run.postings_updated} updated "
                f"from {run.postings_found} items."
            )
            return 0
        else:
            print(f"FAILED: {run.error_message}")
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
