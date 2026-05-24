"""Migration 004: add achievements table + interest_updated_at column.

Backs the dopamine-mechanics features from the Solo's Garden redesign:

  - `achievements` table — 8 pre-seeded achievements (locked by default).
    Each row carries `earned_at` (ISO-8601 UTC, NULL = locked) and `seen_at`
    (when the unlock toast was dismissed).

  - `postings.interest_updated_at` — timestamp updated every time the user
    changes a posting's interest_level. Feeds the daily-streak computation
    (any positive action that day counts as showing up).

Idempotent. Safe to re-run.

Usage:
    python db/migrate_004_achievements_streak.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline.db import connect


NEW_POSTINGS_COLUMNS = [
    ("interest_updated_at", "TEXT"),
]

# Pre-seeded achievements. Order matters: this is also the display order
# on the dashboard's achievement shelf. Icons + names + descriptions are
# locked per the design handoff; do not change without re-syncing with
# design/dopamine-mechanics.md.
ACHIEVEMENT_SEEDS = [
    ("first_app",    "First brave step",    "Sent your first application",      "🌱"),
    ("tailor_5",     "Tailor's apprentice", "Tailored 5 resumes",               "🧵"),
    ("week_streak",  "Week one warrior",    "7-day streak",                     "🔥"),
    ("interview",    "First interview",     "Status → Interviewing",            "💬"),
    ("apps_10",      "Double digits",       "10 applications submitted",        "🏅"),
    ("weekly_15",    "Quota crusher",       "Hit 15 in a week",                 "🚀"),
    ("month_streak", "Steady gardener",     "30-day streak",                    "🌳"),
    ("offer",        "The big one",         "Receive an offer",                 "🌟"),
]


def existing_columns(conn, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row["name"] for row in cur.fetchall()}


def main() -> int:
    conn = connect()
    try:
        # --- 1. postings.interest_updated_at ---
        cols = existing_columns(conn, "postings")
        if not cols:
            print("ERROR: postings table does not exist. Run schema.sql first.")
            return 1

        added_cols, skipped_cols = [], []
        for col_name, col_def in NEW_POSTINGS_COLUMNS:
            if col_name in cols:
                skipped_cols.append(col_name)
            else:
                conn.execute(f"ALTER TABLE postings ADD COLUMN {col_name} {col_def}")
                added_cols.append(col_name)

        # --- 2. achievements table ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL,
                icon        TEXT NOT NULL,
                earned_at   TEXT,
                seen_at     TEXT
            )
        """)

        # Seed any missing rows; INSERT OR IGNORE preserves existing earned_at
        # so re-running the migration doesn't reset progress.
        seeded = 0
        for ach_id, name, desc, icon in ACHIEVEMENT_SEEDS:
            cur = conn.execute(
                "INSERT OR IGNORE INTO achievements (id, name, description, icon) VALUES (?, ?, ?, ?)",
                (ach_id, name, desc, icon),
            )
            if cur.rowcount:
                seeded += 1

        conn.commit()

        # --- Report ---
        if added_cols:
            print(f"postings: added columns: {', '.join(added_cols)}")
        if skipped_cols:
            print(f"postings: skipped (already present): {', '.join(skipped_cols)}")
        print(f"achievements: seeded {seeded} new rows (table now has {len(ACHIEVEMENT_SEEDS)} total)")

        # Final verification
        final_cols = existing_columns(conn, "postings")
        for col_name, _ in NEW_POSTINGS_COLUMNS:
            assert col_name in final_cols, f"post-migration check failed: postings.{col_name} missing"
        cur = conn.execute("SELECT COUNT(*) c FROM achievements")
        assert cur.fetchone()["c"] == len(ACHIEVEMENT_SEEDS), "achievements row count mismatch"

        print("Migration complete.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
