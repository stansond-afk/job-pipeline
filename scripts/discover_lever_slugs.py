"""Discover Lever API slugs for target companies.

Lever's public API endpoint: https://api.lever.co/v0/postings/<slug>?mode=json
Returns a JSON array of postings if the slug is valid, 404 otherwise.

Usage:
    python scripts/discover_lever_slugs.py

Writes verified slugs to stdout and to data/lever_slugs.csv.
"""

import csv
import time
import requests
from pathlib import Path

OUT_PATH = Path(__file__).parent.parent / "data" / "lever_slugs.csv"

# Target companies tagged as Lever in the xlsx, with candidate slug variants to try.
# Format: (canonical_name, [slug_candidates])
TARGETS = [
    ("Union of Concerned Scientists", [
        "ucs",
        "union-of-concerned-scientists",
        "unionofconcernedscientists",
        "ucsusa",
    ]),
    ("American Clean Power Association", [
        "acp",
        "cleanpower",
        "american-clean-power",
        "americancleanpower",
        "acpa",
    ]),
    ("Third Way", [
        "thirdway",
        "third-way",
        "thirdwaythink",
    ]),
    ("International Republican Institute", [
        "iri",
        "international-republican-institute",
        "internationalrepublicaninstitute",
    ]),
    ("Asia Foundation", [
        "asiafoundation",
        "asia-foundation",
        "theasiafoundation",
    ]),
    ("Palantir", [
        "palantir",
        "palantirtechnologies",
        "palantir-technologies",
    ]),
]

BASE_URL = "https://api.lever.co/v0/postings/{}?mode=json"
HEADERS = {"User-Agent": "Mozilla/5.0 (job search research tool)"}


def try_slug(slug: str) -> int | None:
    """Return posting count if slug is valid, None if 404, -1 on other error."""
    try:
        r = requests.get(BASE_URL.format(slug), headers=HEADERS, timeout=10)
        if r.status_code == 200:
            try:
                data = r.json()
                return len(data) if isinstance(data, list) else 0
            except Exception:
                return 0
        elif r.status_code == 404:
            return None
        else:
            return -1
    except Exception as e:
        print(f"    Error on {slug}: {e}")
        return -1


def main():
    hits = []
    print("Discovering Lever slugs...\n")

    for company, candidates in TARGETS:
        print(f"{company}")
        found = False
        for slug in candidates:
            count = try_slug(slug)
            if count is not None and count >= 0:
                print(f"  ✓ {slug} — {count} postings")
                hits.append({"company": company, "slug": slug, "posting_count": count})
                found = True
                break
            else:
                print(f"  ✗ {slug}")
            time.sleep(0.5)  # be polite
        if not found:
            print(f"  — no slug found")
            hits.append({"company": company, "slug": "", "posting_count": 0})
        print()

    # Write results
    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["company", "slug", "posting_count"])
        w.writeheader()
        w.writerows(hits)

    verified = [h for h in hits if h["slug"]]
    print(f"Done. {len(verified)}/{len(TARGETS)} slugs found.")
    print(f"Results written to: {OUT_PATH}")
    print("\nVerified slugs:")
    for h in verified:
        print(f"  {h['company']:<45} slug={h['slug']}  ({h['posting_count']} postings)")


if __name__ == "__main__":
    main()
