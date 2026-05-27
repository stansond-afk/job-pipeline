"""Theme registry — six selectable visual identities.

This is a Python mirror of handoff/code/themes.js. When updating one,
update the other to match. The JS file is the design source-of-truth;
this file is what the Python dashboard generator reads from.

Architecture (see handoff/architecture.md for the full picture):

  - Themes are pure data — tokens (CSS variables), copy strings, mascot key.
  - The dashboard generator emits one HTML page that consumes whatever
    theme is set in config/profile.yaml.
  - Adding a 7th theme = adding a new entry to THEMES. No code changes.

Required keys per theme (validated by validate_theme below):

  id, name, blurb, tagline, tone, mascot (or None), decoration, dark (bool),
  tokens (dict of CSS variable name → value), copy (dict of string templates).

Copy templates may contain {placeholders}:
  {pct}        — percent of weekly goal complete
  {done}       — apps submitted this week
  {goal}       — weekly goal (default 15)
  {remaining}  — goal - done, clamped to 0

The dashboard generator interpolates these at render time. Unknown
placeholders are left as-is (defensive).
"""

from __future__ import annotations

from typing import Optional


# ─────────────────────────────────────────────────────────────────────────
# All six themes — palette tokens + copy register.
# Mirrors handoff/code/themes.js verbatim. Keep in sync.
# ─────────────────────────────────────────────────────────────────────────

THEMES: dict[str, dict] = {

    # ─── 1. Paper · the plain default ───────────────────────────────────
    # Clean cream + ink, single accent. No mascot, no hand-written script.
    # Safe default for new accounts — imposes nothing.
    "paper": {
        "id":          "paper",
        "name":        "Paper",
        "blurb":       "Clean cream paper and ink. No mascot, no extras. Just the work.",
        "tagline":     "minimal · neutral · quiet",
        "tone":        "quiet narrator",
        "mascot":      None,
        "decoration":  "paper",
        "dark":        False,
        "tokens": {
            "--bg":            "#F2EFE8",
            "--paper":         "#FFFFFF",
            "--ink":           "#1A1A1A",
            "--sub":           "#6B6B6B",
            "--line":          "#D8D4CB",
            "--row":           "#F2EFE8",
            "--a1":            "#3A6A8C",
            "--a1-dk":         "#234B68",
            "--a2":            "#8A8580",
            "--a2-dk":         "#5C5854",
            "--sun":           "#E8D9A8",
            "--sun-dk":        "#9A8853",
            "--warm":          "#B87363",
            "--good":          "#8FA88E",
            "--serif":         "'EB Garamond', Georgia, serif",
            "--sans":          "'Inter', system-ui, sans-serif",
            "--hand":          "'EB Garamond', Georgia, serif",
            "--radius-card":   "6px",
            "--radius-pill":   "4px",
            "--radius-tag":    "4px",
            "--kicker-tt":     "uppercase",
            "--kicker-ls":     "2px",
            "--shadow-card":   "0 0 0 1px rgba(0,0,0,0.04)",
            "--shadow-cta":    "0 2px 6px -2px rgba(0,0,0,0.25)",
        },
        "copy": {
            "productName":     "Jobline",
            "greetingScript":  "Good morning,",
            "nameSuffix":      ".",
            "mascotName":      None,
            "mascotSays":      "Note:",
            "mascotQuote":     "small steady acts.",
            "celebrate":       "Mark today done",
            "streakSuffix":    "days, in a row",
            "streakIcon":      "·",
            "ringCopy":        "{done} of {goal} this week.",
            "ringSub":         "{remaining} more to finish the week.",
            "sparklineCopy":   "Best day: last Friday — 4 applications. Pace +22% week-over-week.",
            "funnelTitle":     "Pipeline",
            "funnelFooter":    "each step happened because you made it happen.",
            "picksTitle":      "Today's three",
            "picksKicker":     "selected",
            "pickMeUpKicker":  "a small thing",
            "pickMeUpTitle":   "Read this slowly",
            "achKicker":       "marked",
            "tableKicker":     "all postings",
            "tableTitle":      "Full list",
            "footer":          "—",
            "affirmations": [
                "You sent applications today. That is real work.",
                "A 'no' is not a verdict. It is information.",
                "You showed up. That's enough today.",
                "Steady effort. The work compounds.",
                "One more. Then rest.",
                "You did the thing you said you would do.",
                "Future you is grateful for today's effort.",
            ],
        },
    },

    # ─── 2. Garden · warm, hand-written ─────────────────────────────────
    # The original Solongo direction. Capybara is optional. Feminine-leaning.
    "garden": {
        "id":          "garden",
        "name":        "Garden",
        "blurb":       "Cream, soft pastels, and a calm capybara if you want one. Warmth in the corners.",
        "tagline":     "warm · soft · hand-written",
        "tone":        "gentle friend",
        "mascot":      "capybara",
        "decoration":  "sun-clouds",
        "dark":        False,
        "tokens": {
            "--bg":            "#FBF7EF",
            "--paper":         "#FFFDF7",
            "--ink":           "#2E2B3D",
            "--sub":           "#6F6A82",
            "--line":          "#E7DFCD",
            "--row":           "#F4EFE2",
            "--a1":            "#9CC3E8",
            "--a1-dk":         "#5B8AB8",
            "--a2":            "#C9B8E0",
            "--a2-dk":         "#8A77B0",
            "--sun":           "#F4D87C",
            "--sun-dk":        "#C49F37",
            "--warm":          "#F0A89C",
            "--good":          "#B9DBC4",
            "--serif":         "'Fraunces', Georgia, serif",
            "--sans":          "'Nunito', system-ui, sans-serif",
            "--hand":          "'Caveat', cursive",
            "--radius-card":   "20px",
            "--radius-pill":   "999px",
            "--radius-tag":    "12px",
            "--kicker-tt":     "uppercase",
            "--kicker-ls":     "1.2px",
            "--shadow-card":   "0 1px 0 rgba(255,255,255,0.7) inset, 0 8px 20px -16px rgba(80,60,30,0.15)",
            "--shadow-cta":    "0 6px 16px -8px rgba(0,0,0,0.4)",
        },
        "copy": {
            "productName":     "Jobline",
            "greetingScript":  "good morning,",
            "nameSuffix":      " ☀",
            "mascotName":      "Pip",
            "mascotSays":      "Today:",
            "mascotQuote":     "take it one job at a time.",
            "celebrate":       "Celebrate today",
            "streakSuffix":    "days showing up",
            "streakIcon":      "🔥",
            "ringCopy":        "you're {pct}% of the way there",
            "ringSub":         "{remaining} more this week and the goal is yours.",
            "sparklineCopy":   "Best day: last Friday (4 apps). Pace is up 22% from last week.",
            "funnelTitle":     "From discovery to dream job",
            "funnelFooter":    "each arrow is a small brave act.",
            "picksTitle":      "Three to look at today",
            "picksKicker":     "today's picks",
            "pickMeUpKicker":  "a small lift",
            "pickMeUpTitle":   "Something for you",
            "achKicker":       "your shelf",
            "tableKicker":     "all postings",
            "tableTitle":      "The full list — search & filter",
            "footer":          "made with care",
            "affirmations": [
                "You showed up today. That's real.",
                "Every 'no' is data, not a verdict.",
                "Look at you go.",
                "Beautiful work. Onward.",
                "You're doing the hard thing, slowly. That's the way.",
                "Future you is cheering for present you.",
                "Steady warmth wins.",
            ],
        },
    },

    # ─── 3. Tide · calm coastal ─────────────────────────────────────────
    # Sea-blues + warm sand. Otter mascot (Marlow) that floats by quietly.
    # Universally calm; reads gender-neutral.
    "tide": {
        "id":          "tide",
        "name":        "Tide",
        "blurb":       "Soft sea-blues and warm sand. Spacious, gender-neutral, with an otter who floats by occasionally.",
        "tagline":     "coastal · spacious · neutral",
        "tone":        "calm",
        "mascot":      "otter",
        "decoration":  "waves",
        "dark":        False,
        "tokens": {
            "--bg":            "#EAF1F4",
            "--paper":         "#F8FBFC",
            "--ink":           "#1F3A4A",
            "--sub":           "#5E7886",
            "--line":          "#CFDDE4",
            "--row":           "#E2EBEF",
            "--a1":            "#5E94B2",
            "--a1-dk":         "#3D6F86",
            "--a2":            "#87B4C9",
            "--a2-dk":         "#5887A1",
            "--sun":           "#E8D6A8",
            "--sun-dk":        "#A8924D",
            "--warm":          "#E89B8E",
            "--good":          "#90B8AE",
            "--serif":         "'Lora', Georgia, serif",
            "--sans":          "'Nunito', system-ui, sans-serif",
            "--hand":          "'Caveat', cursive",
            "--radius-card":   "16px",
            "--radius-pill":   "999px",
            "--radius-tag":    "12px",
            "--kicker-tt":     "lowercase",
            "--kicker-ls":     "1.4px",
            "--shadow-card":   "0 1px 0 rgba(255,255,255,0.6) inset, 0 6px 18px -12px rgba(30,60,80,0.18)",
            "--shadow-cta":    "0 6px 16px -8px rgba(20,40,60,0.4)",
        },
        "copy": {
            "productName":     "Jobline",
            "greetingScript":  "hello,",
            "nameSuffix":      ".",
            "mascotName":      "Marlow",
            "mascotSays":      "Today:",
            "mascotQuote":     "small, steady tides.",
            "celebrate":       "Mark the day",
            "streakSuffix":    "days, in a row",
            "streakIcon":      "○",
            "ringCopy":        "you're {pct}% of the way through the week",
            "ringSub":         "{remaining} more this week to close it out.",
            "sparklineCopy":   "Best day: last Friday (4 apps). Pace is up 22% from last week.",
            "funnelTitle":     "From shore to deep water",
            "funnelFooter":    "each step is one you took.",
            "picksTitle":      "Three picked for today",
            "picksKicker":     "today's three",
            "pickMeUpKicker":  "a quiet moment",
            "pickMeUpTitle":   "Take a breath",
            "achKicker":       "your shoreline",
            "tableKicker":     "all postings",
            "tableTitle":      "Every posting — search & filter",
            "footer":          "steady as the tide",
            "affirmations": [
                "You showed up today. That's enough.",
                "A 'no' is one wave. There are more.",
                "Slow, warm, steady — that's the way.",
                "Good work, quietly done.",
                "Today's effort matters.",
                "You did what you said you would do.",
                "Salt air, small acts. Both count.",
            ],
        },
    },

    # ─── 4. Quiet Focus · sharp & professional ──────────────────────────
    # Masculine-leaning. Slate + deep blue. No mascot. Warmth is in words.
    "quiet": {
        "id":          "quiet",
        "name":        "Quiet Focus",
        "blurb":       "Slate and deep blue. Sharper type, fewer ornaments. Warm in the words, professional everywhere else.",
        "tagline":     "calm · masculine · focused",
        "tone":        "steady mentor",
        "mascot":      None,
        "decoration":  "horizon",
        "dark":        False,
        "tokens": {
            "--bg":            "#ECEEF2",
            "--paper":         "#FFFFFF",
            "--ink":           "#161D27",
            "--sub":           "#5A6573",
            "--line":          "#D8DCE3",
            "--row":           "#F4F5F8",
            "--a1":            "#3B6CA8",
            "--a1-dk":         "#234780",
            "--a2":            "#7D9DC0",
            "--a2-dk":         "#4F6E92",
            "--sun":           "#D9A05B",
            "--sun-dk":        "#A77836",
            "--warm":          "#C77565",
            "--good":          "#6E9F8C",
            "--serif":         "'Newsreader', Georgia, serif",
            "--sans":          "'Inter', system-ui, sans-serif",
            "--hand":          "'Inter', system-ui, sans-serif",
            "--radius-card":   "10px",
            "--radius-pill":   "6px",
            "--radius-tag":    "8px",
            "--kicker-tt":     "uppercase",
            "--kicker-ls":     "1.6px",
            "--shadow-card":   "0 1px 2px rgba(20,30,50,0.04), 0 4px 12px -6px rgba(20,30,50,0.08)",
            "--shadow-cta":    "0 4px 12px -6px rgba(20,30,50,0.3)",
        },
        "copy": {
            "productName":     "Jobline",
            "greetingScript":  "Good morning,",
            "nameSuffix":      ".",
            "mascotName":      None,
            "mascotSays":      "Today:",
            "mascotQuote":     "one focused hour beats three scattered ones.",
            "celebrate":       "Mark today",
            "streakSuffix":    "consecutive days",
            "streakIcon":      "●",
            "ringCopy":        "{pct}% of the week behind you.",
            "ringSub":         "{remaining} more to close out the week.",
            "sparklineCopy":   "Best day: last Friday — 4 apps. Pace is up 22% from last week.",
            "funnelTitle":     "Pipeline",
            "funnelFooter":    "each step is one you took.",
            "picksTitle":      "Today's focus list",
            "picksKicker":     "priority",
            "pickMeUpKicker":  "reset",
            "pickMeUpTitle":   "Step away for a minute",
            "achKicker":       "milestones",
            "tableKicker":     "all postings",
            "tableTitle":      "Full pipeline",
            "footer":          "steady work, steady gains",
            "affirmations": [
                "You showed up today. That counts.",
                "Quiet, consistent — that's the work.",
                "A 'no' is information, not a verdict.",
                "Today's effort is tomorrow's offer.",
                "You did the work you set out to do.",
                "One more, then rest.",
                "Good work, quietly done.",
            ],
        },
    },

    # ─── 5. Mountain · grounded neutral ─────────────────────────────────
    # Stone grays + sage. Peak motif. No animal mascot. Reads neither
    # masculine nor feminine — genuinely neutral.
    "mountain": {
        "id":          "mountain",
        "name":        "Mountain",
        "blurb":       "Stone, sage, and alpine air. Grounded and unhurried. A peak as your only companion.",
        "tagline":     "grounded · calm · steady",
        "tone":        "grounded guide",
        "mascot":      None,
        "decoration":  "peak",
        "dark":        False,
        "tokens": {
            "--bg":            "#ECE9E3",
            "--paper":         "#F6F4EE",
            "--ink":           "#2C2E2A",
            "--sub":           "#6E6F69",
            "--line":          "#D4CFC4",
            "--row":           "#E5E1D8",
            "--a1":            "#7A8B82",
            "--a1-dk":         "#4F5E54",
            "--a2":            "#95A89B",
            "--a2-dk":         "#5F7468",
            "--sun":           "#D9B872",
            "--sun-dk":        "#9F8443",
            "--warm":          "#B87363",
            "--good":          "#95A89B",
            "--serif":         "'Source Serif Pro', Georgia, serif",
            "--sans":          "'Inter', system-ui, sans-serif",
            "--hand":          "'Source Serif Pro', Georgia, serif",
            "--radius-card":   "8px",
            "--radius-pill":   "6px",
            "--radius-tag":    "6px",
            "--kicker-tt":     "uppercase",
            "--kicker-ls":     "1.8px",
            "--shadow-card":   "0 1px 2px rgba(30,30,20,0.04), 0 6px 14px -8px rgba(30,30,20,0.1)",
            "--shadow-cta":    "0 4px 10px -4px rgba(30,30,20,0.3)",
        },
        "copy": {
            "productName":     "Jobline",
            "greetingScript":  "Good morning,",
            "nameSuffix":      ".",
            "mascotName":      None,
            "mascotSays":      "Today:",
            "mascotQuote":     "one step, then another.",
            "celebrate":       "Mark the day",
            "streakSuffix":    "days, climbing",
            "streakIcon":      "▲",
            "ringCopy":        "{pct}% of the way to the ridge",
            "ringSub":         "{remaining} more this week and you crest it.",
            "sparklineCopy":   "Best day: last Friday — 4 apps. Pace is up 22% from last week.",
            "funnelTitle":     "Base camp to summit",
            "funnelFooter":    "each switchback is the path forward.",
            "picksTitle":      "Today's route",
            "picksKicker":     "today's route",
            "pickMeUpKicker":  "a still moment",
            "pickMeUpTitle":   "Look up. Breathe.",
            "achKicker":       "summits reached",
            "tableKicker":     "the whole range",
            "tableTitle":      "Every posting — search & filter",
            "footer":          "step by step",
            "affirmations": [
                "One step, then another. You did it.",
                "Mountains are climbed by people who kept walking.",
                "A 'no' is a switchback, not the end.",
                "Steady breath. Steady feet.",
                "You went higher today than yesterday.",
                "The view is for the patient.",
                "Look how far behind you the trailhead is.",
            ],
        },
    },

    # ─── 6. Dusk · warm dark mode ───────────────────────────────────────
    # Aubergine + amber. Luna moth mascot (Vesper). Only dark theme.
    "dusk": {
        "id":          "dusk",
        "name":        "Dusk",
        "blurb":       "Warm dark mode. Aubergine, amber, and a luna moth named Vesper if you want her along.",
        "tagline":     "dark · warm · nocturnal",
        "tone":        "soft companion",
        "mascot":      "moth",
        "decoration":  "stars",
        "dark":        True,
        "tokens": {
            "--bg":            "#1B1726",
            "--paper":         "#2A2336",
            "--ink":           "#F5EBE0",
            "--sub":           "#9B8FAF",
            "--line":          "#3A3148",
            "--row":           "#241D30",
            "--a1":            "#A684C9",
            "--a1-dk":         "#C6A8E2",
            "--a2":            "#7390B8",
            "--a2-dk":         "#9CB5D4",
            "--sun":           "#E8B86C",
            "--sun-dk":        "#F5CE89",
            "--warm":          "#D69BAA",
            "--good":          "#9BBFA3",
            "--serif":         "'Fraunces', Georgia, serif",
            "--sans":          "'Inter', system-ui, sans-serif",
            "--hand":          "'Caveat', cursive",
            "--radius-card":   "16px",
            "--radius-pill":   "999px",
            "--radius-tag":    "12px",
            "--kicker-tt":     "uppercase",
            "--kicker-ls":     "1.4px",
            "--shadow-card":   "0 1px 0 rgba(255,255,255,0.04) inset, 0 12px 30px -16px rgba(0,0,0,0.6)",
            "--shadow-cta":    "0 8px 22px -10px rgba(0,0,0,0.6)",
        },
        "copy": {
            "productName":     "Jobline",
            "greetingScript":  "good evening,",
            "nameSuffix":      ".",
            "mascotName":      "Vesper",
            "mascotSays":      "Tonight:",
            "mascotQuote":     "the day is over. you did enough.",
            "celebrate":       "Close the day",
            "streakSuffix":    "nights of showing up",
            "streakIcon":      "✦",
            "ringCopy":        "{pct}% of the week is behind you",
            "ringSub":         "{remaining} more and the week is yours.",
            "sparklineCopy":   "Best day: last Friday (4 apps). Pace is up 22% from last week.",
            "funnelTitle":     "From spark to offer",
            "funnelFooter":    "every step is one you took.",
            "picksTitle":      "Three to look at tonight",
            "picksKicker":     "tonight's light",
            "pickMeUpKicker":  "a tiny lantern",
            "pickMeUpTitle":   "Pause, breathe out",
            "achKicker":       "your constellation",
            "tableKicker":     "all postings",
            "tableTitle":      "Every posting — search & filter",
            "footer":          "rest is part of the work",
            "affirmations": [
                "The day is closing. You did your part.",
                "A 'no' under a kind sky is still just one 'no'.",
                "Soft, steady, exactly enough.",
                "Tomorrow is also a day. Rest tonight.",
                "Quiet work today, real progress.",
                "You are loved by someone who knows what today cost.",
                "Rest now. Tomorrow you'll go again.",
            ],
        },
    },
}


# Safe default for new accounts. Imposes nothing — picking Paper means
# the user actively wanted zero personality. Don't auto-promote to Garden.
DEFAULT_THEME_ID = "paper"


# ─────────────────────────────────────────────────────────────────────────
# Public accessors
# ─────────────────────────────────────────────────────────────────────────


def list_theme_ids() -> list[str]:
    """All known theme keys, in display order."""
    return list(THEMES.keys())


def list_themes() -> list[dict]:
    """All theme dicts, in display order."""
    return list(THEMES.values())


def get_theme(theme_id: Optional[str]) -> dict:
    """Return a theme by ID. Falls back to the default ('paper') if the
    requested ID isn't known. Never raises — the dashboard should always
    render even with a corrupt config."""
    if theme_id and theme_id in THEMES:
        return THEMES[theme_id]
    return THEMES[DEFAULT_THEME_ID]


def is_valid_theme_id(theme_id: str) -> bool:
    """For server-side validation when writing to the user prefs table."""
    return theme_id in THEMES


# ─────────────────────────────────────────────────────────────────────────
# Copy interpolation
# ─────────────────────────────────────────────────────────────────────────


def fmt(template: str, **vars) -> str:
    """Fill {placeholders} in a copy template. Unknown placeholders are
    left intact (defensive — broken copy is better than a crash).

    Example:
        >>> fmt("you're {pct}% there", pct=42)
        "you're 42% there"
        >>> fmt("hello {name}", greeting="hi")  # unknown var
        "hello {name}"
    """
    if not template:
        return ""
    try:
        return template.format(**vars)
    except (KeyError, IndexError):
        # Partial fill: replace what we can, leave the rest as-is
        out = template
        for k, v in vars.items():
            out = out.replace("{" + k + "}", str(v))
        return out


# ─────────────────────────────────────────────────────────────────────────
# Schema validation (used by tests / migrations)
# ─────────────────────────────────────────────────────────────────────────


REQUIRED_THEME_KEYS = {
    "id", "name", "blurb", "tagline", "tone", "mascot", "decoration",
    "dark", "tokens", "copy",
}

REQUIRED_TOKEN_KEYS = {
    "--bg", "--paper", "--ink", "--sub", "--line", "--row",
    "--a1", "--a1-dk", "--a2", "--a2-dk",
    "--sun", "--sun-dk", "--warm", "--good",
    "--serif", "--sans", "--hand",
    "--radius-card", "--radius-pill", "--radius-tag",
    "--kicker-tt", "--kicker-ls",
    "--shadow-card", "--shadow-cta",
}

REQUIRED_COPY_KEYS = {
    "productName", "greetingScript", "nameSuffix",
    "mascotName", "mascotSays", "mascotQuote",
    "celebrate", "streakSuffix", "streakIcon",
    "ringCopy", "ringSub", "sparklineCopy",
    "funnelTitle", "funnelFooter",
    "picksTitle", "picksKicker",
    "pickMeUpKicker", "pickMeUpTitle",
    "achKicker", "tableKicker", "tableTitle",
    "footer", "affirmations",
}


def validate_theme(theme: dict) -> list[str]:
    """Return a list of validation errors. Empty list = theme is well-formed.

    Used in tests + by the wizard before writing the user's theme choice.
    """
    errors = []
    missing = REQUIRED_THEME_KEYS - set(theme.keys())
    if missing:
        errors.append(f"missing top-level keys: {sorted(missing)}")
    if "tokens" in theme:
        missing_tokens = REQUIRED_TOKEN_KEYS - set(theme["tokens"].keys())
        if missing_tokens:
            errors.append(f"missing tokens: {sorted(missing_tokens)}")
    if "copy" in theme:
        missing_copy = REQUIRED_COPY_KEYS - set(theme["copy"].keys())
        if missing_copy:
            errors.append(f"missing copy keys: {sorted(missing_copy)}")
        if "affirmations" in theme["copy"]:
            affs = theme["copy"]["affirmations"]
            if not isinstance(affs, list) or len(affs) < 3:
                errors.append("affirmations must be a list with >= 3 entries")
    return errors
