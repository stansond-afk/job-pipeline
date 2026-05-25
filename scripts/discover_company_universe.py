"""Discover ATS boards across a $1B+ revenue company universe.

Builds a candidate company list by scraping public sources (Wikipedia
tables), then probes each company against Greenhouse + Lever APIs to
find which have public job boards we can scrape.

Solves the question: "There are great companies that aren't on
Fortune 500 / 1000 — can we find them anyway?" Answer: yes, by
aggregating multiple public sources and probing each programmatically.

USAGE
-----

    # First time / quarterly: refresh the company list from Wikipedia
    python scripts/discover_company_universe.py refresh

    # Probe each company against Greenhouse + Lever APIs (~30 min for ~600
    # companies due to rate limiting). Output is reviewable CSV.
    python scripts/discover_company_universe.py probe

    # Verify each hit by fetching board metadata + spot-checking actual
    # postings against company identity (rules out generic-slug collisions
    # like "national" matching the wrong company)
    python scripts/discover_company_universe.py verify

    # Do all three in sequence
    python scripts/discover_company_universe.py all

OUTPUT
------

    config/company_universe.csv    — aggregated list from Wikipedia (cached)
    config/probed_universe.csv     — probe results (raw)
    config/verified_universe.csv   — only the hits that passed verification

After running, eyeball verified_universe.csv and copy real hits into
config/targets.csv. (The generic-fork wizard offers a "import discovered
targets" step that automates this for non-technical users.)

SOURCES
-------

  1. S&P 500            ~500 US public companies, $1B+ revenue floor
  2. Largest US by rev  ~100 US largest by revenue (Fortune-style)
  3. Largest private    ~125 large private companies (Cargill, Mars, Koch...)

After dedup: ~600 unique companies. Total runtime for full pipeline
on a fresh universe: ~45-60 minutes.

EXTENDING
---------

To add a new source, write a `fetch_<source>()` function returning
list[dict] with at minimum a `company` key. Add it to `SOURCES`. The
aggregator handles dedup. Good candidates to add later:

  - Forbes Best Midsize Companies (~400, $1-10B revenue)
  - Crunchbase unicorn list (private VC-backed $1B+ valuations)
  - SEC EDGAR (every US-listed public company with revenue >$1B)

To probe a new ATS (e.g. SmartRecruiters, Ashby), add a `probe_<ats>()`
function and add it to `PROBERS`. Verification gets harder for ATSes
that don't expose a board-name field; falls back to manual review.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# BeautifulSoup is an existing dep (used by manual_entry.py).
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
UNIVERSE_CSV = CONFIG_DIR / "company_universe.csv"
PROBED_CSV = CONFIG_DIR / "probed_universe.csv"
VERIFIED_CSV = CONFIG_DIR / "verified_universe.csv"

USER_AGENT = "job-pipeline/0.1 (slug discovery; https://github.com/stansond-afk/job-pipeline)"
# SEC EDGAR requires a User-Agent with contact info; include an email so
# their fair-access logging works. Replace with your own when forking.
SEC_USER_AGENT = "job-pipeline/0.1 stansond@gmail.com"

# Community registry — shared infrastructure where users pool discovered slugs.
# Default points at the maintainer's deployed Worker; override via the
# JOB_PIPELINE_REGISTRY_URL env var if you run your own.
import os as _os
DEFAULT_REGISTRY_URL = "https://job-pipeline-registry.stansond.workers.dev"
REGISTRY_URL = _os.environ.get("JOB_PIPELINE_REGISTRY_URL", DEFAULT_REGISTRY_URL)
RATE_LIMIT_DELAY_SEC = 0.2     # Generous: Greenhouse/Lever public APIs
                                # easily handle 5 req/sec from a single client.
REQUEST_TIMEOUT = 15

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html"})


# ═════════════════════════════════════════════════════════════════════════
# SOURCES — Wikipedia table scrapers
# ═════════════════════════════════════════════════════════════════════════
#
# Each source returns list[dict] with keys: company, source, headquarters
# (optional), industry (optional). The aggregator dedupes by canonicalized
# company name, preserving the first source that mentioned it.


def fetch_sp500() -> list[dict]:
    """S&P 500 components — 500 US public companies, $1B+ revenue floor."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    soup = _wiki(url)
    table = soup.find("table", class_="wikitable")
    rows = []
    for tr in table.find_all("tr")[1:]:  # skip header
        cells = tr.find_all(["td", "th"])
        if len(cells) < 5:
            continue
        rows.append({
            "company":      _text(cells[1]),
            "source":       "sp500",
            "industry":     _text(cells[2]),
            "headquarters": _text(cells[4]),
        })
    return rows


def fetch_largest_us_by_revenue() -> list[dict]:
    """List of largest US companies by revenue (Fortune-100-ish list)."""
    url = "https://en.wikipedia.org/wiki/List_of_largest_companies_in_the_United_States_by_revenue"
    soup = _wiki(url)
    table = soup.find("table", class_="wikitable")
    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        rows.append({
            "company":      _text(cells[1]),
            "source":       "largest_us",
            "industry":     _text(cells[2]),
            "headquarters": _text(cells[6]) if len(cells) > 6 else "",
        })
    return rows


def fetch_largest_private() -> list[dict]:
    """List of largest private non-governmental companies by revenue
    (global). Many are US-headquartered (Cargill, Mars, Koch, Publix...);
    foreign ones may still have major US operations + Greenhouse boards."""
    url = "https://en.wikipedia.org/wiki/List_of_largest_private_non-governmental_companies_by_revenue"
    soup = _wiki(url)
    table = soup.find("table", class_="wikitable")
    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 4:
            continue
        rows.append({
            "company":      _text(cells[1]),
            "source":       "private",
            "industry":     "",
            "headquarters": _text(cells[3]),
        })
    return rows


def fetch_sec_edgar_tickers() -> list[dict]:
    """Every US-listed public company from SEC EDGAR. Single JSON, ~10K
    rows. Includes ETFs, foreign ADRs, SPACs — much of which won't have
    a Greenhouse board, but the slug-cache in probe() handles the waste."""
    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, timeout=REQUEST_TIMEOUT,
                     headers={"User-Agent": SEC_USER_AGENT,
                              "Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    return [
        {
            "company": entry.get("title", "").strip(),
            "source": "sec_edgar",
            "industry": "",
            "headquarters": "",
            "ticker": entry.get("ticker", "").strip(),
        }
        for entry in data.values()
        if entry.get("title")
    ]


def fetch_largest_charities() -> list[dict]:
    """Wikipedia: List of charitable foundations / largest US charities.
    NGOs are a known under-covered slice — many have Greenhouse boards
    (WRI, RMI, etc.) but aren't in the corporate revenue lists."""
    url = "https://en.wikipedia.org/wiki/List_of_wealthiest_charitable_foundations"
    soup = _wiki(url)
    table = soup.find("table", class_="wikitable")
    rows = []
    if not table:
        return rows
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        # Different rows have different schemas; try the first text-cell
        company = ""
        for c in cells[:3]:
            txt = _text(c)
            if txt and not txt.replace(",", "").replace(".", "").isdigit():
                company = txt
                break
        if not company:
            continue
        rows.append({
            "company":      company,
            "source":       "charity",
            "industry":     "nonprofit",
            "headquarters": "",
        })
    return rows


def fetch_think_tanks() -> list[dict]:
    """Wikipedia: List of think tanks in the US. Highly relevant for
    sustainability / policy / international development domains."""
    url = "https://en.wikipedia.org/wiki/List_of_think_tanks_in_the_United_States"
    try:
        soup = _wiki(url)
    except Exception:
        return []
    rows = []
    # The page is mostly lists/links rather than a single table. Pull
    # link text from main content area's bullet lists.
    content = soup.find("div", id="mw-content-text")
    if not content:
        return rows
    seen: set[str] = set()
    for li in content.find_all("li"):
        # Pick the first link if any — that's typically the org name
        a = li.find("a")
        if not a:
            continue
        name = a.get_text(strip=True)
        if (not name or len(name) < 4 or len(name) > 80
                or name.lower() in seen):
            continue
        # Quick filter: must look like an organization (has at least one
        # capitalized non-stopword), not a meta-link like "See also")
        if " " not in name and not name[0].isupper():
            continue
        # Skip Wikipedia navigation noise
        if name.lower().startswith(("see also", "category:", "references",
                                     "external links", "edit", "main article")):
            continue
        seen.add(name.lower())
        rows.append({
            "company":      name,
            "source":       "think_tank",
            "industry":     "think-tank",
            "headquarters": "",
        })
    return rows


SOURCES = [
    ("S&P 500",                fetch_sp500),
    ("Largest US by revenue",  fetch_largest_us_by_revenue),
    ("Largest private",        fetch_largest_private),
    ("Largest charities",      fetch_largest_charities),
    ("US think tanks",         fetch_think_tanks),
    ("SEC EDGAR (US public)",  fetch_sec_edgar_tickers),  # big — last so logs show ramp
]


def _wiki(url: str):
    r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def _text(cell) -> str:
    """Extract clean text from a BS4 cell. Strips footnote refs."""
    for sup in cell.find_all("sup"):
        sup.decompose()
    return cell.get_text(strip=True)


# ═════════════════════════════════════════════════════════════════════════
# REFRESH — aggregate sources into config/company_universe.csv
# ═════════════════════════════════════════════════════════════════════════


def cmd_refresh() -> int:
    print("Refreshing company universe from Wikipedia sources...\n")
    all_rows: list[dict] = []
    for label, fn in SOURCES:
        try:
            rows = fn()
            print(f"  {label:30} {len(rows)} companies")
            all_rows.extend(rows)
        except Exception as e:
            print(f"  {label:30} ERROR: {e}")
        time.sleep(RATE_LIMIT_DELAY_SEC)

    # Dedup by canonicalized company name. Preserve first occurrence's source.
    seen: dict[str, dict] = {}
    for row in all_rows:
        key = _canonicalize(row["company"])
        if not key:
            continue
        if key in seen:
            # Tag additional sources but don't replace
            seen[key]["sources"] = seen[key].get("sources", seen[key]["source"]) + "," + row["source"]
        else:
            row["sources"] = row["source"]
            seen[key] = row

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["company", "sources", "industry", "headquarters"]
    with UNIVERSE_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in seen.values():
            w.writerow(row)

    print()
    print(f"Wrote {len(seen)} unique companies to {UNIVERSE_CSV}")
    return 0


def _canonicalize(name: str) -> str:
    """Lowercase, strip punctuation + corporate suffixes, for dedup keys."""
    s = name.lower()
    s = re.sub(r"\([^)]*\)", " ", s)        # drop parenthetical
    s = re.sub(r"[^a-z0-9]+", " ", s)
    tokens = [t for t in s.split() if t]
    while tokens and tokens[-1] in {"inc", "corp", "corporation", "ltd",
                                     "limited", "llc", "co", "company",
                                     "group", "the"}:
        tokens.pop()
    return "".join(tokens)


# ═════════════════════════════════════════════════════════════════════════
# SLUG CANDIDATES — generate plausible slugs from a company name
# ═════════════════════════════════════════════════════════════════════════
#
# Lifted from the original discover_greenhouse_slugs.py (Solongo's repo).
# The order matters: most distinctive guesses first to maximize early hits
# and minimize wasted API calls.


_ACRONYM_IN_PARENS_RE = re.compile(r"\(([A-Z0-9][A-Z0-9\-]*)\)")

_CORPORATE_SUFFIXES = [
    "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation",
    "international", "global", "usa", "us", "group", "foundation", "institute",
    "association", "society", "council", "center", "centre", "project",
    "initiative", "network", "alliance", "coalition", "company", "co",
    "holdings",
]
_FILLER_WORDS = {"the", "and", "of", "for", "a", "an", "on", "in"}


def candidate_slugs(name: str) -> list[str]:
    """Return ordered list of plausible Greenhouse/Lever slugs for a company.

    Strategy: include both very-specific full-name variants AND short
    acronyms, ordered from most-likely-to-be-unique first. The verifier
    catches false positives downstream when a generic slug collides.
    """
    out: list[str] = []
    seen = set()

    def add(s: str):
        s = s.strip().lower()
        if s and 2 <= len(s) <= 50 and s not in seen:
            seen.add(s)
            out.append(s)

    # Acronyms in parentheses (e.g. "World Resources Institute (WRI)" → WRI)
    for m in _ACRONYM_IN_PARENS_RE.finditer(name):
        add(m.group(1))

    # Normalize: drop parenthetical, normalize punctuation
    norm = re.sub(r"\([^)]*\)", "", name).lower()
    norm = re.sub(r"[^a-z0-9\s]+", " ", norm)
    tokens = [t for t in norm.split() if t]
    tokens = [t for t in tokens if t not in _FILLER_WORDS]
    stripped = list(tokens)
    while stripped and stripped[-1] in _CORPORATE_SUFFIXES:
        stripped.pop()

    if stripped:
        add("".join(stripped))               # e.g. "charlesriverassociates"
        add("-".join(stripped))              # e.g. "charles-river-associates"
        # First word alone (e.g. "Bain" from "Bain & Company") — only if it's
        # not generic. The verifier handles false positives anyway.
        if len(stripped[0]) >= 4:
            add(stripped[0])
        # First two words combined
        if len(stripped) >= 2:
            add("".join(stripped[:2]))
            add("-".join(stripped[:2]))
        # All-letters acronym from initials
        if len(stripped) >= 2:
            acro = "".join(t[0] for t in stripped if t and t[0].isalpha())
            if 2 <= len(acro) <= 6:
                add(acro)

    return out


# ═════════════════════════════════════════════════════════════════════════
# PROBE — test each company against Greenhouse + Lever APIs
# ═════════════════════════════════════════════════════════════════════════


def probe_greenhouse(slug: str) -> tuple[bool, int]:
    """Return (has_jobs, job_count). False on any error."""
    try:
        r = SESSION.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return False, 0
        data = r.json()
        if not isinstance(data, dict) or "jobs" not in data:
            return False, 0
        count = (data.get("meta") or {}).get("total", 0) or len(data.get("jobs") or [])
        return count > 0, count
    except Exception:
        return False, 0


def probe_lever(slug: str) -> tuple[bool, int]:
    try:
        r = SESSION.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return False, 0
        data = r.json()
        if not isinstance(data, list):
            return False, 0
        return len(data) > 0, len(data)
    except Exception:
        return False, 0


PROBERS = [
    ("greenhouse", probe_greenhouse),
    ("lever",      probe_lever),
]


def cmd_probe(limit: Optional[int] = None) -> int:
    """Probe each company in the universe. Uses cross-company slug caching
    so we never probe the same (ats, slug) tuple twice — at universe scale
    (~10K companies, many sharing generic candidate slugs like 'national'
    or 'american'), this is the difference between a 6-hour and 20-hour
    run.

    With --limit, probes only the first N companies. Useful for sanity
    testing on a fresh universe before committing to the full run.
    """
    if not UNIVERSE_CSV.exists():
        print(f"ERROR: {UNIVERSE_CSV} not found. Run 'refresh' first.")
        return 1

    with UNIVERSE_CSV.open() as f:
        companies = list(csv.DictReader(f))
    if limit:
        companies = companies[:limit]

    # Slug result cache: (ats, slug) → (ok, count). Survives within one
    # probe run; persistence across runs is intentionally avoided so a
    # company opening a new Greenhouse board between probes is picked up.
    cache: dict[tuple[str, str], tuple[bool, int]] = {}

    print(f"Probing {len(companies)} companies against {len(PROBERS)} ATSes.")
    print(f"Slug-result caching ON (deduplicates API calls across companies).")
    print(f"Rate limit: {RATE_LIMIT_DELAY_SEC}s between API calls.\n")

    results: list[dict] = []
    hits = 0
    api_calls = 0
    cache_hits = 0
    last_progress = time.time()
    started = time.time()

    for i, c in enumerate(companies, 1):
        company = c["company"]
        candidates = candidate_slugs(company)
        found_ats, found_slug, found_count = "", "", 0

        for ats_name, prober in PROBERS:
            for slug in candidates:
                key = (ats_name, slug)
                if key in cache:
                    cache_hits += 1
                    ok, count = cache[key]
                else:
                    api_calls += 1
                    ok, count = prober(slug)
                    cache[key] = (ok, count)
                    time.sleep(RATE_LIMIT_DELAY_SEC)
                if ok:
                    found_ats, found_slug, found_count = ats_name, slug, count
                    break
            if found_ats:
                break

        if found_ats:
            hits += 1
            print(f"  [{i}/{len(companies)}] {company[:50]:50} → {found_ats}:{found_slug} ({found_count} jobs)")

        results.append({
            "company":       company,
            "sources":       c.get("sources", ""),
            "headquarters":  c.get("headquarters", ""),
            "industry":      c.get("industry", ""),
            "found_ats":     found_ats,
            "verified_slug": found_slug,
            "job_count":     found_count,
        })

        # Periodic progress on quieter stretches
        if time.time() - last_progress > 30:
            elapsed = time.time() - started
            rate = i / elapsed
            eta_min = (len(companies) - i) / rate / 60 if rate > 0 else 0
            print(f"  [{i}/{len(companies)}] {hits} hits · {api_calls} API calls · "
                  f"{cache_hits} cache hits · ETA {eta_min:.0f} min")
            last_progress = time.time()

    _write_csv(PROBED_CSV, results)
    elapsed_min = (time.time() - started) / 60
    print()
    print(f"Done in {elapsed_min:.1f} min: {hits}/{len(companies)} companies have a Greenhouse/Lever board.")
    print(f"  API calls:  {api_calls}")
    print(f"  Cache hits: {cache_hits} (saved that many redundant probes)")
    print(f"  Output: {PROBED_CSV}")
    return 0


# ═════════════════════════════════════════════════════════════════════════
# VERIFY — fetch board metadata + check posting content matches company
# ═════════════════════════════════════════════════════════════════════════
#
# Why this exists: short generic slugs ("national", "general", "inter",
# "capital", "oliver") often hit boards belonging to UNRELATED companies.
# Without verification the false-positive rate is ~50%. Verification gets
# it down to <5%.


_GENERIC_TOKENS = {
    "international", "national", "global", "general", "the", "of", "and",
    "for", "co", "inc", "llc", "corp", "corporation", "group", "company",
    "american", "united", "states", "usa", "us", "institute", "foundation",
    "association", "society", "center", "centre", "council", "alliance",
    "coalition", "network", "agency", "services", "solutions", "consulting",
}


def _distinctive_token(name: str) -> str:
    """The longest non-generic token from a company name. Empty if none."""
    name = re.sub(r"\([^)]*\)", "", name)
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z]+", name)]
    distinctive = [t for t in tokens if t not in _GENERIC_TOKENS and len(t) > 2]
    return max(distinctive, key=len) if distinctive else ""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch_greenhouse_board_name(slug: str) -> Optional[str]:
    """Greenhouse's /v1/boards/<slug> returns the board's display name —
    use that to verify the slug isn't pointing at a different company."""
    try:
        r = SESSION.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}",
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        return (r.json().get("name") or "").strip()
    except Exception:
        return None


def fetch_lever_first_postings(slug: str, n: int = 2) -> list[dict]:
    """Lever has no metadata API, so verification relies on inspecting
    actual postings — their location, team, title."""
    try:
        r = SESSION.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return data[:n] if isinstance(data, list) else []
    except Exception:
        return []


def verify_match(company: str, found_ats: str, slug: str) -> tuple[str, str]:
    """Return (verdict, evidence). Verdict ∈
        verified  — high confidence this slug belongs to this company
        mismatch  — slug points at a different company
        review    — couldn't conclusively verify (Lever, or no metadata)"""
    co_dist = _distinctive_token(company)

    if found_ats == "greenhouse":
        board = fetch_greenhouse_board_name(slug) or ""
        if not board:
            return "review", "no board metadata returned"
        # Real match: company's distinctive token appears in board name
        if co_dist and _norm(co_dist) in _norm(board):
            return "verified", f"board='{board}' contains distinctive '{co_dist}'"
        # Or: board's distinctive token appears in company name
        bd_dist = _distinctive_token(board)
        if bd_dist and _norm(bd_dist) in _norm(company):
            return "verified", f"company contains board's distinctive '{bd_dist}'"
        return "mismatch", f"board='{board}' has no token overlap with company"

    if found_ats == "lever":
        postings = fetch_lever_first_postings(slug, n=2)
        if not postings:
            return "review", "no postings returned"
        # Concatenate posting metadata; look for the company's distinctive
        # token in it. Most Lever clients have their company name in
        # team / categories / posting text somewhere.
        blob = " ".join(
            str(p.get(k, "")) + " " + str(p.get("categories", {}))
            for p in postings
            for k in ("text", "team", "department")
        ).lower()
        if co_dist and _norm(co_dist) in _norm(blob):
            return "verified", f"postings reference '{co_dist}'"
        return "review", f"postings don't clearly reference company; manual check needed"

    return "review", "unknown ATS"


def cmd_verify() -> int:
    if not PROBED_CSV.exists():
        print(f"ERROR: {PROBED_CSV} not found. Run 'probe' first.")
        return 1

    with PROBED_CSV.open() as f:
        rows = [r for r in csv.DictReader(f) if r.get("found_ats")]
    print(f"Verifying {len(rows)} hits...\n")

    # Detect duplicate-slug collisions (same slug claimed by multiple companies)
    slug_owners: dict[tuple, str] = {}

    out_rows = []
    counts = {"verified": 0, "mismatch": 0, "review": 0, "duplicate": 0}
    for r in rows:
        company = r["company"]
        ats = r["found_ats"]
        slug = r["verified_slug"]
        key = (ats, slug)

        if key in slug_owners:
            verdict = "duplicate"
            evidence = f"already claimed by '{slug_owners[key]}'"
        else:
            slug_owners[key] = company
            verdict, evidence = verify_match(company, ats, slug)

        time.sleep(RATE_LIMIT_DELAY_SEC)
        counts[verdict] = counts.get(verdict, 0) + 1

        mark = {"verified": "✓", "mismatch": "✗ FALSE", "duplicate": "✗ DUP", "review": "?"}[verdict]
        print(f"  {mark:8} {company[:40]:40} → {ats}:{slug} | {evidence[:50]}")

        out_rows.append({**r, "verdict": verdict, "evidence": evidence})

    _write_csv(VERIFIED_CSV, out_rows)
    print()
    print("Summary:")
    for v, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {v:10} {c}")
    print()
    print(f"Wrote {len(out_rows)} rows to {VERIFIED_CSV}")
    print(f"Review the file, then copy 'verified' rows into config/targets.csv.")
    return 0


# ═════════════════════════════════════════════════════════════════════════
# COMMUNITY REGISTRY — share + pull slugs across forks
# ═════════════════════════════════════════════════════════════════════════
#
# All optional + explicit. The `share` step prompts before sending; the
# `update-from-community` step shows you the diff before writing anything.


def _contributor_hash() -> str:
    """SHA256 of the user's email from config/profile.yaml. Opaque
    identifier — the registry uses this for dedup + abuse caps but
    never sees the plaintext. Empty string if email unconfigured."""
    import hashlib
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from jobpipeline import config
        email = (config.email() or "").strip().lower()
    except Exception:
        email = ""
    if not email:
        # Fall back to a stable per-machine identifier so anonymous
        # submissions still dedupe correctly.
        import socket
        email = f"anonymous@{socket.gethostname()}"
    return hashlib.sha256(email.encode("utf-8")).hexdigest()


def cmd_share() -> int:
    """Upload verified slugs to the community registry. Opt-in prompt
    before any data leaves the machine."""
    if not VERIFIED_CSV.exists():
        print(f"ERROR: {VERIFIED_CSV} not found. Run 'verify' first.")
        return 1

    with VERIFIED_CSV.open() as f:
        rows = [r for r in csv.DictReader(f) if r.get("verdict") == "verified"]
    if not rows:
        print("Nothing to share — no rows have verdict='verified'.")
        return 0

    print(f"About to share {len(rows)} verified slugs with the community registry:")
    print(f"  Endpoint:    {REGISTRY_URL}/api/community/submit-slugs")
    print(f"  Contributor: sha256(your email) — your email itself is NEVER sent")
    print()
    print("First 5 entries:")
    for r in rows[:5]:
        print(f"  {r['found_ats']:11} {r['verified_slug']:25} ({r['job_count']:>4} jobs)  {r['company'][:35]}")
    if len(rows) > 5:
        print(f"  ... and {len(rows) - 5} more")
    print()
    answer = input("Send these to the registry? [y/N]: ").strip().lower()
    if answer != "y":
        print("Aborted. Nothing sent.")
        return 0

    submissions = [{
        "ats":                r["found_ats"],
        "slug":               r["verified_slug"],
        "company_hint":       r["company"],
        "job_count_observed": int(r.get("job_count", 0) or 0),
    } for r in rows]

    # Chunk into batches of 200 (the Worker's per-request limit).
    batch_size = 200
    total_accepted = 0
    total_duplicates = 0
    total_rejected = 0
    for batch_start in range(0, len(submissions), batch_size):
        batch = submissions[batch_start: batch_start + batch_size]
        try:
            r = requests.post(
                f"{REGISTRY_URL}/api/community/submit-slugs",
                json={
                    "contributor_email_hash": _contributor_hash(),
                    "submissions": batch,
                },
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            if r.status_code != 200:
                print(f"  ERROR: HTTP {r.status_code}: {r.text[:200]}")
                return 1
            data = r.json()
            if not data.get("ok"):
                print(f"  ERROR: {data}")
                return 1
            total_accepted += data.get("accepted", 0)
            total_duplicates += data.get("duplicates", 0)
            total_rejected += data.get("rejected", 0)
        except Exception as e:
            print(f"  ERROR: {e}")
            return 1

    print()
    print(f"Submitted {len(submissions)} slugs:")
    print(f"  ✓ Accepted:   {total_accepted}")
    print(f"  · Duplicates: {total_duplicates}  (already submitted by you in a prior run)")
    print(f"  ✗ Rejected:   {total_rejected}    (invalid format or unknown ATS)")
    print()
    print("Thanks for contributing.")
    return 0


def cmd_update_from_community() -> int:
    """Pull the community consensus registry, diff against the local
    targets config, and prompt to merge new slugs."""
    print(f"Pulling community registry from {REGISTRY_URL}...")
    try:
        r = requests.get(
            f"{REGISTRY_URL}/api/community/slugs",
            params={"min_submissions": 2},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        if r.status_code != 200:
            print(f"ERROR: HTTP {r.status_code}: {r.text[:200]}")
            return 1
        data = r.json()
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    if not data.get("ok"):
        print(f"ERROR: {data}")
        return 1

    registry = data.get("registry", [])
    print(f"Got {len(registry)} community-verified slugs (min_submissions=2).")
    print()

    # Compare against local config/targets.csv
    targets_csv = CONFIG_DIR / "targets.csv"
    have: set[tuple[str, str]] = set()
    if targets_csv.exists():
        with targets_csv.open() as f:
            for row in csv.DictReader(f):
                ats = (row.get("ats") or "").strip().lower()
                slug = (row.get("ats_identifier") or "").strip().lower()
                if ats and slug:
                    have.add((ats, slug))

    new_rows = [
        r for r in registry
        if (r["ats"], r["slug"]) not in have
    ]
    print(f"  Already configured locally: {len(registry) - len(new_rows)}")
    print(f"  New from community:         {len(new_rows)}")
    print()

    if not new_rows:
        print("Nothing new to add. Your local targets are in sync with the community.")
        return 0

    # Show preview
    print("Sample of new community slugs (first 15):")
    for r in new_rows[:15]:
        company = r.get("company_canonical", "")
        count = r.get("submission_count", 0)
        print(f"  {r['ats']:11} {r['slug']:25} ({count} community submissions)  {company[:35]}")
    if len(new_rows) > 15:
        print(f"  ... and {len(new_rows) - 15} more")
    print()

    answer = input(f"Append all {len(new_rows)} to config/targets.csv? [y/N]: ").strip().lower()
    if answer != "y":
        print("Aborted. Nothing written.")
        return 0

    # Append. Preserve the existing schema (companies use targets.csv's columns).
    # Read header to get column order
    if not targets_csv.exists():
        targets_csv.parent.mkdir(parents=True, exist_ok=True)
        with targets_csv.open("w", newline="") as f:
            csv.writer(f).writerow(["company", "category", "priority", "location", "ats", "ats_identifier", "notes"])

    with targets_csv.open() as f:
        header = next(csv.reader(f))

    appended = 0
    with targets_csv.open("a", newline="") as f:
        w = csv.writer(f)
        for r in new_rows:
            row = []
            for col in header:
                if col == "company":
                    row.append(r.get("company_canonical", ""))
                elif col == "ats":
                    row.append(r["ats"])
                elif col == "ats_identifier":
                    row.append(r["slug"])
                elif col == "notes":
                    row.append(f"from community registry ({r.get('submission_count', 1)} submissions)")
                else:
                    row.append("")
            w.writerow(row)
            appended += 1

    print(f"Appended {appended} rows to {targets_csv}.")
    print(f"Re-run your scrapers to pick up the new targets:")
    print(f"  python3 scripts/scrape_greenhouse.py")
    print(f"  python3 scripts/scrape_lever.py")
    return 0


# ═════════════════════════════════════════════════════════════════════════
# IO helpers
# ═════════════════════════════════════════════════════════════════════════


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ═════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════


def cmd_all(limit: Optional[int] = None) -> int:
    rc = cmd_refresh()
    if rc != 0:
        return rc
    print()
    rc = cmd_probe(limit=limit)
    if rc != 0:
        return rc
    print()
    return cmd_verify()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover ATS boards across a $1B+ company universe.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh", help="Scrape sources → company_universe.csv")
    p_probe = sub.add_parser("probe",
        help="Probe each company against Greenhouse + Lever APIs (slow)")
    p_probe.add_argument("--limit", type=int, default=None,
        help="Probe only the first N companies (for testing).")
    sub.add_parser("verify",  help="Verify each hit by fetching board metadata")
    p_all = sub.add_parser("all", help="Run refresh → probe → verify in sequence")
    p_all.add_argument("--limit", type=int, default=None,
        help="Probe only the first N companies (for testing).")
    sub.add_parser("share",
        help="Submit your verified slugs to the community registry (opt-in)")
    sub.add_parser("update-from-community",
        help="Pull community-verified slugs + prompt to merge into config/targets.csv")
    args = parser.parse_args()

    if args.cmd == "refresh":
        return cmd_refresh()
    if args.cmd == "probe":
        return cmd_probe(limit=args.limit)
    if args.cmd == "verify":
        return cmd_verify()
    if args.cmd == "all":
        return cmd_all(limit=args.limit)
    if args.cmd == "share":
        return cmd_share()
    if args.cmd == "update-from-community":
        return cmd_update_from_community()
    return 1


if __name__ == "__main__":
    sys.exit(main())
