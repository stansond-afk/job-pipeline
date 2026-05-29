"""Mascot + decoration SVG renderers — one per theme.

Python port of handoff/code/mascots.jsx. Each renderer returns an
inline SVG (or HTML) string. The dashboard generator picks the right
one via theme["mascot"] / theme["decoration"] keys + the registries
at the bottom.

To add a mascot: write a `*_svg(size)` function, register it in
MASCOT_RENDERERS, reference `mascot: "yourkey"` in jobpipeline.themes.

Internal colors in the mascot SVGs are intentionally fixed — the
animal looks the same across themes (a capybara is a capybara), only
the surrounding chrome shifts. Decorations DO consume theme tokens
via `var(--ink)` / `var(--sun)` etc. so the skybox harmonises with
each theme automatically.
"""

from __future__ import annotations

import random


# ─────────────────────────────────────────────────────────────────────────
# Mascots
# ─────────────────────────────────────────────────────────────────────────


def capybara_svg(size: int = 62, mood: str = "happy") -> str:
    """Garden mascot (Pip). Drawn from ellipses + circles. `mood` ∈ {happy, sleepy}."""
    eye_y = 56 if mood == "sleepy" else 54
    eye_h = 1 if mood == "sleepy" else 4
    highlights = ""
    if mood != "sleepy":
        highlights = (
            '<circle cx="49" cy="53" r="1" fill="#fff"/>'
            '<circle cx="73" cy="53" r="1" fill="#fff"/>'
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


def otter_svg(size: int = 62) -> str:
    """Tide mascot (Marlow). Floating river otter."""
    return (
        f'<svg viewBox="0 0 130 110" width="{size}" height="{int(size * 110 / 130)}" '
        f'aria-hidden="true">'
        '<ellipse cx="65" cy="96" rx="50" ry="6" fill="#87B4C9" opacity=".4"/>'
        '<ellipse cx="65" cy="100" rx="44" ry="3" fill="#87B4C9" opacity=".3"/>'
        '<ellipse cx="65" cy="76" rx="48" ry="20" fill="#8B6849"/>'
        '<ellipse cx="65" cy="78" rx="36" ry="12" fill="#D4A87A"/>'
        '<circle cx="98" cy="64" r="18" fill="#8B6849"/>'
        '<ellipse cx="108" cy="68" rx="10" ry="7" fill="#D4A87A"/>'
        '<circle cx="96" cy="60" r="2" fill="#2A2A3A"/>'
        '<circle cx="104" cy="60" r="2" fill="#2A2A3A"/>'
        '<circle cx="96.7" cy="59.3" r="0.6" fill="#fff"/>'
        '<circle cx="104.7" cy="59.3" r="0.6" fill="#fff"/>'
        '<ellipse cx="113" cy="66" rx="2" ry="1.5" fill="#2A2A3A"/>'
        '<path d="M111 70 L 118 71 M 111 72 L 118 74" stroke="#2A2A3A" '
        'stroke-width="0.6" opacity=".6"/>'
        '<path d="M108 71 Q 111 73 113 71" fill="none" stroke="#2A2A3A" '
        'stroke-width="0.9" stroke-linecap="round"/>'
        '<ellipse cx="55" cy="68" rx="7" ry="5" fill="#8B6849"/>'
        '<ellipse cx="68" cy="66" rx="7" ry="5" fill="#8B6849"/>'
        '<ellipse cx="55" cy="68" rx="4" ry="2.5" fill="#5E3F2A" opacity=".5"/>'
        '<ellipse cx="68" cy="66" rx="4" ry="2.5" fill="#5E3F2A" opacity=".5"/>'
        '<ellipse cx="20" cy="74" rx="10" ry="4" fill="#8B6849"/>'
        '<circle cx="62" cy="80" r="3" fill="#E89B8E"/>'
        '<path d="M60 80 L 64 80 M 62 78 L 62 82" stroke="#fff" '
        'stroke-width="0.6" opacity=".7"/>'
        '</svg>'
    )


def moth_svg(size: int = 62) -> str:
    """Dusk mascot (Vesper). Luna-moth-ish, glowing."""
    return (
        f'<svg viewBox="0 0 120 120" width="{size}" height="{size}" '
        f'aria-hidden="true">'
        '<circle cx="60" cy="60" r="50" fill="#A684C9" opacity=".15"/>'
        '<circle cx="60" cy="60" r="38" fill="#E8B86C" opacity=".1"/>'
        '<path d="M60 56 Q 22 30 14 58 Q 22 74 60 64 Z" fill="#A8D4A8"/>'
        '<path d="M60 56 Q 98 30 106 58 Q 98 74 60 64 Z" fill="#A8D4A8"/>'
        '<path d="M60 64 Q 30 80 20 108 Q 38 96 60 76 Z" fill="#9BC498"/>'
        '<path d="M60 64 Q 90 80 100 108 Q 82 96 60 76 Z" fill="#9BC498"/>'
        '<circle cx="34" cy="58" r="5" fill="#E8B86C"/>'
        '<circle cx="86" cy="58" r="5" fill="#E8B86C"/>'
        '<circle cx="34" cy="58" r="2.5" fill="#2A2336"/>'
        '<circle cx="86" cy="58" r="2.5" fill="#2A2336"/>'
        '<circle cx="34.8" cy="57.2" r="0.8" fill="#fff"/>'
        '<circle cx="86.8" cy="57.2" r="0.8" fill="#fff"/>'
        '<ellipse cx="60" cy="64" rx="4" ry="22" fill="#2A2336"/>'
        '<circle cx="60" cy="44" r="6" fill="#2A2336"/>'
        '<circle cx="57.5" cy="43" r="1.1" fill="#E8B86C"/>'
        '<circle cx="62.5" cy="43" r="1.1" fill="#E8B86C"/>'
        '<path d="M58 40 Q 50 30 46 26 M 62 40 Q 70 30 74 26" stroke="#2A2336" '
        'stroke-width="1.2" fill="none" stroke-linecap="round"/>'
        '<path d="M50 32 L 47 30 M 52 34 L 49 33 M 54 36 L 51 36 M 70 32 L 73 30 '
        'M 68 34 L 71 33 M 66 36 L 69 36" stroke="#2A2336" stroke-width="0.7" '
        'stroke-linecap="round" opacity=".8"/>'
        '</svg>'
    )


def monogram_svg(initials: str, size: int = 62) -> str:
    """Fallback when the theme has no mascot OR the user disabled it.

    Uses CSS vars (--paper, --line, --ink, --serif) so it harmonises
    with the active theme automatically.
    """
    initials = (initials or "J").strip()[:2].upper() or "J"
    font_size = round(size * 0.42)
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:var(--paper);border:1.5px solid var(--line);'
        f'display:grid;place-items:center;font-family:var(--serif);'
        f'font-size:{font_size}px;font-weight:500;color:var(--ink);'
        f'letter-spacing:-0.02em;">{_esc(initials)}</div>'
    )


MASCOT_RENDERERS = {
    "capybara": capybara_svg,
    "otter":    otter_svg,
    "moth":     moth_svg,
}


def mascot_or_monogram(theme: dict, mascot_enabled: bool, initials: str,
                       size: int = 62) -> str:
    """Pick the right avatar for the current theme + user prefs.

    Order:
      1. If the theme has a mascot key AND the user has mascot_enabled,
         render that mascot.
      2. Otherwise fall back to monogram with the user's initials.
    """
    key = theme.get("mascot")
    if key and mascot_enabled and key in MASCOT_RENDERERS:
        return MASCOT_RENDERERS[key](size=size)
    return monogram_svg(initials, size=size)


# ─────────────────────────────────────────────────────────────────────────
# Decorations — the "skybox" behind the greeting bar
# ─────────────────────────────────────────────────────────────────────────
#
# Each function returns an HTML string positioned with `position:absolute;
# inset:0` (or similar). They read theme colors via CSS vars so they
# harmonise with each theme automatically.


def deco_sun_clouds() -> str:
    """Garden — pastel sun + cloud pills behind the greeting."""
    return (
        '<div class="deco" aria-hidden="true">'
        '<div style="position:absolute;right:220px;top:-30px;width:90px;height:90px;'
        'border-radius:50%;background:var(--sun);opacity:0.7;"></div>'
        '<div style="position:absolute;right:210px;top:-20px;width:70px;height:70px;'
        'border-radius:50%;background:var(--sun);"></div>'
        '<div style="position:absolute;left:220px;top:18px;width:60px;height:16px;'
        'border-radius:20px;background:var(--paper);opacity:0.85;"></div>'
        '<div style="position:absolute;left:380px;top:40px;width:40px;height:12px;'
        'border-radius:20px;background:var(--paper);opacity:0.85;"></div>'
        '</div>'
    )


def deco_horizon() -> str:
    """Quiet Focus — three subtle horizon lines."""
    return (
        '<svg class="deco" viewBox="0 0 1200 200" preserveAspectRatio="none" '
        'style="position:absolute;inset:0;width:100%;height:100%;opacity:0.4;" '
        'aria-hidden="true">'
        '<line x1="0" y1="160" x2="1200" y2="160" stroke="var(--a1)" '
        'stroke-width="1" opacity="0.4"/>'
        '<line x1="0" y1="170" x2="1200" y2="170" stroke="var(--a1)" '
        'stroke-width="0.6" opacity="0.25"/>'
        '<line x1="0" y1="178" x2="1200" y2="178" stroke="var(--a1)" '
        'stroke-width="0.4" opacity="0.15"/>'
        '</svg>'
    )


def deco_waves() -> str:
    """Tide — soft sine waves + a sun."""
    return (
        '<svg class="deco" viewBox="0 0 1200 200" preserveAspectRatio="none" '
        'style="position:absolute;inset:0;width:100%;height:100%;" '
        'aria-hidden="true">'
        '<path d="M0 150 Q 150 130 300 150 T 600 150 T 900 150 T 1200 150 '
        'L 1200 200 L 0 200 Z" fill="var(--a2)" opacity="0.25"/>'
        '<path d="M0 170 Q 200 155 400 170 T 800 170 T 1200 170 L 1200 200 '
        'L 0 200 Z" fill="var(--a1)" opacity="0.2"/>'
        '<circle cx="1080" cy="50" r="40" fill="var(--sun)" opacity="0.5"/>'
        '</svg>'
    )


def deco_paper() -> str:
    """Paper — minimal top + bottom hairlines."""
    return (
        '<div class="deco" aria-hidden="true">'
        '<div style="position:absolute;left:0;top:0;right:0;height:1px;'
        'background:var(--line);"></div>'
        '<div style="position:absolute;left:0;bottom:0;right:0;height:1px;'
        'background:var(--line);"></div>'
        '</div>'
    )


def deco_stars() -> str:
    """Dusk — scattered dots + a crescent moon. Star positions are
    deterministic per render (seeded by date-of-year via the
    surrounding generator) so the page renders the same content for
    the same day."""
    # Use a deterministic seed so the same day produces the same stars,
    # but different days produce different patterns. Caller controls the
    # seed via Python's random module state.
    stars = []
    for _ in range(22):
        x = random.uniform(2, 98)
        y = random.uniform(2, 98)
        r = 0.6 + random.random() * 1.6
        o = 0.3 + random.random() * 0.6
        stars.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 0.18:.2f}" '
            f'fill="var(--ink)" opacity="{o:.2f}"/>'
        )
    return (
        '<svg class="deco" viewBox="0 0 100 100" preserveAspectRatio="none" '
        'style="position:absolute;inset:0;width:100%;height:100%;" '
        'aria-hidden="true">'
        + "".join(stars)
        + '<circle cx="92" cy="22" r="6" fill="var(--sun)" opacity="0.8"/>'
        + '<circle cx="88" cy="22" r="6" fill="var(--paper)"/>'
        + '</svg>'
    )


def deco_peak() -> str:
    """Mountain — alpine ridge silhouette + snow on the peak."""
    return (
        '<svg class="deco" viewBox="0 0 1200 200" preserveAspectRatio="none" '
        'style="position:absolute;inset:0;width:100%;height:100%;" '
        'aria-hidden="true">'
        '<path d="M0 180 L 280 70 L 460 150 L 720 30 L 940 130 L 1200 80 '
        'L 1200 200 L 0 200 Z" fill="var(--a1)" opacity="0.18"/>'
        '<path d="M0 180 L 280 70 L 460 150 L 720 30 L 940 130 L 1200 80" '
        'fill="none" stroke="var(--a1-dk)" stroke-width="1" opacity="0.4"/>'
        '<path d="M720 30 L 700 60 L 720 50 L 740 60 Z" fill="var(--paper)" '
        'opacity="0.6"/>'
        '</svg>'
    )


DECORATION_RENDERERS = {
    "sun-clouds": deco_sun_clouds,
    "horizon":    deco_horizon,
    "waves":      deco_waves,
    "paper":      deco_paper,
    "stars":      deco_stars,
    "peak":       deco_peak,
}


def render_decoration(theme: dict) -> str:
    """Render the theme's chosen skybox. Falls back to empty string for
    themes that don't name a decoration (defensive)."""
    key = theme.get("decoration")
    if key and key in DECORATION_RENDERERS:
        return DECORATION_RENDERERS[key]()
    return ""


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────


def _esc(s: str) -> str:
    """Minimal HTML escape for embedding text into the monogram SVG."""
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def initials_from_name(name: str) -> str:
    """Pick a 1-2 character monogram from a display name.

    Examples:
        'Solongo'                 → 'S'
        'Erdenesolongo Tsogbaatar' → 'ET'
        'Mara'                    → 'M'
        ''                        → 'J'  (Jobline default)
    """
    if not name or not name.strip():
        return "J"
    parts = [p for p in name.strip().split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper()
