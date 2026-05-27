# Integration Guide — Wiring 6 Themes into the Flask App

> **Scope:** how to take the existing single-theme `solongo-jobs` Flask app and ship the 6-theme system. Pure mechanical instructions; design decisions are settled elsewhere.

This guide assumes the repo layout from the previous handoff:
- `solongo_jobs/` — Flask app
- `solongo_jobs/persistence.py` — SQLite layer
- `dashboard/index.html` (or `templates/dashboard.html`) — the current dashboard template
- `scripts/generate_dashboard.py` — emits the static dashboard

If file names differ, adapt — the steps are the same.

---

## Step 1 · Schema changes (one migration)

Add 4 columns to `users` (create the table if it doesn't yet exist; previous handoff was single-user, so `users` may not exist):

```sql
-- migrations/0NN_user_prefs.sql
CREATE TABLE IF NOT EXISTS users (
  id              INTEGER PRIMARY KEY,
  display_name    TEXT,
  supporter_name  TEXT,
  theme           TEXT    NOT NULL DEFAULT 'paper',
  mascot_enabled  INTEGER NOT NULL DEFAULT 1,
  show_love_note  INTEGER NOT NULL DEFAULT 1,
  created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- if users already exists with display_name, just add columns:
-- ALTER TABLE users ADD COLUMN supporter_name TEXT;
-- ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'paper';
-- ALTER TABLE users ADD COLUMN mascot_enabled INTEGER NOT NULL DEFAULT 1;
-- ALTER TABLE users ADD COLUMN show_love_note INTEGER NOT NULL DEFAULT 1;
```

**Validation:** server-side, allow only known theme keys. Hardcode the list — don't let arbitrary strings into the DB.

```python
# solongo_jobs/prefs.py
THEMES = {'paper', 'garden', 'tide', 'quiet', 'mountain', 'dusk'}
def is_valid_theme(t: str) -> bool: return t in THEMES
```

---

## Step 2 · Two new endpoints

### `GET /api/prefs`

Returns the current user's prefs as JSON.

```python
@app.get('/api/prefs')
def get_prefs():
    u = current_user()  # however you resolve the user
    return jsonify({
        'theme':            u.theme or 'paper',
        'mascotEnabled':    bool(u.mascot_enabled),
        'name':             u.display_name or 'friend',
        'supporter':        u.supporter_name or '',
        'showPersonalNote': bool(u.show_love_note),
    })
```

### `POST /api/prefs`

Partial update — only keys provided are written. Used by both onboarding and the in-app theme switcher.

```python
@app.post('/api/prefs')
def set_prefs():
    body = request.json or {}
    u = current_user()
    if 'theme' in body:
        if not is_valid_theme(body['theme']):
            return ('invalid theme', 400)
        u.theme = body['theme']
    if 'mascotEnabled' in body:    u.mascot_enabled = bool(body['mascotEnabled'])
    if 'name' in body:              u.display_name = body['name'][:80]
    if 'supporter' in body:         u.supporter_name = body['supporter'][:120]
    if 'showPersonalNote' in body:  u.show_love_note = bool(body['showPersonalNote'])
    save_user(u)
    return ('', 204)
```

That's the entire backend surface for theming.

---

## Step 3 · Onboarding route

A first-run flow at `/onboard`. Two ways to ship:

### Option A — full page (recommended)

`GET /onboard` renders an onboarding HTML that's a thin shell around the `Onboarding` React component:

```html
<!-- templates/onboard.html -->
<!doctype html>
<html><head>...fonts and styles...</head>
<body><div id="root"></div>
<script src="/static/themes.js"></script>
<script type="text/babel" src="/static/mascots.jsx"></script>
<script type="text/babel" src="/static/onboarding.jsx"></script>
<script type="text/babel">
  ReactDOM.createRoot(document.getElementById('root')).render(
    <Onboarding initialPrefs={DEFAULT_PREFS} onComplete={async (p) => {
      await fetch('/api/prefs', { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify(p) });
      window.location.href = '/';
    }} />
  );
</script>
</body></html>
```

Redirect to `/onboard` from `/` whenever the user's `theme` column was never set explicitly — easiest signal: track a separate `onboarded_at` timestamp.

```python
@app.get('/')
def home():
    u = current_user()
    if not u.onboarded_at:
        return redirect('/onboard')
    return render_dashboard(u)
```

### Option B — modal on first dashboard load

If you'd rather not add a route, render the picker as a full-screen modal that the dashboard mounts on first load. Cleaner UX but slightly more code. Either is fine.

---

## Step 4 · Refactor the dashboard template

The existing `dashboard/index.html` is hardcoded for Garden colors. Replace its body's color literals with CSS vars, and set those vars on the root element from server-side template data.

### Before

```html
<style>
  body { background: #FBF7EF; color: #2E2B3D; font-family: 'Nunito', ...; }
  .card { background: #FFFDF7; border: 1px solid #E7DFCD; ... }
</style>
```

### After

```html
<!-- emit the theme's tokens straight into a root <style> block from Jinja -->
<style>
  {% for var, val in theme.tokens.items() %}{{ var }}: {{ val }};{% endfor %}
  body { background: var(--bg); color: var(--ink); font-family: var(--sans); }
  .card { background: var(--paper); border: 1px solid var(--line); ... }
</style>
```

Server-side, load `theme = THEMES[user.theme]` from a Python port of `themes.js`. **Don't try to import the JS file**; transcribe the 6 theme dicts into a Python module (or load `themes.json` produced by serialising the JS). The handoff `code/themes.js` is the source; mirror it.

### `themes.py` (Python mirror)

```python
# solongo_jobs/themes.py — mirror of handoff/code/themes.js
# Update both files together when changing tokens.

THEMES = {
  'paper': {
    'name': 'Paper',
    'mascot': None,
    'decoration': 'paper',
    'dark': False,
    'tokens': {
      '--bg':    '#F2EFE8',
      '--paper': '#FFFFFF',
      '--ink':   '#1A1A1A',
      # ...etc, exactly mirroring code/themes.js
    },
    'copy': {
      'greetingScript': 'Good morning,',
      # ...etc
    },
  },
  # ...the other 5 themes
}
```

If duplication feels brittle, expose a `GET /static/themes.json` endpoint that emits the canonical JSON and have both server and client read from it. For 6 themes the duplication is fine.

---

## Step 5 · Port `mascots.jsx` + `dashboard.jsx`

Drop these straight into `static/` (or `solongo_jobs/static/`) verbatim. They are React + Babel components; the existing app already uses inline JSX via `@babel/standalone` per the previous handoff.

Required script tags in the dashboard template (in this order):

```html
<script src="https://unpkg.com/react@18.3.1/..."></script>
<script src="https://unpkg.com/react-dom@18.3.1/..."></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/..."></script>

<script src="/static/themes.js"></script>
<script type="text/babel" src="/static/shared-data.jsx"></script>
<script type="text/babel" src="/static/mascots.jsx"></script>
<script type="text/babel" src="/static/dashboard.jsx"></script>

<script type="text/babel">
  // server emits prefs as a JSON island:
  const prefs = {{ prefs|tojson }};
  const theme = THEMES[prefs.theme];
  ReactDOM.createRoot(document.getElementById('root')).render(
    <Dashboard theme={theme} prefs={prefs} />
  );
</script>
```

The dashboard component reads `prefs` for the user's name + supporter, and reads `theme` for everything visual. The existing data wiring (`/api/posting/*`, `/api/apply`, etc.) does NOT change — the dashboard's components still call the same endpoints.

---

## Step 6 · In-app theme switcher (settings page)

A settings page at `/settings` lets users change their theme post-onboarding. Build it as:

- 6 theme cards (reuse `ThemeCard` from `onboarding.jsx`)
- One toggle for `mascotEnabled` (only shown when current theme has a mascot)
- Name + supporter inputs
- Toggle for `showPersonalNote`
- "Save" → `POST /api/prefs` → reload

**Don't ship the sticky bar at the top** of the dashboard (used in `code/index.html` for the reference). That's a demo affordance. Real settings live in a settings page.

---

## Step 7 · Generate-dashboard script

The `scripts/generate_dashboard.py` that emits a static dashboard:

- Loads user prefs (or the single-user prefs from CLI args / env)
- Loads the matching theme from `themes.py`
- Renders `templates/dashboard.html` with `{theme, prefs}` in context
- Writes to `dashboard/index.html`

No behavior changes from before — just one additional pass to apply the theme tokens.

---

## Step 8 · Mobile read-only view

Same theme system applies. On the Cloudflare read-only view:

- Fetch prefs once at page load
- Set CSS vars on `<body>`
- Render the read-only dashboard with the chosen theme

No mascot animations, no celebration triggers (read-only) — but the theme still applies. The theme is a personal-comfort setting, not a feature gate.

---

## Step 9 · Dopamine mechanics — unchanged

Confetti, affirmations, achievements, streak — all the timing and trigger rules from the previous handoff's `dopamine-mechanics.md` still apply. Only the *palette* and *copy strings* change per theme; the events themselves are universal.

The reference `dashboard.jsx` already wires the celebrate button → confetti + affirmation toast with the correct theme palette automatically.

---

## Step 10 · Acceptance checklist

Before shipping, verify:

- [ ] New account → lands on `/onboard` → picks a theme → lands on dashboard with that theme
- [ ] User changes theme in settings → dashboard reflects the new theme on next page load
- [ ] `mascotEnabled = false` on Garden/Tide/Dusk → mascot avatar replaced with monogram
- [ ] `supporter_name = ''` → love note silently disabled (no broken UI)
- [ ] `showPersonalNote = false` → love note hidden
- [ ] Confetti fires with the active theme's palette
- [ ] Affirmation toast pulls from `theme.copy.affirmations`
- [ ] Dark theme (Dusk) doesn't have any unreadable text (white-on-white, black-on-black) — spot check every section
- [ ] Mobile read-only view applies the theme correctly
- [ ] Switching themes does NOT lose user data (jobs, applications, statuses)

---

## Anti-checklist (things to NOT do)

- ❌ Don't add per-theme conditionals in component code. CSS vars + the registry pattern cover every case.
- ❌ Don't store the full theme object in the database. Store the key (`'tide'`); look up the object server-side and client-side.
- ❌ Don't auto-detect theme from system preference. Users explicitly chose; respect that.
- ❌ Don't show all 6 theme thumbnails at the top of the dashboard. The theme is a setting, not a constant decision.
- ❌ Don't deprecate Paper (the plain one). It's the default. Some users actively want zero personality.

---

## Cost / time estimate

For a single afternoon of focused work:

- Schema + migration: 30 min
- /api/prefs endpoints: 30 min
- Port `themes.js` + `mascots.jsx` + `dashboard.jsx` into static/: 30 min
- Refactor dashboard template to read CSS vars from theme: 1-2 hours
- Onboarding page wiring: 1 hour
- Settings page: 1 hour
- QA across 6 themes: 1 hour

Total: ~half a day if the existing single-theme dashboard is already React-based; more like a full day if it's still server-rendered Jinja with hardcoded styles.
