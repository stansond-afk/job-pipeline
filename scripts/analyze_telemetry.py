"""analyze_telemetry.py — coverage-gap report from url_telemetry (D32).

Reads the url_telemetry table and produces actionable views for scraper-coverage
expansion. The data answers four questions:

  1. SLUG GAPS (highest payoff): which Greenhouse/Lever/etc slugs is JobSpy
     finding that our direct scrapers don't have configured? Each one is a
     one-line config addition that converts a noisy JobSpy-only signal into
     reliable direct coverage.

  2. TARGET-LIST CROSSREF: which slug-gaps are A-tier or B-tier companies on
     Stanson's target list? Those are the wins to grab first.

  3. PLATFORM PRIORITY: which Workday / iCIMS / BambooHR / Avature tenants
     are showing up most often? Informs Phase 3 adapter prioritization and
     seeds the initial tenant list for whichever adapter ships first.

  4. UNKNOWN LONG-TAIL: which domains aren't being recognized at all but
     show up repeatedly? Candidates for future parser additions.

The report is plain text by default (designed for terminal reading and copy-
pasting into the project state doc). Pass --markdown for a slightly tidier
report suitable for committing to the repo.

Usage:
    python scripts/analyze_telemetry.py
    python scripts/analyze_telemetry.py --markdown > docs/coverage_gaps.md
    python scripts/analyze_telemetry.py --top 30        # show more rows per section
    python scripts/analyze_telemetry.py --since 30d     # only consider postings
                                                          first seen in last 30 days
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "jobs.db"
TARGETS_MASTER_CSV = REPO_ROOT / "config" / "targets.csv"


# ─────────────────────────────────────────────────────────────────────────
# Target-list crossref
# ─────────────────────────────────────────────────────────────────────────

def load_targets_master() -> list[dict]:
    """Read config/targets.csv. Returns [] if the file is missing.

    The crossref logic is best-effort — if the master list is unavailable
    we just skip the target-list view rather than crashing.
    """
    if not TARGETS_MASTER_CSV.exists():
        return []
    rows = []
    with TARGETS_MASTER_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def normalize_company(name: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace for fuzzy matching.

    Telemetry's company_name comes from scrapers and is often spelled slightly
    differently from targets_master.csv (e.g. "World Resources Institute" vs
    "World Resources Institute (WRI)"). Normalizing both sides catches these.
    """
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"\([^)]*\)", " ", n)         # drop parenthetical bits
    n = re.sub(r"[^a-z0-9\s]", " ", n)       # strip punctuation
    n = re.sub(r"\s+", " ", n).strip()
    # Common corporate suffixes that drift between sources
    for suffix in (" inc", " llc", " corp", " corporation", " ltd", " limited", " group", " co"):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n


def build_target_index(targets: list[dict]) -> dict[str, dict]:
    """Map normalized company name -> target row. Last write wins on collision
    (rare; collisions usually mean the master list has near-duplicates we'd
    want to surface for cleanup anyway).
    """
    idx = {}
    for r in targets:
        key = normalize_company(r.get("company") or "")
        if key:
            idx[key] = r
    return idx


def crossref_target(target_idx: dict[str, dict], company_name: Optional[str]) -> Optional[dict]:
    """Look up a telemetry company name against the target index."""
    if not company_name:
        return None
    key = normalize_company(company_name)
    if not key:
        return None
    if key in target_idx:
        return target_idx[key]
    # Fall back to substring matching for short telemetry names against longer
    # target entries. Only triggers when the key is reasonably distinctive
    # (>=4 chars) to avoid spurious hits.
    if len(key) >= 4:
        for target_key, target_row in target_idx.items():
            if key in target_key or target_key in key:
                return target_row
    return None


# ─────────────────────────────────────────────────────────────────────────
# Time filtering
# ─────────────────────────────────────────────────────────────────────────

def parse_since(since: Optional[str]) -> Optional[str]:
    """Parse a relative time spec like '30d', '7d', '24h' into an ISO cutoff.

    Returns None if since is None (i.e., no time filter). Raises ValueError
    on malformed input.
    """
    if not since:
        return None
    m = re.match(r"^(\d+)\s*([dh])$", since.strip().lower())
    if not m:
        raise ValueError(f"Invalid --since value: {since!r}. Expected like '30d' or '24h'.")
    n = int(m.group(1))
    unit = m.group(2)
    delta = timedelta(days=n) if unit == "d" else timedelta(hours=n)
    cutoff = datetime.now(timezone.utc) - delta
    return cutoff.isoformat(timespec="seconds")


# ─────────────────────────────────────────────────────────────────────────
# Query helpers
# ─────────────────────────────────────────────────────────────────────────

# Sources we treat as the "direct scraper" canonical set, by ATS. If a slug
# appears in url_telemetry under any of these sources, we consider it covered.
DIRECT_SCRAPER_SOURCES = {
    "greenhouse": {"greenhouse"},
    "lever":      {"lever"},
    "usajobs":    {"usajobs"},
    "neogov":     {"neogov"},
    # Phase 3 candidates — no direct scraper yet, so the set is empty.
    "workday":    set(),
    "icims":      set(),
    "bamboohr":   set(),
    "avature":    set(),
    "smartrecruiters": set(),
    "dayforce":   set(),
    "ashby":      set(),
    "workable":   set(),
    "jobvite":    set(),
    "ultipro":    set(),
    "adp":        set(),
    "paycom":     set(),
}


def slug_gaps_for_ats(
    conn: sqlite3.Connection,
    ats: str,
    since_iso: Optional[str],
) -> list[sqlite3.Row]:
    """Slugs detected for this ATS that are NOT covered by a direct scraper."""
    direct_sources = DIRECT_SCRAPER_SOURCES.get(ats, set())
    time_filter = "AND added_at >= ?" if since_iso else ""
    params: list = [ats]
    if since_iso:
        params.append(since_iso)

    if direct_sources:
        # Subquery defines "covered" set of slugs
        placeholders = ",".join("?" * len(direct_sources))
        sql = f"""
        SELECT ats_slug,
               COUNT(*) AS n,
               COUNT(DISTINCT company_name) AS distinct_companies,
               GROUP_CONCAT(DISTINCT company_name) AS companies,
               GROUP_CONCAT(DISTINCT source) AS sources
        FROM url_telemetry
        WHERE ats_guess = ?
          AND ats_slug IS NOT NULL
          AND ats_slug NOT IN (
              SELECT ats_slug FROM url_telemetry
              WHERE ats_guess = ?
                AND ats_slug IS NOT NULL
                AND source IN ({placeholders})
          )
          {time_filter}
        GROUP BY ats_slug
        ORDER BY n DESC
        """
        params = [ats, ats, *direct_sources]
        if since_iso:
            params.append(since_iso)
    else:
        # No direct scraper exists — every observed slug is a candidate
        sql = f"""
        SELECT ats_slug,
               COUNT(*) AS n,
               COUNT(DISTINCT company_name) AS distinct_companies,
               GROUP_CONCAT(DISTINCT company_name) AS companies,
               GROUP_CONCAT(DISTINCT source) AS sources
        FROM url_telemetry
        WHERE ats_guess = ?
          AND ats_slug IS NOT NULL
          {time_filter}
        GROUP BY ats_slug
        ORDER BY n DESC
        """

    return conn.execute(sql, params).fetchall()


def ats_totals(conn: sqlite3.Connection, since_iso: Optional[str]) -> list[sqlite3.Row]:
    where = "WHERE added_at >= ?" if since_iso else ""
    params = [since_iso] if since_iso else []
    sql = f"""
        SELECT ats_guess,
               COUNT(*) AS n,
               COUNT(DISTINCT ats_slug) AS distinct_slugs,
               COUNT(DISTINCT source) AS distinct_sources
        FROM url_telemetry
        {where}
        GROUP BY ats_guess
        ORDER BY n DESC
    """
    return conn.execute(sql, params).fetchall()


def unknown_domains(conn: sqlite3.Connection, since_iso: Optional[str], limit: int) -> list[sqlite3.Row]:
    where = "WHERE ats_guess = 'unknown'"
    params: list = []
    if since_iso:
        where += " AND added_at >= ?"
        params.append(since_iso)
    sql = f"""
        SELECT domain,
               COUNT(*) AS n,
               COUNT(DISTINCT company_name) AS distinct_companies,
               GROUP_CONCAT(DISTINCT company_name) AS companies
        FROM url_telemetry
        {where}
          AND domain <> ''
        GROUP BY domain
        ORDER BY n DESC
        LIMIT ?
    """
    params.append(limit)
    return conn.execute(sql, params).fetchall()


# ─────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────

def trunc(s: Optional[str], n: int) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1] + "…"


def render_report(
    conn: sqlite3.Connection,
    target_idx: dict[str, dict],
    since_iso: Optional[str],
    since_label: Optional[str],
    top: int,
    use_markdown: bool,
) -> str:
    out: list[str] = []
    h1 = "# " if use_markdown else ""
    h2 = "## " if use_markdown else ""
    h3 = "### " if use_markdown else ""
    hr = "\n---\n" if use_markdown else ("\n" + "─" * 75 + "\n")
    code = "`" if use_markdown else ""

    when = since_label or "all-time"
    out.append(f"{h1}URL telemetry — coverage report ({when})")
    out.append("")
    out.append(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    out.append(f"Database: {DB_PATH}")
    out.append("")

    # ── Summary ─────────────────────────────────────────────────────────
    totals = ats_totals(conn, since_iso)
    grand_total = sum(r["n"] for r in totals)
    out.append(hr.strip())
    out.append(f"{h2}Summary")
    out.append("")
    out.append(f"Total telemetry rows in window: {grand_total}")
    out.append("")
    out.append("ATS distribution:")
    for r in totals:
        ats = r["ats_guess"]
        slugs = f"  ({r['distinct_slugs']} distinct slugs)" if r["distinct_slugs"] else ""
        out.append(f"  {r['n']:>6}  {ats:<18}{slugs}")
    out.append("")

    # ── Section 1: SLUG GAPS for direct-scraped ATSes (Greenhouse, Lever) ─
    out.append(hr.strip())
    out.append(f"{h2}1. Slug gaps — easy wins")
    out.append("")
    out.append("These ATSes have direct scrapers configured today. Each row")
    out.append("below is a slug found in telemetry (e.g., via JobSpy) but")
    out.append("MISSING from the direct scraper's config. Adding the slug to")
    out.append("the scraper's target list gives reliable direct coverage of")
    out.append("that company on every run.")
    out.append("")

    direct_atses = [a for a, srcs in DIRECT_SCRAPER_SOURCES.items() if srcs]
    for ats in direct_atses:
        gaps = slug_gaps_for_ats(conn, ats, since_iso)[:top]
        out.append(f"{h3}{ats.title()} — {len(gaps)} slug gap{'s' if len(gaps) != 1 else ''}")
        if not gaps:
            out.append("  (No gaps — direct scraper already covers everything telemetry has seen.)")
            out.append("")
            continue
        # Build target-cross-ref view
        for r in gaps:
            slug = r["ats_slug"]
            companies = (r["companies"] or "").split(",") if r["companies"] else []
            primary_company = companies[0].strip() if companies else "?"
            target = crossref_target(target_idx, primary_company)
            target_tag = ""
            if target:
                priority = target.get("priority") or "?"
                category = target.get("category") or ""
                target_tag = f"  [TARGET {priority}-tier {category}]"
            sources_short = trunc(r["sources"], 40)
            out.append(
                f"  {r['n']:>3}  {code}{slug:<35}{code}  "
                f"{trunc(primary_company, 40):<40}{target_tag}"
            )
            if not use_markdown and len(companies) > 1:
                out.append(f"        also: {trunc(', '.join(c.strip() for c in companies[1:]), 60)}")
            if not use_markdown:
                out.append(f"        via: {sources_short}")
        out.append("")

    # ── Section 2: TARGET-LIST CROSSREF ─────────────────────────────────
    out.append(hr.strip())
    out.append(f"{h2}2. Slug gaps that are on your target list")
    out.append("")
    out.append("Same data as section 1, filtered to A/B/C-tier companies from")
    out.append("config/targets.csv. These are the highest-leverage fixes:")
    out.append("companies you already care about that you could be scraping")
    out.append("directly but aren't.")
    out.append("")
    target_hits = []
    if not target_idx:
        out.append("  (config/targets.csv not found — skipping crossref.)")
    else:
        for ats in direct_atses:
            for r in slug_gaps_for_ats(conn, ats, since_iso):
                companies = (r["companies"] or "").split(",") if r["companies"] else []
                primary_company = companies[0].strip() if companies else None
                target = crossref_target(target_idx, primary_company)
                if target:
                    target_hits.append({
                        "ats": ats,
                        "slug": r["ats_slug"],
                        "n": r["n"],
                        "company": primary_company,
                        "priority": target.get("priority") or "?",
                        "category": target.get("category") or "",
                        "target_company": target.get("company") or "",
                    })
        # Order by priority tier then count
        priority_order = {"A": 0, "B": 1, "C": 2}
        target_hits.sort(key=lambda h: (priority_order.get(h["priority"], 9), -h["n"]))
        if not target_hits:
            out.append("  (No slug gaps match your target list right now.)")
        else:
            for h in target_hits:
                out.append(
                    f"  [{h['priority']}] {code}{h['slug']:<30}{code}  "
                    f"({h['ats']:<10})  {trunc(h['target_company'], 50)}  "
                    f"— {h['n']} posting{'s' if h['n'] != 1 else ''}"
                )
    out.append("")

    # ── Section 3: PHASE 3 PLATFORM PRIORITY ────────────────────────────
    out.append(hr.strip())
    out.append(f"{h2}3. Phase 3 adapter prioritization")
    out.append("")
    out.append("Top tenants per multi-tenant ATS where we DON'T have a direct")
    out.append("scraper yet. The tenant slugs here would seed the initial")
    out.append("config for that adapter on first build.")
    out.append("")

    phase3_atses = ["workday", "icims", "bamboohr", "avature", "smartrecruiters",
                    "dayforce", "ashby", "ultipro", "jobvite", "workable", "adp", "paycom"]
    any_phase3 = False
    for ats in phase3_atses:
        gaps = slug_gaps_for_ats(conn, ats, since_iso)[:top]
        # Filter out NULL slugs (already handled in query) and skip if empty
        gaps = [g for g in gaps if g["ats_slug"]]
        if not gaps:
            continue
        any_phase3 = True
        total = sum(g["n"] for g in gaps)
        out.append(f"{h3}{ats.title()} — {len(gaps)} tenant{'s' if len(gaps) != 1 else ''}, {total} postings total")
        for r in gaps:
            companies = (r["companies"] or "").split(",") if r["companies"] else []
            primary_company = companies[0].strip() if companies else "?"
            target = crossref_target(target_idx, primary_company)
            tag = f"  [{target.get('priority')}-tier]" if target else ""
            out.append(
                f"  {r['n']:>3}  {code}{r['ats_slug']:<35}{code}  "
                f"{trunc(primary_company, 40)}{tag}"
            )
        out.append("")
    if not any_phase3:
        out.append("  (No Phase 3 ATSes detected in telemetry yet.)")
        out.append("")

    # ── Section 4: UNKNOWN LONG-TAIL ────────────────────────────────────
    out.append(hr.strip())
    out.append(f"{h2}4. Unrecognized domains")
    out.append("")
    out.append("Domains that don't match any known ATS pattern. High-volume")
    out.append("entries here are candidates for adding to the URL parser.")
    out.append("Each entry's `companies` column shows what company names")
    out.append("appeared on that domain — useful for spotting niche ATS")
    out.append("platforms vs. one-off company career pages.")
    out.append("")
    unknowns = unknown_domains(conn, since_iso, top)
    if not unknowns:
        out.append("  (No unrecognized domains in window.)")
    else:
        for r in unknowns:
            companies = trunc(r["companies"] or "", 60)
            out.append(
                f"  {r['n']:>4}  {code}{trunc(r['domain'], 45):<45}{code}  "
                f"{companies}"
            )
    out.append("")

    # ── Footer ──────────────────────────────────────────────────────────
    out.append(hr.strip())
    out.append("Tips:")
    out.append("  - Section 1 wins: add slug to config/targets.csv with ats=greenhouse (or lever)")
    out.append("    then re-run scripts/scrape_greenhouse.py.")
    out.append("  - Section 2 wins: same as section 1 but you definitely care.")
    out.append("  - Section 3 informs which Phase 3 adapter to build first and what")
    out.append("    tenant slugs to seed it with.")
    out.append("  - Section 4: add new platforms to jobpipeline/url_telemetry.py")
    out.append("    by extending the parse() function with a new regex.")
    out.append("")

    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--top", type=int, default=15,
        help="Max rows per section (default: 15)",
    )
    parser.add_argument(
        "--since", default=None,
        help="Filter to telemetry added in window like '30d', '7d', '24h' (default: all)",
    )
    parser.add_argument(
        "--markdown", action="store_true",
        help="Format output as markdown (for committing to a file)",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found.", file=sys.stderr)
        return 1

    try:
        since_iso = parse_since(args.since)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        # Sanity: telemetry table must exist
        ok = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='url_telemetry'"
        ).fetchone()
        if not ok:
            print("ERROR: url_telemetry table not found. Run db/migrate_003_url_telemetry.py first.", file=sys.stderr)
            return 1

        targets = load_targets_master()
        target_idx = build_target_index(targets)
        report = render_report(
            conn, target_idx,
            since_iso=since_iso,
            since_label=args.since,
            top=args.top,
            use_markdown=args.markdown,
        )
        print(report)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
