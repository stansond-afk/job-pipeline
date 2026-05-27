# Architecture — The Modular Theme Pattern

> **Read this before touching any component code.** Once you've internalised the pattern below, the rest of the handoff is just data.

---

## 1. The one big idea

**There is ONE dashboard component. There are 6 themes. The themes are pure data.**

Adding a 7th theme is a 30-line entry in `themes.js`. No JSX changes. No new components. No `if (theme === 'garden')` branches anywhere.

```
┌─────────────────────────────────────────────────────────────────┐
│  themes.js          (data only)                                 │
│    THEMES = { paper, garden, tide, quiet, mountain, dusk }      │
│                                                                 │
│  mascots.jsx        (one component per mascot key)              │
│    MASCOTS = { capybara, otter, moth }                          │
│    DECORATIONS = { 'sun-clouds', 'horizon', 'waves', ... }      │
│                                                                 │
│  dashboard.jsx      (reads theme + prefs; renders everything)   │
│    <Dashboard theme={THEMES[prefs.theme]} prefs={prefs} />      │
└─────────────────────────────────────────────────────────────────┘
```

If you find yourself adding a `switch(theme.id)` somewhere in the dashboard code, **stop**. That means a theme-specific concern needs to become a theme-driven token or a registry-keyed component. Talk to the user.

---

## 2. The four moving parts

### 2.1 Tokens (CSS variables)

Every visible color, font, radius, shadow, and letter-spacing lives in a CSS variable. Themes set them on a wrapper `<div style={theme.tokens}>`; every component below reads `var(--ink)` etc.

```js
// themes.js
quiet: {
  tokens: {
    "--bg":     "#ECEEF2",
    "--paper":  "#FFFFFF",
    "--ink":    "#161D27",
    "--sub":    "#5A6573",
    "--a1":     "#3B6CA8",
    "--serif":  "'Newsreader', Georgia, serif",
    "--radius-card": "10px",
    // ...
  },
}
```

```jsx
// dashboard.jsx
function ThemeShell({ theme, children }) {
  return <div style={{ ...theme.tokens, color: "var(--ink)" }}>{children}</div>;
}
```

**Why CSS vars, not Tailwind / a JS object?** Three reasons:

1. **Cascading.** A theme set at the dashboard root automatically reaches every nested element, including the table rows, badge tiles, and the affirmation toast — no prop drilling.
2. **No re-render churn on theme switch.** Switching themes is one DOM attribute update; React doesn't re-render anything.
3. **Server-side render friendliness.** Flask can emit `<div style="--bg: #fff; --ink: #111">` from a Jinja template and the page renders correctly before any JS hydrates.

### 2.2 Mascots — registry pattern

Mascots are React components in `mascots.jsx`, registered in a lookup table:

```js
const MASCOTS = {
  capybara: MascotCapybara,
  otter:    MascotOtter,
  moth:     MascotMoth,
};
```

Themes name their mascot:

```js
garden: { mascot: 'capybara', ... }
quiet:  { mascot: null,       ... }
```

The dashboard renders:

```jsx
const Mascot = theme.mascot ? MASCOTS[theme.mascot] : null;
return Mascot && prefs.mascotEnabled
  ? <Mascot size={62} />
  : <MascotMonogram initials={initials} />;
```

**Mascots are visually distinct but structurally identical** — every mascot accepts `{ size, style }` and renders inside a circular ~62px avatar slot. Drop in a commissioned illustration later by replacing one component; nothing else changes.

### 2.3 Decorations — registry pattern (same as mascots)

The "skybox" behind the greeting bar — sun + clouds for Garden, waves for Tide, stars for Dusk, etc. — is one component per key:

```js
const DECORATIONS = {
  'sun-clouds': DecoSunClouds,
  'horizon':    DecoHorizon,
  'waves':      DecoWaves,
  'paper':      DecoPaper,
  'stars':      DecoStars,
  'peak':       DecoPeak,
};
```

Themes reference one:

```js
tide: { decoration: 'waves', ... }
```

Each decoration uses `position: absolute; inset: 0` and reads theme tokens (`fill="var(--sun)"`) so it harmonises automatically. Adding a new decoration is one new component + one map entry.

### 2.4 Copy register — interpolated strings

Every string the dashboard shows comes from `theme.copy`. Strings can contain `{placeholders}` that the dashboard fills in:

```js
quiet: {
  copy: {
    greetingScript: "Good morning,",
    nameSuffix: ".",
    ringCopy: "{pct}% of the week behind you.",
    ringSub: "{remaining} more to close out the week.",
    affirmations: [
      "You showed up today. That counts.",
      "Quiet, consistent — that's the work.",
      // ...
    ],
  }
}
```

```jsx
const text = fmt(theme.copy.ringCopy, { pct: 53 });
// → "53% of the week behind you."
```

The full set of placeholder variables the dashboard provides:

| Placeholder | Meaning |
|---|---|
| `{pct}` | Percent of weekly goal complete |
| `{done}` | Apps submitted this week |
| `{goal}` | Weekly goal (default 15) |
| `{remaining}` | `goal - done`, clamped to 0+ |

**Adding more placeholders:** extend the `vars` object passed to `fmt()` in `dashboard.jsx`. Existing copy strings ignore unknown placeholders.

---

## 3. User preferences

Per-user state lives in 4 columns and one client object:

```sql
ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'paper';
ALTER TABLE users ADD COLUMN mascot_enabled BOOLEAN DEFAULT 1;
ALTER TABLE users ADD COLUMN supporter_name TEXT;
ALTER TABLE users ADD COLUMN show_love_note BOOLEAN DEFAULT 1;
-- display_name already exists; reuse it.
```

```js
// shape passed to <Dashboard prefs={...} />
const prefs = {
  theme: 'tide',              // → key into THEMES
  mascotEnabled: true,        // → mascot vs monogram
  name: 'Solongo',            // → users.display_name
  supporter: 'Stanson',       // → users.supporter_name
  showPersonalNote: true,     // → render love-note pill
};
```

**Default for new accounts:** `theme: 'paper'`, `mascotEnabled: true`, `supporter: ''`, `showPersonalNote: true`.

Paper is the safe default. Picking Garden as default would impose a personality on people who didn't ask. Paper imposes nothing.

---

## 4. The dashboard component tree

```
<Dashboard theme prefs>
  <ThemeShell theme>                  ← sets all CSS vars on wrapper
    <TopBar theme prefs>              ← greeting + mascot + streak + Celebrate CTA
    <LoveNote theme prefs>            ← "{supporter} thinks you're the best…"
    <WeeklyRing theme>
    <Sparkline theme>
    <Funnel theme>
    <TodaysPicks theme>
      <JobCard /> × 3
    <PickMeUp theme>
    <Achievements theme>
    <JobsTable theme>
    <Affirmation theme prefs>         ← floating toast on celebrate
    <ThemedConfetti theme>            ← falls when celebrate fires
```

Every child reads from `theme.copy` for strings and from CSS vars for visuals. No child knows what theme it's inside.

---

## 5. The single hand-fonts caveat

Some themes use a hand-written font ("Caveat") for accents. Others (Paper, Quiet Focus, Mountain) don't — they fall back to italic serif so the same JSX renders correctly.

```js
garden: { tokens: { "--hand": "'Caveat', cursive" } }
paper:  { tokens: { "--hand": "'EB Garamond', Georgia, serif" } }
```

The `<Hand>` component in `dashboard.jsx` always sets `fontStyle: 'italic'` so the fallback themes get a soft serif-italic accent that visually echoes (but doesn't impersonate) the hand-written feel.

---

## 6. Confetti — palette per theme

`ConfettiBurst` from `shared-data.jsx` takes a `palette` prop. The dashboard composes the palette from CSS vars resolved against the theme's token table (CSS vars don't resolve inside inline styles on freshly mounted dynamic components reliably, so we resolve to hex manually):

```jsx
function ThemedConfetti({ theme }) {
  const keys = ['--sun', '--warm', '--a1', '--a2', '--good'];
  const palette = keys.map(k => theme.tokens[k]);
  return <ConfettiBurst palette={palette} />;
}
```

If you add a token to a theme, you don't need to update confetti unless you want a new color in the burst.

---

## 7. Adding a 7th theme — the full checklist

If a future contributor wants to add a theme (you don't, right now — six is the brief):

1. **Pick a key.** Lowercase, single word. e.g. `forest`.
2. **Add tokens.** Copy an existing entry in `themes.js` and edit. Required: all 17 CSS vars in the existing entries. Easiest to start from `paper` and add chroma.
3. **Pick a mascot.** Either set `mascot: null`, or add a new component in `mascots.jsx` and register the key.
4. **Pick a decoration.** Either reuse an existing key, or add a new component in `mascots.jsx` and register the key.
5. **Write copy.** Every key in an existing theme's `copy` block must be present. Use the same `{placeholders}`. Keep affirmations to 7-ish entries.
6. **Done.** No other file changes. The picker auto-discovers themes via `Object.values(THEMES)`.

If a step above fails the modularity guarantee — e.g. you need a new layout for a theme — that's a sign the layout should become a per-theme token, not a special case.

---

## 8. The anti-patterns

In the spirit of being explicit:

- ❌ **Theme-specific JSX branches.** `theme.id === 'garden' && <CapybaraSpecificThing />`. Wrong. Becomes a registry-keyed component or a token.
- ❌ **Hardcoded colors in components.** `color: '#2E2B3D'`. Wrong. Should be `color: 'var(--ink)'`.
- ❌ **Copy strings in components.** `<button>Apply →</button>` in dashboard.jsx is fine *only* for words that never change per theme. Anything that has a copywriting personality (greetings, kickers, affirmations, celebrate-button label) goes in `theme.copy`.
- ❌ **A theme without a `copy` block.** Falls back to undefined strings. Always copy the full set of keys from an existing theme when adding.

---

## 9. Where the existing handoff doc still applies

`design-tokens.md`, `voice-and-tone.md`, `dopamine-mechanics.md`, and `components.md` from the previous handoff describe the Garden theme in detail. Their *layout, spacing, dopamine triggers, and component breakdowns are still accurate* — the new architecture just generalises the color/type/copy concerns. When in doubt about a non-theme-specific behavior (when confetti fires, what status colors mean, etc.), the older docs are still the source of truth. This handoff's `voice-and-tone.md` and `components.md` supersede them only for theme-variant concerns.
