"""Config loader — single source of truth for user-specific values.

Every module that needs to know "what's the user's short name" or "what
keyword weights matter" reads through here. The actual values live in
YAML files under config/.

Lookup order:
    config/<name>.yaml         (personal — gitignored, created by wizard)
    config/<name>.example.yaml (template — committed, fallback)

This dual-file pattern means the project runs end-to-end before the
wizard is ever run (using the example values), which is useful for
CI smoke tests and development. Real users always overwrite via wizard.

All loads are cached. Call config.reload() after writing to the YAML
files (the wizard does this when it commits).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


def _load(name: str) -> dict:
    """Load config/<name>.yaml, falling back to .example.yaml."""
    personal = CONFIG_DIR / f"{name}.yaml"
    example = CONFIG_DIR / f"{name}.example.yaml"
    path = personal if personal.exists() else example
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def profile() -> dict:
    """User identity + dashboard customization (config/profile.yaml)."""
    return _load("profile")


@lru_cache(maxsize=1)
def scoring() -> dict:
    """Scoring config — role filters, keyword weights, thresholds."""
    return _load("scoring")


@lru_cache(maxsize=1)
def geo_patterns() -> dict:
    """Geographic boost/demote tiers."""
    return _load("geo_patterns")


def reload() -> None:
    """Clear cache. Call after the wizard writes new YAML files."""
    profile.cache_clear()
    scoring.cache_clear()
    geo_patterns.cache_clear()


# ─────────────────────────────────────────────────────────────────────────
# Convenience accessors — the bits scripts reach for over and over. Reading
# these by name beats deeply-nested dict lookups + provides sensible
# fallbacks when a key is missing.
# ─────────────────────────────────────────────────────────────────────────


def short_name() -> str:
    """Dashboard greeting name (e.g. "good morning, {short_name}")."""
    return _path("profile", "user", "short_name", default="You")


def full_name() -> str:
    return _path("profile", "user", "full_name", default="Your Name")


def email() -> str:
    return _path("profile", "user", "email", default="")


def location_anchor() -> str:
    return _path("profile", "location", "anchor", default="")


def mascot_name() -> str:
    return _path("profile", "dashboard", "mascot", "name", default="Pip")


def mascot_species() -> str:
    return _path("profile", "dashboard", "mascot", "species", default="capybara")


def weekly_goal() -> int:
    return _path("profile", "dashboard", "weekly_goal", default=15)


def theme_id() -> str:
    """Return the user's chosen theme key. Falls back to 'paper'
    (the safe default — no personality imposed)."""
    return _path("profile", "dashboard", "theme", default="paper")


def mascot_enabled() -> bool:
    """Whether the theme's mascot should be shown. Only relevant for
    themes that have a mascot at all (Garden, Tide, Dusk)."""
    val = _path("profile", "dashboard", "mascot_enabled", default=True)
    return bool(val)


def supporter_name() -> str:
    """Name of someone who supports the user. Surfaces as a love note
    on the dashboard. Empty string disables the note silently."""
    return _path("profile", "dashboard", "supporter_name", default="") or ""


def show_love_note() -> bool:
    """Master toggle for the love-note pill. Independent of
    supporter_name so the name can stay saved even when hidden."""
    val = _path("profile", "dashboard", "show_love_note", default=True)
    return bool(val)


def footer_text() -> str:
    raw = _path("profile", "dashboard", "footer_text",
                default="made with care · for {short_name}")
    return raw.replace("{short_name}", short_name())


def tailored_watch_dir() -> str:
    """Where to scan for tailored resume/cover-letter files (~ expanded)."""
    raw = _path("profile", "tailored_files", "watch_dir", default="~/Downloads")
    return str(Path(raw).expanduser())


def tailored_marker() -> str:
    """Filename substring that marks a file as tailored output."""
    raw = _path("profile", "tailored_files", "marker", default="_tailored_")
    slug = short_name().lower().replace(" ", "")
    return raw.replace("{short_name_slug}", slug)


def score_thresholds() -> dict[str, float]:
    """Strong / Good / Medium boundaries (0-1 scale)."""
    raw = scoring().get("thresholds", {}) or {}
    return {
        "strong": float(raw.get("strong", 0.75)),
        "good":   float(raw.get("good",   0.50)),
        "medium": float(raw.get("medium", 0.20)),
    }


def role_blacklist() -> list[str]:
    return [s for s in (scoring().get("role_blacklist") or []) if s]


def role_whitelist() -> list[str]:
    return [s for s in (scoring().get("role_whitelist") or []) if s]


def keyword_groups() -> dict[str, dict]:
    """Returns {group_name: {weight: float, keywords: [str, ...]}}."""
    raw = scoring().get("keyword_groups") or {}
    out = {}
    for name, group in raw.items():
        if not isinstance(group, dict):
            continue
        out[name] = {
            "weight": float(group.get("weight", 1.0)),
            "keywords": [k for k in (group.get("keywords") or []) if k],
        }
    return out


def geo_tier_config() -> dict[str, dict]:
    """Returns the 4 tier configs (boost/remote_us/other_us/foreign)."""
    raw = geo_patterns()
    return {
        "boost":     raw.get("boost", {})     or {},
        "remote_us": raw.get("remote_us", {}) or {},
        "other_us":  raw.get("other_us", {})  or {},
        "foreign":   raw.get("foreign", {})   or {},
    }


# ─────────────────────────────────────────────────────────────────────────
# Internal
# ─────────────────────────────────────────────────────────────────────────


def _path(file: str, *keys: str, default: Any = None) -> Any:
    """Walk into a config dict by key path, returning default on any miss."""
    src = {"profile": profile(), "scoring": scoring(), "geo": geo_patterns()}[file]
    node: Any = src
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node if node is not None else default
