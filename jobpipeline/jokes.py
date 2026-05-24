"""Pick-me-up jokes + mascot greeting quotes for the dashboard.

Hand-curated, in the calm-mentor / witty-best-friend voice
(self-deprecating about the job market, never punching down). Voice
rules per design/voice-and-tone.md.

Each joke is a (setup, punchline) pair. Setup goes in the hand-written
accent font; punchline in the body color. Keep both under ~80 chars.

Mascot-specific jokes use the literal token "{mascot}" — it gets
substituted with the user's mascot name (config/profile.yaml) at render
time so the joke reads naturally regardless of which mascot they picked.

Selection is deterministic by day-of-year for the default pick (so it
feels stable through the day); shuffled on user demand.
"""

from __future__ import annotations

from datetime import date

from . import config


# Each entry is (setup, punchline). The literal text "{mascot}" is
# substituted with config.mascot_name() at render time.
JOKES = [
    ("Why did the résumé go to therapy?",
     "Too many unresolved bullet points."),

    ("What did the cover letter say to the hiring manager?",
     "'Dear Sir/Madam, please love me.'"),

    ("How do you make a recruiter laugh?",
     "Tell them your salary expectations."),

    ("Why don't job searches get along with calendars?",
     "Too many 'we'll get back to you next week's."),

    ("What's a job seeker's favorite tea?",
     "Recruitea. (It never arrives.)"),

    ("How many recruiters does it take to change a lightbulb?",
     "We'll circle back on that."),

    ("Why did {mascot} apply to be a barista?",
     "Heard the bar was low."),

    ("What's the difference between an application and a black hole?",
     "Black holes occasionally emit something."),

    ("Why are job descriptions like horoscopes?",
     "Vague, optimistic, and require 5 years of relevant experience."),

    ("{mascot}'s wisdom on networking events:",
     "'The shrimp is free. The smiling is not.'"),

    ("What did the LinkedIn algorithm say to the qualified candidate?",
     "Have you considered relocating to Iceland?"),

    ("Why was the ATS rejected from improv class?",
     "It couldn't say 'yes, and' to a single resume."),

    ("How do you spot a senior engineer at a career fair?",
     "They're the one quietly eating all the M&Ms."),

    ("What's the most common ghost story?",
     "'They said they'd update me by Friday.'"),

    ("{mascot}'s take on take-home assignments:",
     "'Eight hours of free labor, but make it a culture fit.'"),

    ("What's an introvert's favorite interview format?",
     "The one that got cancelled."),

    ("Why did the candidate cross the road?",
     "To submit the same résumé to a different portal."),

    ("{mascot} on the words 'rockstar' and 'ninja':",
     "'Neither of those people would sit in your meetings.'"),
]


def _interp(text: str) -> str:
    """Substitute {mascot} placeholder with the configured mascot name."""
    return text.replace("{mascot}", config.mascot_name())


def todays_joke() -> tuple[str, str]:
    """Stable joke for today (deterministic by day-of-year)."""
    idx = date.today().toordinal() % len(JOKES)
    q, a = JOKES[idx]
    return (_interp(q), _interp(a))


def joke_at(idx: int) -> tuple[str, str]:
    """Joke at a specific index (used by the shuffle button)."""
    q, a = JOKES[idx % len(JOKES)]
    return (_interp(q), _interp(a))


# Greeting-bar mascot quotes. Calm-mentor mode; rotate by hour of day.
MASCOT_QUOTES = [
    ("morning", [
        "take it one job at a time.",
        "Mondays are fresh starts.",
        "showing up counts.",
        "the well is full today.",
        "you have time. you have time.",
    ]),
    ("afternoon", [
        "three planes is enough. send them.",
        "lunch is also a contribution.",
        "you're allowed to take a beat.",
        "'we'll get back to you' is the most expensive lie in tech.",
    ]),
    ("evening", [
        "rest counts as showing up.",
        "you did a thing today. that's enough.",
        "tomorrow is also a day.",
        "close the tab. {mascot}'s watching the inbox.",
    ]),
]


def todays_mascot_quote(hour: int) -> tuple[str, str]:
    """Return (greeting, quote) tuple. Greeting like "good morning";
    quote rotates by day-of-year so the same quote shows all day."""
    if hour < 12:
        bucket = "morning"
    elif hour < 18:
        bucket = "afternoon"
    else:
        bucket = "evening"

    for name, quotes in MASCOT_QUOTES:
        if name == bucket:
            idx = date.today().toordinal() % len(quotes)
            return (f"good {name}", _interp(quotes[idx]))
    return ("hello", "you're doing fine.")
