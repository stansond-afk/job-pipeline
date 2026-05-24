"""Greenhouse slug discovery.

For each company flagged as ATS = 'greenhouse' in the master target list,
try a set of plausible slug variations against the public Greenhouse API
and report which (if any) work.

Why this exists:
    Scaling manual slug verification to 200+ companies is untenable. This script
    automates the grunt work — you review the output and decide whether to accept
    the findings.

Run:
    python scripts/discover_greenhouse_slugs.py

Input:
    Reads config/targets.csv — a superset of config/targets.csv. One row per
    company with their name and proposed ATS. The discovery script only tries
    rows where ATS == 'greenhouse'.

Output:
    Writes config/targets_discovered.csv with two new columns: 'verified_slug' and
    'job_count'. Manual review confirms before merging into config/targets.csv.
    Also prints a summary to stdout.

Design notes:
    - Rate-limited: 1 request / 0.5 sec across all trials, keep it polite.
    - Considers a slug "verified" if the API returns JSON with a 'jobs' key AND
      'meta.total' > 0. A board that exists but has 0 jobs is not useful.
    - Does NOT modify config/targets.csv directly. You eyeball the discovered file
      and decide what to accept.
"""

from __future__ import annotations

import csv
import re
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_CSV = REPO_ROOT / "config" / "targets.csv"
OUTPUT_CSV = REPO_ROOT / "data" / "targets_discovered.csv"

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
REQUEST_TIMEOUT_SEC = 15
RATE_LIMIT_DELAY_SEC = 0.5

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/json",
    "User-Agent": "job-pipeline/0.1 (slug discovery; personal job search tooling)",
})


# ---------------------------------------------------------------------------
# Slug generation — the heart of the script
# ---------------------------------------------------------------------------

_ACRONYM_IN_PARENS_RE = re.compile(r"\(([A-Z0-9][A-Z0-9\-]*)\)")
_NON_ALPHANUM_RE = re.compile(r"[^a-z0-9]+")

# Common suffixes we can safely strip to make alternate slug variants
_CORPORATE_SUFFIXES = [
    "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation",
    "international", "global", "usa", "us", "group", "foundation", "institute",
    "association", "society", "council", "center", "centre", "project",
    "initiative", "network", "alliance", "coalition", "company",
]

# Fillers that almost never appear in slugs but might appear in names
_FILLER_WORDS = {"the", "and", "of", "for", "a", "an", "on", "in"}


def _normalize(s: str) -> str:
    """Lowercase and strip everything that isn't a-z / 0-9 / space."""
    s = s.lower()
    # Drop parenthesized text (acronyms are extracted separately)
    s = re.sub(r"\([^)]*\)", "", s)
    # Collapse anything non-alphanumeric to a space
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    return " ".join(s.split())


def _split_words(s: str) -> list[str]:
    return _normalize(s).split()


def _strip_fillers(words: list[str]) -> list[str]:
    return [w for w in words if w not in _FILLER_WORDS]


def _strip_suffixes(words: list[str]) -> list[str]:
    result = list(words)
    while result and result[-1] in _CORPORATE_SUFFIXES:
        result.pop()
    return result


def candidate_slugs(company_name: str) -> list[str]:
    """Produce an ordered list of slug candidates to try.

    Strategy: try the most-likely slugs first, so we short-circuit on the
    first hit and don't waste requests.
    """
    candidates: list[str] = []

    # 1. Acronym from parens — "World Resources Institute (WRI)" -> "wri"
    # Also handle compound like "(WWF-US)" -> try "wwf" first, then "wwfus"
    # Highest-signal variant: if the name literally contains (XYZ), try xyz first.
    m = _ACRONYM_IN_PARENS_RE.search(company_name)
    if m:
        raw = m.group(1).lower()
        # If there's a dash, first segment is usually the org's own acronym
        if "-" in raw:
            candidates.append(raw.split("-", 1)[0])
            candidates.append(raw.replace("-", ""))
        else:
            candidates.append(raw)

    # 2. Acronym from capital letters across all words (e.g., "Center for American Progress" -> cap)
    # Strip parenthesized content first so we don't double-count the acronym we already tried.
    name_no_parens = re.sub(r"\([^)]*\)", "", company_name)
    words = _split_words(name_no_parens)
    words_no_filler = _strip_fillers(words)
    words_trimmed = _strip_suffixes(words_no_filler)

    if len(words_no_filler) >= 2:
        original_caps = re.findall(r"\b[A-Z]", name_no_parens)
        if 2 <= len(original_caps) <= 6:
            candidates.append("".join(original_caps).lower())

    # 3. All words concatenated, no separators — "worldresourcesinstitute"
    if words_trimmed:
        candidates.append("".join(words_trimmed))
    if words_no_filler and words_no_filler != words_trimmed:
        candidates.append("".join(words_no_filler))

    # 4. Hyphenated — "world-resources-institute"
    if words_trimmed:
        candidates.append("-".join(words_trimmed))
    if words_no_filler and words_no_filler != words_trimmed:
        candidates.append("-".join(words_no_filler))

    # 5. First word only (if distinctive enough; skip for generic words)
    if words_trimmed and len(words_trimmed[0]) >= 4:
        candidates.append(words_trimmed[0])

    # 6. First two words concatenated
    if len(words_trimmed) >= 2:
        candidates.append("".join(words_trimmed[:2]))

    # Dedupe, preserve order, strip empties
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        c = c.strip()
        if c and c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


# ---------------------------------------------------------------------------
# API probing
# ---------------------------------------------------------------------------

def probe_slug(slug: str) -> tuple[bool, int, Optional[str]]:
    """Return (is_valid, job_count, error_or_none).

    Valid means: HTTP 200, JSON has 'jobs' key, AND at least one job.
    An empty board (jobs=[]) is not considered a useful find — likely a stale slug
    or an org that's hosted on Greenhouse but never posts publicly.
    """
    url = GREENHOUSE_API.format(slug=slug)
    try:
        resp = SESSION.get(url, timeout=REQUEST_TIMEOUT_SEC)
    except requests.RequestException as e:
        return False, 0, f"request failed: {e}"

    if resp.status_code == 404:
        return False, 0, None  # Expected, no error worth logging
    if resp.status_code != 200:
        return False, 0, f"HTTP {resp.status_code}"

    try:
        data = resp.json()
    except ValueError as e:
        return False, 0, f"bad JSON: {e}"

    if "jobs" not in data:
        return False, 0, "missing 'jobs' key in response"

    count = len(data["jobs"])
    if count == 0:
        return False, 0, "empty board"
    return True, count, None


def discover_for_company(company_name: str) -> dict:
    """Try candidate slugs for one company and return a result record."""
    candidates = candidate_slugs(company_name)
    result = {
        "company": company_name,
        "verified_slug": "",
        "job_count": 0,
        "tried_slugs": candidates,
        "notes": "",
    }

    if not candidates:
        result["notes"] = "no candidates generated"
        return result

    attempts: list[str] = []
    for slug in candidates:
        valid, count, err = probe_slug(slug)
        attempts.append(f"{slug}={'✓' if valid else '✗'}")
        time.sleep(RATE_LIMIT_DELAY_SEC)
        if valid:
            result["verified_slug"] = slug
            result["job_count"] = count
            result["notes"] = f"hit on attempt {len(attempts)}: {', '.join(attempts)}"
            return result

    result["notes"] = f"no hit: {', '.join(attempts)}"
    return result


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def read_master() -> list[dict]:
    """Load targets_master.csv, return rows where ats == 'greenhouse'."""
    if not MASTER_CSV.exists():
        print(f"ERROR: master target list not found at {MASTER_CSV}")
        print("Expected columns: company, category, priority, ats, ats_identifier")
        sys.exit(1)

    rows = []
    with MASTER_CSV.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            if (r.get("ats") or "").strip().lower() == "greenhouse":
                rows.append(r)
    return rows


def write_discovered(rows: list[dict]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["company", "category", "priority", "ats",
                  "original_ats_identifier", "verified_slug", "job_count", "notes"]
    with OUTPUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    targets = read_master()
    if not targets:
        print("No Greenhouse-tagged companies in targets_master.csv. Nothing to do.")
        return 0

    print(f"Probing Greenhouse slugs for {len(targets)} companies "
          f"(~{RATE_LIMIT_DELAY_SEC}s per candidate, up to ~7 candidates each).")
    print(f"Expect roughly {len(targets) * 3}-{len(targets) * 7} seconds total.")
    print()

    results: list[dict] = []
    for i, target in enumerate(targets, 1):
        company = target["company"]
        print(f"[{i}/{len(targets)}] {company}...", end=" ", flush=True)
        discovery = discover_for_company(company)
        if discovery["verified_slug"]:
            print(f"✓ slug='{discovery['verified_slug']}' ({discovery['job_count']} jobs)")
        else:
            print(f"✗ no hit")

        results.append({
            "company": company,
            "category": target.get("category", ""),
            "priority": target.get("priority", ""),
            "ats": target.get("ats", ""),
            "original_ats_identifier": target.get("ats_identifier", ""),
            "verified_slug": discovery["verified_slug"],
            "job_count": discovery["job_count"],
            "notes": discovery["notes"],
        })

    write_discovered(results)
    hits = [r for r in results if r["verified_slug"]]
    misses = [r for r in results if not r["verified_slug"]]

    print()
    print("=" * 60)
    print(f"Found slugs: {len(hits)} / {len(results)} companies")
    print(f"Total postings across verified boards: {sum(r['job_count'] for r in hits)}")
    print()
    print(f"Output written to: {OUTPUT_CSV}")
    print()
    print("Review that file, then:")
    print("  1. For companies where verified_slug is empty, they may not actually")
    print("     use Greenhouse. Mark their ATS as 'unknown' in the master xlsx.")
    print("  2. For companies with a verified_slug, update config/targets.csv with")
    print("     the new slug and re-run scripts/scrape_greenhouse.py.")

    if misses:
        print()
        print(f"Misses ({len(misses)}):")
        for r in misses:
            print(f"  - {r['company']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
