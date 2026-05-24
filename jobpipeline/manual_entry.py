"""Manual job entry — core logic.

Adds a single posting to the DB from a URL or pasted JD text, with optional
metadata overrides. Used by:
  - scripts/manual_entry_server.py (Flask wrapper for the dashboard form)
  - any future CLI / GitHub Action that wants to drop a job into the pipeline

No Flask, no requests for argparse. Pure logic — call add_manual_posting()
with the inputs and it returns a dict describing what happened.

Source tagging:
    source='manual', source_job_id=<sha1(url+role+company)[:16]>

The (source, source_job_id) UNIQUE constraint in postings means:
  - Re-pasting the same URL deduplicates cleanly
  - A URL pasted twice with different role/company names creates two records
    (intentional — typo correction by re-paste)

Scoring runs immediately. The new posting will appear in the dashboard at its
proper rank as soon as the page is regenerated (or refreshed if served live).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Make sibling package importable when this is called from a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import connect
from jobpipeline.models import Posting, SourceRun, utcnow_iso
from jobpipeline.persistence import log_run, upsert_posting

log = logging.getLogger(__name__)

# Optional dependencies — fail gracefully if missing so install is one-step
try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class EntryResult:
    """Outcome of a manual-entry attempt. Serializable for JSON return."""
    ok: bool
    message: str
    posting_id: Optional[int] = None
    is_new: Optional[bool] = None
    fit_score: Optional[float] = None
    score_notes: Optional[str] = None
    extracted: Optional[dict[str, Any]] = None  # what we auto-detected
    warnings: Optional[list[str]] = None

    def to_dict(self) -> dict[str, Any]:
        d = {"ok": self.ok, "message": self.message}
        if self.posting_id is not None:
            d["posting_id"] = self.posting_id
        if self.is_new is not None:
            d["is_new"] = self.is_new
        if self.fit_score is not None:
            d["fit_score"] = self.fit_score
        if self.score_notes is not None:
            d["score_notes"] = self.score_notes
        if self.extracted is not None:
            d["extracted"] = self.extracted
        if self.warnings:
            d["warnings"] = self.warnings
        return d


# ---------------------------------------------------------------------------
# URL fetching + extraction
# ---------------------------------------------------------------------------

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# A page is considered "thin" if it has less than this many chars of body
# text. Most JS-rendered ATSes return a shell of <100 chars; a real JD page
# is typically several thousand chars. 500 is a generous floor.
THIN_PAGE_THRESHOLD = 500


def fetch_url(url: str, timeout: int = 20) -> tuple[Optional[str], Optional[str]]:
    """Fetch a URL. Returns (html_or_none, error_or_none)."""
    if not _HAS_REQUESTS:
        return None, "requests library not installed"
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text, None
    except requests.RequestException as e:
        return None, f"fetch failed: {type(e).__name__}: {str(e)[:200]}"


@dataclass
class ExtractedFields:
    """Auto-detected fields from a fetched page or pasted text."""
    role: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    jd_text: Optional[str] = None
    posted_at: Optional[str] = None


def _clean_text(s: str) -> str:
    """Collapse whitespace and trim. Returns empty string if input is empty."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def extract_from_html(html: str) -> tuple[ExtractedFields, list[str]]:
    """Best-effort extraction of role/company/location/jd_text from page HTML.

    Returns (fields, warnings). Empty fields are left as None for the caller
    to fill in (or prompt the user for).

    Strategy, in priority order:
      1. JSON-LD JobPosting microdata (most reliable when present)
      2. Open Graph og:title / og:site_name
      3. <title> tag parsing — typical pattern is "Role - Company | Suffix"
      4. <meta name="description"> for jd_text fallback
      5. Body text for jd_text
    """
    fields = ExtractedFields()
    warnings: list[str] = []

    if not _HAS_BS4:
        warnings.append("beautifulsoup4 not installed; raw text extraction only")
        # Cheap fallback: take the whole body as jd_text after stripping tags
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        fields.jd_text = _clean_text(text)
        return fields, warnings

    soup = BeautifulSoup(html, "html.parser")

    # 1. JSON-LD JobPosting (reliable signal — many ATSes embed this)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        # Sometimes a list of objects, sometimes a single object
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "JobPosting":
                fields.role = fields.role or _clean_text(item.get("title") or "")
                org = item.get("hiringOrganization") or {}
                if isinstance(org, dict):
                    fields.company = fields.company or _clean_text(org.get("name") or "")
                loc = item.get("jobLocation")
                if isinstance(loc, list) and loc:
                    loc = loc[0]
                if isinstance(loc, dict):
                    addr = loc.get("address") or {}
                    if isinstance(addr, dict):
                        parts = [
                            _clean_text(addr.get("addressLocality") or ""),
                            _clean_text(addr.get("addressRegion") or ""),
                        ]
                        loc_str = ", ".join(p for p in parts if p)
                        if loc_str:
                            fields.location = fields.location or loc_str
                desc = item.get("description") or ""
                if isinstance(desc, str) and desc:
                    # description in JSON-LD is often HTML
                    desc_clean = re.sub(r"<[^>]+>", " ", desc)
                    fields.jd_text = fields.jd_text or _clean_text(desc_clean)
                fields.posted_at = fields.posted_at or item.get("datePosted")

    # 2. Open Graph
    og_title = soup.find("meta", property="og:title")
    og_site = soup.find("meta", property="og:site_name")
    if og_title and og_title.get("content"):
        if not fields.role:
            fields.role = _clean_text(og_title["content"])
    if og_site and og_site.get("content"):
        if not fields.company:
            fields.company = _clean_text(og_site["content"])

    # 3. <title> tag — common patterns: "Role at Company",
    #    "Role - Company", "Role | Company", "Role - Company - Job Board",
    #    "Role - Company | Job Board" (mixed separators).
    #
    # Strategy: split on ALL plausible separators in one pass, then take
    # the first segment as role and pick the first non-job-board segment
    # as company. This handles "ESG Analyst - World Bank | LinkedIn"
    # correctly as role="ESG Analyst", company="World Bank".
    if not fields.role or not fields.company:
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title_text = _clean_text(title_tag.string)
            # Split on any of these separators (regex with explicit space context
            # to avoid matching mid-word hyphens).
            split_re = re.compile(r"\s+(?:at|-|—|–|\||·)\s+", re.IGNORECASE)
            parts = [p.strip() for p in split_re.split(title_text) if p.strip()]
            if len(parts) >= 2:
                if not fields.role:
                    fields.role = parts[0]
                if not fields.company:
                    generic_suffixes = (
                        "indeed", "linkedin", "glassdoor", "monster",
                        "ziprecruiter", "wayup", "jobs", "careers",
                        "myworkdayjobs", "greenhouse",
                    )
                    # Walk segments after the first; take the first that
                    # doesn't look like a job-board suffix.
                    for candidate in parts[1:]:
                        if not any(g in candidate.lower() for g in generic_suffixes):
                            fields.company = candidate
                            break
                    # If every later segment looked like a job board, fall
                    # back to the first one rather than leaving company blank.
                    if not fields.company:
                        fields.company = parts[1]
            elif not fields.role:
                fields.role = title_text

    # 4. JD text fallback — meta description, then body
    if not fields.jd_text:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            fields.jd_text = _clean_text(meta_desc["content"])

    # 5. Body text — last resort, takes everything (verbose but better than nothing)
    if not fields.jd_text:
        # Strip script/style/nav/footer/header/aside tags first
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        body = soup.find("body")
        if body:
            fields.jd_text = _clean_text(body.get_text(separator=" "))

    # Sanity check: thin extraction → warn
    if fields.jd_text and len(fields.jd_text) < THIN_PAGE_THRESHOLD:
        warnings.append(
            f"Extracted JD text is short ({len(fields.jd_text)} chars). "
            "Page may be JS-rendered — consider pasting JD text manually."
        )

    return fields, warnings


def extract_from_pasted_text(text: str) -> ExtractedFields:
    """Best-effort extraction from pasted JD text. Heuristic only.

    The first non-empty line is often the role title. We don't try to guess
    company/location from raw pasted text — too unreliable.
    """
    fields = ExtractedFields()
    if not text:
        return fields
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        # First line, capped — protects against pathological "title is the
        # entire JD pasted on one line" inputs.
        first = lines[0]
        if len(first) <= 200:
            fields.role = first
    fields.jd_text = _clean_text(text)
    return fields


# ---------------------------------------------------------------------------
# Source-job-id synthesis
# ---------------------------------------------------------------------------

def _make_source_job_id(url: Optional[str], role: str, company: str) -> str:
    """Stable hash for dedup. Same (url + role + company) → same id."""
    seed = "|".join([
        (url or "").strip().lower(),
        role.strip().lower(),
        company.strip().lower(),
    ])
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def add_manual_posting(
    *,
    url: Optional[str] = None,
    jd_text: Optional[str] = None,
    role: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    fetch: bool = True,
    rescore: bool = True,
) -> EntryResult:
    """Add a manually-entered posting to the DB.

    At least one of (url with fetch=True), (jd_text), or (role + company)
    must be provided.

    Args:
      url: posting URL. If fetch=True and the URL is reachable, we try to
        auto-detect role/company/location/jd_text from the page.
      jd_text: pasted job description text. Used when URL fetch fails or
        the user prefers to paste directly.
      role / company / location: explicit overrides. If provided, they
        win over auto-detected values.
      fetch: if False, skip URL fetching even if url is provided. Useful
        when the caller has already fetched.
      rescore: if True, run the scorer on the new posting after upsert.

    Returns:
      EntryResult with ok=True and posting_id on success, or ok=False
      with message describing what went wrong.
    """
    warnings: list[str] = []
    extracted = ExtractedFields()

    # 1. If URL given and fetch enabled, try to extract
    fetched_html: Optional[str] = None
    if url and fetch:
        fetched_html, fetch_err = fetch_url(url)
        if fetch_err:
            warnings.append(fetch_err)
        elif fetched_html:
            extracted, html_warnings = extract_from_html(fetched_html)
            warnings.extend(html_warnings)

    # 2. If JD text was pasted, use that to fill in (overriding URL extraction
    #    only where pasted text gives us a signal)
    if jd_text:
        text_extracted = extract_from_pasted_text(jd_text)
        if not extracted.jd_text or len(text_extracted.jd_text or "") > len(extracted.jd_text or ""):
            extracted.jd_text = text_extracted.jd_text
        if not extracted.role and text_extracted.role:
            extracted.role = text_extracted.role

    # 3. Apply explicit overrides (caller-provided values win)
    final_role = role or extracted.role
    final_company = company or extracted.company
    final_location = location or extracted.location
    final_jd_text = extracted.jd_text  # don't let JD text be overridden by None

    # 4. Validate
    if not final_role:
        return EntryResult(
            ok=False,
            message="Could not determine role title. Please provide one explicitly.",
            extracted=_extracted_to_dict(extracted),
            warnings=warnings,
        )
    if not final_company:
        return EntryResult(
            ok=False,
            message="Could not determine company. Please provide one explicitly.",
            extracted=_extracted_to_dict(extracted),
            warnings=warnings,
        )
    if not (url or final_jd_text):
        return EntryResult(
            ok=False,
            message="Need either a URL or pasted JD text. Both were empty.",
            warnings=warnings,
        )

    # 5. Build the Posting
    source_job_id = _make_source_job_id(url, final_role, final_company)
    posting = Posting(
        source="manual",
        source_job_id=source_job_id,
        company=final_company.strip(),
        role=final_role.strip(),
        url=(url or "").strip() or "(no url)",
        location=(final_location or "").strip() or None,
        department=None,
        jd_text=final_jd_text or None,
        posted_at=extracted.posted_at,
    )

    # 6. Upsert + log
    conn = connect()
    run = SourceRun(source="manual", company=f"{final_role} @ {final_company}")
    started = time.monotonic()
    try:
        now = utcnow_iso()
        was_new = upsert_posting(conn, posting, now)
        run.postings_found = 1
        if was_new:
            run.postings_new = 1
        else:
            run.postings_updated = 1
        run.status = "success"
    except Exception as e:
        run.status = "error"
        run.error_message = f"{type(e).__name__}: {str(e)[:200]}"
        run.duration_ms = int((time.monotonic() - started) * 1000)
        log_run(conn, run)
        conn.commit()
        conn.close()
        return EntryResult(
            ok=False,
            message=f"Database error: {run.error_message}",
            warnings=warnings,
        )
    run.duration_ms = int((time.monotonic() - started) * 1000)
    log_run(conn, run)
    conn.commit()

    # 7. Look up the posting we just upserted, score it
    posting_id: Optional[int] = None
    fit_score: Optional[float] = None
    score_notes: Optional[str] = None
    cur = conn.cursor()
    cur.execute(
        "SELECT id, fit_score, score_notes FROM postings "
        "WHERE source = ? AND source_job_id = ?",
        (posting.source, posting.source_job_id),
    )
    row = cur.fetchone()
    if row is not None:
        posting_id = row["id"]

    if rescore and posting_id is not None:
        try:
            from scripts.score_postings import score_posting  # type: ignore
            fit_score, score_notes = score_posting(
                posting.role, posting.jd_text or "", posting.location
            )
            cur.execute(
                "UPDATE postings SET fit_score = ?, score_notes = ? WHERE id = ?",
                (fit_score, score_notes, posting_id),
            )
            conn.commit()
        except Exception as e:
            warnings.append(f"scoring failed: {type(e).__name__}: {e}")

    conn.close()

    return EntryResult(
        ok=True,
        message=("Added new posting" if run.postings_new else "Updated existing posting"),
        posting_id=posting_id,
        is_new=bool(run.postings_new),
        fit_score=fit_score,
        score_notes=score_notes,
        extracted=_extracted_to_dict(extracted),
        warnings=warnings or None,
    )


def _extracted_to_dict(e: ExtractedFields) -> dict[str, Any]:
    return {
        "role": e.role,
        "company": e.company,
        "location": e.location,
        "jd_text_length": len(e.jd_text) if e.jd_text else 0,
        "posted_at": e.posted_at,
    }
