"""Dopamine-mechanics layer: streak, weekly goal, funnel, sparkline, achievements.

Backs the new "Solo's Garden" dashboard sections per
design_handoff_solongo_dashboard/dopamine-mechanics.md.

Defensive against missing tables — every function returns sensible
defaults if the achievements table or interest_updated_at column hasn't
been migrated in yet. Lets the dashboard render even on a partially-
upgraded DB.

Public surface:
    current_streak(conn)                  → int
    weekly_progress(conn)                 → dict {done, goal, days_active}
    sparkline_data(conn, days=14)         → list[int]
    funnel_counts(conn)                   → list[dict] (6 stages)
    get_achievements(conn)                → list[dict] (8 achievements)
    check_and_unlock(conn, now=None)      → list[str] (newly unlocked ids)
    todays_picks(conn, n=3)               → list[dict] (top N postings)
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from . import config


def weekly_goal() -> int:
    """Per-user weekly application target (config/profile.yaml)."""
    return config.weekly_goal()


# Achievement definitions — display order matters (this is the order they
# appear on the dashboard shelf). Pre-seeded by migration 004; this list is
# the source of truth for icons/names/descriptions when migration runs.
ACHIEVEMENT_DEFS = [
    {"id": "first_app",    "name": "First brave step",    "description": "Sent your first application", "icon": "🌱"},
    {"id": "tailor_5",     "name": "Tailor's apprentice", "description": "Tailored 5 resumes",          "icon": "🧵"},
    {"id": "week_streak",  "name": "Week one warrior",    "description": "7-day streak",                "icon": "🔥"},
    {"id": "interview",    "name": "First interview",     "description": "Status → Interviewing",       "icon": "💬"},
    {"id": "apps_10",      "name": "Double digits",       "description": "10 applications submitted",   "icon": "🏅"},
    {"id": "weekly_15",    "name": "Quota crusher",       "description": "Hit 15 in a week",            "icon": "🚀"},
    {"id": "month_streak", "name": "Steady gardener",     "description": "30-day streak",               "icon": "🌳"},
    {"id": "offer",        "name": "The big one",         "description": "Receive an offer",            "icon": "🌟"},
]


# Statuses that count as a submitted application (forward of "tailored")
SUBMITTED_STATUSES = ("submitted", "interviewing", "offered", "rejected", "withdrawn", "closed")


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------
#
# Background: scrapers (especially JobSpy) commonly find the same job many
# times — once per keyword query, sometimes once per board. The raw postings
# table can contain 41 rows for one PwC job in Baltimore. Each scrape gets
# a different source_job_id so the UNIQUE(source, source_job_id) constraint
# doesn't catch them.
#
# We dedup at QUERY TIME on a normalized (company, role, location) key:
#   - lowercase + trim each field
#   - strip ", US" / ", USA" / ", United States" / "." from location
#     (catches "Washington, DC" vs "Washington, DC, US" vs "Washington, D.C.")
#
# Picking the canonical row in each dedup group (window-function ORDER BY):
#   1. Rows with an application win (preserves user's pipeline state)
#   2. Direct ATS sources beat aggregators (greenhouse > lever > usajobs >
#      neogov > greenjobs > manual > jobspy:*)
#   3. Highest fit_score wins
#   4. Most recently seen wins


def _location_norm_expr(col: str) -> str:
    """SQL expression normalizing a location column for dedup grouping."""
    return (
        f"LOWER(TRIM(REPLACE(REPLACE(REPLACE(REPLACE("
        f"COALESCE({col}, ''), "
        f"', United States', ''), ', USA', ''), ', US', ''), '.', '')))"
    )


def dedup_key_expr(table_alias: str = "p") -> str:
    """SQL expression: returns the dedup key for a posting row."""
    return (
        f"LOWER(TRIM(COALESCE({table_alias}.company, ''))) || '|' || "
        f"LOWER(TRIM(COALESCE({table_alias}.role, ''))) || '|' || "
        f"{_location_norm_expr(table_alias + '.location')}"
    )


def canonical_rank_order(table_alias: str = "p", app_alias: str = "a") -> str:
    """SQL ORDER BY clause: picks the canonical row inside each dedup group."""
    return (
        f"CASE WHEN {app_alias}.id IS NOT NULL THEN 0 ELSE 1 END, "
        f"CASE "
        f"  WHEN {table_alias}.source = 'greenhouse' THEN 1 "
        f"  WHEN {table_alias}.source = 'lever' THEN 2 "
        f"  WHEN {table_alias}.source = 'usajobs' THEN 3 "
        f"  WHEN {table_alias}.source = 'neogov' THEN 4 "
        f"  WHEN {table_alias}.source = 'greenjobs' THEN 5 "
        f"  WHEN {table_alias}.source = 'manual' THEN 6 "
        f"  WHEN {table_alias}.source LIKE 'jobspy%' THEN 7 "
        f"  ELSE 99 "
        f"END, "
        f"COALESCE({table_alias}.fit_score, 0) DESC, "
        f"{table_alias}.first_seen DESC"
    )


# ---------------------------------------------------------------------------
# Schema-presence helpers
# ---------------------------------------------------------------------------


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row["name"] == column for row in cur.fetchall())


# ---------------------------------------------------------------------------
# Streak
# ---------------------------------------------------------------------------


def current_streak(conn: sqlite3.Connection) -> int:
    """Number of consecutive days ending today where the user took at
    least one action (changed an application status OR changed a
    posting's interest_level).

    Counts UTC days — close enough for a US user; we don't need timezone-
    accurate streak math.
    """
    has_interest_ts = _has_column(conn, "postings", "interest_updated_at")

    if has_interest_ts:
        sql = """
            SELECT DISTINCT DATE(t) AS d FROM (
                SELECT updated_at AS t FROM applications
                UNION
                SELECT interest_updated_at AS t FROM postings WHERE interest_updated_at IS NOT NULL
            )
            ORDER BY d DESC
        """
    else:
        # Migration 004 hasn't run yet — fall back to applications-only signal
        sql = "SELECT DISTINCT DATE(updated_at) AS d FROM applications ORDER BY d DESC"

    rows = conn.execute(sql).fetchall()
    streak = 0
    today = datetime.now(timezone.utc).date()
    for row in rows:
        d = row["d"]
        if not d:
            continue
        try:
            parsed = date.fromisoformat(d[:10])
        except ValueError:
            continue
        if parsed == today - timedelta(days=streak):
            streak += 1
        elif streak == 0 and parsed == today - timedelta(days=1):
            # No activity today yet, but yesterday had activity — streak still alive at 1
            streak = 1
        else:
            break
    return streak


# ---------------------------------------------------------------------------
# Weekly goal
# ---------------------------------------------------------------------------


def weekly_progress(conn: sqlite3.Connection, goal: Optional[int] = None) -> dict:
    """Applications submitted Mon 00:00 → Sun 23:59 (local).

    Returns:
        done:        count of submitted-or-forward applications this week
        goal:        the weekly target (15 by default)
        days_active: list[bool] length 7 — True if that day (M,T,W,T,F,S,S)
                     had at least one submission
        subtitle:    pre-computed copy line per dopamine-mechanics.md § 2
    """
    if goal is None:
        goal = weekly_goal()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=7)

    rows = conn.execute(
        f"""
        SELECT DATE(submitted_at) AS d
        FROM applications
        WHERE status IN ({",".join("?" * len(SUBMITTED_STATUSES))})
          AND submitted_at IS NOT NULL
          AND DATE(submitted_at) >= ?
          AND DATE(submitted_at) < ?
        """,
        (*SUBMITTED_STATUSES, week_start.isoformat(), week_end.isoformat()),
    ).fetchall()

    days_active = [False] * 7
    done = 0
    for row in rows:
        d = row["d"]
        if not d:
            continue
        try:
            parsed = date.fromisoformat(d[:10])
        except ValueError:
            continue
        idx = (parsed - week_start).days
        if 0 <= idx < 7:
            days_active[idx] = True
            done += 1

    return {
        "done": done,
        "goal": goal,
        "days_active": days_active,
        "subtitle": _weekly_subtitle(done, goal),
    }


def _weekly_subtitle(done: int, goal: int) -> str:
    """Copy line for the weekly ring per voice-and-tone library."""
    if done == 0:
        return "Mondays are fresh starts."
    if done >= goal:
        if done == goal:
            return "You did it. 15 in a week. Rest tonight."
        return f"{done} this week. Show-off."
    pct = round(done / goal * 100)
    if done <= 4:
        return f"You're {pct}% of the way there."
    if done <= 9:
        return "Halfway, capy! Keep going."
    return f"So close. {goal - done} more this week and you crush the quota."


# ---------------------------------------------------------------------------
# Sparkline
# ---------------------------------------------------------------------------


def sparkline_data(conn: sqlite3.Connection, days: int = 14) -> list[int]:
    """Daily count of applications submitted over the last N days.

    Returns a list of length `days`, ordered oldest → newest. Today is
    the last element. Days with no submissions are 0.
    """
    today = date.today()
    start = today - timedelta(days=days - 1)

    rows = conn.execute(
        f"""
        SELECT DATE(submitted_at) AS d, COUNT(*) AS c
        FROM applications
        WHERE status IN ({",".join("?" * len(SUBMITTED_STATUSES))})
          AND submitted_at IS NOT NULL
          AND DATE(submitted_at) >= ?
        GROUP BY DATE(submitted_at)
        """,
        (*SUBMITTED_STATUSES, start.isoformat()),
    ).fetchall()

    by_day = {}
    for row in rows:
        try:
            d = date.fromisoformat(row["d"][:10])
            by_day[d] = row["c"]
        except (ValueError, TypeError):
            continue

    return [by_day.get(start + timedelta(days=i), 0) for i in range(days)]


def sparkline_context(data: list[int]) -> dict:
    """Pre-computed copy strings for the sparkline card."""
    if not data or sum(data) == 0:
        return {
            "best_label": "no apps yet",
            "delta_label": "today is a blank page.",
        }
    best_idx = max(range(len(data)), key=lambda i: data[i])
    best_count = data[best_idx]
    today = date.today()
    best_date = today - timedelta(days=(len(data) - 1 - best_idx))
    days_ago = (today - best_date).days
    if days_ago == 0:
        when = "today"
    elif days_ago == 1:
        when = "yesterday"
    elif days_ago < 7:
        when = best_date.strftime("%A").lower()
    else:
        when = f"last {best_date.strftime('%A').lower()}"

    # Week-over-week delta on the last 7 days vs previous 7
    if len(data) >= 14:
        this_week = sum(data[-7:])
        prev_week = sum(data[-14:-7])
        if prev_week == 0:
            delta = "Last week was quiet — this week's already on the board."
        else:
            pct = round((this_week - prev_week) / prev_week * 100)
            if pct > 0:
                delta = f"Your pace is up {pct}% from last week."
            elif pct < 0:
                delta = f"Down {abs(pct)}% from last week — Huckleberry says: that's okay."
            else:
                delta = "Steady. Same pace as last week."
    else:
        delta = "Still warming up the data."

    return {
        "best_label": f"{when} ({best_count} apps)" if best_count > 1 else f"{when} (1 app)",
        "delta_label": delta,
    }


# ---------------------------------------------------------------------------
# Funnel
# ---------------------------------------------------------------------------


def funnel_counts(conn: sqlite3.Connection) -> list[dict]:
    """7-stage funnel from discovery to offer.

    Posting-side counts (active, strong_fits, radar) are DEDUPLICATED by the
    canonical (company, role, normalized_location) key — same as the table.
    Application-side counts are 1:1 with applications, no dedup needed.

    Stages (left → right):
        active        — unique postings with is_active=1
        strong_fits   — unique active postings with fit_score >= 0.75
        radar         — unique active postings flagged interested/very_interested
        tailored      — applications.status IN (tailored, submitted, interviewing, offered, rejected, withdrawn, closed)
        applied       — applications.status IN SUBMITTED_STATUSES
        interviewing  — applications.status = 'interviewing'
        offered       — applications.status = 'offered'
    """
    def count(sql: str, params: tuple = ()) -> int:
        return conn.execute(sql, params).fetchone()[0]

    # Dedup expression uses bare column names since the queries reference
    # postings without an alias.
    dedup_key_bare = dedup_key_expr("p").replace("p.", "")

    active = count(
        f"SELECT COUNT(DISTINCT {dedup_key_bare}) FROM postings WHERE is_active = 1"
    )
    strong_fits = count(
        f"SELECT COUNT(DISTINCT {dedup_key_bare}) FROM postings "
        f"WHERE is_active = 1 AND fit_score >= 0.75"
    )
    radar = count(
        f"SELECT COUNT(DISTINCT {dedup_key_bare}) FROM postings "
        f"WHERE is_active = 1 AND interest_level IN ('interested','very_interested')"
    )
    tailored = count(
        "SELECT COUNT(*) FROM applications WHERE status IN ('tailored','submitted','interviewing','offered','rejected','withdrawn','closed')"
    )
    applied = count(
        f"SELECT COUNT(*) FROM applications WHERE status IN ({','.join('?' * len(SUBMITTED_STATUSES))})",
        SUBMITTED_STATUSES,
    )
    interviewing = count("SELECT COUNT(*) FROM applications WHERE status = 'interviewing'")
    offered = count("SELECT COUNT(*) FROM applications WHERE status = 'offered'")

    return [
        {"key": "active",       "label": "Active postings", "count": active,       "tone": "neutral"},
        {"key": "strong_fits",  "label": "Strong fits",     "count": strong_fits,  "tone": "sun"},
        {"key": "radar",        "label": "On her radar",    "count": radar,        "tone": "sky"},
        {"key": "tailored",     "label": "Tailored",        "count": tailored,     "tone": "lilac"},
        {"key": "applied",      "label": "Applied",         "count": applied,      "tone": "coral"},
        {"key": "interviewing", "label": "Interviewing",    "count": interviewing, "tone": "sun"},
        {"key": "offered",      "label": "Offers",          "count": offered,      "tone": "mint"},
    ]


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------


def get_achievements(conn: sqlite3.Connection) -> list[dict]:
    """Return all 8 achievements with `earned` boolean + `earned_at` value.

    Defensive: if the achievements table doesn't exist yet (migration 004
    not run), returns all 8 as locked.
    """
    if not _has_table(conn, "achievements"):
        return [{**defn, "earned": False, "earned_at": None} for defn in ACHIEVEMENT_DEFS]

    rows = {
        row["id"]: row["earned_at"]
        for row in conn.execute("SELECT id, earned_at FROM achievements")
    }
    return [
        {**defn, "earned": rows.get(defn["id"]) is not None, "earned_at": rows.get(defn["id"])}
        for defn in ACHIEVEMENT_DEFS
    ]


def check_and_unlock(conn: sqlite3.Connection, now: Optional[str] = None) -> list[str]:
    """Evaluate all unlock conditions and mark newly-earned achievements.

    Returns the list of achievement ids unlocked on this call. Safe to
    run as often as desired (idempotent — already-earned achievements
    are skipped).
    """
    if not _has_table(conn, "achievements"):
        return []

    now_iso = now or datetime.now(timezone.utc).isoformat()
    already_earned = {
        row["id"]
        for row in conn.execute(
            "SELECT id FROM achievements WHERE earned_at IS NOT NULL"
        )
    }

    def is_met(check_id: str) -> bool:
        if check_id == "first_app":
            return bool(conn.execute("SELECT 1 FROM applications LIMIT 1").fetchone())
        if check_id == "tailor_5":
            row = conn.execute(
                "SELECT COUNT(DISTINCT posting_id) c FROM applications "
                "WHERE resume_path IS NOT NULL AND resume_path != ''"
            ).fetchone()
            return row["c"] >= 5
        if check_id == "interview":
            return bool(conn.execute(
                "SELECT 1 FROM applications WHERE status = 'interviewing' LIMIT 1"
            ).fetchone())
        if check_id == "apps_10":
            row = conn.execute(
                f"SELECT COUNT(*) c FROM applications "
                f"WHERE status IN ({','.join('?' * len(SUBMITTED_STATUSES))})",
                SUBMITTED_STATUSES,
            ).fetchone()
            return row["c"] >= 10
        if check_id == "weekly_15":
            return weekly_progress(conn)["done"] >= weekly_goal()
        if check_id == "week_streak":
            return current_streak(conn) >= 7
        if check_id == "month_streak":
            return current_streak(conn) >= 30
        if check_id == "offer":
            return bool(conn.execute(
                "SELECT 1 FROM applications WHERE status = 'offered' LIMIT 1"
            ).fetchone())
        return False

    unlocked = []
    for defn in ACHIEVEMENT_DEFS:
        if defn["id"] in already_earned:
            continue
        if is_met(defn["id"]):
            conn.execute(
                "UPDATE achievements SET earned_at = ? WHERE id = ?",
                (now_iso, defn["id"]),
            )
            unlocked.append(defn["id"])

    if unlocked:
        conn.commit()
    return unlocked


# ---------------------------------------------------------------------------
# Today's picks
# ---------------------------------------------------------------------------


def todays_picks(conn: sqlite3.Connection, n: int = 3) -> list[dict]:
    """Top N postings to feature on the dashboard's "today's picks" card.

    Deduplicated by the canonical (company, role, normalized_location) key
    so a job that appears 40 times across JobSpy keyword runs only shows
    once.

    Selection logic (priority order within unique jobs):
      1. very_interested with no application yet, ranked by fit_score DESC
      2. interested with no application yet, ranked by fit_score DESC
      3. not_reviewed with no application yet, ranked by fit_score DESC

    Returns dicts ready for direct JSON serialization to the dashboard.
    """
    sql = f"""
        WITH ranked AS (
            SELECT
                p.id, p.company, p.role, p.location, p.source, p.url,
                p.fit_score, p.first_seen, p.interest_level,
                ROW_NUMBER() OVER (
                    PARTITION BY {dedup_key_expr("p")}
                    ORDER BY {canonical_rank_order("p", "a")}
                ) AS rn
            FROM postings p
            LEFT JOIN applications a ON a.posting_id = p.id
            WHERE p.is_active = 1
              AND a.id IS NULL
              AND p.fit_score > 0
        )
        SELECT
            id, company, role, location, source, url, fit_score,
            first_seen, interest_level,
            CASE
                WHEN interest_level = 'very_interested' THEN 1
                WHEN interest_level = 'interested'      THEN 2
                WHEN interest_level = 'not_reviewed'    THEN 3
                ELSE 4
            END AS pick_bucket
        FROM ranked
        WHERE rn = 1
        ORDER BY pick_bucket ASC, fit_score DESC, first_seen DESC
        LIMIT ?
    """
    rows = conn.execute(sql, (n,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# "On her radar" count (for kicker text in today's picks)
# ---------------------------------------------------------------------------


def radar_count(conn: sqlite3.Connection) -> int:
    dedup_key_bare = dedup_key_expr("p").replace("p.", "")
    row = conn.execute(
        f"SELECT COUNT(DISTINCT {dedup_key_bare}) c "
        f"FROM postings p "
        f"LEFT JOIN applications a ON a.posting_id = p.id "
        f"WHERE p.is_active = 1 AND a.id IS NULL "
        f"AND p.interest_level IN ('interested','very_interested')"
    ).fetchone()
    return row["c"]
