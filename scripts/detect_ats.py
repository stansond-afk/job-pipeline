"""Detect ATS platform and slug from a list of company career page URLs.

For each company, fetches the careers page and looks for known ATS patterns
in the HTML. Outputs a CSV with company, detected ATS, and slug/tenant URL.

Usage:
    python scripts/detect_ats.py

Edit TARGETS below to add/remove companies.
Requires: requests, beautifulsoup4 (pip install requests beautifulsoup4)
"""

import re
import csv
import time
import requests
from pathlib import Path

OUT_PATH = Path(__file__).parent.parent / "data" / "ats_detected.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# (company_name, careers_page_url)
TARGETS = [
    ("Rocky Mountain Institute",        "https://rockymountain.wd1.myworkdayjobs.com/RMI"),
    ("Center for American Progress",    "https://www.americanprogress.org/about-us/jobs/"),
    ("Atlantic Council",                "https://www.atlanticcouncil.org/careers/"),
    ("Clean Air Task Force",            "https://www.catf.us/careers/"),
    ("Ceres",                           "https://www.ceres.org/careers/opportunities"),
    ("Results for Development",         "https://www.r4d.org/about/careers/"),
    ("Center for Climate & Energy Solutions", "https://www.c2es.org/about/careers/"),
    ("BlueGreen Alliance",              "https://www.bluegreenalliance.org/about/jobs/"),
    ("Bipartisan Policy Center",        "https://bipartisanpolicy.org/careers/"),
    ("New America",                     "https://www.newamerica.org/jobs/"),
    ("Rockefeller Foundation",          "https://www.rockefellerfoundation.org/about-us/careers/"),
    ("Bloomberg Philanthropies",        "https://www.bloomberg.org/careers/"),
    ("Hewlett Foundation",              "https://hewlett.org/about/careers/"),
    ("IREX",                            "https://www.irex.org/job-seekers"),
    ("Freedom House",                   "https://freedomhouse.org/about/jobs"),
    ("Bain & Company",                  "https://careers.bain.com/jobs"),
    ("Analysis Group",                  "https://www.analysisgroup.com/careers/"),
    # Additional high-value targets from xlsx not yet scraped
    ("ERM",                             "https://www.erm.com/careers/"),
    ("ICF International",               "https://www.icf.com/careers"),
    ("Tetra Tech",                      "https://www.tetratech.com/en/careers"),
    ("Conservation International",      "https://www.conservation.org/about/careers"),
    ("World Wildlife Fund",             "https://careers.worldwildlife.org/"),
    ("Environmental Defense Fund",      "https://www.edf.org/jobs"),
    ("Counterpart International",       "https://www.counterpart.org/careers/"),
    ("DAI Global",                      "https://www.dai.com/working-with-dai/job-opportunities"),
    ("Chemonics",                       "https://chemonics.com/careers/"),
    ("Winrock International",           "https://www.winrock.org/about/careers/"),
    ("FHI 360",                         "https://www.fhi360.org/careers"),
    ("Urban Institute",                 "https://www.urban.org/about/careers"),
    ("Brookings Institution",           "https://www.brookings.edu/about-brookings/careers/"),
    ("RAND Corporation",                "https://www.rand.org/jobs.html"),
]

# ATS detection patterns — (ats_name, regex_on_page_html)
ATS_PATTERNS = [
    ("greenhouse",   r"boards\.greenhouse\.io/([a-z0-9_-]+)"),
    ("greenhouse",   r"job-boards\.greenhouse\.io/([a-z0-9_-]+)"),
    ("lever",        r"jobs\.lever\.co/([a-z0-9_-]+)"),
    ("workday",      r"([\w-]+)\.wd\d+\.myworkdayjobs\.com"),
    ("workday",      r"myworkdayjobs\.com/([\w-]+)"),
    ("icims",        r"careers-([a-z0-9-]+)\.icims\.com"),
    ("ashby",        r"jobs\.ashbyhq\.com/([a-z0-9_-]+)"),
    ("bamboohr",     r"([a-z0-9-]+)\.bamboohr\.com"),
    ("smartrecruiters", r"careers\.smartrecruiters\.com/([a-zA-Z0-9_-]+)"),
    ("rippling",     r"ats\.rippling\.com/([a-z0-9_-]+)"),
    ("paycom",       r"([a-z0-9-]+)\.paycom\.com"),
    ("jobvite",      r"jobs\.jobvite\.com/([a-zA-Z0-9_-]+)"),
]


def detect_ats(url: str) -> tuple[str, str, str]:
    """
    Fetch the URL and detect ATS from HTML.
    Returns (ats_name, slug_or_tenant, actual_url_fetched).
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        final_url = r.url
        html = r.text

        # Check final URL first (redirect may reveal ATS)
        for ats, pattern in ATS_PATTERNS:
            m = re.search(pattern, final_url, re.IGNORECASE)
            if m:
                return ats, m.group(1) if m.lastindex else final_url, final_url

        # Check page HTML
        for ats, pattern in ATS_PATTERNS:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                return ats, m.group(1) if m.lastindex else "", final_url

        return "unknown", "", final_url

    except requests.exceptions.TooManyRedirects:
        return "error", "too_many_redirects", url
    except Exception as e:
        return "error", str(e)[:60], url


def main():
    results = []
    print(f"Detecting ATS for {len(TARGETS)} companies...\n")

    for company, url in TARGETS:
        ats, slug, final_url = detect_ats(url)
        status = f"✓ {ats} — {slug}" if ats not in ("unknown", "error") else f"? {ats}"
        print(f"  {company:<45} {status}")
        results.append({
            "company": company,
            "careers_url": url,
            "final_url": final_url,
            "ats": ats,
            "slug": slug,
        })
        time.sleep(0.75)

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["company", "careers_url", "final_url", "ats", "slug"])
        w.writeheader()
        w.writerows(results)

    verified = [r for r in results if r["ats"] not in ("unknown", "error")]
    greenhouse_hits = [r for r in verified if r["ats"] == "greenhouse"]
    lever_hits = [r for r in verified if r["ats"] == "lever"]
    workday_hits = [r for r in verified if r["ats"] == "workday"]
    other_hits = [r for r in verified if r["ats"] not in ("greenhouse", "lever", "workday")]

    print(f"\n{'='*60}")
    print(f"Results: {len(verified)}/{len(TARGETS)} ATS detected")
    print(f"  Greenhouse: {len(greenhouse_hits)}")
    print(f"  Lever:      {len(lever_hits)}")
    print(f"  Workday:    {len(workday_hits)}")
    print(f"  Other:      {len(other_hits)}")
    print(f"\nFull results written to: {OUT_PATH}")

    if greenhouse_hits:
        print("\nNew Greenhouse slugs to add to targets.csv:")
        for r in greenhouse_hits:
            print(f"  {r['company']:<45} slug={r['slug']}")
    if lever_hits:
        print("\nNew Lever slugs to add to lever_slugs.csv:")
        for r in lever_hits:
            print(f"  {r['company']:<45} slug={r['slug']}")


if __name__ == "__main__":
    main()
