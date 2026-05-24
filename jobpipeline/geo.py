"""Geographic tier detection — config-driven.

Reads from config/geo_patterns.yaml. Four tiers:

    boost     → additive (default +0.15)  — your target metro
    remote_us → additive (default +0.05)  — remote-US-friendly
    other_us  → multiplicative (default ×0.5) — other US locations, soft demote
    foreign   → score = 0                  — non-US, hard filter
    unknown   → no change                  — empty/missing location

Foreign-country tokens are baked in (universal — same for every user).
US-state detection prevents American cities sharing names with foreign
capitals ("London, KY", "Paris, TX") from being misclassified.

The user's target metro patterns + remote-US patterns come from config.
"""

from __future__ import annotations

from typing import Optional, Tuple

from . import config


# ─────────────────────────────────────────────────────────────────────────
# Universal: US state detection
# ─────────────────────────────────────────────────────────────────────────

US_STATE_CODES = (
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
    "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
    "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok",
    "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
    "wi", "wy", "dc",
)

US_STATE_NAMES = (
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington state", "west virginia", "wisconsin", "wyoming",
    "united states", "usa",
)


# ─────────────────────────────────────────────────────────────────────────
# Universal: foreign-country tokens. If the location contains any of these
# (and isn't overridden by US state detection above), the posting is
# treated as foreign — score=0, hard filter. The user can extend via
# config/geo_patterns.yaml → foreign.extra_patterns.
# ─────────────────────────────────────────────────────────────────────────

FOREIGN_TOKENS_BUILTIN = (
    # English-language non-US countries
    "united kingdom", "uk", "england", "scotland", "wales", "northern ireland",
    "london", "manchester", "edinburgh", "birmingham, uk", "bristol, uk",
    "ireland", "dublin",
    "canada", "toronto", "vancouver", "montreal", "ottawa", "calgary",
    "australia", "sydney", "melbourne", "brisbane", "perth, australia",
    "new zealand", "auckland", "wellington",
    "singapore", "hong kong",
    "south africa", "cape town", "johannesburg",
    "philippines", "manila", "pasig", "quezon",
    "india", "mumbai", "delhi", "bangalore", "bengaluru", "hyderabad",
    "chennai", "pune", "kolkata", "noida", "gurgaon", "gurugram",
    # Continental Europe
    "germany", "berlin", "munich", "frankfurt", "hamburg", "cologne",
    "france", "paris", "lyon", "marseille",
    "spain", "madrid", "barcelona",
    "italy", "rome", "milan", "florence",
    "netherlands", "amsterdam", "rotterdam", "the hague",
    "belgium", "brussels",
    "switzerland", "zurich", "geneva", "bern",
    "austria", "vienna",
    "sweden", "stockholm", "gothenburg",
    "norway", "oslo",
    "denmark", "copenhagen",
    "finland", "helsinki",
    "poland", "warsaw", "krakow",
    "czech republic", "prague", "czechia",
    "hungary", "budapest",
    "romania", "bucharest",
    "bulgaria", "sofia",
    "greece", "athens",
    "portugal", "lisbon", "porto",
    # Latin America
    "mexico", "mexico city", "guadalajara", "monterrey",
    "brazil", "sao paulo", "são paulo", "rio de janeiro",
    "argentina", "buenos aires",
    "chile", "santiago",
    "colombia", "bogota", "bogotá",
    "peru", "lima",
    "costa rica", "san jose, costa rica",
    # Asia
    "japan", "tokyo", "osaka",
    "china", "beijing", "shanghai", "shenzhen", "guangzhou",
    "south korea", "seoul",
    "taiwan", "taipei",
    "thailand", "bangkok",
    "vietnam", "ho chi minh", "hanoi",
    "indonesia", "jakarta",
    "malaysia", "kuala lumpur",
    "pakistan", "karachi", "lahore", "islamabad",
    "bangladesh", "dhaka",
    # Middle East / Africa
    "uae", "united arab emirates", "dubai", "abu dhabi",
    "saudi arabia", "riyadh", "jeddah",
    "qatar", "doha",
    "israel", "tel aviv", "jerusalem",
    "egypt", "cairo",
    "kenya", "nairobi",
    "nigeria", "lagos", "abuja",
    "ghana", "accra",
    # Generic non-US signals
    "europe", "emea", "apac", "latam", "middle east",
)


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────


def _is_us_location(low_location: str) -> bool:
    """True if the location contains a US state name or 2-letter code."""
    if ", us" in low_location or low_location.endswith(", us") or " us " in low_location:
        return True
    for name in US_STATE_NAMES:
        if name in low_location:
            return True
    for code in US_STATE_CODES:
        if (f", {code}" == low_location[-len(code) - 2:] or
            f", {code}," in low_location or
            f", {code} " in low_location):
            return True
    return False


def _user_boost_patterns() -> tuple[str, ...]:
    tiers = config.geo_tier_config()
    return tuple(p.lower() for p in (tiers["boost"].get("patterns") or []))


def _user_remote_patterns() -> tuple[str, ...]:
    tiers = config.geo_tier_config()
    return tuple(p.lower() for p in (tiers["remote_us"].get("patterns") or []))


def _foreign_extra_patterns() -> tuple[str, ...]:
    tiers = config.geo_tier_config()
    return tuple(p.lower() for p in (tiers["foreign"].get("extra_patterns") or []))


def _boost_weight() -> float:
    return float(config.geo_tier_config()["boost"].get("weight", 0.15))


def _remote_weight() -> float:
    return float(config.geo_tier_config()["remote_us"].get("weight", 0.05))


def _other_us_multiplier() -> float:
    """Absolute value of the configured weight; -0.5 → 0.5 multiplier."""
    w = float(config.geo_tier_config()["other_us"].get("weight", -0.5))
    return abs(w)


# ─────────────────────────────────────────────────────────────────────────
# Public surface
# ─────────────────────────────────────────────────────────────────────────


def geo_tier(location: Optional[str]) -> Tuple[str, float]:
    """Return (tier_label, additive_boost).

    Order of checks:
      1. User's boost patterns (most specific)
      2. Explicit remote-US tokens (from config + bare "remote"/"anywhere")
      3. US state detection (overrides foreign — protects "London, KY")
      4. Foreign country tokens (builtin + user extras)
      5. Default: other_us
    """
    if not location:
        return "unknown", 0.0
    low = location.lower().strip()

    for token in _user_boost_patterns():
        if token in low:
            return "boost", _boost_weight()

    for token in _user_remote_patterns():
        if token in low:
            return "remote_us", _remote_weight()
    if low == "remote" or low == "anywhere" or "work from home" in low:
        return "remote_us", _remote_weight()

    if _is_us_location(low):
        return "other_us", 0.0

    foreign_tokens = FOREIGN_TOKENS_BUILTIN + _foreign_extra_patterns()
    for token in foreign_tokens:
        if token in low:
            return "foreign", 0.0

    return "other_us", 0.0


def apply_geo_boost(score: float, notes: str, location: Optional[str]) -> Tuple[float, str]:
    """Apply geographic adjustments to a non-zero keyword score.

    boost     → score + boost_weight (clamped at 1.0)
    remote_us → score + remote_weight (clamped at 1.0)
    other_us  → score × other_us_multiplier (soft demote)
    foreign   → score = 0 (hard filter)
    unknown   → unchanged
    """
    if score <= 0:
        return score, notes

    tier, boost = geo_tier(location)

    if tier == "foreign":
        suffix = "geo:foreign"
        return 0.0, f"{notes} | {suffix}" if notes and notes != "no_keyword_hits" else suffix

    if tier == "other_us":
        mult = _other_us_multiplier()
        new_score = round(score * mult, 4)
        suffix = f"geo:other_us*{mult}"
        return new_score, f"{notes} | {suffix}" if notes and notes != "no_keyword_hits" else suffix

    if tier == "unknown":
        return score, f"{notes} | geo:unknown" if notes and notes != "no_keyword_hits" else "geo:unknown"

    new_score = round(min(score + boost, 1.0), 4)
    suffix = f"geo:{tier}+{boost:.2f}"
    return new_score, f"{notes} | {suffix}" if notes and notes != "no_keyword_hits" else suffix
