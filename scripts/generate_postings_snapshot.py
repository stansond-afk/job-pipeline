"""Generate dashboard/postings.json — minimal snapshot for the Worker's
GET /api/posting/<id> endpoint.

This runs as a separate step in the nightly Actions workflow alongside
generate_dashboard.py. The Worker reads this JSON file via env.ASSETS
to pre-fill the Apply modal — much cheaper than putting full posting
data in D1.

Push 3 of Path C: truncate jd_text to first N chars to bound file size.
The Apply modal uses this for the JD snapshot pre-fill, which the user
then can edit before submitting. 3000 chars is enough to capture the
substance of most JDs (responsibilities, qualifications, location).

Usage (from repo root):
    python scripts/generate_postings_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobpipeline.db import connect

OUT_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "postings.json"

# Cap on jd_text length per row. 3000 chars is enough to cover most JDs'
# substance; longer JDs get truncated with an ellipsis.
JD_TEXT_CAP = 3000

# Match the dashboard's render floor — the Apply modal only opens for
# postings the user can actually see, so we don't need to ship snapshots
# for filtered-out rows. Kept in sync with generate_dashboard.RENDER_MIN_FIT_SCORE.
SNAPSHOT_MIN_FIT_SCORE = 0.15

SNAPSHOT_COLUMNS = [
    "id",
    "company",
    "role",
    "url",
    "location",
    "jd_text",
    "interest_level",
]


def main() -> int:
    conn = connect()
    cur = conn.execute(f"""
        SELECT {', '.join('p.' + c for c in SNAPSHOT_COLUMNS)}
        FROM postings p
        LEFT JOIN applications a ON a.posting_id = p.id
        WHERE p.is_active = 1
          AND (
            p.fit_score >= ?
            OR a.id IS NOT NULL
            OR p.interest_level IN ('interested','very_interested')
          )
        GROUP BY p.id
        ORDER BY p.id
    """, (SNAPSHOT_MIN_FIT_SCORE,))
    rows = []
    truncated_count = 0
    for r in cur.fetchall():
        d = dict(r)
        if d.get("jd_text") and len(d["jd_text"]) > JD_TEXT_CAP:
            d["jd_text"] = d["jd_text"][:JD_TEXT_CAP] + "…"
            truncated_count += 1
        rows.append(d)

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")

    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"Wrote {len(rows)} postings to {OUT_PATH} ({size_mb:.1f} MB)")
    print(f"  ({truncated_count} JDs truncated to {JD_TEXT_CAP} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
