# Components — Per-Section Specs

> **Source of truth:** `code/dashboard.jsx`. This doc describes intent and what each component reads from the theme. Where this doc and the code disagree, fix both.

All components are token-driven. Hex values appear nowhere; every visual quantity is a CSS var. Strings come from `theme.copy`.

---

## 1. ThemeShell (the wrapper)

```jsx
<ThemeShell theme={theme}>{children}</ThemeShell>
```

Sets the 17 CSS vars from `theme.tokens` on a wrapper div. Everything below it reads them via `var(--ink)` etc. Renders `background: var(--bg)`, `color: var(--ink)`, `fontFamily: var(--sans)` on itself.

**Don't nest two ThemeShells.** A theme switch is `<ThemeShell theme={newTheme}>` at the same level — React's reconciliation handles the rest.

---

## 2. Card / CardTitle (primitives)

The only card primitive. Every section is a `<Card>` variant.

```jsx
<Card pad={22}>
  <CardTitle kicker="this week" action={<...>}>Weekly goal</CardTitle>
  ...
</Card>
```

- Background: `var(--paper)`
- Border: `1px solid var(--line)`
- Radius: `var(--radius-card)` (varies per theme: 6px Paper → 20px Garden)
- Shadow: `var(--shadow-card)`

CardTitle renders:
- A kicker (uppercase or lowercase per theme via `--kicker-tt`), letter-spacing `--kicker-ls`, color `--sub`
- The title in serif, weight 500, size 22

---

## 3. TopBar (greeting)

Reads from theme: `decoration`, `mascot`, `copy.greetingScript`, `copy.nameSuffix`, `copy.mascotSays`, `copy.mascotQuote`, `copy.streakSuffix`, `copy.streakIcon`, `copy.celebrate`.

Layout: `1fr auto` grid. Left = mascot/monogram (78px circle) + greeting block. Right = streak pill + Celebrate CTA.

**Decoration:** absolutely-positioned behind content via `<Deco />` looked up from `window.DECORATIONS[theme.decoration]`. Sets fills against theme tokens so it harmonises.

**Background gradient:** mixes the theme's `--a1`, `--a2`, and `--sun` via `color-mix(in oklch, ...)`. The Dusk theme overrides to use the paper colors directly (dark mode looks weird with the bright gradient).

**Mascot vs monogram:** `Mascot = theme.mascot ? MASCOTS[theme.mascot] : null`. Render `<Mascot />` if both present AND `prefs.mascotEnabled`; else `<MascotMonogram initials={...} />`.

---

## 4. LoveNote

Reads from `prefs.supporter`, `prefs.showPersonalNote`, and `theme.copy.mascotName`.

A dismissible pill below the greeting bar. Background: `color-mix(in oklch, var(--warm) 18%, var(--paper))`. Border: 1px in the warm-derived hue. Content: a `<Hand>` heading with the message.

**Hide rules:**
- `prefs.showPersonalNote === false` → never render
- `prefs.supporter === ''` → never render
- User clicked × → don't render this session (component-local state)

---

## 5. WeeklyRing

Standard card. 152×152 ring on left, text block on right.

- Ring stroke: `var(--sun)` for progress, `var(--row)` for the empty track
- 4 tiny flowers around the ring at N/E/S/W in `--warm`, `--a1`, `--a2`, `--good`
- Center number in serif, 40px, 500 weight
- Right block uses `<Hand>` for the percent line and `--sub` for the body sentence
- Day pills: 7 × 28×36px rounded tiles, sun-yellow if active

Reads `theme.copy.ringCopy` (with `{pct}` placeholder) and `theme.copy.ringSub` (with `{remaining}`).

---

## 6. Sparkline

Standard card. SVG line chart, 14 days of submit counts.

- Area fill: `var(--a1)` at 25% opacity
- Stroke: `var(--a1-dk)`, 2.5px
- Points: 3px circles in `var(--sun)` for non-zero days, 1.5px in `var(--line)` for zeros
- Context line: reads `theme.copy.sparklineCopy` (a fully-rendered string; no placeholders for now)

---

## 7. Funnel

6 stages, 6-column grid, 8px gap.

Tone-to-token mapping (the data uses tone names, the component resolves to CSS vars):

| `tone` | Token |
|---|---|
| `neutral` | `--row` |
| `sky` | `--a1` |
| `lilac` | `--a2` |
| `sun` | `--sun` |
| `coral` | `--warm` |
| `mint` | `--good` |

Each stage: number in serif 26px, label in 11px ink, dim to 55% opacity if count is 0. Connector `→` between stages.

Footer line: `<Hand>` reads `theme.copy.funnelFooter`.

---

## 8. TodaysPicks + JobCard

`TodaysPicks` is a card containing a 3-column grid of `JobCard`s. Reads `theme.copy.picksKicker` and `theme.copy.picksTitle`.

`JobCard` (per-card):
- 5px left border colored by interest (`--warm` very, `--a1` interested, `--line` not-reviewed, `--sub` not-interested)
- Top row: company kicker + role (serif 18) on left, score chip on right
- Score chip: `var(--sun)` background, 800-weight, 12px
- Meta row: 📍 location · source · posted in `--sub`
- Buttons: Tailor → (`--a2` bg) and Apply ✓ (`--ink` bg)

---

## 9. PickMeUp

Standard card with `linear-gradient(160deg, var(--paper), var(--row))` background.

- Kicker / title from `theme.copy.pickMeUpKicker` / `pickMeUpTitle`
- `🎲 new one` button on the right
- Photo placeholder: 130px tall striped div (`PhotoPlaceholder` from `shared-data.jsx`)
- Joke pair below in a dashed-border inner card: question in `<Hand>`, answer in `--ink`

---

## 10. Achievements

Standard card. 4×2 grid, 10px gap.

Earned tile: gradient `var(--row)` → `var(--paper)`, dashed `var(--sun)` border, ✓ corner badge in `var(--sun)`.

Locked tile: `var(--row)` background, dashed `var(--line)` border, 50% opacity, grayscaled icon. **Name + description still visible** — discovery is part of the reward.

Reads `theme.copy.achKicker` for the kicker.

---

## 11. JobsTable

Standard card. Search input + status select + hide-pass checkbox + reset button.

6-column grid: `1.6fr 1.6fr 0.9fr 0.7fr 0.8fr 0.9fr` = Company / Role / Location / Score / Interest / Action.

- Header row: 10px uppercase `--sub` labels, +0.8 letter-spacing
- Each row: 12×8 padding per cell, `var(--row)` divider between rows
- Score chip: tier-colored (`--sun` strong / `--good` good / `--row` medium / `--line` low)
- Interest pill: colored by current value (`--warm` very, `--a1` interested, `--row` else)
- Status pill or Apply button per row

Reads `theme.copy.tableKicker` and `theme.copy.tableTitle`. Empty state: just shows "no matches" — theme-specific flavor copy is a future enhancement.

---

## 12. Affirmation toast

Floating, top 90px, centered. Background `var(--ink)`, text `var(--bg)`. 999px radius. Mascot avatar at 36px on left (if theme has one and `mascotEnabled`); message in serif 18.

Text comes from `theme.copy.affirmations[Math.floor(Math.random() * ...)]`.

Entry animation: `a-pop` keyframe with overshoot bounce, 400ms.

---

## 13. ThemedConfetti

`ConfettiBurst` from `shared-data.jsx` driven by a theme-derived palette:

```js
const palette = ['--sun', '--warm', '--a1', '--a2', '--good'].map(k => theme.tokens[k]);
```

Resolves to hex because the confetti pieces use inline `style.background` (CSS vars don't always cascade reliably into dynamically-created inline-style children).

---

## 14. The components that AREN'T in this folder

- **Apply modal** — punted from the previous handoff; still TODO. When you build it, match the theme via CSS vars same as everything else.
- **Settings page** — see `integration-guide.md` § 6.
- **Read-only mobile view** — see `integration-guide.md` § 8.

---

## 15. Adding a new section to the dashboard

If you need to add e.g. a "saved searches" card:

1. Build it as a `<Card>` + `<CardTitle>` like every other section.
2. Use CSS vars for every color.
3. If it has any user-visible copy with personality, add a new key to every theme's `copy` block — even if 4 of them get identical strings. Future-proofs theme variations.
4. If it has a placeholder like `{count}`, add the placeholder to the `fmt()` call site in `dashboard.jsx`.

Never hardcode a color or font in a new section. The day you do, the theme system breaks.
