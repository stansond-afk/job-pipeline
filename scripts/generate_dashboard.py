"""Generate the dashboard — "Solo's Garden" design.

Outputs: dashboard/index.html

The warm-pastel design defined in design/. All user-facing strings
(name, mascot, greeting copy) read from config/profile.yaml at render
time. Sections:

    - Greeting bar (mascot avatar + streak pill + celebrate button)
    - Weekly goal ring (SVG) + 14-day sparkline (SVG)
    - 7-stage funnel
    - Today's picks (3 hand-picked job cards) + mascot's pick-me-up
    - Achievements shelf (4×2 grid, locked/earned states)
    - Redesigned all-postings table with search/filter chips/sort

Data layer feeds via jobpipeline.achievements (streak, weekly, sparkline,
funnel, picks, achievements). JD-summary logic preserved from prior version.
Apply modal + interest/status dropdowns + Worker/Flask JS preserved
verbatim — only the wrapping chrome changes.

Usage:
    python scripts/generate_dashboard.py

Architecture note: rows are rendered server-side in Python (one HTML row
per posting), then filtered/sorted client-side with vanilla JS. Sort
reorders DOM elements; filters use show/hide. This matches the prior
file's approach and avoids a major architectural shift.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpipeline import achievements, config, jokes

DB_PATH = Path(__file__).parent.parent / "db" / "jobs.db"
OUT_PATH = Path(__file__).parent.parent / "dashboard" / "index.html"


# ---------------------------------------------------------------------------
# Design tokens (mirror design/design-tokens.md)
# ---------------------------------------------------------------------------

PALETTE = {
    "cream":    "#FBF7EF",
    "paper":    "#FFFDF7",
    "ink":      "#2E2B3D",
    "sub":      "#6F6A82",
    "sky":      "#9CC3E8",
    "sky_dk":   "#5B8AB8",
    "lilac":    "#C9B8E0",
    "lilac_dk": "#8A77B0",
    "sun":      "#F4D87C",
    "sun_dk":   "#C49F37",
    "coral":    "#F0A89C",
    "mint":     "#B9DBC4",
    "line":     "#E7DFCD",
}


# Capybara mascot — drawn from ellipses + circles. Inline SVG so no
# external assets needed. `mood` ∈ {happy, sleepy}. The user's mascot
# name comes from config/profile.yaml; only the SVG art is fixed.
def pip_svg(size: int = 62, mood: str = "happy") -> str:
    eye_y = 56 if mood == "sleepy" else 54
    eye_h = 1 if mood == "sleepy" else 4
    highlights = ""
    if mood != "sleepy":
        highlights = (
            '<circle cx="49" cy="53" r="1" fill="#fff" />'
            '<circle cx="73" cy="53" r="1" fill="#fff" />'
        )
    return (
        f'<svg viewBox="0 0 120 110" width="{size}" height="{int(size * 110 / 120)}" '
        f'aria-hidden="true">'
        '<ellipse cx="42" cy="32" rx="9" ry="7" fill="#a47b56"/>'
        '<ellipse cx="78" cy="32" rx="9" ry="7" fill="#a47b56"/>'
        '<ellipse cx="42" cy="33" rx="4" ry="3" fill="#7d5d40"/>'
        '<ellipse cx="78" cy="33" rx="4" ry="3" fill="#7d5d40"/>'
        '<ellipse cx="60" cy="55" rx="36" ry="30" fill="#c39673"/>'
        '<ellipse cx="60" cy="74" rx="22" ry="14" fill="#d8b08c"/>'
        f'<ellipse cx="48" cy="{eye_y}" rx="3.5" ry="{eye_h}" fill="#2a2a3a"/>'
        f'<ellipse cx="72" cy="{eye_y}" rx="3.5" ry="{eye_h}" fill="#2a2a3a"/>'
        f'{highlights}'
        '<ellipse cx="36" cy="66" rx="5" ry="3" fill="#f0a89c" opacity="0.55"/>'
        '<ellipse cx="84" cy="66" rx="5" ry="3" fill="#f0a89c" opacity="0.55"/>'
        '<ellipse cx="60" cy="70" rx="3" ry="2" fill="#2a2a3a"/>'
        '<ellipse cx="60" cy="78" rx="6" ry="3" fill="none" stroke="#2a2a3a" '
        'stroke-width="1.4" stroke-linecap="round"/>'
        '<circle cx="32" cy="22" r="3" fill="#f4d87c"/>'
        '<circle cx="30" cy="18" r="2.5" fill="#f0a89c"/>'
        '<circle cx="34" cy="17" r="2.5" fill="#c9b8e0"/>'
        '<circle cx="36" cy="22" r="2.5" fill="#9cc3e8"/>'
        '<circle cx="32" cy="22" r="1.5" fill="#fbf7ef"/>'
        '</svg>'
    )


# Affirmations — interpolated with user's short_name and mascot name from
# config/profile.yaml at render time. JS picks randomly without repeating
# within a session.
def _affirmations() -> list[str]:
    name = config.short_name()
    mascot = config.mascot_name()
    return [
        f"Great job, {name}!",
        "You showed up today. That's enough.",
        "Every 'no' is data, not a verdict.",
        "Look at you go 👀",
        "Beautiful work. Onward.",
        f"{mascot} is so proud of you.",
        "You are doing the hard thing. Slowly. Bravely.",
        "Future you is cheering for present you.",
        "Tailoring is the hardest part. You did it.",
    ]


STATUS_LABELS = {
    "new":          "New",
    "reviewing":    "Reviewing",
    "tailored":     "Tailored",
    "submitted":    "Applied",
    "interviewing": "Interviewing",
    "offered":      "Offered",
    "rejected":     "Rejected",
    "withdrawn":    "Withdrawn",
    "closed":       "Closed",
}


# ---------------------------------------------------------------------------
# JD summary extraction (preserved verbatim from prior version)
# ---------------------------------------------------------------------------

def strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_ROLE_SECTION_HEADERS = [
    r"what you['']ll do",
    r"what you will do",
    r"key responsibilities",
    r"primary responsibilities",
    r"core responsibilities",
    r"essential (functions|duties)",
    r"day[- ]to[- ]day",
    r"in this role",
    r"the role",
    r"about the role",
    r"position summary",
    r"job summary",
    r"position description",
    r"role overview",
    r"role description",
    r"responsibilities",
]
_HEADER_RE = re.compile(
    r"\b(" + "|".join(_ROLE_SECTION_HEADERS) + r")\s*[:\.\-—\n]",
    re.IGNORECASE,
)

_BOILERPLATE_PATTERNS = [
    r"\bequal opportunity\b", r"\bdiversity (and|&) inclusion\b",
    r"\baffirmative action\b", r"\bregardless of race\b", r"\bis a leading\b",
    r"\bfounded in\b", r"\bwe are committed to\b", r"\bour mission\b",
    r"\bour values\b", r"\babout (us|the company|our company)\b",
    r"\bheadquartered in\b", r"\bbillion[- ]dollar\b", r"\bfortune \d+\b",
    r"\bglobal leader\b",
]
_BOILERPLATE_RE = re.compile("|".join(_BOILERPLATE_PATTERNS), re.IGNORECASE)

_ROLE_SIGNAL_PATTERNS = [
    r"\byou['']ll\b", r"\byou will\b", r"\byour role\b", r"\bthis role\b",
    r"\bthe successful candidate\b", r"\bin this position\b",
    r"\bthe ideal candidate\b", r"\bresponsibilities include\b",
    r"\bduties include\b", r"\brequired (skills|qualifications|experience)\b",
    r"\bminimum qualifications\b", r"\bbasic qualifications\b",
    r"\b(must|should) have\b",
]
_ROLE_SIGNAL_RE = re.compile("|".join(_ROLE_SIGNAL_PATTERNS), re.IGNORECASE)


def make_summary(jd_text: str, max_chars: int = 300) -> str:
    clean = strip_html(jd_text or "")
    if not clean:
        return ""
    if len(clean) <= max_chars:
        return clean
    section = _extract_role_section(clean, max_chars)
    if section:
        return section
    best = _best_paragraph(clean, max_chars)
    if best:
        return best
    return _truncate_to_sentence(clean, max_chars)


def _extract_role_section(clean: str, max_chars: int):
    match = _HEADER_RE.search(clean)
    if not match:
        return None
    after = clean[match.end():].lstrip(" :.\n-—")
    if len(after) < 30:
        return None
    return _truncate_to_sentence(after, max_chars)


def _best_paragraph(clean: str, max_chars: int):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean) if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [p.strip() for p in clean.split(". ") if len(p.strip()) > 60]
    if not paragraphs:
        return None
    scored = []
    for p in paragraphs:
        if len(p) < 40:
            continue
        score = len(_ROLE_SIGNAL_RE.findall(p)) - len(_BOILERPLATE_RE.findall(p))
        scored.append((score, p))
    if not scored:
        return None
    scored.sort(key=lambda t: t[0], reverse=True)
    best_score, best_p = scored[0]
    if best_score <= 0:
        return None
    return _truncate_to_sentence(best_p, max_chars)


def _truncate_to_sentence(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_period = cut.rfind(". ")
    if last_period > max_chars // 2:
        return cut[: last_period + 1]
    return cut.rstrip() + "…"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_postings(conn):
    """Dedup + priority-bucket sort.

    Each unique (company, role, normalized-location) tuple appears once;
    the canonical row is picked by the application-first / direct-ATS-first
    rules in achievements.canonical_rank_order. See PROJECT_STATE_12.md
    § D27 for the priority-bucket logic that drives row order on top of
    dedup.
    """
    sql = f"""
        WITH ranked AS (
            SELECT
                p.id, p.source, p.company, p.role, p.location, p.url,
                p.posted_at, p.first_seen, p.fit_score, p.score_notes,
                p.jd_text, p.interest_level,
                a.id AS application_id, a.status, a.submitted_at,
                a.updated_at AS app_updated_at,
                ROW_NUMBER() OVER (
                    PARTITION BY {achievements.dedup_key_expr("p")}
                    ORDER BY {achievements.canonical_rank_order("p", "a")}
                ) AS dedup_rn
            FROM postings p
            LEFT JOIN applications a ON a.posting_id = p.id
            WHERE p.is_active = 1
        )
        SELECT
            id, source, company, role, location, url, posted_at,
            first_seen, fit_score, score_notes, jd_text, interest_level,
            application_id, status, submitted_at, app_updated_at,
            CASE
                WHEN interest_level = 'not_interested' THEN 6
                WHEN application_id IS NOT NULL AND status IN ('rejected','withdrawn','closed') THEN 5
                WHEN application_id IS NOT NULL THEN 4
                WHEN interest_level = 'interested' THEN 3
                WHEN interest_level = 'very_interested' THEN 1
                ELSE 2
            END AS priority_bucket
        FROM ranked
        WHERE dedup_rn = 1
        ORDER BY
            priority_bucket ASC,
            CASE WHEN priority_bucket IN (4, 5) THEN 0 ELSE 1 END ASC,
            COALESCE(app_updated_at, '') DESC,
            fit_score DESC,
            first_seen DESC
    """
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_sources(conn):
    """Distinct source values present in the active postings — used for the
    source filter dropdown so we only show sources that have results."""
    cur = conn.execute(
        "SELECT DISTINCT source FROM postings WHERE is_active = 1 ORDER BY source"
    )
    return [row[0] for row in cur.fetchall() if row[0]]


def fetch_last_scrape(conn):
    """Most recent first_seen across postings — header timestamp."""
    cur = conn.execute("SELECT MAX(first_seen) FROM postings")
    val = cur.fetchone()[0]
    return (val or "")[:10]


# ---------------------------------------------------------------------------
# URL + escape helpers
# ---------------------------------------------------------------------------

def tailor_url(posting):
    role = posting["role"] or ""
    company = posting["company"] or ""
    name = config.short_name()
    prompt = (
        f"Please tailor {name}'s resume and cover letter for this role: "
        f"{role} at {company}. Job URL: {posting['url']}"
    )
    return f"https://claude.ai/new?q={urllib.parse.quote(prompt)}"


def score_tier(score):
    """Returns one of: strong / good / medium / low / filtered."""
    if not score or score == 0:
        return "filtered"
    if score >= 0.75:
        return "strong"
    if score >= 0.5:
        return "good"
    if score >= 0.2:
        return "medium"
    return "low"


def score_color(tier):
    return {
        "strong":   PALETTE["sun"],
        "good":     PALETTE["mint"],
        "medium":   PALETTE["cream"],
        "low":      PALETTE["line"],
        "filtered": PALETTE["line"],
    }[tier]


def relative_date(iso_date: str) -> str:
    """Convert ISO date → '2d ago' / '5h ago' for table display."""
    if not iso_date:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        from datetime import timezone
        delta = datetime.now(timezone.utc) - dt
        if delta.days >= 30:
            return f"{delta.days // 30}mo ago"
        if delta.days >= 7:
            return f"{delta.days // 7}w ago"
        if delta.days >= 1:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours >= 1:
            return f"{hours}h ago"
        return "just now"
    except (ValueError, TypeError):
        return iso_date[:10]


# ---------------------------------------------------------------------------
# Row rendering — table body (one row per posting, fully static HTML)
# ---------------------------------------------------------------------------

def render_action_cell(p):
    """Tailor button always; Apply or inline status dropdown + edit icon
    depending on whether the posting has an application row."""
    tailor = html.escape(tailor_url(p))
    posting_id = int(p["id"])
    status = p["status"]
    application_id = p["application_id"]

    tailor_btn = (
        f'<a class="btn-tailor" href="{tailor}" target="_blank" rel="noopener">'
        f'Tailor →</a>'
    )

    if status and application_id is not None:
        options_html = "".join(
            f'<option value="{html.escape(val)}"'
            f'{" selected" if val == status else ""}>{html.escape(label)}</option>'
            for val, label in STATUS_LABELS.items()
        )
        return (
            f'<select class="status-select status-{html.escape(status)}" '
            f'data-application-id="{application_id}" '
            f'data-current-status="{html.escape(status)}" '
            f'onchange="onStatusChange(event, {application_id})" '
            f'title="Change status">{options_html}</select>'
            f'<button type="button" class="btn-edit-app" '
            f'data-posting-id="{posting_id}" '
            f'onclick="openApplyModal({posting_id})" '
            f'title="Edit application details">✎</button>'
            f'{tailor_btn}'
        )

    return (
        f'<button type="button" class="btn-apply" '
        f'data-posting-id="{posting_id}" '
        f'onclick="openApplyModal({posting_id})">Apply →</button>'
        f'{tailor_btn}'
    )


def render_interest_dropdown(p):
    current = p["interest_level"] or "not_reviewed"
    options = [
        ("not_reviewed",    "—"),
        ("very_interested", "♥ Very"),
        ("interested",      "● Interested"),
        ("not_interested",  "Pass"),
    ]
    opts_html = "".join(
        f'<option value="{val}"{" selected" if val == current else ""}>{html.escape(label)}</option>'
        for val, label in options
    )
    return (
        f'<select class="interest-select interest-{current}" '
        f'data-posting-id="{p["id"]}" '
        f'onchange="onInterestChange(event, {p["id"]})" '
        f'title="Interest level">{opts_html}</select>'
    )


def render_row(p):
    tier = score_tier(p["fit_score"])
    row_class = f"row-{tier}"
    app_state = p["status"] if p["status"] else "unapplied"
    interest = p["interest_level"] or "not_reviewed"

    source_full = p["source"] or "unknown"
    source_class = source_full.split(":")[0]

    company = html.escape(p["company"] or "—")
    role = html.escape(p["role"] or "—")
    location = html.escape(p["location"] or "—")
    posted = relative_date(p["posted_at"] or p["first_seen"])
    url = html.escape(p["url"] or "#")
    score = p["fit_score"] or 0
    score_pct = int(score * 100) if score else 0
    score_bg = score_color(tier)

    # Data attributes needed by JS filter/sort logic. Lowercased + stripped
    # so JS doesn't have to do casework.
    search_blob = " ".join(filter(None, [p["company"], p["role"], p["location"]])).lower()
    data_attrs = (
        f'data-app-state="{app_state}" '
        f'data-interest="{interest}" '
        f'data-tier="{tier}" '
        f'data-source="{source_class}" '
        f'data-score="{score:.4f}" '
        f'data-company="{html.escape((p["company"] or "").lower())}" '
        f'data-search="{html.escape(search_blob)}"'
    )

    score_chip = (
        f'<span class="score-chip" style="background:{score_bg}">'
        f'{score_pct}</span>'
    ) if score > 0 else (
        f'<span class="score-chip score-chip-filtered">—</span>'
    )

    return f"""
    <tr class="job-row {row_class} app-{app_state} interest-row-{interest}" {data_attrs}>
        <td class="td-company"><span class="row-company">{company}</span></td>
        <td class="td-role">
          <a href="{url}" target="_blank" rel="noopener">{role}</a>
          <div class="row-meta">{html.escape(source_full)} · {posted}</div>
        </td>
        <td class="td-location">{location}</td>
        <td class="td-score">{score_chip}</td>
        <td class="td-interest">{render_interest_dropdown(p)}</td>
        <td class="td-action">{render_action_cell(p)}</td>
    </tr>"""


# ---------------------------------------------------------------------------
# Section rendering — top-of-page cards
# ---------------------------------------------------------------------------

def render_greeting_bar(streak: int) -> str:
    now = datetime.now()
    greeting, quote = jokes.todays_mascot_quote(now.hour)
    date_str = now.strftime("%A, %B %-d")
    user_name = config.short_name()
    mascot = config.mascot_name()

    # Streak pill — solid number even on day 0 (the "0 days" framing is
    # honest; ramps up with first action).
    streak_label = "showing up" if streak > 0 else "fresh start"

    return f"""
    <div class="greeting-bar">
      <div class="greeting-sun"></div>
      <div class="greeting-sun-inner"></div>
      <div class="greeting-cloud-1"></div>
      <div class="greeting-cloud-2"></div>

      <div class="greeting-left">
        <div class="pip-avatar">{pip_svg(62)}</div>
        <div class="greeting-text">
          <div class="greeting-hello">{html.escape(greeting)},</div>
          <div class="greeting-name">{html.escape(user_name)} <span class="greeting-sun-glyph">☀</span></div>
          <div class="greeting-meta">{html.escape(date_str)} · {html.escape(mascot)} says: <em>“{html.escape(quote)}”</em></div>
        </div>
      </div>

      <div class="greeting-right">
        <div class="streak-pill">
          <span class="streak-emoji">🔥</span>
          <div>
            <div class="streak-count">{streak} day{"s" if streak != 1 else ""}</div>
            <div class="streak-sub">{streak_label}</div>
          </div>
        </div>
        <button class="celebrate-btn" onclick="triggerCelebrate()">🎉 Celebrate today</button>
        <span id="server-status" class="server-status">server offline</span>
      </div>
    </div>"""


def render_weekly_ring(weekly: dict) -> str:
    done = weekly["done"]
    goal = weekly["goal"]
    pct = min(1.0, done / goal) if goal else 0
    R = 64
    import math
    C = 2 * math.pi * R
    dash = f"{C * pct:.1f} {C:.1f}"
    pct_text = round(pct * 100)
    days_active = weekly["days_active"]
    day_letters = ["M", "T", "W", "T", "F", "S", "S"]
    pills = "".join(
        f'<div class="day-pill{" day-pill-on" if days_active[i] else ""}">{day_letters[i]}</div>'
        for i in range(7)
    )

    return f"""
    <div class="card">
      <div class="card-head">
        <div class="kicker">this week</div>
        <div class="card-title">Weekly goal</div>
      </div>
      <div class="weekly-body">
        <div class="weekly-ring">
          <svg viewBox="0 0 152 152" width="152" height="152" aria-label="weekly goal ring">
            <circle cx="76" cy="76" r="{R}" fill="none" stroke="{PALETTE['cream']}" stroke-width="14"/>
            <circle cx="76" cy="76" r="{R}" fill="none"
              stroke="{PALETTE['sun']}" stroke-width="14" stroke-linecap="round"
              stroke-dasharray="{dash}" transform="rotate(-90 76 76)"/>
            <circle cx="76" cy="6"   r="4" fill="{PALETTE['coral']}"/>
            <circle cx="146" cy="76" r="4" fill="{PALETTE['sky']}"/>
            <circle cx="76" cy="146" r="4" fill="{PALETTE['lilac']}"/>
            <circle cx="6"  cy="76"  r="4" fill="{PALETTE['mint']}"/>
          </svg>
          <div class="weekly-ring-center">
            <div class="weekly-ring-num">{done}</div>
            <div class="weekly-ring-of">of {goal}</div>
          </div>
        </div>
        <div class="weekly-meta">
          <div class="hand-accent">you're {pct_text}% of the way there</div>
          <div class="weekly-subtitle">{html.escape(weekly['subtitle'])}</div>
          <div class="day-pills">{pills}</div>
        </div>
      </div>
    </div>"""


def render_sparkline(data: list, ctx: dict) -> str:
    W, H = 280, 70
    pad_top = 8
    max_v = max(max(data), 1) if data else 1
    n = len(data) if data else 1
    step = W / max(n - 1, 1)
    pts = []
    for i, v in enumerate(data or []):
        x = i * step
        y = pad_top + (H - pad_top) - (v / max_v) * (H - pad_top - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    pts_str = " ".join(pts)
    area = f"0,{H} " + pts_str + f" {W},{H}"

    points_svg = "".join(
        f'<circle cx="{i*step:.1f}" cy="{pad_top + (H - pad_top) - (v / max_v) * (H - pad_top - 4):.1f}" '
        f'r="{3 if v > 0 else 1.5}" fill="{PALETTE["sun"] if v > 0 else PALETTE["line"]}"/>'
        for i, v in enumerate(data or [])
    )

    from datetime import date, timedelta
    start_date = (date.today() - timedelta(days=n - 1)).strftime("%b %-d") if n > 1 else "today"

    return f"""
    <div class="card">
      <div class="card-head">
        <div class="kicker">momentum</div>
        <div class="card-title">Last {n} days</div>
      </div>
      <svg viewBox="0 0 {W} {H + 12}" width="100%" height="{H + 12}"
           preserveAspectRatio="none" class="sparkline-svg">
        <polygon points="{area}" fill="{PALETTE['sky']}" opacity="0.25"/>
        <polyline points="{pts_str}" fill="none" stroke="{PALETTE['sky_dk']}"
          stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        {points_svg}
      </svg>
      <div class="sparkline-axis">
        <span>{html.escape(start_date)}</span><span>today</span>
      </div>
      <div class="sparkline-ctx">
        <strong>Best day:</strong> {html.escape(ctx['best_label'])}. {html.escape(ctx['delta_label'])}
      </div>
    </div>"""


def render_funnel(stages: list) -> str:
    tiles = []
    for i, s in enumerate(stages):
        tone = s["tone"]
        bg = {
            "neutral": PALETTE["cream"],
            "sky":     PALETTE["sky"],
            "lilac":   PALETTE["lilac"],
            "sun":     PALETTE["sun"],
            "coral":   PALETTE["coral"],
            "mint":    PALETTE["mint"],
        }[tone]
        border = f'border: 1px solid {PALETTE["line"]};' if tone == "neutral" else "border: none;"
        opacity = "0.55" if s["count"] == 0 else "1"
        connector = (
            f'<div class="funnel-arrow">→</div>'
            if i < len(stages) - 1 else ""
        )
        tiles.append(f"""
        <div class="funnel-cell">
          <div class="funnel-tile" style="background:{bg};{border}opacity:{opacity};">
            <div class="funnel-count">{s['count']}</div>
            <div class="funnel-label">{html.escape(s['label'])}</div>
          </div>
          {connector}
        </div>""")

    return f"""
    <div class="card">
      <div class="card-head">
        <div class="kicker">your funnel</div>
        <div class="card-title">From discovery to dream job</div>
      </div>
      <div class="funnel-grid">{"".join(tiles)}</div>
      <div class="funnel-footnote">each arrow is a tiny act of courage.</div>
    </div>"""


def render_todays_picks(picks: list, radar_count: int) -> str:
    if not picks:
        return f"""
        <div class="card">
          <div class="card-head">
            <div class="kicker">today's blue-sky picks</div>
            <div class="card-title">{html.escape(config.mascot_name())} picked these just for you</div>
          </div>
          <div class="empty-state">
            <div class="hand-accent">an empty sky — what'll you send first?</div>
            <div class="empty-sub">{html.escape(config.mascot_name())} is waiting for the scrapers to find something good.</div>
          </div>
        </div>"""

    cards = []
    for p in picks:
        interest = p.get("interest_level", "not_reviewed")
        border_color = {
            "very_interested": PALETTE["coral"],
            "interested":      PALETTE["sky"],
            "not_reviewed":    PALETTE["line"],
        }.get(interest, PALETTE["line"])
        company = html.escape(p["company"] or "—")
        role = html.escape(p["role"] or "—")
        location = html.escape(p["location"] or "—")
        source = html.escape(p["source"] or "—")
        posted = relative_date(p.get("first_seen", ""))
        score = p.get("fit_score") or 0
        score_pct = int(score * 100)
        url = html.escape(p["url"] or "#")
        posting_id = int(p["id"])

        cards.append(f"""
        <div class="pick-card" style="border-left: 5px solid {border_color};">
          <div class="pick-head">
            <div>
              <div class="pick-company">{company}</div>
              <a href="{url}" target="_blank" rel="noopener" class="pick-role">{role}</a>
            </div>
            <div class="score-chip score-chip-pick" style="background:{PALETTE['sun']}">{score_pct}</div>
          </div>
          <div class="pick-meta">
            <span>📍 {location}</span>
            <span>·</span>
            <span>{source}</span>
            <span>·</span>
            <span>{posted}</span>
          </div>
          <div class="pick-actions">
            <a class="btn-tailor btn-pick" href="{html.escape(tailor_url(p))}" target="_blank" rel="noopener">Tailor →</a>
            <button type="button" class="btn-apply btn-pick btn-pick-apply"
                    onclick="openApplyModal({posting_id})">Apply →</button>
          </div>
        </div>""")

    # Action copy: prefer "X of N on your radar" when there's enough on the
    # radar to make the framing accurate; otherwise just "<mascot>'s top picks".
    mascot = config.mascot_name()
    if radar_count >= len(picks):
        action_copy = f"{len(picks)} of {radar_count} on your radar"
    elif radar_count > 0:
        action_copy = f"{radar_count} on your radar · {len(picks) - radar_count} fresh fit{'s' if (len(picks) - radar_count) != 1 else ''}"
    else:
        action_copy = f"{mascot}'s top fits today"

    return f"""
    <div class="card">
      <div class="card-head">
        <div class="kicker">today's blue-sky picks</div>
        <div class="card-title">{html.escape(mascot)} picked these just for you
          <span class="card-action">{html.escape(action_copy)}</span>
        </div>
      </div>
      <div class="picks-grid">{"".join(cards)}</div>
    </div>"""


def render_pick_me_up() -> str:
    q, a = jokes.todays_joke()
    from datetime import date

    # Pick a stable puppy ID per day so the first paint is consistent — the
    # 🎲 shuffle button cycles to a new one. placedog.net has ~250 photos
    # indexed; we use a wide range and let any 404s fall through to the
    # CSS gradient fallback (rendered behind the img by .photo-placeholder).
    initial_puppy_id = (date.today().toordinal() * 37) % 200 + 1

    # Soft fallback color for the wrapping div — visible if the image
    # fails to load. Rotates daily so the fallback isn't monotonous.
    fallback_colors = ["#C5D8E8", "#D8C5E8", "#E8E1C5", "#E8C5C5", "#C5E8D8"]
    fb = fallback_colors[date.today().toordinal() % len(fallback_colors)]

    captions = [
        "a small friend, just for you",
        "huckleberry says hi to this one",
        "today's good dog",
        "borrowed for a moment",
        "look at those paws",
    ]
    initial_caption = captions[date.today().toordinal() % len(captions)]

    return f"""
    <div class="card pick-me-up-card">
      <div class="card-head">
        <div class="kicker">huckleberry's daily pick-me-up</div>
        <div class="card-title">A little something for you
          <button class="shuffle-btn" onclick="shufflePickMeUp()">🎲 new one</button>
        </div>
      </div>
      <div class="photo-placeholder" id="pickmeup-photo"
           style="background: repeating-linear-gradient(135deg, {fb} 0 14px, {_shade(fb, 6)} 14px 28px);">
        <img id="pickmeup-img"
             alt="A friendly dog for you"
             referrerpolicy="no-referrer"
             onerror="this.style.display='none'">
        <div class="photo-caption" id="pickmeup-caption">{html.escape(initial_caption)}</div>
      </div>
      <div class="joke-box">
        <div class="joke-q hand-accent" id="joke-q">{html.escape(q)}</div>
        <div class="joke-a" id="joke-a">{html.escape(a)}</div>
      </div>
    </div>"""


def _shade(hex_color: str, pct: int) -> str:
    """Darken a hex color by `pct` units. Mirrors shade() in shared-data.jsx."""
    n = int(hex_color.lstrip("#"), 16)
    r = max(0, min(255, (n >> 16) - pct))
    g = max(0, min(255, ((n >> 8) & 0xff) - pct))
    b = max(0, min(255, (n & 0xff) - pct))
    return f"#{(r << 16) | (g << 8) | b:06x}"


def render_achievements(items: list) -> str:
    earned_count = sum(1 for a in items if a["earned"])
    tiles = []
    for a in items:
        earned_class = "earned" if a["earned"] else "locked"
        badge = '<div class="badge-check">✓</div>' if a["earned"] else ""
        tiles.append(f"""
        <div class="achievement {earned_class}">
          <div class="ach-icon">{a['icon']}</div>
          <div class="ach-name">{html.escape(a['name'])}</div>
          <div class="ach-desc">{html.escape(a['description'])}</div>
          {badge}
        </div>""")
    return f"""
    <div class="card">
      <div class="card-head">
        <div class="kicker">your shelf</div>
        <div class="card-title">Achievements <span class="card-count">· {earned_count} of {len(items)}</span></div>
      </div>
      <div class="achievements-grid">{"".join(tiles)}</div>
    </div>"""


# ---------------------------------------------------------------------------
# Main HTML template + JS
# ---------------------------------------------------------------------------

def generate(postings, sources, weekly, sparkline, sparkline_ctx, funnel,
             picks, radar_count, achievements_list, streak, last_scraped):
    generated_at = datetime.now().strftime("%B %-d, %Y at %-I:%M %p")
    rows_html = "\n".join(render_row(p) for p in postings)
    affirmations_json = json.dumps(_affirmations())
    jokes_json = json.dumps([list(j) for j in jokes.JOKES])
    source_options = "".join(
        f'<option value="{html.escape(s.split(":")[0])}">{html.escape(s.split(":")[0])}</option>'
        for s in sorted(set(s.split(":")[0] for s in sources))
    )

    css = _build_css()
    body_html = _build_body_html(
        rows_html=rows_html,
        greeting_bar=render_greeting_bar(streak),
        weekly_ring=render_weekly_ring(weekly),
        sparkline=render_sparkline(sparkline, sparkline_ctx),
        funnel=render_funnel(funnel),
        todays_picks=render_todays_picks(picks, radar_count),
        pick_me_up=render_pick_me_up(),
        achievements_html=render_achievements(achievements_list),
        source_options=source_options,
        total_count=len(postings),
        generated_at=generated_at,
        last_scraped=last_scraped,
    )
    js = _build_js(affirmations_json, jokes_json)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="author" content="Stanson Dobbs">
<meta name="generator" content="job-pipeline (https://github.com/stansond-afk/job-pipeline)">
<title>{html.escape(config.short_name())} — Job Pipeline</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Nunito:wght@400;500;600;700;800&family=Caveat:wght@500;600;700&display=swap" rel="stylesheet">
<style>
{css}
</style>
</head>
<body>
{body_html}
<script>
{js}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CSS (Solo's Garden tokens + components)
# ---------------------------------------------------------------------------

def _build_css() -> str:
    P = PALETTE
    # All literal { } in CSS must be doubled — but since we're not using
    # f-string interpolation in the CSS itself, we just use a regular
    # string with .format() substitution.
    return f"""
  :root {{
    --cream: {P['cream']};
    --paper: {P['paper']};
    --ink: {P['ink']};
    --sub: {P['sub']};
    --sky: {P['sky']};
    --sky-dk: {P['sky_dk']};
    --lilac: {P['lilac']};
    --lilac-dk: {P['lilac_dk']};
    --sun: {P['sun']};
    --sun-dk: {P['sun_dk']};
    --coral: {P['coral']};
    --mint: {P['mint']};
    --line: {P['line']};

    --font-serif: 'Fraunces', Georgia, 'Times New Roman', serif;
    --font-sans:  'Nunito', system-ui, -apple-system, sans-serif;
    --font-hand:  'Caveat', cursive;

    --radius-pill: 999px;
    --radius-card: 22px;
    --radius-card-lg: 28px;
    --radius-input: 10px;
    --radius-tag: 14px;

    --shadow-card: 0 1px 0 rgba(255,255,255,0.7) inset, 0 8px 20px -16px rgba(80,60,30,0.15);
    --shadow-float: 0 16px 30px -10px rgba(0,0,0,0.4);
    --shadow-button: 0 6px 16px -8px rgba(0,0,0,0.4);
  }}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  html, body {{
    background: var(--cream);
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }}

  body {{
    padding: 24px;
    max-width: 1360px;
    margin: 0 auto;
    min-height: 100vh;
  }}

  a {{ color: var(--ink); text-decoration: none; }}
  a:hover {{ color: var(--sky-dk); }}

  button {{ font-family: var(--font-sans); }}
  input, select, textarea {{ font-family: var(--font-sans); }}

  /* ----- Card primitive ----- */
  .card {{
    background: var(--paper);
    border-radius: var(--radius-card);
    padding: 22px;
    border: 1px solid var(--line);
    box-shadow: var(--shadow-card);
    position: relative;
    margin-bottom: 16px;
  }}

  .card-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 14px;
    gap: 14px;
  }}
  .kicker {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
    color: var(--sub);
    text-transform: uppercase;
  }}
  .card-title {{
    font-family: var(--font-serif);
    font-size: 22px;
    font-weight: 500;
    color: var(--ink);
    margin-top: 2px;
    line-height: 1.2;
    display: flex;
    align-items: baseline;
    gap: 10px;
    justify-content: space-between;
    flex-wrap: wrap;
  }}
  .card-action {{ font-size: 12px; color: var(--sub); font-weight: 400; font-family: var(--font-sans); }}
  .card-count {{ font-size: 13px; color: var(--sub); font-weight: 400; font-family: var(--font-sans); }}
  .hand-accent {{
    font-family: var(--font-hand);
    color: var(--sky-dk);
    font-size: 22px;
    line-height: 1.1;
  }}

  /* ----- Grids ----- */
  .grid-2col-12-10 {{ display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }}
  .grid-2col-16-10 {{ display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; }}
  @media (max-width: 820px) {{
    .grid-2col-12-10, .grid-2col-16-10 {{ grid-template-columns: 1fr; }}
  }}

  /* ----- Greeting bar ----- */
  .greeting-bar {{
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    padding: 22px 28px;
    border-radius: var(--radius-card-lg);
    background: linear-gradient(135deg, #E4EEF8 0%, #F0E7F5 60%, #FFF6DE 100%);
    border: 1px solid var(--line);
    position: relative;
    overflow: hidden;
    margin-bottom: 16px;
    gap: 16px;
  }}
  .greeting-sun {{
    position: absolute; right: 220px; top: -30px;
    width: 90px; height: 90px; border-radius: 50%;
    background: var(--sun); opacity: 0.7;
    pointer-events: none;
  }}
  .greeting-sun-inner {{
    position: absolute; right: 210px; top: -20px;
    width: 70px; height: 70px; border-radius: 50%;
    background: var(--sun);
    pointer-events: none;
  }}
  .greeting-cloud-1, .greeting-cloud-2 {{
    position: absolute; border-radius: 20px;
    background: var(--paper); opacity: 0.85;
    pointer-events: none;
  }}
  .greeting-cloud-1 {{ left: 220px; top: 18px; width: 60px; height: 16px; }}
  .greeting-cloud-2 {{ left: 380px; top: 40px; width: 40px; height: 12px; }}

  .greeting-left {{
    display: flex; gap: 18px; align-items: center;
    position: relative;
  }}
  .pip-avatar {{
    width: 78px; height: 78px; border-radius: 50%;
    background: var(--paper);
    display: grid; place-items: center;
    border: 2px solid var(--cream);
    box-shadow: 0 6px 18px -8px rgba(80,60,30,0.25);
    flex-shrink: 0;
  }}
  .greeting-hello {{
    font-family: var(--font-hand);
    font-size: 28px;
    color: var(--sky-dk);
    line-height: 1;
  }}
  .greeting-name {{
    font-family: var(--font-serif);
    font-size: 42px;
    font-weight: 500;
    color: var(--ink);
    line-height: 1.05;
    margin-top: 2px;
  }}
  .greeting-sun-glyph {{ color: var(--coral); }}
  .greeting-meta {{ margin-top: 6px; color: var(--sub); font-size: 14px; }}

  .greeting-right {{
    display: flex; gap: 10px; align-items: center;
    position: relative;
    flex-wrap: wrap;
    justify-content: flex-end;
  }}
  .streak-pill {{
    display: flex; align-items: center; gap: 8px;
    background: var(--paper);
    padding: 8px 14px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--line);
  }}
  .streak-emoji {{ font-size: 18px; }}
  .streak-count {{ font-weight: 800; font-size: 18px; line-height: 1; color: var(--ink); }}
  .streak-sub {{ font-size: 10px; color: var(--sub); margin-top: 2px; }}

  .celebrate-btn {{
    background: var(--ink); color: var(--cream); border: none;
    padding: 12px 18px; border-radius: var(--radius-pill);
    font-family: var(--font-sans); font-weight: 700; font-size: 13px;
    cursor: pointer; box-shadow: var(--shadow-button);
  }}
  .celebrate-btn:hover {{ opacity: 0.9; }}

  .server-status {{
    font-size: 11px; color: var(--sub);
    display: inline-flex; align-items: center; gap: 5px;
    margin-left: 4px;
  }}
  .server-status::before {{
    content: ''; display: inline-block;
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--sub);
  }}
  .server-status.online::before {{ background: #6cd47a; }}

  /* ----- Weekly ring ----- */
  .weekly-body {{ display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }}
  .weekly-ring {{ position: relative; width: 152px; height: 152px; flex-shrink: 0; }}
  .weekly-ring-center {{
    position: absolute; inset: 0;
    display: grid; place-items: center; text-align: center;
  }}
  .weekly-ring-num {{
    font-family: var(--font-serif); font-size: 40px; font-weight: 500;
    color: var(--ink); line-height: 1;
  }}
  .weekly-ring-of {{ font-size: 12px; color: var(--sub); margin-top: 4px; }}
  .weekly-meta {{ flex: 1; min-width: 200px; }}
  .weekly-subtitle {{
    margin-top: 8px; color: var(--sub); font-size: 13px; line-height: 1.45;
  }}
  .day-pills {{ display: flex; gap: 4px; margin-top: 12px; }}
  .day-pill {{
    width: 28px; height: 36px; border-radius: 10px;
    display: grid; place-items: center;
    background: var(--cream); color: var(--sub);
    font-weight: 700; font-size: 11px;
  }}
  .day-pill-on {{ background: var(--sun); color: var(--ink); }}

  /* ----- Sparkline ----- */
  .sparkline-svg {{ overflow: visible; }}
  .sparkline-axis {{
    display: flex; justify-content: space-between;
    margin-top: 6px; color: var(--sub); font-size: 11px;
  }}
  .sparkline-ctx {{ margin-top: 10px; font-size: 13px; color: var(--ink); line-height: 1.45; }}
  .sparkline-ctx strong {{ color: var(--sky-dk); font-weight: 700; }}

  /* ----- Funnel ----- */
  .funnel-grid {{
    display: grid; grid-template-columns: repeat(7, 1fr);
    gap: 8px; align-items: stretch;
  }}
  .funnel-cell {{ position: relative; }}
  .funnel-tile {{
    border-radius: var(--radius-tag);
    padding: 14px 10px; text-align: center;
    min-height: 84px;
    display: flex; flex-direction: column; justify-content: center;
  }}
  .funnel-count {{
    font-family: var(--font-serif); font-size: 24px; font-weight: 500;
    color: var(--ink); line-height: 1;
  }}
  .funnel-label {{ font-size: 11px; color: var(--ink); margin-top: 6px; font-weight: 600; }}
  .funnel-arrow {{
    position: absolute; right: -7px; top: 50%;
    transform: translateY(-50%);
    color: var(--sub); font-size: 14px; z-index: 1;
  }}
  .funnel-footnote {{
    font-family: var(--font-hand); font-size: 18px;
    color: var(--lilac-dk); margin-top: 14px; text-align: right;
  }}
  @media (max-width: 980px) {{
    .funnel-grid {{ grid-template-columns: repeat(4, 1fr); }}
    .funnel-arrow {{ display: none; }}
  }}
  @media (max-width: 600px) {{
    .funnel-grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}

  /* ----- Today's picks ----- */
  .picks-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
  @media (max-width: 720px) {{ .picks-grid {{ grid-template-columns: 1fr; }} }}
  .pick-card {{
    background: var(--paper);
    border-radius: 18px;
    padding: 16px;
    border: 1px solid var(--line);
    display: flex; flex-direction: column; gap: 10px; height: 100%;
  }}
  .pick-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }}
  .pick-company {{
    font-size: 11px; color: var(--sub);
    font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
  }}
  .pick-role {{
    font-family: var(--font-serif); font-size: 18px; font-weight: 500;
    color: var(--ink); margin-top: 2px; line-height: 1.2;
    display: block;
  }}
  .pick-role:hover {{ color: var(--sky-dk); }}
  .pick-meta {{ display: flex; gap: 8px; flex-wrap: wrap; font-size: 12px; color: var(--sub); }}
  .pick-actions {{ display: flex; gap: 8px; margin-top: auto; }}

  /* ----- Pick-me-up ----- */
  .pick-me-up-card {{
    background: linear-gradient(160deg, var(--paper), var(--cream));
  }}
  .shuffle-btn {{
    background: var(--cream); border: 1px solid var(--line);
    color: var(--ink); font-size: 11px; font-weight: 700;
    padding: 6px 10px; border-radius: var(--radius-pill);
    cursor: pointer; font-family: var(--font-sans);
  }}
  .shuffle-btn:hover {{ background: var(--paper); }}
  .photo-placeholder {{
    position: relative; height: 180px; border-radius: 18px;
    overflow: hidden;
    box-shadow: inset 0 0 0 1px rgba(0,0,0,0.04);
  }}
  .photo-placeholder img {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    /* contain (not cover) so the whole dog is visible — the gradient
       background shows through any letterbox, framing the photo. */
    object-fit: contain;
    display: block;
  }}
  .photo-caption {{
    position: absolute; left: 12px; bottom: 12px;
    background: rgba(255,255,255,0.92); color: #3b3b48;
    font-family: ui-monospace, Menlo, monospace; font-size: 11px;
    padding: 5px 9px; border-radius: 8px;
    z-index: 1;
  }}
  .joke-box {{
    margin-top: 12px; padding: 12px;
    border-radius: 14px;
    background: var(--cream);
    border: 1px dashed var(--line);
  }}
  .joke-q {{ font-family: var(--font-hand); font-size: 22px; color: var(--sky-dk); line-height: 1.1; }}
  .joke-a {{ font-size: 13px; color: var(--ink); margin-top: 4px; }}

  /* ----- Achievements ----- */
  .achievements-grid {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
  }}
  @media (max-width: 720px) {{ .achievements-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  .achievement {{
    border-radius: 14px; padding: 12px; text-align: center;
    position: relative;
    border: 1px dashed var(--line);
    background: var(--cream);
  }}
  .achievement.earned {{
    background: linear-gradient(180deg, var(--cream), var(--paper));
    border: 1px dashed var(--sun);
    opacity: 1;
  }}
  .achievement.locked {{ opacity: 0.5; }}
  .achievement.locked .ach-icon {{ filter: grayscale(0.8); }}
  .ach-icon {{ font-size: 28px; }}
  .ach-name {{ font-family: var(--font-serif); font-size: 13px; color: var(--ink); margin-top: 4px; font-weight: 500; }}
  .ach-desc {{ font-size: 10px; color: var(--sub); margin-top: 2px; line-height: 1.3; }}
  .badge-check {{
    position: absolute; top: -6px; right: -6px;
    width: 22px; height: 22px; border-radius: 50%;
    background: var(--sun); display: grid; place-items: center;
    font-size: 12px; font-weight: 800; color: var(--ink);
  }}

  /* ----- Empty state ----- */
  .empty-state {{ padding: 24px 12px; text-align: center; }}
  .empty-sub {{ color: var(--sub); font-size: 12px; margin-top: 6px; }}

  /* ----- Table & filter bar ----- */
  .table-card {{ overflow: visible; }}
  .filter-bar {{
    display: grid;
    grid-template-columns: minmax(220px, 1.4fr) repeat(4, minmax(0, 1fr)) auto;
    gap: 8px; align-items: center; margin-bottom: 12px;
  }}
  @media (max-width: 900px) {{
    .filter-bar {{ grid-template-columns: 1fr 1fr; }}
  }}
  .search-wrap {{ position: relative; }}
  .search-wrap::before {{
    content: '🔎'; position: absolute; left: 12px; top: 50%;
    transform: translateY(-50%);
    font-size: 14px; color: var(--sub); pointer-events: none;
  }}
  .search-input {{
    width: 100%; padding: 9px 12px 9px 34px;
    border: 1px solid var(--line); border-radius: var(--radius-input);
    background: var(--paper); font-size: 13px; color: var(--ink); outline: none;
  }}
  .search-input:focus {{ border-color: var(--sky-dk); }}
  .search-clear {{
    position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
    background: var(--cream); border: none; border-radius: 50%;
    width: 20px; height: 20px; font-size: 12px; color: var(--sub);
    cursor: pointer; display: none;
  }}
  .search-clear.visible {{ display: inline-block; }}

  .filter-select {{
    background: var(--paper); border: 1px solid var(--line);
    border-radius: var(--radius-input); padding: 7px 28px 7px 10px;
    font-size: 12px; color: var(--ink); font-weight: 600;
    cursor: pointer; appearance: none;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='%236F6A82' d='M5 6L0 0h10z'/></svg>");
    background-repeat: no-repeat; background-position: right 9px center;
  }}
  .filter-select:focus {{ outline: none; border-color: var(--sky-dk); }}

  .reset-btn {{
    background: var(--cream); color: var(--sub);
    border: 1px solid var(--line);
    padding: 8px 14px; border-radius: var(--radius-input);
    font-weight: 700; font-size: 12px; cursor: pointer;
    white-space: nowrap;
  }}
  .reset-btn.active {{
    background: var(--ink); color: var(--cream); border-color: var(--ink);
    cursor: pointer;
  }}
  .reset-btn:not(.active) {{ cursor: default; }}

  .secondary-row {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px; gap: 8px; flex-wrap: wrap;
  }}
  .chips-row {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .chip {{
    background: var(--cream); color: var(--ink);
    border: 1px solid var(--line);
    padding: 4px 10px; border-radius: var(--radius-pill);
    font-size: 11px; font-weight: 700; cursor: pointer;
  }}
  .chip.active {{ background: var(--sun); border-color: var(--sun-dk); }}

  .sort-block {{ display: flex; gap: 12px; align-items: center; }}
  .pass-toggle {{
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; color: var(--sub); cursor: pointer;
  }}
  .pass-toggle input {{ accent-color: var(--sky-dk); width: 14px; height: 14px; cursor: pointer; }}
  .sort-block-inner {{
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; color: var(--sub);
  }}
  .sort-select {{ padding: 5px 22px 5px 8px; font-size: 11px; }}

  .add-job-toggle-btn {{
    display: none;
    background: var(--ink); color: var(--cream); border: none;
    padding: 7px 12px; border-radius: var(--radius-input);
    font-weight: 700; font-size: 12px; cursor: pointer;
    margin-left: auto;
  }}
  .add-job-toggle-btn.visible {{ display: inline-flex; }}
  .add-job-toggle-btn:hover {{ opacity: 0.9; }}

  /* Add Job panel */
  #add-job-panel {{
    display: none; background: var(--paper);
    border: 1px solid var(--line); border-radius: var(--radius-card);
    padding: 18px; margin-bottom: 16px;
  }}
  #add-job-panel.expanded {{ display: block; }}
  .add-job-form {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start;
  }}
  .add-job-form label {{
    display: block; font-size: 11px; color: var(--sub);
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;
  }}
  .add-job-form input, .add-job-form textarea {{
    width: 100%; background: var(--cream); border: 1px solid var(--line);
    color: var(--ink); border-radius: var(--radius-input);
    padding: 8px 12px; font-size: 13px; outline: none;
  }}
  .add-job-form textarea {{ min-height: 80px; resize: vertical; }}
  .add-job-form .full-width {{ grid-column: 1 / -1; }}
  .add-job-form .help-text {{ font-size: 11px; color: var(--sub); grid-column: 1 / -1; }}
  .add-job-actions {{ grid-column: 1 / -1; display: flex; gap: 10px; align-items: center; }}

  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  thead th {{
    text-align: left; padding: 8px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.8px;
    color: var(--sub); text-transform: uppercase;
    border-bottom: 1px solid var(--line); white-space: nowrap;
  }}
  tbody td {{
    padding: 12px 8px; border-bottom: 1px solid var(--cream);
    vertical-align: top; font-size: 13px;
  }}
  tr.job-row:hover td {{ background: var(--cream); }}
  tr.interest-row-not_interested {{ opacity: 0.4; }}
  tr.interest-row-not_interested:hover {{ opacity: 0.7; }}

  .td-company {{ font-weight: 600; color: var(--ink); }}
  .row-company {{ display: inline-block; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom; }}
  .td-role a {{ color: var(--ink); font-weight: 500; }}
  .td-role a:hover {{ color: var(--sky-dk); text-decoration: underline; }}
  .row-meta {{ font-size: 10px; color: var(--sub); margin-top: 2px; }}
  .td-location {{ color: var(--sub); font-size: 12px; }}
  .td-action {{ white-space: nowrap; }}

  .score-chip {{
    color: var(--ink);
    padding: 3px 10px; border-radius: var(--radius-pill);
    font-weight: 800; font-size: 11px; display: inline-block;
  }}
  .score-chip-filtered {{
    background: var(--line); color: var(--sub); font-weight: 600;
  }}
  .score-chip-pick {{ font-size: 12px; padding: 4px 11px; }}

  .interest-select, .status-select {{
    appearance: none;
    border-radius: var(--radius-pill);
    padding: 4px 22px 4px 9px;
    font-size: 11px; font-weight: 700;
    cursor: pointer;
    background-repeat: no-repeat;
    background-position: right 7px center;
    background-size: 8px;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='8' height='8' viewBox='0 0 8 8'><path fill='%232E2B3D' d='M0 2 L4 6 L8 2 Z'/></svg>");
  }}
  .interest-select:disabled, .status-select:disabled {{
    cursor: not-allowed; opacity: 0.6;
  }}

  /* Interest pill colors per design-tokens.md */
  .interest-not_reviewed {{ background: var(--cream); color: var(--sub); border: 1px solid var(--line); }}
  .interest-very_interested {{ background: var(--coral); color: var(--ink); border: 1px solid var(--coral); }}
  .interest-interested {{ background: var(--sky); color: var(--ink); border: 1px solid var(--sky); }}
  .interest-not_interested {{ background: var(--line); color: var(--sub); border: 1px solid var(--line); }}

  /* Status pill colors per design-tokens.md */
  .status-select {{ border: 1px solid; margin-right: 4px; }}
  .status-new          {{ background: var(--cream); color: var(--ink);    border-color: var(--line); }}
  .status-reviewing    {{ background: var(--cream); color: var(--ink);    border-color: var(--line); }}
  .status-tailored     {{ background: var(--lilac); color: var(--ink);    border-color: var(--lilac-dk); }}
  .status-submitted    {{ background: var(--sun);   color: var(--ink);    border-color: var(--sun-dk); }}
  .status-interviewing {{ background: var(--coral); color: var(--ink);    border-color: var(--coral); }}
  .status-offered      {{ background: var(--mint);  color: var(--ink);    border-color: var(--mint); }}
  .status-rejected     {{ background: var(--line);  color: var(--sub);    border-color: var(--line); }}
  .status-withdrawn    {{ background: var(--line);  color: var(--sub);    border-color: var(--line); }}
  .status-closed       {{ background: var(--line);  color: var(--sub);    border-color: var(--line); }}

  .btn-tailor {{
    background: var(--lilac); color: var(--ink);
    padding: 5px 12px; border-radius: var(--radius-input);
    font-weight: 700; font-size: 11px;
    border: none; cursor: pointer; display: inline-block;
    margin-right: 4px;
  }}
  .btn-tailor:hover {{ background: var(--lilac-dk); color: var(--cream); }}
  .btn-apply {{
    background: var(--ink); color: var(--cream); border: none;
    padding: 5px 12px; border-radius: var(--radius-input);
    font-weight: 700; font-size: 11px; cursor: pointer;
    margin-right: 4px;
  }}
  .btn-apply:hover {{ opacity: 0.9; }}
  .btn-edit-app {{
    background: transparent; border: 1px solid var(--line);
    color: var(--sub); padding: 3px 7px;
    border-radius: var(--radius-input);
    font-size: 11px; line-height: 1; cursor: pointer;
    margin-right: 4px;
  }}
  .btn-edit-app:hover {{ color: var(--ink); border-color: var(--sky-dk); }}

  .btn-pick {{ flex: 1; padding: 8px 12px; font-size: 12px; text-align: center; }}
  .btn-pick-apply {{ background: var(--ink); color: var(--cream); }}

  /* ----- Empty table state ----- */
  .table-empty {{
    padding: 32px 12px; text-align: center; color: var(--sub);
  }}

  /* ----- Pagination ----- */
  .pagination-bar {{
    display: flex; justify-content: space-between; align-items: center;
    gap: 12px; flex-wrap: wrap;
    margin-top: 16px; padding-top: 16px;
    border-top: 1px solid var(--line);
  }}
  .pagination-controls {{
    display: flex; align-items: center; gap: 8px;
  }}
  .page-btn {{
    background: var(--cream); border: 1px solid var(--line);
    color: var(--ink); font-weight: 700;
    padding: 6px 12px; border-radius: var(--radius-input);
    font-size: 12px; cursor: pointer; min-width: 36px;
    font-family: var(--font-sans);
  }}
  .page-btn:hover:not(:disabled) {{ background: var(--paper); border-color: var(--sky-dk); }}
  .page-btn:disabled {{ opacity: 0.35; cursor: not-allowed; }}
  .page-indicator {{
    font-size: 12px; color: var(--sub); font-weight: 600;
    padding: 0 8px; white-space: nowrap;
  }}
  .page-indicator strong {{ color: var(--ink); font-weight: 700; }}
  .page-meta {{
    font-size: 12px; color: var(--sub);
    display: flex; align-items: center; gap: 12px;
  }}
  .page-size-select {{ padding: 5px 22px 5px 8px; font-size: 11px; }}

  /* ----- Footer ----- */
  .page-footer {{
    margin-top: 18px; text-align: center;
    font-family: var(--font-hand); font-size: 18px;
    color: var(--lilac-dk);
  }}
  .page-credit {{
    margin-top: 6px; text-align: center;
    font-size: 10px; color: var(--sub);
    letter-spacing: 0.3px; opacity: 0.65;
  }}
  .page-credit a {{ color: var(--sub); text-decoration: none; }}
  .page-credit a:hover {{ color: var(--sky-dk); text-decoration: underline; }}

  /* ----- Confetti ----- */
  #confetti-container {{
    position: fixed; inset: 0; pointer-events: none;
    overflow: hidden; z-index: 50;
  }}
  @keyframes confetti-fall {{
    0%   {{ transform: translate(0, -20px) rotate(0deg); opacity: 1; }}
    90%  {{ opacity: 1; }}
    100% {{ transform: translate(var(--dx, 0px), 110vh) rotate(720deg); opacity: 0.4; }}
  }}
  .confetti-piece {{
    position: absolute; top: 0; border-radius: 2px;
    animation: confetti-fall var(--dur, 2.6s) cubic-bezier(.2,.6,.4,1) var(--delay, 0s) forwards;
  }}

  /* ----- Affirmation toast ----- */
  #affirmation-toast {{
    position: fixed; left: 50%; top: 90px; transform: translateX(-50%);
    background: var(--ink); color: var(--cream);
    padding: 14px 22px; border-radius: var(--radius-pill);
    box-shadow: var(--shadow-float);
    display: none; align-items: center; gap: 12px; z-index: 60;
  }}
  #affirmation-toast.show {{ display: flex; animation: a-pop 0.4s cubic-bezier(.2,.8,.4,1.4); }}
  @keyframes a-pop {{
    from {{ transform: translateX(-50%) translateY(-10px) scale(0.9); opacity: 0; }}
    to   {{ transform: translateX(-50%) translateY(0) scale(1); opacity: 1; }}
  }}
  .affirmation-pip {{
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--paper); display: grid; place-items: center;
    flex-shrink: 0;
  }}
  .affirmation-text {{ font-family: var(--font-serif); font-size: 18px; }}
  .affirmation-close {{
    background: transparent; border: none; color: var(--cream);
    font-size: 18px; cursor: pointer; opacity: 0.7;
  }}

  /* ----- Apply modal (chrome restyled, behavior unchanged) ----- */
  .modal-backdrop {{
    display: none; position: fixed; inset: 0;
    background: rgba(46, 43, 61, 0.55);
    z-index: 100;
    align-items: center; justify-content: center;
    padding: 24px;
  }}
  .modal-backdrop.open {{ display: flex; }}
  .modal {{
    background: var(--paper);
    border: 1px solid var(--line);
    border-radius: var(--radius-card);
    width: 100%; max-width: 720px; max-height: 90vh;
    overflow-y: auto;
    padding: 24px 28px;
    box-shadow: var(--shadow-float);
  }}
  .modal-header {{
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 16px; border-bottom: 1px solid var(--line);
    padding-bottom: 14px; margin-bottom: 16px;
  }}
  .modal-title {{ font-family: var(--font-serif); font-size: 20px; font-weight: 500; line-height: 1.3; color: var(--ink); }}
  .modal-subtitle {{ font-size: 12px; color: var(--sub); margin-top: 4px; }}
  .modal-close {{
    background: none; border: none; color: var(--sub);
    font-size: 22px; line-height: 1; cursor: pointer; padding: 0 4px;
  }}
  .modal-close:hover {{ color: var(--ink); }}
  .modal-row {{ margin-bottom: 14px; }}
  .modal-row label {{
    display: block; font-size: 11px; color: var(--sub);
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;
  }}
  .modal-row textarea, .modal-row input, .modal-row select {{
    width: 100%; background: var(--cream); border: 1px solid var(--line);
    color: var(--ink); border-radius: var(--radius-input);
    padding: 8px 12px; font-size: 13px; outline: none;
  }}
  .modal-row textarea {{ min-height: 60px; resize: vertical; line-height: 1.5; }}
  .modal-row textarea:focus, .modal-row input:focus, .modal-row select:focus {{
    border-color: var(--sky-dk);
  }}
  #apply-jd {{ min-height: 180px; font-family: ui-monospace, Menlo, monospace; font-size: 12px; }}
  .modal-footer {{
    display: flex; align-items: center; gap: 10px;
    padding-top: 14px; border-top: 1px solid var(--line); margin-top: 8px;
  }}
  .btn-submit {{
    background: var(--ink); color: var(--cream); border: none;
    padding: 9px 18px; border-radius: var(--radius-pill);
    font-weight: 700; font-size: 13px; cursor: pointer;
  }}
  .btn-submit:hover {{ opacity: 0.9; }}
  .btn-submit:disabled {{ opacity: 0.4; cursor: not-allowed; }}
  .btn-cancel {{
    background: transparent; color: var(--sub);
    border: 1px solid var(--line);
    padding: 9px 14px; border-radius: var(--radius-pill);
    font-size: 13px; cursor: pointer;
  }}
  .btn-cancel:hover {{ color: var(--ink); border-color: var(--sky-dk); }}
  #apply-status, #add-job-status, #count-display {{ font-size: 12px; color: var(--sub); margin-left: auto; }}
  #apply-status.error, #add-job-status.error {{ color: var(--coral); }}
  #apply-status.success, #add-job-status.success {{ color: var(--sky-dk); }}
"""


# ---------------------------------------------------------------------------
# HTML body
# ---------------------------------------------------------------------------

def _build_body_html(**kw) -> str:
    return f"""
<div id="confetti-container"></div>

<div id="affirmation-toast">
  <div class="affirmation-pip">{pip_svg(28)}</div>
  <div class="affirmation-text" id="affirmation-text"></div>
  <button class="affirmation-close" onclick="dismissAffirmation()">×</button>
</div>

{kw['greeting_bar']}

<div class="grid-2col-12-10">
  {kw['weekly_ring']}
  {kw['sparkline']}
</div>

{kw['funnel']}

<div class="grid-2col-16-10">
  {kw['todays_picks']}
  {kw['pick_me_up']}
</div>

{kw['achievements_html']}

<div id="add-job-panel">
  <form class="add-job-form" id="add-job-form" onsubmit="return submitAddJob(event)">
    <div class="full-width">
      <label for="aj-url">Job URL <span style="text-transform:none;color:var(--sub)">(we'll auto-fetch role/company/location)</span></label>
      <input type="url" id="aj-url" placeholder="https://example.com/jobs/12345" autocomplete="off">
    </div>
    <div class="full-width">
      <label for="aj-jd">Or paste the JD text directly</label>
      <textarea id="aj-jd" placeholder="Paste the full job description here if URL fetch doesn't work…"></textarea>
    </div>
    <div>
      <label for="aj-role">Role title <span style="text-transform:none;color:var(--sub)">(optional)</span></label>
      <input type="text" id="aj-role" placeholder="auto-detected from page" autocomplete="off">
    </div>
    <div>
      <label for="aj-company">Company <span style="text-transform:none;color:var(--sub)">(optional)</span></label>
      <input type="text" id="aj-company" placeholder="auto-detected from page" autocomplete="off">
    </div>
    <div class="full-width">
      <label for="aj-location">Location <span style="text-transform:none;color:var(--sub)">(optional — affects geo boost)</span></label>
      <input type="text" id="aj-location" placeholder="e.g. Washington, DC or Remote, US" autocomplete="off">
    </div>
    <div class="help-text">
      Provide a URL <em>or</em> JD text (or both). Role/company fields are optional.
    </div>
    <div class="add-job-actions">
      <button type="submit" class="btn-submit" id="aj-submit">Add Job</button>
      <button type="button" class="btn-cancel" onclick="toggleAddJob(false)">Cancel</button>
      <span id="add-job-status"></span>
    </div>
  </form>
</div>

<div class="card table-card">
  <div class="card-head">
    <div>
      <div class="kicker">all postings</div>
      <div class="card-title">The full list — search & filter
        <span class="card-action">showing <strong id="count-visible">{kw['total_count']}</strong> of {kw['total_count']}</span>
      </div>
    </div>
    <button class="add-job-toggle-btn" id="add-job-toggle-btn" onclick="toggleAddJob()">+ Add Job</button>
  </div>

  <div class="filter-bar">
    <div class="search-wrap">
      <input type="text" id="search" class="search-input" placeholder="search company, role, location…" oninput="filterTable()">
      <button type="button" class="search-clear" id="search-clear" onclick="clearSearch()" aria-label="clear">×</button>
    </div>
    <select id="source-filter" class="filter-select" onchange="filterTable()">
      <option value="">all sources</option>
      {kw['source_options']}
    </select>
    <select id="score-filter" class="filter-select" onchange="filterTable()">
      <option value="">any fit</option>
      <option value="strong">★ strong · 75+</option>
      <option value="good">good · 50–74</option>
      <option value="medium">medium · 20–49</option>
      <option value="low">low · &lt;20</option>
      <option value="unfiltered" selected>hide filtered</option>
      <option value="filtered">filtered only</option>
    </select>
    <select id="status-filter" class="filter-select" onchange="filterTable()">
      <option value="">any status</option>
      <option value="unapplied">not yet applied</option>
      <option value="applied">applied (any)</option>
      <option value="submitted">submitted</option>
      <option value="interviewing">interviewing</option>
      <option value="offered">offered</option>
      <option value="rejected">rejected</option>
    </select>
    <select id="interest-filter" class="filter-select" onchange="filterTable()">
      <option value="hide_pass" selected>hide “pass” jobs</option>
      <option value="">any interest</option>
      <option value="very_interested">♥ very interested</option>
      <option value="interested">● interested</option>
      <option value="not_reviewed">○ not reviewed</option>
      <option value="not_interested">pass only</option>
    </select>
    <button id="reset-btn" class="reset-btn" onclick="resetFilters()">no filters</button>
  </div>

  <div class="secondary-row">
    <div class="chips-row">
      <button class="chip" data-chip="dmv" onclick="toggleChip('dmv')">DMV only</button>
      <button class="chip" data-chip="remote" onclick="toggleChip('remote')">remote</button>
      <button class="chip" data-chip="strong" onclick="toggleChip('strong')">★ strong fits</button>
      <button class="chip" data-chip="radar" onclick="toggleChip('radar')">♥ on her radar</button>
      <button class="chip" data-chip="new-week" onclick="toggleChip('new-week')">new this week</button>
    </div>
    <div class="sort-block">
      <div class="sort-block-inner">
        sort:
        <select id="sort-select" class="filter-select sort-select" onchange="applySort()">
          <option value="interest">interest, then fit</option>
          <option value="score">fit score</option>
          <option value="company">company A→Z</option>
          <option value="recent">most recent</option>
        </select>
      </div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Company</th>
        <th>Role</th>
        <th>Location</th>
        <th>Score</th>
        <th>Interest</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody id="jobs-body">
{kw['rows_html']}
    </tbody>
  </table>

  <div class="table-empty" id="empty-state" style="display:none;">
    <div class="hand-accent">nothing matches that combo.</div>
    <div style="font-size:12px; color: var(--sub); margin-top: 6px;">
      {html.escape(config.mascot_name())} suggests <a href="#" onclick="resetFilters(); return false;" style="color: var(--sky-dk); font-weight: 700; text-decoration: underline;">clearing filters</a> and trying again.
    </div>
  </div>

  <div class="pagination-bar" id="pagination-bar">
    <div class="pagination-controls">
      <button type="button" class="page-btn" id="page-first" onclick="goToPage(1)" title="first page">«</button>
      <button type="button" class="page-btn" id="page-prev" onclick="goToPage(currentPage - 1)" title="previous page">‹</button>
      <span class="page-indicator" id="page-indicator">page <strong>1</strong> of <strong>1</strong></span>
      <button type="button" class="page-btn" id="page-next" onclick="goToPage(currentPage + 1)" title="next page">›</button>
      <button type="button" class="page-btn" id="page-last" onclick="goToPage(totalPages)" title="last page">»</button>
    </div>
    <div class="page-meta">
      <span id="page-range">showing 1–50</span>
      <span>·</span>
      <span>
        <select id="page-size-select" class="filter-select page-size-select" onchange="changePageSize()">
          <option value="25">25 per page</option>
          <option value="50" selected>50 per page</option>
          <option value="100">100 per page</option>
          <option value="200">200 per page</option>
        </select>
      </span>
    </div>
  </div>
</div>

<!-- Apply modal -->
<div class="modal-backdrop" id="apply-modal-backdrop" onclick="onBackdropClick(event)">
  <div class="modal" role="dialog" aria-labelledby="apply-modal-title">
    <div class="modal-header">
      <div>
        <div class="modal-title" id="apply-modal-title">Loading…</div>
        <div class="modal-subtitle" id="apply-modal-subtitle"></div>
      </div>
      <button type="button" class="modal-close" onclick="closeApplyModal()" aria-label="Close">×</button>
    </div>

    <div class="modal-row">
      <label for="apply-status-select">Status</label>
      <select id="apply-status-select">
        <option value="submitted">Submitted (applied to employer)</option>
        <option value="interviewing">Interviewing</option>
        <option value="offered">Offered</option>
        <option value="rejected">Rejected</option>
        <option value="withdrawn">Withdrawn</option>
        <option value="closed">Closed (not pursuing)</option>
        <option value="tailored">Tailored (resume done, not yet applied)</option>
        <option value="reviewing">Reviewing (still deciding)</option>
        <option value="new">New</option>
      </select>
    </div>

    <div class="modal-row">
      <label for="apply-resume-select">Resume file <span style="text-transform:none;color:var(--sub)">(from <span id="apply-watch-dir">~/Downloads</span>)</span></label>
      <select id="apply-resume-select" onchange="onResumeSelectChange()">
        <option value="">— None —</option>
        <option value="__manual__">Other (paste path…)</option>
      </select>
      <input type="text" id="apply-resume-manual" placeholder="/Users/.../resume.docx" style="display:none; margin-top:6px;">
    </div>

    <div class="modal-row">
      <label for="apply-cover-select">Cover letter file</label>
      <select id="apply-cover-select" onchange="onCoverSelectChange()">
        <option value="">— None —</option>
        <option value="__manual__">Other (paste path…)</option>
      </select>
      <input type="text" id="apply-cover-manual" placeholder="/Users/.../cover.docx" style="display:none; margin-top:6px;">
    </div>

    <div class="modal-row">
      <label for="apply-jd">JD snapshot <span style="text-transform:none;color:var(--sub)">(edit to clean up)</span></label>
      <textarea id="apply-jd" placeholder="Edit the JD text here. Preserved with your application."></textarea>
    </div>

    <div class="modal-row">
      <label for="apply-notes">Notes <span style="text-transform:none;color:var(--sub)">(optional)</span></label>
      <textarea id="apply-notes" placeholder="Recruiter contact, portal quirks, anything to remember…"></textarea>
    </div>

    <div class="modal-footer">
      <button type="button" class="btn-submit" id="apply-submit" onclick="submitApply()">Save</button>
      <button type="button" class="btn-cancel" onclick="closeApplyModal()">Cancel</button>
      <span id="apply-status"></span>
    </div>
  </div>
</div>

<div class="page-footer">{html.escape(config.footer_text())} · <span style="font-family: var(--font-sans); font-size: 11px;">generated {kw['generated_at']} · last scrape {kw['last_scraped']}</span></div>
<div class="page-credit">originally by <a href="https://github.com/stansond-afk" target="_blank" rel="noopener">Stanson Dobbs</a> · MIT licensed · <a href="https://github.com/stansond-afk/job-pipeline" target="_blank" rel="noopener">source</a></div>
"""


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

def _build_js(affirmations_json: str, jokes_json: str) -> str:
    mascot_json = json.dumps(config.mascot_name())
    return f"""
const AFFIRMATIONS = {affirmations_json};
const JOKES = {jokes_json};
const MASCOT_NAME = {mascot_json};
const PALETTE = {{
  sun:   '{PALETTE['sun']}',
  coral: '{PALETTE['coral']}',
  sky:   '{PALETTE['sky']}',
  lilac: '{PALETTE['lilac']}',
  mint:  '{PALETTE['mint']}',
}};
const CONFETTI_PALETTE = [PALETTE.sun, PALETTE.coral, PALETTE.sky, PALETTE.lilac, PALETTE.mint];

// ---------- Filter / sort / pagination state ----------
const activeChips = new Set();
let usedAffirmations = [];
let currentPage = 1;
let pageSize = 50;
let totalPages = 1;
let filteredRows = [];  // cached after each filter pass; render uses this

function rowPassesFilters(row, q, source, scoreFilter, statusFilter, interestFilter) {{
  const data = row.dataset;
  const tier = data.tier;
  const interest = data.interest;
  const appState = data.appState;
  const rowSource = data.source.toLowerCase();
  const search = (data.search || '').toLowerCase();
  const location = (row.querySelector('.td-location') || {{}}).textContent || '';

  if (q && !search.includes(q) && !location.toLowerCase().includes(q)) return false;
  if (source && rowSource !== source) return false;

  if (scoreFilter === 'filtered'   && tier !== 'filtered') return false;
  if (scoreFilter === 'unfiltered' && tier === 'filtered') return false;
  if (['strong','good','medium','low'].includes(scoreFilter) && tier !== scoreFilter) return false;

  if (statusFilter === 'unapplied' && appState !== 'unapplied') return false;
  if (statusFilter === 'applied'   && appState === 'unapplied') return false;
  const specific = ['submitted','interviewing','offered','rejected','withdrawn','closed','tailored','reviewing','new'];
  if (specific.includes(statusFilter) && appState !== statusFilter) return false;

  if (interestFilter === 'hide_pass' && interest === 'not_interested') return false;
  if (interestFilter === 'pass_only' && interest !== 'not_interested') return false;
  if (['very_interested','interested','not_reviewed','not_interested'].includes(interestFilter)
      && interest !== interestFilter) return false;

  if (activeChips.has('dmv')) {{
    const loc = location.toLowerCase();
    if (!(loc.includes('washington') || loc.includes(', dc') || loc.includes(', d.c.')
          || loc.includes(', va') || loc.includes(', md')
          || loc.includes('virginia') || loc.includes('maryland')
          || loc.includes('arlington') || loc.includes('fairfax') || loc.includes('alexandria')
          || loc.includes('mclean') || loc.includes('reston'))) return false;
  }}
  if (activeChips.has('remote')) {{
    if (!location.toLowerCase().includes('remote')) return false;
  }}
  if (activeChips.has('strong')) {{
    if (tier !== 'strong') return false;
  }}
  if (activeChips.has('radar')) {{
    if (interest !== 'very_interested' && interest !== 'interested') return false;
  }}
  if (activeChips.has('new-week')) {{
    const meta = (row.querySelector('.row-meta') || {{}}).textContent || '';
    const dayMatch = meta.match(/(\\d+)d ago/);
    const isRecentDay = dayMatch && parseInt(dayMatch[1], 10) < 7;
    const isRecentHr = /h ago/.test(meta) || /just now/.test(meta);
    if (!isRecentDay && !isRecentHr) return false;
  }}

  return true;
}}

function filterTable(opts) {{
  // opts.preservePage: true to keep currentPage as-is (used when a status
  // or interest dropdown changes mid-page — the user shouldn't get yanked
  // back to page 1). Default behavior is to reset to page 1 (used when
  // search/filters change).
  const preservePage = !!(opts && opts.preservePage);

  const q = (document.getElementById('search').value || '').toLowerCase();
  const source = document.getElementById('source-filter').value.toLowerCase();
  const scoreFilter = document.getElementById('score-filter').value;
  const statusFilter = document.getElementById('status-filter').value;
  const interestFilter = document.getElementById('interest-filter').value;

  document.getElementById('search-clear').classList.toggle('visible', q.length > 0);

  // First pass: build the filtered list.
  const allRows = document.querySelectorAll('#jobs-body tr');
  filteredRows = [];
  allRows.forEach(row => {{
    if (rowPassesFilters(row, q, source, scoreFilter, statusFilter, interestFilter)) {{
      filteredRows.push(row);
    }}
  }});

  if (!preservePage) currentPage = 1;
  renderPage();
  updateResetButton();
}}

function renderPage() {{
  // Show only rows in the current page window; hide everything else.
  const total = filteredRows.length;
  totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (currentPage > totalPages) currentPage = totalPages;
  if (currentPage < 1) currentPage = 1;

  const start = (currentPage - 1) * pageSize;
  const end = start + pageSize;
  const visibleSlice = new Set(filteredRows.slice(start, end));

  // Single pass: show rows in the window, hide everything else.
  document.querySelectorAll('#jobs-body tr').forEach(row => {{
    row.style.display = visibleSlice.has(row) ? '' : 'none';
  }});

  // Update header counter ("showing X of Y")
  document.getElementById('count-visible').textContent = total;
  const empty = document.getElementById('empty-state');
  if (empty) empty.style.display = total === 0 ? '' : 'none';

  // Update pagination bar
  const bar = document.getElementById('pagination-bar');
  bar.style.display = total === 0 ? 'none' : 'flex';

  document.getElementById('page-indicator').innerHTML =
    'page <strong>' + currentPage + '</strong> of <strong>' + totalPages + '</strong>';

  if (total === 0) {{
    document.getElementById('page-range').textContent = '';
  }} else {{
    const rangeEnd = Math.min(end, total);
    document.getElementById('page-range').textContent =
      'showing ' + (start + 1) + '–' + rangeEnd + ' of ' + total;
  }}

  // Enable/disable nav buttons
  document.getElementById('page-first').disabled = currentPage <= 1;
  document.getElementById('page-prev').disabled  = currentPage <= 1;
  document.getElementById('page-next').disabled  = currentPage >= totalPages;
  document.getElementById('page-last').disabled  = currentPage >= totalPages;
}}

function goToPage(n) {{
  if (n < 1 || n > totalPages || n === currentPage) return;
  currentPage = n;
  renderPage();
  // Scroll the table card into view so the user sees the new rows without
  // having to scroll up manually.
  document.querySelector('.table-card')?.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}

function changePageSize() {{
  pageSize = parseInt(document.getElementById('page-size-select').value, 10) || 50;
  currentPage = 1;
  renderPage();
}}

function updateResetButton() {{
  const btn = document.getElementById('reset-btn');
  let n = 0;
  if (document.getElementById('search').value) n++;
  if (document.getElementById('source-filter').value) n++;
  // Treat default 'unfiltered' as not a filter, but other score values are
  const sv = document.getElementById('score-filter').value;
  if (sv && sv !== 'unfiltered') n++;
  if (document.getElementById('status-filter').value) n++;
  const iv = document.getElementById('interest-filter').value;
  if (iv && iv !== 'hide_pass') n++;
  n += activeChips.size;
  if (n > 0) {{
    btn.classList.add('active');
    btn.textContent = 'clear (' + n + ')';
  }} else {{
    btn.classList.remove('active');
    btn.textContent = 'no filters';
  }}
}}

function clearSearch() {{
  document.getElementById('search').value = '';
  filterTable();
}}

function toggleChip(name) {{
  if (activeChips.has(name)) activeChips.delete(name);
  else activeChips.add(name);
  document.querySelectorAll('.chip').forEach(el => {{
    el.classList.toggle('active', activeChips.has(el.dataset.chip));
  }});
  filterTable();
}}

function resetFilters() {{
  document.getElementById('search').value = '';
  document.getElementById('source-filter').value = '';
  document.getElementById('score-filter').value = 'unfiltered';
  document.getElementById('status-filter').value = '';
  document.getElementById('interest-filter').value = 'hide_pass';
  activeChips.clear();
  document.querySelectorAll('.chip').forEach(el => el.classList.remove('active'));
  filterTable();
}}

function applySort() {{
  const mode = document.getElementById('sort-select').value;
  const tbody = document.getElementById('jobs-body');
  const rows = Array.from(tbody.querySelectorAll('tr'));

  const interestRank = {{ very_interested: 0, interested: 1, not_reviewed: 2, not_interested: 3 }};

  const cmp = {{
    interest: (a, b) => {{
      const r = (interestRank[a.dataset.interest] ?? 2) - (interestRank[b.dataset.interest] ?? 2);
      if (r !== 0) return r;
      return parseFloat(b.dataset.score) - parseFloat(a.dataset.score);
    }},
    score:   (a, b) => parseFloat(b.dataset.score) - parseFloat(a.dataset.score),
    company: (a, b) => (a.dataset.company || '').localeCompare(b.dataset.company || ''),
    recent:  (a, b) => 0,  // current sort is already "most recent" within priority
  }}[mode];

  rows.sort(cmp);
  // Detach + reattach. Faster than per-row appendChild on most browsers.
  const frag = document.createDocumentFragment();
  rows.forEach(r => frag.appendChild(r));
  tbody.appendChild(frag);
  // Refilter so filteredRows is in the new DOM order, and reset to page 1.
  filterTable();
}}

// ---------- Confetti ----------
function fireConfetti(count) {{
  count = count || 36;
  const c = document.getElementById('confetti-container');
  // Remove old confetti
  c.innerHTML = '';
  const frag = document.createDocumentFragment();
  for (let i = 0; i < count; i++) {{
    const piece = document.createElement('div');
    piece.className = 'confetti-piece';
    const size = 6 + Math.random() * 8;
    const left = Math.random() * 100;
    const delay = Math.random() * 0.5;
    const duration = 2.4 + Math.random() * 1.2;
    const color = CONFETTI_PALETTE[i % CONFETTI_PALETTE.length];
    const rot = Math.random() * 360;
    const drift = -40 + Math.random() * 80;
    piece.style.left = left + '%';
    piece.style.width = size + 'px';
    piece.style.height = (size * 1.4) + 'px';
    piece.style.background = color;
    piece.style.transform = 'rotate(' + rot + 'deg)';
    piece.style.setProperty('--dur', duration + 's');
    piece.style.setProperty('--delay', delay + 's');
    piece.style.setProperty('--dx', drift + 'px');
    frag.appendChild(piece);
  }}
  c.appendChild(frag);
  // Self-clean after animation
  setTimeout(() => {{ if (c.children.length) c.innerHTML = ''; }}, 4500);
}}

// ---------- Affirmation toast ----------
function showAffirmation(text) {{
  const t = document.getElementById('affirmation-toast');
  document.getElementById('affirmation-text').textContent = text;
  t.classList.add('show');
  clearTimeout(window._affTimer);
  window._affTimer = setTimeout(dismissAffirmation, 3600);
}}

function dismissAffirmation() {{
  document.getElementById('affirmation-toast').classList.remove('show');
}}

function pickAffirmation() {{
  if (usedAffirmations.length === AFFIRMATIONS.length) usedAffirmations = [];
  let pick;
  do {{
    pick = AFFIRMATIONS[Math.floor(Math.random() * AFFIRMATIONS.length)];
  }} while (usedAffirmations.includes(pick));
  usedAffirmations.push(pick);
  return pick;
}}

function triggerCelebrate() {{
  fireConfetti(36);
  showAffirmation(pickAffirmation());
}}

// ---------- Pick-me-up shuffle ----------
let pickIdx = 0;
const PUPPY_CAPTIONS = [
  "a small friend, just for you",
  "huckleberry says hi to this one",
  "today's good dog",
  "borrowed for a moment",
  "look at those paws",
  "this one has been waiting",
  "tiny ambassador",
];

// Try dog.ceo first (returns native-aspect photos — no head-chopping).
// Fall back to placedog.net (cropped but reliable) on failure.
async function loadPuppyPhoto() {{
  const img = document.getElementById('pickmeup-img');
  if (!img) return;
  img.style.display = '';
  try {{
    const resp = await fetch('https://dog.ceo/api/breeds/image/random', {{ cache: 'no-store' }});
    if (resp.ok) {{
      const data = await resp.json();
      if (data.status === 'success' && data.message) {{
        img.src = data.message;
        return;
      }}
    }}
    throw new Error('dog.ceo unavailable');
  }} catch (e) {{
    // Fallback to placedog.net with a random id
    const newId = Math.floor(Math.random() * 200) + 1;
    img.src = 'https://placedog.net/600/400?id=' + newId;
  }}
}}

function shufflePickMeUp() {{
  // Cycle joke
  pickIdx = (pickIdx + 1) % JOKES.length;
  const [q, a] = JOKES[pickIdx];
  document.getElementById('joke-q').textContent = q;
  document.getElementById('joke-a').textContent = a;
  // New puppy photo
  loadPuppyPhoto();
  // New caption
  const cap = document.getElementById('pickmeup-caption');
  if (cap) {{
    cap.textContent = PUPPY_CAPTIONS[Math.floor(Math.random() * PUPPY_CAPTIONS.length)];
  }}
}}

// Initial photo load — happens once on page load.
loadPuppyPhoto();

// ---------- Add Job ----------
function toggleAddJob(force) {{
  const panel = document.getElementById('add-job-panel');
  const expanded = (force === undefined)
    ? !panel.classList.contains('expanded') : !!force;
  panel.classList.toggle('expanded', expanded);
  if (expanded) {{
    document.getElementById('aj-url').focus();
    document.getElementById('add-job-status').textContent = '';
    document.getElementById('add-job-status').className = '';
  }}
}}

async function submitAddJob(event) {{
  event.preventDefault();
  const submitBtn = document.getElementById('aj-submit');
  const status = document.getElementById('add-job-status');
  const payload = {{
    url: document.getElementById('aj-url').value.trim(),
    jd_text: document.getElementById('aj-jd').value.trim(),
    role: document.getElementById('aj-role').value.trim(),
    company: document.getElementById('aj-company').value.trim(),
    location: document.getElementById('aj-location').value.trim(),
  }};
  if (!payload.url && !payload.jd_text && !(payload.role && payload.company)) {{
    status.textContent = 'Provide a URL, JD text, or role + company.';
    status.className = 'error';
    return false;
  }}
  submitBtn.disabled = true;
  status.textContent = 'Working…';
  status.className = '';
  try {{
    const resp = await fetch('/api/add-job', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload),
    }});
    const data = await resp.json();
    if (data.ok) {{
      if (data.queued) {{
        status.textContent = data.message || 'Posting queued. Will appear after next nightly sync.';
        status.className = 'success';
        document.getElementById('add-job-form').reset();
        submitBtn.disabled = false;
      }} else {{
        const score = data.fit_score !== undefined && data.fit_score !== null
          ? ' (score: ' + (data.fit_score * 100).toFixed(0) + '%)' : '';
        const newOrUpdated = data.is_new ? 'Added' : 'Updated';
        status.textContent = newOrUpdated + ' posting' + score + ' — refreshing…';
        status.className = 'success';
        setTimeout(() => window.location.reload(), 1200);
      }}
    }} else {{
      status.textContent = data.message || 'Failed.';
      status.className = 'error';
      submitBtn.disabled = false;
    }}
  }} catch (err) {{
    status.textContent = 'Network error: ' + err.message;
    status.className = 'error';
    submitBtn.disabled = false;
  }}
  return false;
}}

// ---------- Apply modal ----------
let applyModalPostingId = null;
let applyModalApplicationId = null;

function formatTailoredMtime(mtime) {{
  const ageSeconds = (Date.now() / 1000) - mtime;
  const ageMinutes = ageSeconds / 60;
  if (ageMinutes < 60) return 'just now';
  const ageHours = ageMinutes / 60;
  if (ageHours < 24) return Math.floor(ageHours) + 'h ago';
  const ageDays = ageHours / 24;
  if (ageDays < 30) return Math.floor(ageDays) + 'd ago';
  return Math.floor(ageDays / 30) + 'mo ago';
}}

function populateFileDropdown(selectEl, manualEl, candidates, existingPath) {{
  while (selectEl.options.length > 0) selectEl.remove(0);
  const noneOpt = document.createElement('option');
  noneOpt.value = ''; noneOpt.textContent = '— None —';
  selectEl.appendChild(noneOpt);
  for (const c of candidates) {{
    const opt = document.createElement('option');
    opt.value = c.path;
    const scorePct = Math.round(c.score * 100);
    const ago = formatTailoredMtime(c.mtime);
    opt.textContent = c.basename + '  [' + scorePct + '% match, ' + ago + ']';
    selectEl.appendChild(opt);
  }}
  const manualOpt = document.createElement('option');
  manualOpt.value = '__manual__';
  manualOpt.textContent = 'Other (paste path…)';
  selectEl.appendChild(manualOpt);

  manualEl.style.display = 'none'; manualEl.value = '';
  if (existingPath) {{
    const match = Array.from(selectEl.options).find(o => o.value === existingPath);
    if (match) {{
      selectEl.value = existingPath;
    }} else {{
      selectEl.value = '__manual__';
      manualEl.value = existingPath;
      manualEl.style.display = 'block';
    }}
  }} else if (candidates.length > 0 && candidates[0].score > 0.8) {{
    selectEl.value = candidates[0].path;
  }} else {{
    selectEl.value = '';
  }}
}}

function onResumeSelectChange() {{
  const sel = document.getElementById('apply-resume-select');
  const manualEl = document.getElementById('apply-resume-manual');
  manualEl.style.display = (sel.value === '__manual__') ? 'block' : 'none';
  if (sel.value === '__manual__') manualEl.focus();
}}
function onCoverSelectChange() {{
  const sel = document.getElementById('apply-cover-select');
  const manualEl = document.getElementById('apply-cover-manual');
  manualEl.style.display = (sel.value === '__manual__') ? 'block' : 'none';
  if (sel.value === '__manual__') manualEl.focus();
}}
function resolvedPath(selectId, manualId) {{
  const sel = document.getElementById(selectId);
  const manualEl = document.getElementById(manualId);
  if (sel.value === '__manual__') return (manualEl.value || '').trim();
  return sel.value || '';
}}

async function openApplyModal(postingId) {{
  applyModalPostingId = postingId;
  applyModalApplicationId = null;

  const backdrop = document.getElementById('apply-modal-backdrop');
  const titleEl = document.getElementById('apply-modal-title');
  const subtitleEl = document.getElementById('apply-modal-subtitle');
  const jdEl = document.getElementById('apply-jd');
  const notesEl = document.getElementById('apply-notes');
  const statusSelect = document.getElementById('apply-status-select');
  const resumeSelect = document.getElementById('apply-resume-select');
  const coverSelect = document.getElementById('apply-cover-select');
  const resumeManual = document.getElementById('apply-resume-manual');
  const coverManual = document.getElementById('apply-cover-manual');
  const watchDirEl = document.getElementById('apply-watch-dir');
  const submitBtn = document.getElementById('apply-submit');
  const statusMsg = document.getElementById('apply-status');

  titleEl.textContent = 'Loading…'; subtitleEl.textContent = '';
  jdEl.value = ''; notesEl.value = '';
  statusSelect.value = 'submitted';
  resumeManual.value = ''; resumeManual.style.display = 'none';
  coverManual.value = ''; coverManual.style.display = 'none';
  submitBtn.disabled = true;
  statusMsg.textContent = ''; statusMsg.className = '';
  backdrop.classList.add('open');

  try {{
    const [postingResp, filesResp] = await Promise.all([
      fetch('/api/posting/' + postingId, {{ cache: 'no-store' }}),
      fetch('/api/tailored-files?posting_id=' + postingId, {{ cache: 'no-store' }}),
    ]);
    const postingData = await postingResp.json();
    if (!postingData.ok) {{
      titleEl.textContent = 'Error';
      statusMsg.textContent = postingData.message || 'Could not load posting.';
      statusMsg.className = 'error';
      return;
    }}
    const filesData = await filesResp.json();
    const resumeCandidates = filesData.ok ? (filesData.resume || []) : [];
    const coverCandidates  = filesData.ok ? (filesData.cover || [])  : [];
    if (filesData.ok && filesData.watch_dir) watchDirEl.textContent = filesData.watch_dir;

    const p = postingData.posting;
    const a = postingData.application;
    titleEl.textContent = p.role + ' — ' + p.company;
    subtitleEl.textContent = (p.location || 'Location unknown') + ' · ' + (p.url || 'no URL');

    if (a) {{
      applyModalApplicationId = a.id;
      jdEl.value = a.jd_snapshot || p.jd_text || '';
      notesEl.value = a.notes || '';
      statusSelect.value = a.status || 'submitted';
      populateFileDropdown(resumeSelect, resumeManual, resumeCandidates, a.resume_path || '');
      populateFileDropdown(coverSelect, coverManual, coverCandidates, a.cover_letter_path || '');
    }} else {{
      jdEl.value = p.jd_text || '';
      statusSelect.value = 'submitted';
      populateFileDropdown(resumeSelect, resumeManual, resumeCandidates, '');
      populateFileDropdown(coverSelect, coverManual, coverCandidates, '');
    }}
    submitBtn.disabled = false;
    jdEl.focus();
  }} catch (err) {{
    titleEl.textContent = 'Error';
    statusMsg.textContent = 'Network error: ' + err.message;
    statusMsg.className = 'error';
  }}
}}

function closeApplyModal() {{
  document.getElementById('apply-modal-backdrop').classList.remove('open');
  applyModalPostingId = null;
  applyModalApplicationId = null;
}}

function onBackdropClick(event) {{
  if (event.target.id === 'apply-modal-backdrop') closeApplyModal();
}}

async function onStatusChange(event, applicationId) {{
  const sel = event.target;
  const newStatus = sel.value;
  const oldStatus = sel.dataset.currentStatus;
  if (newStatus === oldStatus) return;
  sel.classList.remove('status-' + oldStatus);
  sel.classList.add('status-' + newStatus);
  try {{
    const resp = await fetch('/api/application/' + applicationId + '/status', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ status: newStatus }}),
    }});
    const data = await resp.json();
    if (data.ok) {{
      sel.dataset.currentStatus = newStatus;
      // Celebrate the forward moves
      const forward = ['submitted','interviewing','offered'];
      if (forward.includes(newStatus) && !forward.includes(oldStatus)) {{
        fireConfetti(newStatus === 'offered' ? 90 : 36);
        if (newStatus === 'interviewing') showAffirmation('Interviewing. They want to meet you.');
        else if (newStatus === 'offered')  showAffirmation('The big one. ' + MASCOT_NAME + ' is so proud.');
        else                                showAffirmation(pickAffirmation());
      }}
    }} else {{
      sel.value = oldStatus;
      sel.classList.remove('status-' + newStatus);
      sel.classList.add('status-' + oldStatus);
      alert('Failed to update status: ' + (data.message || 'unknown error'));
    }}
  }} catch (err) {{
    sel.value = oldStatus;
    sel.classList.remove('status-' + newStatus);
    sel.classList.add('status-' + oldStatus);
    alert('Network error: ' + err.message);
  }}
}}

async function onInterestChange(event, postingId) {{
  const sel = event.target;
  const newLevel = sel.value;
  const row = sel.closest('tr');
  const oldLevel = row?.dataset.interest || 'not_reviewed';
  if (newLevel === oldLevel) return;
  sel.classList.remove('interest-' + oldLevel);
  sel.classList.add('interest-' + newLevel);
  try {{
    const resp = await fetch('/api/posting/' + postingId + '/interest', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ interest_level: newLevel }}),
    }});
    const data = await resp.json();
    if (data.ok) {{
      if (row) row.dataset.interest = newLevel;
      // Small reward when marking very_interested
      if (newLevel === 'very_interested') fireConfetti(12);
    }} else {{
      sel.value = oldLevel;
      sel.classList.remove('interest-' + newLevel);
      sel.classList.add('interest-' + oldLevel);
      alert('Failed: ' + (data.message || 'unknown error'));
    }}
  }} catch (err) {{
    sel.value = oldLevel;
    sel.classList.remove('interest-' + newLevel);
    sel.classList.add('interest-' + oldLevel);
    alert('Network error: ' + err.message);
  }}
}}

async function submitApply() {{
  if (applyModalPostingId === null) return;
  const submitBtn = document.getElementById('apply-submit');
  const statusMsg = document.getElementById('apply-status');
  const payload = {{
    posting_id: applyModalPostingId,
    status: document.getElementById('apply-status-select').value,
    jd_snapshot: document.getElementById('apply-jd').value.trim(),
    notes: document.getElementById('apply-notes').value.trim(),
    resume_path: resolvedPath('apply-resume-select', 'apply-resume-manual'),
    cover_letter_path: resolvedPath('apply-cover-select', 'apply-cover-manual'),
  }};
  submitBtn.disabled = true;
  statusMsg.textContent = 'Saving…'; statusMsg.className = '';
  try {{
    const resp = await fetch('/api/apply', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload),
    }});
    const data = await resp.json();
    if (data.ok) {{
      statusMsg.textContent = (data.is_new ? 'Logged' : 'Updated') + ' — refreshing…';
      statusMsg.className = 'success';
      // Celebrate the apply
      if (payload.status === 'submitted') {{
        fireConfetti(36);
        showAffirmation(pickAffirmation());
      }}
      setTimeout(() => window.location.reload(), 1200);
    }} else {{
      statusMsg.textContent = data.message || 'Failed.';
      statusMsg.className = 'error';
      submitBtn.disabled = false;
    }}
  }} catch (err) {{
    statusMsg.textContent = 'Network error: ' + err.message;
    statusMsg.className = 'error';
    submitBtn.disabled = false;
  }}
}}

// Close modal on Escape
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') {{
    const backdrop = document.getElementById('apply-modal-backdrop');
    if (backdrop.classList.contains('open')) closeApplyModal();
  }}
}});

// ---------- Server health check ----------
//
// Note: Apply buttons stay visible even when offline. They open the modal,
// which fetches /api/posting/<id> and shows an error if the server is
// genuinely unreachable. Hiding the buttons was misleading — a transient
// health-check blip made it look like the feature was gone. Status and
// interest dropdowns DO disable when offline (they're not modals, so a
// click-and-immediate-fail UX is worse than a disabled control).
function setOfflineMode(label) {{
  document.getElementById('add-job-toggle-btn').classList.remove('visible');
  document.querySelectorAll('.status-select').forEach(s => {{
    s.disabled = true;
    s.title = 'Status changes unavailable — server unreachable';
  }});
  document.querySelectorAll('.interest-select').forEach(s => {{
    s.disabled = true;
    s.title = 'Interest changes unavailable — server unreachable';
  }});
  const ss = document.getElementById('server-status');
  if (ss) {{ ss.textContent = label; ss.classList.remove('online'); }}
}}

function setOnlineMode(serverLabel) {{
  document.getElementById('add-job-toggle-btn').classList.add('visible');
  const ss = document.getElementById('server-status');
  if (ss) {{
    ss.textContent = serverLabel === 'cloudflare-worker' ? 'live · cloudflare' : 'server online';
    ss.classList.add('online');
  }}
}}

(async function checkServer() {{
  try {{
    const resp = await fetch('/api/health', {{ method: 'GET', cache: 'no-store' }});
    if (resp.ok) {{
      const data = await resp.json();
      if (data.ok) {{
        setOnlineMode(data.server || 'unknown');
        await applyPendingEvents();
        return;
      }}
    }}
    setOfflineMode('server offline');
  }} catch (e) {{
    setOfflineMode('server offline');
  }}
}})();

async function applyPendingEvents() {{
  try {{
    const resp = await fetch('/api/events/pending', {{ cache: 'no-store' }});
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.ok || !Array.isArray(data.events)) return;
    for (const ev of data.events) {{
      try {{
        if (ev.event_type === 'interest') applyInterestOverlay(ev.posting_id, ev.payload.interest_level);
        else if (ev.event_type === 'status') applyStatusOverlay(ev.application_id, ev.payload.status);
      }} catch (err) {{ console.warn('Overlay error', ev.id, err); }}
    }}
  }} catch (err) {{ console.warn('Could not load pending events:', err); }}
}}

function applyInterestOverlay(postingId, newLevel) {{
  const sel = document.querySelector('.interest-select[data-posting-id="' + postingId + '"]');
  if (!sel) return;
  sel.className = sel.className.split(' ').filter(c => !c.startsWith('interest-')).join(' ');
  sel.classList.add('interest-select');
  sel.classList.add('interest-' + newLevel);
  sel.value = newLevel;
  const row = sel.closest('tr');
  if (row) row.dataset.interest = newLevel;
}}

function applyStatusOverlay(applicationId, newStatus) {{
  const sel = document.querySelector('.status-select[data-application-id="' + applicationId + '"]');
  if (!sel) return;
  sel.value = newStatus;
  sel.dataset.currentStatus = newStatus;
  sel.className = sel.className.split(' ').filter(c => !c.startsWith('status-')).join(' ');
  sel.classList.add('status-select');
  sel.classList.add('status-' + newStatus);
}}

// Initial render — default filters are already set (score: unfiltered, interest: hide_pass)
filterTable();
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Auto-unlock any achievements that should be earned given current state.
    # Cheap, idempotent — runs on every dashboard regen.
    achievements.check_and_unlock(conn)

    postings = fetch_postings(conn)
    sources = fetch_sources(conn)
    weekly = achievements.weekly_progress(conn)
    sparkline = achievements.sparkline_data(conn, days=14)
    sparkline_ctx = achievements.sparkline_context(sparkline)
    funnel = achievements.funnel_counts(conn)
    picks = achievements.todays_picks(conn, n=3)
    radar_count = achievements.radar_count(conn)
    achievements_list = achievements.get_achievements(conn)
    streak = achievements.current_streak(conn)
    last_scraped = fetch_last_scrape(conn)

    conn.close()

    OUT_PATH.parent.mkdir(exist_ok=True)
    html_out = generate(
        postings=postings,
        sources=sources,
        weekly=weekly,
        sparkline=sparkline,
        sparkline_ctx=sparkline_ctx,
        funnel=funnel,
        picks=picks,
        radar_count=radar_count,
        achievements_list=achievements_list,
        streak=streak,
        last_scraped=last_scraped,
    )
    OUT_PATH.write_text(html_out, encoding="utf-8")
    print(f"Dashboard written to: {OUT_PATH}")
    print(f"  {len(postings)} postings, {streak}-day streak, {weekly['done']}/{weekly['goal']} weekly")
    print(f"Open in browser: open {OUT_PATH}")


if __name__ == "__main__":
    main()
