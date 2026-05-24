"""Score all postings against the user's profile.

Algorithm (unchanged from the original v7; what changed is
that every tunable now comes from config/*.yaml instead of being baked
into this file):

  1. Normalize the role title.
  2. Title gate:
       - matches config.scoring.role_blacklist (substring) → filter (score=0)
       - matches config.scoring.role_whitelist           → pass
       - otherwise                                        → score_only
         (score-eligible but capped below "good" threshold)
  3. For each group in config.scoring.keyword_groups, if any keyword from
     that group is in the (role + JD) text, add the group's weight.
  4. Map raw weight to a 0-1 score using thresholds:
       raw ≥ strong_raw   → score 0.75-1.0  (linear in [strong_raw, MAX_RAW])
       raw ≥ good_raw     → score 0.50-0.75 (linear in [good_raw, strong_raw])
       raw > 0            → score 0.05-0.50 (linear in [0, good_raw])
       raw = 0            → score 0
  5. Apply geographic boost via jobpipeline.geo.apply_geo_boost.

NOTE on raw vs. 0-1: the YAML thresholds (`thresholds.strong = 0.75` etc.)
are the *final* score tier boundaries on the 0-1 scale. The conversion
above defines what "weight needed" maps to each tier. The internal
strong_raw / good_raw values are derived from a heuristic that 6.0 raw =
strong, 4.0 raw = good — that's the original defaults, kept for now. If
you want to tune the curve, edit STRONG_RAW / GOOD_RAW below.

Usage:
    python scripts/score_postings.py
    python scripts/score_postings.py --verbose
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

# Make the package importable when this script is invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline import config
from jobpipeline.db import DB_PATH
from jobpipeline.geo import apply_geo_boost, geo_tier


# Raw-weight breakpoints. Defaults match the original score_postings.py.
# These define the shape of the raw → 0-1 mapping, not the tier labels.
STRONG_RAW = 6.0
GOOD_RAW = 4.0


def normalize(text: str) -> str:
    """Lowercase, decode HTML entities, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"&amp;", "and", text)
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─────────────────────────────────────────────────────────────────────────
# Title gate: blacklist (always filter), whitelist (pass), else score_only
# ─────────────────────────────────────────────────────────────────────────


def check_title(role: str) -> tuple[str, str]:
    """Returns (verdict, reason). verdict ∈ {filter, pass, score_only}."""
    norm = normalize(role)
    for pat in config.role_blacklist():
        if pat.lower() in norm:
            return "filter", f"blacklist: {pat}"
    for pat in config.role_whitelist():
        if pat.lower() in norm:
            return "pass", ""
    return "score_only", ""


# ─────────────────────────────────────────────────────────────────────────
# Keyword scoring
# ─────────────────────────────────────────────────────────────────────────


def _max_raw() -> float:
    """Sum of all keyword-group weights — the theoretical max raw score."""
    return sum(g["weight"] for g in config.keyword_groups().values()) or 1.0


def score_posting(role: str, jd_text: str, location: str | None = None) -> tuple[float, str]:
    role = role or ""
    jd_text = jd_text or ""

    verdict, reason = check_title(role)
    if verdict == "filter":
        return 0.0, f"FILTERED: {reason}"

    combined = normalize(role + " " + jd_text)
    raw = 0.0
    notes_parts: list[str] = []

    for name, group in config.keyword_groups().items():
        hits = [kw for kw in group["keywords"] if kw.lower() in combined]
        if hits:
            raw += group["weight"]
            notes_parts.append(f"{name}({len(hits)})")

    # score_only roles capped just below the good threshold
    if verdict == "score_only":
        raw = min(raw, GOOD_RAW - 0.01)

    max_raw = _max_raw()
    if raw >= STRONG_RAW:
        score = 0.75 + 0.25 * min((raw - STRONG_RAW) / max(max_raw - STRONG_RAW, 0.01), 1.0)
    elif raw >= GOOD_RAW:
        score = 0.50 + 0.25 * (raw - GOOD_RAW) / max(STRONG_RAW - GOOD_RAW, 0.01)
    elif raw > 0:
        score = 0.05 + 0.45 * (raw / max(GOOD_RAW, 0.01))
    else:
        score = 0.0

    score = round(score, 4)
    notes_str = " | ".join(notes_parts) if notes_parts else "no_keyword_hits"

    # Apply geographic boost on top of keyword score
    score, notes_str = apply_geo_boost(score, notes_str, location)
    return score, notes_str


# ─────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────


def run(verbose: bool = False) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, role, jd_text, location FROM postings WHERE is_active = 1")
    rows = cur.fetchall()
    print(f"Scoring {len(rows)} active postings…")

    geo_counts: dict[str, int] = {}

    for row_id, role, jd_text, location in rows:
        fit_score, score_notes = score_posting(role, jd_text, location)
        cur.execute(
            "UPDATE postings SET fit_score = ?, score_notes = ? WHERE id = ?",
            (fit_score, score_notes, row_id),
        )
        tier, _ = geo_tier(location)
        geo_counts[tier] = geo_counts.get(tier, 0) + 1
        if verbose:
            print(f"  [{fit_score:.2f}] {(role or '')[:60]:<60} | {score_notes[:60]}")

    conn.commit()

    # Summary
    thresholds = config.score_thresholds()
    cur.execute(
        f"""
        SELECT
            SUM(CASE WHEN fit_score = 0                THEN 1 ELSE 0 END),
            SUM(CASE WHEN fit_score > 0 AND fit_score < ? THEN 1 ELSE 0 END),
            SUM(CASE WHEN fit_score >= ? AND fit_score < ? THEN 1 ELSE 0 END),
            SUM(CASE WHEN fit_score >= ? AND fit_score < ? THEN 1 ELSE 0 END),
            SUM(CASE WHEN fit_score >= ?                THEN 1 ELSE 0 END)
        FROM postings WHERE is_active = 1
        """,
        (thresholds["medium"], thresholds["medium"], thresholds["good"],
         thresholds["good"], thresholds["strong"], thresholds["strong"]),
    )
    filtered, low, medium, good, strong = cur.fetchone()
    print()
    print(f"  Strong  (≥ {thresholds['strong']:.2f}):  {strong or 0}")
    print(f"  Good    (≥ {thresholds['good']:.2f}):  {good or 0}")
    print(f"  Medium  (≥ {thresholds['medium']:.2f}):  {medium or 0}")
    print(f"  Low     (>0):     {low or 0}")
    print(f"  Filtered (= 0):   {filtered or 0}")
    print()
    print("  Geo tiers:")
    for tier, count in sorted(geo_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {tier:10} {count}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score postings against profile.")
    parser.add_argument("--verbose", action="store_true", help="Print per-posting scores.")
    args = parser.parse_args()
    run(verbose=args.verbose)
