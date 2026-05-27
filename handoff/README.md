# Jobline — Multi-Theme Design Handoff

> **For Claude Code:** This folder is the **complete spec** for refactoring the existing single-theme Solongo dashboard into a **public, multi-theme Jobline app** with 6 user-selectable themes. Everything you need is here.
>
> **Read in this order:**
> 1. This file (orientation + folder map)
> 2. `architecture.md` (the modular pattern — how themes are wired)
> 3. `themes-spec.md` (the 6 themes documented)
> 4. `integration-guide.md` (how to wire it into the existing Flask + SQLite app)
> 5. `voice-and-tone.md`, `dopamine-mechanics.md`, `components.md`, `onboarding-spec.md` (reference as needed)
>
> **To see it run:** open `code/index.html` in a browser. It's a complete working reference — onboarding picker, then a themed dashboard. Theme strip at top lets you flip between all 6. State persists to localStorage.

---

## 1. What changed from the previous handoff

The previous handoff (`design_handoff_solongo_dashboard/`) shipped a single direction — "Solo's Garden" — built for Solongo specifically.

This handoff:

- **Opens the app to public users.** Personalisation moves to per-user prefs.
- **Provides 6 themes** users pick during onboarding. One ("Paper") is intentionally plain — not everyone wants extras.
- **Refactors the dashboard to a single token-driven component.** No theme-specific code branches.
- **Keeps the dopamine mechanics intact.** Ring, streak, funnel, picks, pick-me-up, achievements, table — all preserved. Voice register and visual tokens change per theme; mechanics don't.
- **Adds the "someone loves you" pillar** as a dismissible note seeded with a supporter name the user enters during onboarding.

Treat the previous handoff as historical. This folder supersedes it.

---

## 2. Folder map

```
handoff/
├── README.md                  ← you are here
├── architecture.md            ← the modular pattern (READ FIRST)
├── themes-spec.md             ← the 6 themes, with full token + copy specs
├── integration-guide.md       ← Flask + SQLite wiring (READ SECOND)
├── voice-and-tone.md          ← universal voice rules + per-theme deltas
├── dopamine-mechanics.md      ← reward system spec (unchanged from prev)
├── content-providers.md       ← pluggable pick-me-up content system
├── components.md              ← component-by-component breakdown
├── onboarding-spec.md         ← the first-run theme picker
└── code/                      ← working reference implementation
    ├── index.html             ← open this in a browser to see it run
    ├── themes.js              ← all 6 themes as data (lift this verbatim)
    ├── mascots.jsx            ← mascot components + decoration components
    ├── content-providers.jsx  ← 7 pick-me-up content sources + registry
    ├── dashboard.jsx          ← the token-driven dashboard
    ├── onboarding.jsx         ← the first-run picker
    └── shared-data.jsx        ← dummy data + ConfettiBurst (mirror real schema)
```

---

## 3. The 6 themes at a glance

| # | Theme | Feel | Mascot | Best for |
|---|---|---|---|---|
| 1 | **Paper** | True minimal, cream + ink | none | The default. Users who just want a tool. |
| 2 | **Garden** | Warm, soft pastels, hand-written | capybara (Pip) | Cozy, feminine-leaning. (The original Solongo direction, toned down.) |
| 3 | **Tide** | Soft sea-blues, warm sand | otter (Marlow) | Gender-neutral calm. Broadly appealing. |
| 4 | **Quiet Focus** | Slate, deep blue, sharp type | none | Professional, masculine-leaning. Warmth is in the words. |
| 5 | **Mountain** | Stone, sage, alpine air | none | Grounded and steady. No personality, lots of dignity. |
| 6 | **Dusk** | Warm dark mode, aubergine + amber | moth (Vesper) | For night sessions. The only dark theme. |

Mascots are **optional** per user even when the theme has one — Garden / Tide / Dusk all expose a `mascotEnabled` toggle.

`Paper` is the **default for new accounts.** Pick it deliberately for least personality / safest first impression.

---

## 4. Fidelity

**High fidelity** — palette tokens, type, type sizes, mascot SVG shapes, copy strings: lift them straight from `code/themes.js` and the JSX components. They are final unless changed in §7.

**Medium fidelity** — the dashboard layout itself. The reference is one valid layout; you can adapt section ordering or table column widths to fit existing templates as long as you preserve the mechanics and the token consumption.

**Out of scope here** — backend behavior. All Flask endpoints, data shape, and persistence rules stay the same. See `integration-guide.md` for the minimal additions (4 new user columns, an /api/prefs route, a 1-time onboarding flow).

---

## 5. The big picture

Job searches are hard, mostly rejection, and emotionally expensive. The voice does the heavy lifting — pastels alone aren't enough.

Three principles that drove every design decision (preserved verbatim from the previous handoff because they still apply):

1. **Encouragement over metrics.** Every number is paired with affect.
2. **Reward the inputs, not the outputs.** Confetti on *submit*, not on *interview*.
3. **Soften without infantilizing.** Decoration is warmth on top of a serious tool — not a substitute for one.

The 6 themes are six different *registers* of those principles. Garden is twee-leaning warmth; Quiet Focus is stoic warmth; Paper is silent warmth; Dusk is nocturnal warmth. The mechanics are identical.

---

## 6. The "someone loves you" pillar

New in this version. During onboarding the user enters:

- `display_name` — what greets them
- `supporter_name` — a person who believes in them ("my partner Mara", "my mom", "Stanson")

The dashboard surfaces this in two places:

- A dismissible **love note** below the greeting bar: *"Mara thinks you are the best thing in the world."*
- Rotated into the affirmation toast occasionally.

If the user leaves `supporter_name` blank, the love note silently disables (no scolding empty state). The toggle `showPersonalNote` controls visibility globally.

This is intentionally cheesy. The user opted in. Job searches make people forget they are loved; the product can refuse to let that happen.

---

## 7. Open design questions

Decisions still needed:

- **Real mascot illustrations.** Capybara / Otter / Moth are SVG-from-primitives in the reference. They look intentional but are obviously not commissioned art. Pick one of: (a) ship as-is, (b) commission one set, (c) AI-generate (risk: uncanny). Garden's capybara reads best as-is; the others might want real art.
- **Real baby-animal source for pick-me-up.** Still TODO from previous handoff.
- **Joke source.** Static array OK at launch; daily Claude call later.
- **Achievement triggers.** Unchanged from `dopamine-mechanics.md`.
- **Whether to ship Dusk at launch.** Dark mode is more code surface (CSS color schemes, image alpha tuning, etc.). Reasonable to ship 5 themes first and add Dusk later.

---

## 8. Working with this in Claude Code

A starter prompt:

> Read `handoff/README.md`, then `handoff/architecture.md`, then `handoff/integration-guide.md`. The repo's current dashboard is `dashboard/index.html` generated by `scripts/generate_dashboard.py`. We're moving from a single hard-coded design to a 6-theme system per the spec in `handoff/`. For this session, please [TASK]. Stay inside the tokens defined in `handoff/code/themes.js`; flag any place you have to invent a value.

Recommended task sequence:

1. **Schema + prefs API** — `users.theme`, `mascot_enabled`, `supporter_name`, `show_love_note` columns + `/api/prefs` GET/POST endpoint.
2. **Port `themes.js` + `mascots.jsx`** verbatim into the existing dashboard. Wire CSS vars to a wrapper.
3. **Refactor existing components** to read `var(--ink)` etc. instead of hardcoded hexes.
4. **Build the onboarding picker** at `/onboard` (or first-load modal).
5. **Add the love-note pill** to the dashboard layout.
6. **Ship the in-app theme switcher** (settings page; not the demo sticky bar).
7. **Add Dusk-specific tweaks** (dark mode pick-me-up images, etc.) last.

Small, scoped commits beat sweeping rewrites.

---

## 9. Changelog

| Date | Change | Where |
|---|---|---|
| 2026-05-25 | v2 multi-theme handoff. 6 themes, modular pattern. Replaces single-direction v1. | All files |
