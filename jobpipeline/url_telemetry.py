"""URL telemetry — ATS detection and slug extraction.

Given a posting URL, return a (domain, ats_guess, ats_slug) tuple that we can
log to the url_telemetry table. Used by:
  - persistence.upsert_posting() to record telemetry on every scraper insert
  - manual_entry.py for manually-added postings
  - the Cloudflare Worker (D31) for /api/add-job submissions
  - scripts/backfill_url_telemetry.py to populate historical data
  - scripts/analyze_telemetry.py to surface coverage gaps

Design notes:
  - Pure function over the URL string, no I/O. Safe to call from any context.
  - When in doubt, return ats_guess='unknown'. False positives are worse than
    false negatives — a wrongly-tagged URL pollutes the coverage-gap report.
  - The slug is the platform-tenant identifier when extractable. For some
    platforms (Workable, opaque shortened URLs) no slug is available — we
    still tag the ATS but leave the slug NULL.

Coverage (as of session 20, based on actual URL distribution in jobs.db):
  - Top 15 platforms by posting count are all explicitly handled.
  - Long-tail company career sites (amazon.jobs, careers.marriott.com, etc.)
    fall through to 'unknown' — by design. Their value is in the domain
    column, not in inferring a fake ATS guess.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional
from urllib.parse import parse_qs, urlparse


class UrlTelemetry(NamedTuple):
    """Result of url_telemetry.parse(url)."""

    domain: str          # normalized hostname (lowercased, www. stripped, port stripped)
    ats_guess: str       # canonical ATS id; 'unknown' for unrecognized
    ats_slug: Optional[str]  # tenant/company slug when extractable, else None


# Canonical ATS identifiers. Centralized so analyze_telemetry.py can group on these
# and we don't drift between scrapers writing 'workday' vs 'Workday'.
ATS_GREENHOUSE     = "greenhouse"
ATS_LEVER          = "lever"
ATS_WORKDAY        = "workday"
ATS_ICIMS          = "icims"
ATS_BAMBOOHR       = "bamboohr"
ATS_AVATURE        = "avature"
ATS_PAYCOM         = "paycom"
ATS_SMARTRECRUITERS = "smartrecruiters"
ATS_DAYFORCE       = "dayforce"
ATS_ASHBY          = "ashby"
ATS_WORKABLE       = "workable"
ATS_JOBVITE        = "jobvite"
ATS_ULTIPRO        = "ultipro"
ATS_ADP            = "adp"
ATS_USAJOBS        = "usajobs"
ATS_NEOGOV         = "neogov"
ATS_AMAZON         = "amazon"
ATS_LINKEDIN       = "linkedin"     # aggregator, not an ATS — but worth tagging
ATS_INDEED         = "indeed"       # aggregator
ATS_UNKNOWN        = "unknown"


# Internal helpers ----------------------------------------------------------

def _normalize_domain(netloc: str) -> str:
    """Lowercase, strip www. and any port."""
    d = (netloc or "").lower()
    if ":" in d:
        d = d.split(":", 1)[0]
    if d.startswith("www."):
        d = d[4:]
    return d


def _path_segments(path: str) -> list[str]:
    """Return non-empty path segments of a URL path."""
    return [seg for seg in (path or "").split("/") if seg]


# The Workday subdomain pattern: <tenant>.wd<digit>.myworkdayjobs.com
# Also handles the slightly older <tenant>.myworkdayjobs.com without the wd<N>.
_WORKDAY_RE = re.compile(r"^(?P<tenant>[a-z0-9_-]+)\.(?:wd\d+\.)?myworkdayjobs\.com$")

# iCIMS pattern: careers-<tenant>.icims.com  OR  <tenant>.icims.com
_ICIMS_RE = re.compile(r"^(?:careers-)?(?P<tenant>[a-z0-9_-]+)\.icims\.com$")

# BambooHR pattern: <tenant>.bamboohr.com
_BAMBOOHR_RE = re.compile(r"^(?P<tenant>[a-z0-9_-]+)\.bamboohr\.com$")

# Avature pattern: <tenant>.avature.net
_AVATURE_RE = re.compile(r"^(?P<tenant>[a-z0-9_-]+)\.avature\.net$")


# Public API ----------------------------------------------------------------

def parse(url: str) -> UrlTelemetry:
    """Parse a URL into (domain, ats_guess, ats_slug).

    Robust against malformed input — returns UrlTelemetry('', 'unknown', None)
    for unparseable URLs rather than raising. Callers can still write a
    telemetry row in that case if they want; the domain '' is a clear sentinel.
    """
    if not url or not isinstance(url, str):
        return UrlTelemetry(domain="", ats_guess=ATS_UNKNOWN, ats_slug=None)

    try:
        parsed = urlparse(url)
    except Exception:
        return UrlTelemetry(domain="", ats_guess=ATS_UNKNOWN, ats_slug=None)

    domain = _normalize_domain(parsed.netloc)
    if not domain:
        return UrlTelemetry(domain="", ats_guess=ATS_UNKNOWN, ats_slug=None)

    path = parsed.path or ""
    segments = _path_segments(path)

    # --- Greenhouse ---
    # boards.greenhouse.io/<slug>/jobs/<id>     (legacy)
    # job-boards.greenhouse.io/<slug>/jobs/<id> (current)
    # boards.eu.greenhouse.io/<slug>/jobs/<id>
    # grnh.se/<opaque>                          (URL shortener — no extractable slug)
    if domain.endswith("greenhouse.io"):
        slug = segments[0] if segments else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_GREENHOUSE, ats_slug=slug)
    if domain == "grnh.se":
        return UrlTelemetry(domain=domain, ats_guess=ATS_GREENHOUSE, ats_slug=None)

    # --- Lever ---
    # jobs.lever.co/<slug>/<uuid>
    if domain == "jobs.lever.co":
        slug = segments[0] if segments else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_LEVER, ats_slug=slug)

    # --- Workday ---
    # <tenant>.wd<N>.myworkdayjobs.com/...
    wd_match = _WORKDAY_RE.match(domain)
    if wd_match:
        return UrlTelemetry(
            domain=domain,
            ats_guess=ATS_WORKDAY,
            ats_slug=wd_match.group("tenant"),
        )

    # --- iCIMS ---
    icims_match = _ICIMS_RE.match(domain)
    if icims_match:
        return UrlTelemetry(
            domain=domain,
            ats_guess=ATS_ICIMS,
            ats_slug=icims_match.group("tenant"),
        )

    # --- BambooHR ---
    bbhr_match = _BAMBOOHR_RE.match(domain)
    if bbhr_match:
        return UrlTelemetry(
            domain=domain,
            ats_guess=ATS_BAMBOOHR,
            ats_slug=bbhr_match.group("tenant"),
        )

    # --- Avature ---
    av_match = _AVATURE_RE.match(domain)
    if av_match:
        return UrlTelemetry(
            domain=domain,
            ats_guess=ATS_AVATURE,
            ats_slug=av_match.group("tenant"),
        )

    # --- Paycom ---
    # paycomonline.net/v4/ats/... — tenant lives in ?clientkey= query param
    if domain.endswith("paycomonline.net"):
        qs = parse_qs(parsed.query or "")
        clientkey = qs.get("clientkey", [None])[0]
        return UrlTelemetry(domain=domain, ats_guess=ATS_PAYCOM, ats_slug=clientkey)

    # --- SmartRecruiters ---
    # jobs.smartrecruiters.com/<Tenant>/<job-id>-<slug>
    if domain == "jobs.smartrecruiters.com":
        slug = segments[0] if segments else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_SMARTRECRUITERS, ats_slug=slug)

    # --- Dayforce (Ceridian) ---
    # jobs.dayforcehcm.com/<locale>/<tenant>/<portal>/jobs/<id>
    # First segment is locale (en-US), second is tenant.
    if domain == "jobs.dayforcehcm.com":
        slug = segments[1] if len(segments) >= 2 else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_DAYFORCE, ats_slug=slug)

    # --- Ashby ---
    # jobs.ashbyhq.com/<tenant>/<uuid>
    if domain == "jobs.ashbyhq.com":
        # First segment may be URL-encoded (e.g. 'Pulsora%20Inc'). Decode for storage.
        from urllib.parse import unquote
        slug = unquote(segments[0]) if segments else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_ASHBY, ats_slug=slug)

    # --- Workable ---
    # apply.workable.com/j/<opaque-id>  — no tenant in URL
    # <tenant>.workable.com/... — older format
    if domain == "apply.workable.com":
        return UrlTelemetry(domain=domain, ats_guess=ATS_WORKABLE, ats_slug=None)
    if domain.endswith(".workable.com"):
        tenant = domain.split(".workable.com", 1)[0]
        return UrlTelemetry(domain=domain, ats_guess=ATS_WORKABLE, ats_slug=tenant)

    # --- Jobvite ---
    # app.jobvite.com/CompanyJobs/Job.aspx?j=<id>  — no tenant in URL
    # jobs.jobvite.com/<tenant>/...                — older format
    if domain == "app.jobvite.com":
        return UrlTelemetry(domain=domain, ats_guess=ATS_JOBVITE, ats_slug=None)
    if domain.endswith(".jobvite.com"):
        slug = segments[0] if segments else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_JOBVITE, ats_slug=slug)

    # --- UltiPro / UKG ---
    # recruiting.ultipro.com/<TENANT_CODE>/... — first path segment is tenant
    if domain == "recruiting.ultipro.com":
        slug = segments[0] if segments else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_ULTIPRO, ats_slug=slug)

    # --- ADP (Workforce Now / MyJobs / Recruiting) ---
    # workforcenow.adp.com, myjobs.adp.com, recruiting.adp.com — multi-tenant,
    # tenant is in path or query depending on which ADP product.
    if domain.endswith(".adp.com"):
        # Best-effort: take first path segment, but it's often unreliable.
        slug = segments[0] if segments else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_ADP, ats_slug=slug)

    # --- USAJobs ---
    # usajobs.gov/...
    if domain.endswith("usajobs.gov"):
        return UrlTelemetry(domain=domain, ats_guess=ATS_USAJOBS, ats_slug=None)

    # --- NEOGOV ---
    # governmentjobs.com/careers/<jurisdiction>/...
    if domain.endswith("governmentjobs.com"):
        # Slug is jurisdiction (e.g. 'fairfaxcounty', 'loudoun')
        if segments and segments[0] == "careers" and len(segments) >= 2:
            slug = segments[1]
        else:
            slug = segments[0] if segments else None
        return UrlTelemetry(domain=domain, ats_guess=ATS_NEOGOV, ats_slug=slug)

    # --- Amazon Jobs ---
    # amazon.jobs/en/jobs/<id>
    if domain == "amazon.jobs":
        return UrlTelemetry(domain=domain, ats_guess=ATS_AMAZON, ats_slug="amazon")

    # --- LinkedIn / Indeed aggregators ---
    # These are low-signal (JobSpy fell back to permalink when job_url_direct was
    # null), but worth tagging so analyze_telemetry.py can filter them out cleanly.
    if domain.endswith("linkedin.com"):
        return UrlTelemetry(domain=domain, ats_guess=ATS_LINKEDIN, ats_slug=None)
    if domain.endswith("indeed.com"):
        return UrlTelemetry(domain=domain, ats_guess=ATS_INDEED, ats_slug=None)

    # --- Long tail: company career sites and unrecognized ATSes ---
    return UrlTelemetry(domain=domain, ats_guess=ATS_UNKNOWN, ats_slug=None)


# SQL helpers ----------------------------------------------------------------
#
# Kept here (rather than in persistence.py) so the URL-parsing module is the
# single owner of telemetry semantics. persistence.py imports these.

URL_TELEMETRY_INSERT_SQL = """
INSERT OR IGNORE INTO url_telemetry (
    url, domain, ats_guess, ats_slug, company_name, source, added_at, posting_id
) VALUES (
    :url, :domain, :ats_guess, :ats_slug, :company_name, :source, :added_at, :posting_id
);
"""


def record_url_telemetry(
    conn,
    *,
    url: str,
    source: str,
    company_name: Optional[str],
    added_at: str,
    posting_id: Optional[int] = None,
) -> None:
    """Write one url_telemetry row. Idempotent on (url, source) thanks to
    INSERT OR IGNORE. Caller commits.

    Safe to call on every scraper insert — INSERT OR IGNORE means the second
    occurrence of (url, source) is a no-op write at the SQL layer.

    Failures here must NOT propagate up to the caller. Telemetry is
    instrumentation; a failure here should never break a posting insert.
    The caller wraps this in try/except (see persistence.upsert_posting).
    """
    telemetry = parse(url)
    conn.execute(
        URL_TELEMETRY_INSERT_SQL,
        {
            "url": url,
            "domain": telemetry.domain,
            "ats_guess": telemetry.ats_guess,
            "ats_slug": telemetry.ats_slug,
            "company_name": company_name,
            "source": source,
            "added_at": added_at,
            "posting_id": posting_id,
        },
    )
