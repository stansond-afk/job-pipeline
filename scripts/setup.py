"""First-launch setup wizard.

Usage:
    python3 scripts/setup.py

Opens a multi-page wizard at http://localhost:5051. Walks a new user
through:
    1. Welcome
    2. Profile (name, email, location, mascot, weekly goal)
    3. Scoring (target role families + keyword groups)
    4. Geographic preferences
    5. Targets (curate the 248-company starter list)
    6. Cloudflare deploy (step-by-step checklist)
    7. GitHub Actions secrets
    8. Done

Writes to config/*.yaml (personal config — gitignored). Pre-fills from
config/*.example.yaml on first run. Re-runnable — safe to resume.

The wizard does NOT collect Cloudflare credentials directly. It guides
the user to create their own API token in the Cloudflare dashboard, then
asks them to paste it into .env. This keeps secrets out of the wizard's
process memory.
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml
from flask import Flask, redirect, request

from jobpipeline import config, themes

CONFIG_DIR = REPO_ROOT / "config"
WIZARD_PORT = 5051
TOTAL_STEPS = 8

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────────
# YAML helpers — load + save round-trips
# ─────────────────────────────────────────────────────────────────────────


def load_profile() -> dict:
    """Read config/profile.yaml if it exists; else the .example fallback."""
    return _load_yaml("profile")


def save_profile(data: dict) -> None:
    _save_yaml("profile", data)


def load_scoring() -> dict:
    return _load_yaml("scoring")


def save_scoring(data: dict) -> None:
    _save_yaml("scoring", data)


def load_geo() -> dict:
    return _load_yaml("geo_patterns")


def save_geo(data: dict) -> None:
    _save_yaml("geo_patterns", data)


def _load_yaml(name: str) -> dict:
    personal = CONFIG_DIR / f"{name}.yaml"
    example = CONFIG_DIR / f"{name}.example.yaml"
    path = personal if personal.exists() else example
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _save_yaml(name: str, data: dict) -> None:
    path = CONFIG_DIR / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    # Bust the jobpipeline.config cache so the next reader sees fresh values
    config.reload()


# ─────────────────────────────────────────────────────────────────────────
# Page chrome — single shared layout
# ─────────────────────────────────────────────────────────────────────────


CSS = """
:root {
  --cream: #FBF7EF; --paper: #FFFDF7; --ink: #2E2B3D; --sub: #6F6A82;
  --sky: #9CC3E8; --sky-dk: #5B8AB8; --lilac: #C9B8E0; --sun: #F4D87C;
  --coral: #F0A89C; --mint: #B9DBC4; --line: #E7DFCD;
  --shadow-card: 0 1px 0 rgba(255,255,255,0.7) inset, 0 8px 20px -16px rgba(80,60,30,0.15);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--cream); color: var(--ink);
  font-family: 'Nunito', system-ui, sans-serif; font-size: 14px;
  line-height: 1.5; padding: 32px 24px; max-width: 800px;
  margin: 0 auto; min-height: 100vh;
}
.wizard { display: flex; flex-direction: column; gap: 16px; }
.progress {
  font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
  color: var(--sub); text-transform: uppercase;
}
.progress-bar {
  display: flex; gap: 4px; margin-top: 8px;
}
.progress-bar .dot {
  flex: 1; height: 4px; background: var(--line); border-radius: 2px;
}
.progress-bar .dot.done { background: var(--sun); }
.progress-bar .dot.current { background: var(--sky-dk); }
.card {
  background: var(--paper); border-radius: 22px; padding: 32px;
  border: 1px solid var(--line); box-shadow: var(--shadow-card);
}
h1 {
  font-family: 'Fraunces', Georgia, serif; font-size: 28px;
  font-weight: 500; margin-bottom: 8px;
}
h2 {
  font-family: 'Fraunces', Georgia, serif; font-size: 18px;
  font-weight: 500; margin-top: 20px; margin-bottom: 8px;
}
.hand {
  font-family: 'Caveat', cursive; font-size: 22px; color: var(--sky-dk);
  line-height: 1.2; margin-bottom: 12px;
}
p { margin-bottom: 12px; }
small { color: var(--sub); font-size: 12px; }
label {
  display: block; font-size: 11px; font-weight: 700;
  letter-spacing: 0.5px; color: var(--sub);
  text-transform: uppercase; margin: 14px 0 4px;
}
input[type="text"], input[type="email"], input[type="number"],
textarea, select {
  width: 100%; padding: 9px 12px; border: 1px solid var(--line);
  border-radius: 10px; background: var(--cream); color: var(--ink);
  font-size: 13px; font-family: inherit; outline: none;
}
input:focus, textarea:focus, select:focus { border-color: var(--sky-dk); }
textarea { min-height: 90px; resize: vertical; font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
.checkbox-row { display: flex; align-items: center; gap: 8px; margin: 8px 0; }
.checkbox-row input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--sky-dk); }
.checkbox-row label { margin: 0; text-transform: none; letter-spacing: 0; font-weight: 400; color: var(--ink); font-size: 13px; }
.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.actions {
  display: flex; gap: 10px; align-items: center; justify-content: space-between;
  margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--line);
}
.btn {
  background: var(--ink); color: var(--cream); border: none;
  padding: 10px 22px; border-radius: 999px; font-weight: 700;
  font-size: 13px; cursor: pointer; text-decoration: none; display: inline-block;
}
.btn:hover { opacity: 0.9; }
.btn-back {
  background: transparent; color: var(--sub); border: 1px solid var(--line);
}
.btn-back:hover { color: var(--ink); border-color: var(--sky-dk); }
.help {
  background: var(--cream); border-left: 3px solid var(--sky); padding: 12px;
  margin: 12px 0; border-radius: 8px; font-size: 12px; color: var(--sub);
}
.help strong { color: var(--ink); }
ol li, ul li { margin: 6px 0 6px 20px; }
ol code, ul code, p code {
  background: var(--cream); padding: 1px 6px; border-radius: 4px;
  font-family: ui-monospace, Menlo, monospace; font-size: 12px;
}
"""


def page(title: str, body: str, step: int) -> str:
    """Wrap a step body with the standard wizard chrome."""
    dots = "".join(
        f'<div class="dot {"done" if i < step else ("current" if i == step else "")}"></div>'
        for i in range(1, TOTAL_STEPS + 1)
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{title} · setup</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@400;500;600&family=Nunito:wght@400;500;700;800&family=Caveat:wght@500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wizard">
  <div>
    <div class="progress">Step {step} of {TOTAL_STEPS}</div>
    <div class="progress-bar">{dots}</div>
  </div>
  <div class="card">{body}</div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────
# Step 1: Welcome
# ─────────────────────────────────────────────────────────────────────────


@app.route("/")
def welcome():
    body = """
<div class="hand">welcome.</div>
<h1>Let's set up your job pipeline.</h1>
<p>This wizard walks through the configuration in about 10 minutes. You'll need:</p>
<ul>
  <li>An email address you want to use for your job search.</li>
  <li>A general sense of the roles you're targeting.</li>
  <li><strong>Optional:</strong> a Cloudflare account if you want a private,
      phone-accessible dashboard (free; about 5 minutes to set up).</li>
  <li><strong>Optional:</strong> a free USAJobs API key for federal jobs
      (~2 minutes, instant approval).</li>
</ul>
<p>You can pause at any step — your answers save as you go. Re-running
this wizard just resumes where you left off.</p>
<div class="help">
  <strong>What gets written:</strong> personal YAML files in
  <code>config/</code>. They're already gitignored so they won't end up
  in your shared repo. Secrets go to <code>.env</code> (also gitignored).
</div>
<div class="actions">
  <span></span>
  <a class="btn" href="/profile">Get started →</a>
</div>
"""
    return page("Welcome", body, 1)


# ─────────────────────────────────────────────────────────────────────────
# Step 2: Profile
# ─────────────────────────────────────────────────────────────────────────


@app.route("/profile", methods=["GET", "POST"])
def profile_page():
    if request.method == "POST":
        data = load_profile()
        data.setdefault("user", {})
        data.setdefault("location", {})
        data.setdefault("dashboard", {})
        data.setdefault("tailored_files", {})

        data["user"]["full_name"] = request.form.get("full_name", "").strip()
        data["user"]["short_name"] = request.form.get("short_name", "").strip()
        data["user"]["email"] = request.form.get("email", "").strip()
        data["user"]["phone"] = request.form.get("phone", "").strip()
        data["user"]["context"] = request.form.get("context", "").strip()

        data["location"]["anchor"] = request.form.get("anchor", "").strip()
        data["location"]["remote_ok"] = "remote_ok" in request.form
        data["location"]["relocate_ok"] = "relocate_ok" in request.form
        data["location"]["international_ok"] = "international_ok" in request.form

        data["dashboard"].setdefault("mascot", {})
        data["dashboard"]["mascot"]["name"] = request.form.get("mascot_name", "Pip").strip() or "Pip"
        data["dashboard"]["mascot"]["species"] = "capybara"
        try:
            data["dashboard"]["weekly_goal"] = int(request.form.get("weekly_goal", "15"))
        except ValueError:
            data["dashboard"]["weekly_goal"] = 15
        data["dashboard"]["footer_text"] = "made with care · for {short_name}"

        # Sensible default for tailored_files
        data["tailored_files"].setdefault("watch_dir", "~/Downloads")
        data["tailored_files"].setdefault("marker", "_{short_name_slug}_")

        save_profile(data)
        return redirect("/theme")

    p = load_profile()
    u = p.get("user", {})
    loc = p.get("location", {})
    dash = p.get("dashboard", {})
    mascot = dash.get("mascot", {})

    body = f"""
<div class="hand">about you.</div>
<h1>Profile</h1>
<p>Used in your dashboard greeting and any cover letters generated downstream.</p>
<form method="post">
  <div class="row-2">
    <div>
      <label for="full_name">Full name</label>
      <input type="text" name="full_name" id="full_name"
             value="{_esc(u.get('full_name'))}" placeholder="Jane Doe" required>
      <small>Appears on tailored resume + cover letter.</small>
    </div>
    <div>
      <label for="short_name">Short name (dashboard greeting)</label>
      <input type="text" name="short_name" id="short_name"
             value="{_esc(u.get('short_name'))}" placeholder="Jane" required>
      <small>"good morning, &lt;short name&gt;"</small>
    </div>
  </div>

  <div class="row-2">
    <div>
      <label for="email">Email</label>
      <input type="email" name="email" id="email"
             value="{_esc(u.get('email'))}" placeholder="jane@example.com" required>
    </div>
    <div>
      <label for="phone">Phone (optional)</label>
      <input type="text" name="phone" id="phone" value="{_esc(u.get('phone'))}" placeholder="555-555-5555">
    </div>
  </div>

  <label for="anchor">Your location</label>
  <input type="text" name="anchor" id="anchor"
         value="{_esc(loc.get('anchor'))}" placeholder="Seattle, WA" required>
  <small>The metro area you want jobs in. Drives the location scoring boost.</small>

  <div class="checkbox-row">
    <input type="checkbox" name="remote_ok" id="remote_ok"
           {"checked" if loc.get("remote_ok", True) else ""}>
    <label for="remote_ok">Open to fully-remote roles in the US</label>
  </div>
  <div class="checkbox-row">
    <input type="checkbox" name="relocate_ok" id="relocate_ok"
           {"checked" if loc.get("relocate_ok") else ""}>
    <label for="relocate_ok">Open to relocating elsewhere in the US</label>
  </div>
  <div class="checkbox-row">
    <input type="checkbox" name="international_ok" id="international_ok"
           {"checked" if loc.get("international_ok") else ""}>
    <label for="international_ok">Open to international roles</label>
  </div>

  <h2>Your career context (optional)</h2>
  <textarea name="context" placeholder="career relaunch after a 6-year break; sustainability is the bullseye; data analyst / program coordinator also in scope">{_esc(u.get('context'))}</textarea>
  <small>Free-text — used by tailoring downstream. Skip if unsure.</small>

  <h2>Dashboard customization</h2>
  <div class="row-2">
    <div>
      <label for="mascot_name">Mascot name</label>
      <input type="text" name="mascot_name" id="mascot_name"
             value="{_esc(mascot.get('name', 'Pip'))}" placeholder="Pip">
      <small>A capybara appears at the top of your dashboard. Name it.</small>
    </div>
    <div>
      <label for="weekly_goal">Weekly application goal</label>
      <input type="number" name="weekly_goal" id="weekly_goal" min="1" max="50"
             value="{dash.get('weekly_goal', 15)}">
      <small>The ring on your dashboard fills toward this number.</small>
    </div>
  </div>

  <div class="actions">
    <a class="btn btn-back" href="/">← Back</a>
    <button class="btn" type="submit">Continue →</button>
  </div>
</form>
"""
    return page("Profile", body, 2)


# ─────────────────────────────────────────────────────────────────────────
# Step 3: Theme picker
# ─────────────────────────────────────────────────────────────────────────


@app.route("/theme", methods=["GET", "POST"])
def theme_page():
    if request.method == "POST":
        data = load_profile()
        data.setdefault("dashboard", {})

        # Validate the picked theme against the known list
        picked = (request.form.get("theme") or "paper").strip().lower()
        if not themes.is_valid_theme_id(picked):
            picked = "paper"
        data["dashboard"]["theme"] = picked
        data["dashboard"]["mascot_enabled"] = "mascot_enabled" in request.form
        data["dashboard"]["supporter_name"] = (
            request.form.get("supporter_name", "").strip()[:120]
        )
        data["dashboard"]["show_love_note"] = "show_love_note" in request.form

        # Also sync the legacy mascot.name field with whatever the chosen
        # theme uses, so anywhere in the codebase that still reads it gets
        # a sensible value. The theme's `mascotName` may be None for themes
        # without mascots (Paper, Quiet, Mountain); fall back gracefully.
        theme = themes.get_theme(picked)
        mascot_name = (theme.get("copy") or {}).get("mascotName") or "Pip"
        data["dashboard"].setdefault("mascot", {})
        data["dashboard"]["mascot"]["name"] = mascot_name

        save_profile(data)
        return redirect("/scoring")

    p = load_profile()
    dash = p.get("dashboard", {})
    current = dash.get("theme") or "paper"
    mascot_on = dash.get("mascot_enabled", True)
    supporter = dash.get("supporter_name") or ""
    love_on = dash.get("show_love_note", True)

    cards_html = ""
    for tid in themes.list_theme_ids():
        t = themes.get_theme(tid)
        toks = t["tokens"]
        is_current = (tid == current)
        # 5-color swatch preview from the theme's tokens
        swatch_colors = [toks["--bg"], toks["--paper"], toks["--a1"],
                         toks["--sun"], toks["--warm"]]
        swatch_html = "".join(
            f'<span class="swatch-dot" style="background:{c};"></span>'
            for c in swatch_colors
        )
        mascot_label = t["mascot"].capitalize() if t["mascot"] else "no mascot"
        cards_html += f"""
<label class="theme-card{' theme-card-selected' if is_current else ''}"
       style="background: {toks['--paper']}; border-color: {toks['--line']};">
  <input type="radio" name="theme" value="{tid}"{' checked' if is_current else ''}
         style="position:absolute; opacity:0; pointer-events:none;">
  <div class="theme-card-header" style="color: {toks['--ink']};">
    <strong>{_esc(t['name'])}</strong>
    <span class="theme-card-mascot" style="color: {toks['--sub']};">{_esc(mascot_label)}</span>
  </div>
  <div class="theme-card-tagline" style="color: {toks['--sub']};">{_esc(t['tagline'])}</div>
  <div class="theme-card-swatch">{swatch_html}</div>
  <div class="theme-card-blurb" style="color: {toks['--ink']};">{_esc(t['blurb'])}</div>
</label>"""

    extra_css = """
<style>
  .theme-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    margin: 8px 0 4px;
  }
  @media (max-width: 600px) { .theme-grid { grid-template-columns: 1fr; } }
  .theme-card {
    border: 1px solid var(--line); border-radius: 14px; padding: 14px;
    cursor: pointer; display: flex; flex-direction: column; gap: 8px;
    position: relative; transition: transform 0.1s, box-shadow 0.15s;
  }
  .theme-card:hover { transform: translateY(-1px); box-shadow: 0 4px 12px -6px rgba(0,0,0,0.15); }
  .theme-card-selected {
    box-shadow: 0 0 0 2px var(--sky-dk), 0 4px 12px -6px rgba(0,0,0,0.15);
  }
  .theme-card-header {
    display: flex; justify-content: space-between; align-items: baseline;
    font-size: 16px;
  }
  .theme-card-mascot { font-size: 11px; font-weight: 400; }
  .theme-card-tagline {
    font-size: 11px; letter-spacing: 0.4px; text-transform: lowercase;
  }
  .theme-card-swatch { display: flex; gap: 4px; }
  .swatch-dot {
    width: 18px; height: 18px; border-radius: 50%;
    box-shadow: 0 0 0 1px rgba(0,0,0,0.08) inset;
  }
  .theme-card-blurb { font-size: 12px; line-height: 1.4; opacity: 0.85; }
</style>
"""

    body = f"""
{extra_css}
<div class="hand">how should it feel?</div>
<h1>Pick a theme</h1>
<p>The dashboard ships with six visual identities. Mechanics are
identical — only the look, mascot, and tone of the affirmation copy
change. Click any card to pick it. You can change this anytime later
in <code>config/profile.yaml</code>.</p>
<div class="help">
  <strong>Default is Paper</strong> — minimal, no mascot, no script
  font. Pick it if you want a clean tool with zero flourish. Garden
  (warm, capybara) was the original direction. Quiet Focus and Mountain
  are gender-neutral / professional. Tide is calm coastal. Dusk is the
  only dark theme.
</div>

<form method="post">
  <div class="theme-grid">{cards_html}</div>

  <h2 style="margin-top: 24px;">Extras</h2>

  <div class="checkbox-row">
    <input type="checkbox" name="mascot_enabled" id="mascot_enabled"
           {"checked" if mascot_on else ""}>
    <label for="mascot_enabled">
      Show the theme's mascot when it has one (Garden, Tide, Dusk).
      Uncheck for a monogram avatar instead.
    </label>
  </div>

  <h2 style="margin-top: 16px;">Someone who believes in you (optional)</h2>
  <p style="font-size: 12px; color: var(--sub);">
    Job searches make people forget they are loved. If you enter a name,
    the dashboard will surface a small dismissible note —
    "{{name}} thinks you're the best thing in the world." Cheesy on purpose;
    leave blank to silently disable.
  </p>
  <label for="supporter_name">Supporter name (optional)</label>
  <input type="text" name="supporter_name" id="supporter_name"
         value="{_esc(supporter)}" placeholder="e.g. Mara · my mom · my partner">

  <div class="checkbox-row" style="margin-top: 8px;">
    <input type="checkbox" name="show_love_note" id="show_love_note"
           {"checked" if love_on else ""}>
    <label for="show_love_note">
      Show the love note when supporter is set. Uncheck to keep the
      name saved but hide the pill.
    </label>
  </div>

  <div class="actions">
    <a class="btn btn-back" href="/profile">← Back</a>
    <button class="btn" type="submit">Continue →</button>
  </div>
</form>
"""
    return page("Theme", body, 3)


# ─────────────────────────────────────────────────────────────────────────
# Step 4: Scoring
# ─────────────────────────────────────────────────────────────────────────


@app.route("/scoring", methods=["GET", "POST"])
def scoring_page():
    if request.method == "POST":
        data = load_scoring()
        data["thresholds"] = {
            "strong": float(request.form.get("strong_thresh", 0.75)),
            "good":   float(request.form.get("good_thresh",   0.50)),
            "medium": float(request.form.get("medium_thresh", 0.20)),
        }
        data["role_whitelist"] = [
            line.strip() for line in (request.form.get("whitelist", "") or "").splitlines()
            if line.strip()
        ]
        data["role_blacklist"] = [
            line.strip() for line in (request.form.get("blacklist", "") or "").splitlines()
            if line.strip()
        ]
        # Keyword groups — one per group; user enters CSV of keywords + weight
        groups: dict = {}
        for i in range(5):  # up to 5 groups, named domain_1..5 if left default
            name = (request.form.get(f"kw_name_{i}") or "").strip()
            weight = request.form.get(f"kw_weight_{i}") or ""
            kws = request.form.get(f"kw_words_{i}") or ""
            if not (name and weight and kws.strip()):
                continue
            try:
                w = float(weight)
            except ValueError:
                continue
            words = [k.strip() for k in kws.replace("\n", ",").split(",") if k.strip()]
            if words:
                groups[name] = {"weight": w, "keywords": words}
        if groups:
            data["keyword_groups"] = groups
        save_scoring(data)
        return redirect("/geo")

    s = load_scoring()
    thresh = s.get("thresholds", {})
    whitelist = "\n".join(s.get("role_whitelist") or [])
    blacklist = "\n".join(s.get("role_blacklist") or [])
    groups = list((s.get("keyword_groups") or {}).items())
    # Pad to at least 3 visible rows
    while len(groups) < 3:
        groups.append((f"domain_{len(groups)+1}", {"weight": 2.0, "keywords": []}))

    group_html = ""
    for i, (name, group) in enumerate(groups[:5]):
        weight = group.get("weight", 1.0)
        words = ", ".join(group.get("keywords") or [])
        group_html += f"""
<div class="row-2" style="margin-top:12px">
  <div>
    <label>Group {i+1} name</label>
    <input type="text" name="kw_name_{i}" value="{_esc(name)}" placeholder="domain_core">
  </div>
  <div>
    <label>Weight</label>
    <input type="number" step="0.5" name="kw_weight_{i}" value="{weight}" min="0">
  </div>
</div>
<label>Keywords (comma-separated)</label>
<textarea name="kw_words_{i}" placeholder="sustainability, ESG, climate">{_esc(words)}</textarea>
"""

    body = f"""
<div class="hand">what catches your eye?</div>
<h1>Scoring</h1>
<p>This controls which postings bubble to the top of your dashboard.</p>
<div class="help">
  Each posting starts at <strong>0</strong>. We add the weight of every keyword
  group whose words appear in the role title or job description. Postings whose
  titles match your role blacklist get filtered out entirely (score = 0).
</div>

<form method="post">
  <h2>Role filters</h2>
  <label>Role whitelist (one per line)</label>
  <textarea name="whitelist" placeholder="analyst&#10;coordinator&#10;specialist">{_esc(whitelist)}</textarea>
  <small>A posting whose title matches any of these substrings passes the filter.
    Case-insensitive. Use simple substrings (not regex).</small>

  <label>Role blacklist (one per line)</label>
  <textarea name="blacklist" placeholder="(TS/SCI)&#10;senior director&#10;registered nurse">{_esc(blacklist)}</textarea>
  <small>Postings matching any of these are filtered out (score = 0).
    Common entries: clearance markers, levels too senior/junior, functions outside your target.</small>

  <h2>Keyword groups</h2>
  <p>Each group adds its weight to a posting if any of its words appear in the
     role title or JD text. Higher weight = stronger signal.</p>
  {group_html}

  <h2>Score tier thresholds (advanced)</h2>
  <div class="row-2">
    <div>
      <label>Strong fit ≥</label>
      <input type="number" step="0.05" min="0" max="1" name="strong_thresh" value="{thresh.get('strong', 0.75)}">
    </div>
    <div>
      <label>Good fit ≥</label>
      <input type="number" step="0.05" min="0" max="1" name="good_thresh" value="{thresh.get('good', 0.50)}">
    </div>
  </div>
  <label>Medium fit ≥</label>
  <input type="number" step="0.05" min="0" max="1" name="medium_thresh" value="{thresh.get('medium', 0.20)}">
  <small>The four tier boundaries on the dashboard. Defaults usually work fine.</small>

  <div class="actions">
    <a class="btn btn-back" href="/profile">← Back</a>
    <button class="btn" type="submit">Continue →</button>
  </div>
</form>
"""
    return page("Scoring", body, 4)


# ─────────────────────────────────────────────────────────────────────────
# Step 4: Geographic preferences
# ─────────────────────────────────────────────────────────────────────────


@app.route("/geo", methods=["GET", "POST"])
def geo_page():
    if request.method == "POST":
        data = load_geo()
        # Boost: user pastes one pattern per line
        boost_patterns = [
            l.strip().lower() for l in (request.form.get("boost_patterns", "") or "").splitlines()
            if l.strip()
        ]
        data["boost"] = {
            "weight": float(request.form.get("boost_weight", 0.15)),
            "description": "Your target metro",
            "patterns": boost_patterns,
        }
        data["remote_us"] = {
            "weight": float(request.form.get("remote_weight", 0.05)),
            "description": "Remote-US — counts as workable",
            "patterns": ["remote", "remote - us", "remote, us", "remote (us)", "anywhere"],
        }
        data["other_us"] = {
            "weight": float(request.form.get("other_us_weight", -0.5)),
            "description": "Anywhere else in the US — demoted but visible",
        }
        data["foreign"] = {
            "weight": -1.0,
            "description": "Outside the US — filtered out",
            "extra_patterns": [],
        }
        save_geo(data)
        return redirect("/targets")

    g = load_geo()
    boost = g.get("boost", {})
    other = g.get("other_us", {})
    boost_patterns_text = "\n".join(boost.get("patterns") or [])

    # If the user filled in profile.location.anchor, suggest patterns based on it
    anchor = config.location_anchor()
    suggestion = ""
    if anchor and not boost_patterns_text:
        # Naive: just use the anchor itself + a lowercase variant
        suggestion = anchor.lower() + "\n" + anchor.replace(",", "").lower()

    body = f"""
<div class="hand">where, exactly?</div>
<h1>Geographic preferences</h1>
<p>The dashboard boosts postings in your target metro and demotes
postings in other US cities (they're still visible — just sorted lower).
Foreign postings are hard-filtered (score = 0) unless you opt in.</p>

<form method="post">
  <h2>Target metro patterns</h2>
  <label>Boost patterns (one per line, lowercase)</label>
  <textarea name="boost_patterns" placeholder="seattle, wa&#10;bellevue, wa&#10;redmond, wa">{_esc(boost_patterns_text or suggestion)}</textarea>
  <small>Any posting whose location contains one of these substrings gets a boost.
    Include common variations (with/without "wa", with/without comma, etc.). Case-insensitive.</small>

  <div class="row-2">
    <div>
      <label>Boost amount</label>
      <input type="number" step="0.05" name="boost_weight" value="{boost.get('weight', 0.15)}">
      <small>Added to score (0-1 scale). 0.15 is a strong signal.</small>
    </div>
    <div>
      <label>Remote-US boost</label>
      <input type="number" step="0.05" name="remote_weight" value="{g.get('remote_us', {}).get('weight', 0.05)}">
      <small>Smaller boost for "remote in US" postings.</small>
    </div>
  </div>

  <label>Other-US multiplier</label>
  <input type="number" step="0.1" name="other_us_weight" value="{other.get('weight', -0.5)}">
  <small>Negative number = demote. -0.5 means "score × 0.5" (other US cities
    visible but ranked lower).  Set to 0 if you want no penalty for other US locations.</small>

  <div class="help">
    Foreign postings are <strong>always hard-filtered</strong> (score = 0).
    If you're open to international roles, set <code>international_ok: true</code>
    in <code>config/profile.yaml</code> and we'll add a follow-up step in a
    future wizard version. For now, US postings only.
  </div>

  <div class="actions">
    <a class="btn btn-back" href="/scoring">← Back</a>
    <button class="btn" type="submit">Continue →</button>
  </div>
</form>
"""
    return page("Geographic preferences", body, 5)


# ─────────────────────────────────────────────────────────────────────────
# Step 5: Targets
# ─────────────────────────────────────────────────────────────────────────


@app.route("/targets", methods=["GET", "POST"])
def targets_page():
    targets_csv = CONFIG_DIR / "targets.csv"
    example_csv = CONFIG_DIR / "targets.example.csv"
    src = targets_csv if targets_csv.exists() else example_csv

    if request.method == "POST":
        action = request.form.get("action")
        if action == "use_example":
            # Copy the example file to the personal one
            if not targets_csv.exists():
                targets_csv.write_text(example_csv.read_text())
        elif action == "use_blank":
            targets_csv.write_text("company,category,priority,location,ats,ats_identifier,notes\n")
        return redirect("/cloudflare")

    # Show a preview of what's in the example file
    import csv as _csv
    preview = []
    if src.exists():
        with src.open() as f:
            reader = _csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 8:
                    break
                preview.append(row)

    preview_html = ""
    if preview:
        rows_html = "".join(
            f"<tr><td>{_esc(r.get('company',''))}</td><td>{_esc(r.get('ats',''))}</td>"
            f"<td>{_esc(r.get('location',''))}</td></tr>"
            for r in preview
        )
        preview_html = f"""
<table style="width:100%; border-collapse: collapse; margin: 12px 0; font-size: 12px;">
  <thead>
    <tr style="border-bottom: 1px solid var(--line); text-align: left;">
      <th style="padding: 6px;">Company</th>
      <th style="padding: 6px;">ATS</th>
      <th style="padding: 6px;">Location</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
<small>… and 240 more.</small>
"""

    body = f"""
<div class="hand">where to look?</div>
<h1>Target companies</h1>
<p>The Greenhouse / Lever / NEOGOV scrapers pull from a list of companies you
care about. We've included 248 companies as a starter list — mostly mid-to-large
employers across consulting, government, and nonprofits.</p>

<div class="help">
  Preview of the first 8 companies in the starter list:
  {preview_html}
  <p style="margin-top:8px"><strong>Note:</strong> the starter list skews toward the DC-area
    employers the original Solongo build cared about. You can curate it later —
    the wizard's "blank slate" option below is fine if you'd rather start fresh
    and add only what you care about via the dashboard's "+ Add Job" feature.</p>
</div>

<form method="post">
  <h2>Choose your starting point</h2>
  <p>Either option saves <code>config/targets.csv</code> — you can edit it any
     time after setup in any text editor or spreadsheet app.</p>

  <div class="actions" style="border-top: none; padding-top: 8px; margin-top: 8px; flex-direction: column; align-items: stretch; gap: 12px;">
    <button class="btn" type="submit" name="action" value="use_example"
            style="background: var(--sun); color: var(--ink);">
      Use the 248-company starter list →
    </button>
    <button class="btn" type="submit" name="action" value="use_blank"
            style="background: var(--lilac); color: var(--ink);">
      Start with a blank list (add via dashboard) →
    </button>
  </div>

  <div class="actions">
    <a class="btn btn-back" href="/geo">← Back</a>
    <span></span>
  </div>
</form>
"""
    return page("Target companies", body, 6)


# ─────────────────────────────────────────────────────────────────────────
# Step 6: Cloudflare deploy
# ─────────────────────────────────────────────────────────────────────────


@app.route("/cloudflare", methods=["GET", "POST"])
def cloudflare_page():
    if request.method == "POST":
        # We don't store secrets via the wizard. Just record whether the user
        # wants the deployed dashboard, so we know whether to prompt them again.
        return redirect("/github")

    body = """
<div class="hand">your private url.</div>
<h1>Deploy to Cloudflare (optional)</h1>
<p>This is the step that gives you a private URL like
<code>your-name-job-pipeline.workers.dev</code> that you can pull up on your phone
during the day. Protected by Cloudflare Access so only your email can get in.</p>

<p><strong>This is optional.</strong> If you skip it, the dashboard still works
perfectly on your laptop via <code>./launch.sh</code> — you just don't get the
phone access.</p>

<h2>The honest version</h2>
<p>The wizard <em>can't</em> automate the Cloudflare setup completely. You'll need to:</p>
<ol>
  <li>Create a free <a href="https://dash.cloudflare.com/sign-up" target="_blank">Cloudflare account</a> if you don't have one.</li>
  <li>Generate an API token (5 mins; we walk through this below).</li>
  <li>Run two commands to create the D1 database + deploy the Worker.</li>
  <li>Set up Cloudflare Access on the dashboard (1 minute, in their UI).</li>
</ol>
<p>Total: about 10 minutes once you've signed up.</p>

<h2>Step-by-step</h2>
<ol>
  <li><strong>Sign up at <a href="https://dash.cloudflare.com/sign-up" target="_blank">dash.cloudflare.com/sign-up</a></strong> if you haven't.</li>
  <li><strong>Create an API token:</strong> go to
    <a href="https://dash.cloudflare.com/profile/api-tokens" target="_blank">dash.cloudflare.com/profile/api-tokens</a>
    → "Create Token" → "Custom token". Permissions needed:
    <ul>
      <li>Account → D1 → Edit</li>
      <li>Account → Workers Scripts → Edit</li>
      <li>Account → Workers Routes → Edit</li>
    </ul>
    Click "Continue to summary" → "Create Token". Copy the token (you'll only see it once).
  </li>
  <li><strong>Find your account ID:</strong> open any page in the Cloudflare dashboard;
      it's in the right sidebar.
  </li>
  <li><strong>Open <code>.env</code> in your code editor</strong> (in the repo root).
      Paste the token + account ID into the appropriate lines:
      <ul>
        <li><code>CLOUDFLARE_API_TOKEN=&lt;paste here&gt;</code></li>
        <li><code>CLOUDFLARE_ACCOUNT_ID=&lt;paste here&gt;</code></li>
      </ul>
  </li>
  <li><strong>Create the D1 database</strong> by running this in your terminal
      (from the repo root):
    <pre style="background: var(--cream); padding: 10px; border-radius: 8px; font-size: 12px; margin: 8px 0;">npx wrangler d1 create job-pipeline-events</pre>
      It'll print a UUID — copy that into <code>.env</code> as <code>D1_DATABASE_ID</code>.
  </li>
  <li><strong>Set up Cloudflare Access</strong>:
    <ul>
      <li>Go to <a href="https://one.dash.cloudflare.com" target="_blank">one.dash.cloudflare.com</a> (Zero Trust).</li>
      <li>Set up your team (one-time; pick any subdomain).</li>
      <li>Access → Applications → Add an application → Self-hosted.</li>
      <li>Subdomain: <code>job-pipeline</code> (or whatever WORKER_NAME you chose).</li>
      <li>Policy: Allow → Emails → your email.</li>
      <li>After saving, copy the "Application Audience (AUD) tag" from the application's
          settings page into <code>.env</code> as <code>ACCESS_AUD</code>.
          Also note your team domain (e.g. <code>your-team.cloudflareaccess.com</code>)
          and put it in <code>ACCESS_TEAM_DOMAIN</code>.
      </li>
    </ul>
  </li>
  <li><strong>Generate <code>wrangler.jsonc</code> + deploy:</strong>
    <pre style="background: var(--cream); padding: 10px; border-radius: 8px; font-size: 12px; margin: 8px 0;">bash scripts/build_wrangler.sh
npx wrangler deploy</pre>
  </li>
</ol>

<div class="help">
  <strong>Stuck?</strong> Skip this step for now. You can come back via
  <code>python3 scripts/setup.py</code> and pick it up later. The local
  dashboard works without Cloudflare.
</div>

<form method="post">
  <div class="actions">
    <a class="btn btn-back" href="/targets">← Back</a>
    <button class="btn" type="submit">Continue (I'll do Cloudflare later or already did it) →</button>
  </div>
</form>
"""
    return page("Cloudflare deploy", body, 7)


# ─────────────────────────────────────────────────────────────────────────
# Step 7: Done
# ─────────────────────────────────────────────────────────────────────────


@app.route("/github", methods=["GET", "POST"])
def github_page():
    if request.method == "POST":
        return redirect("/done")
    body = """
<div class="hand">last bit.</div>
<h1>GitHub Actions (optional)</h1>
<p>If you push this repo to GitHub, Actions will run the scrapers M/W/F on
a cron schedule. You don't have to leave your laptop on. This requires the
same secrets you set up in <code>.env</code>, copied to your GitHub repo:</p>

<ol>
  <li>Push your repo: <code>git remote add origin https://github.com/&lt;your-username&gt;/job-pipeline.git && git push -u origin main</code></li>
  <li>Go to your repo on GitHub → Settings → Secrets and variables → Actions.</li>
  <li>Add these "Repository secrets" (same values as your <code>.env</code>):
    <ul>
      <li><code>CLOUDFLARE_API_TOKEN</code></li>
      <li><code>CLOUDFLARE_ACCOUNT_ID</code></li>
      <li><code>D1_DATABASE_ID</code></li>
      <li><code>ACCESS_AUD</code></li>
      <li><code>USAJOBS_API_KEY</code> (if using)</li>
      <li><code>USAJOBS_USER_AGENT</code> (if using; this is your email)</li>
    </ul>
  </li>
  <li>The workflow runs automatically on the next M/W/F at 7 AM UTC. You can
      also trigger it manually from the Actions tab.</li>
</ol>

<form method="post">
  <div class="actions">
    <a class="btn btn-back" href="/cloudflare">← Back</a>
    <button class="btn" type="submit">All done →</button>
  </div>
</form>
"""
    return page("GitHub Actions", body, 8)


@app.route("/done")
def done_page():
    name = config.short_name() or "you"
    body = f"""
<div class="hand">all set, {_esc(name)}.</div>
<h1>Setup complete.</h1>
<p>Here's what to do next:</p>
<ol>
  <li>Close this window.</li>
  <li>Run your first scrape:
    <pre style="background: var(--cream); padding: 10px; border-radius: 8px; font-size: 12px; margin: 8px 0;">python3 scripts/init_db.py
for m in db/migrate_*.py; do python3 "$m"; done
python3 scripts/scrape_greenhouse.py
python3 scripts/scrape_lever.py
python3 scripts/scrape_neogov.py
python3 scripts/scrape_jobspy.py  # slow (~10 min first time)
python3 scripts/score_postings.py
python3 scripts/generate_dashboard.py
open dashboard/index.html</pre>
  </li>
  <li>Open the dashboard. Mark some jobs Interested / Very interested.</li>
  <li>Tomorrow: open it again. The workflow is running for you in the background.</li>
</ol>
<p>If something looks off, the config files in <code>config/</code> are plain
   YAML — open in any text editor to tweak. Re-run <code>python3 scripts/setup.py</code>
   any time to revisit a step.</p>

<div class="help">
  <strong>Daily-use tips:</strong>
  <ul style="margin-top: 4px">
    <li>The dashboard auto-refreshes every M/W/F if you set up GitHub Actions.</li>
    <li>"+ Add Job" lets you paste a URL or JD text for any job your scrapers missed.</li>
    <li>Click "Tailor →" on a row to open a Claude chat pre-filled with the JD.</li>
    <li>Click "Apply" after submitting; the modal logs your application + the JD snapshot.</li>
  </ul>
</div>

<p style="margin-top: 24px; text-align: center; font-family: 'Caveat', cursive; font-size: 22px; color: var(--lilac-dk);">
  good luck out there.
</p>
"""
    return page("Done", body, 8)


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────


def _esc(s) -> str:
    """HTML-escape a value for safe insertion into the templates."""
    import html as _html
    return _html.escape(str(s) if s is not None else "")


# ─────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────


def main() -> None:
    url = f"http://localhost:{WIZARD_PORT}/"
    print(f"\n  🌱  Setup wizard starting at {url}")
    print(f"  Your config will be saved to {CONFIG_DIR}/\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    # Use debug=False so we don't double-launch the browser on the reloader
    app.run(host="127.0.0.1", port=WIZARD_PORT, debug=False)


if __name__ == "__main__":
    main()
