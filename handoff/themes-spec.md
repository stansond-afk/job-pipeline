# The 6 Themes — Full Specs

Each theme below is fully specified — palette, type, mascot, decoration, copy register, voice. **The source of truth is `code/themes.js`**; this doc describes intent and where each value gets used. If the two disagree, the JSON wins (the dashboard reads it directly).

---

## Theme 1 · Paper (the plain default)

> **Pick this** when a user wants a tool with no personality. It's the safe default for new accounts.

| | |
|---|---|
| Key | `paper` |
| Tagline | minimal · neutral · quiet |
| Mascot | none |
| Decoration | `paper` (two hairlines top + bottom of greeting bar) |
| Dark mode | no |
| Vibe | cream paper, ink, quiet whitespace |

**Palette**

| Token | Hex | Use |
|---|---|---|
| `--bg` | #F2EFE8 | page background |
| `--paper` | #FFFFFF | card surfaces |
| `--ink` | #1A1A1A | primary text |
| `--sub` | #6B6B6B | secondary text |
| `--line` | #D8D4CB | borders |
| `--a1` | #3A6A8C | the one info accent (sparingly) |
| `--sun` | #E8D9A8 | weekly-goal ring fill |
| `--warm` | #B87363 | "very interested" only |
| `--good` | #8FA88E | offered status only |

**Type**

- Serif: EB Garamond (titles, ring number, kickers as Aa preview)
- Sans: Inter (body, table, buttons)
- Hand: EB Garamond italic (fallback — no script font)

**Geometry**

- Card radius: 6px (sharp, like a printed card)
- Pill radius: 4px
- Shadow: 1px hairline border only, no drop shadow

**Voice**

- Greeting: "Good morning, {name}."
- Mascot line: "Note: small steady acts."
- Celebrate button: "Mark today done"
- Streak: "7 days, in a row"
- Affirmations: 7 calm one-liners. Sample: *"You sent applications today. That is real work."*

---

## Theme 2 · Garden (warm, hand-written)

> The original Solongo direction, slightly toned down. Twee-leaning warmth.

| | |
|---|---|
| Key | `garden` |
| Tagline | warm · soft · hand-written |
| Mascot | capybara — **Pip** |
| Decoration | `sun-clouds` (a sun rising over the greeting bar; small cloud pills) |
| Dark mode | no |
| Vibe | cozy, soft pastels, a calm capybara off to one side |

**Palette**

| Token | Hex | Use |
|---|---|---|
| `--bg` | #FBF7EF | cream page |
| `--paper` | #FFFDF7 | paper-white cards |
| `--ink` | #2E2B3D | primary text |
| `--sub` | #6F6A82 | secondary text |
| `--line` | #E7DFCD | borders |
| `--a1` | #9CC3E8 | sky (interested) |
| `--a2` | #C9B8E0 | lilac (tailor button) |
| `--sun` | #F4D87C | strong fit, weekly goal |
| `--warm` | #F0A89C | very-interested coral |
| `--good` | #B9DBC4 | mint (offered) |

**Type**

- Serif: Fraunces 400-700
- Sans: Nunito 400-800
- Hand: Caveat 500-700

**Geometry**

- Card radius: 20px (round, friendly)
- Pill radius: 999px (full pill)

**Voice**

- Greeting: "good morning, {name} ☀"
- Mascot line: "Today: take it one job at a time."
- Celebrate: "Celebrate today"
- Streak: "7 days showing up 🔥"
- Affirmations sample: *"You're doing the hard thing, slowly. That's the way."*

---

## Theme 3 · Tide (calm coastal, gender-neutral)

> The most universally-likeable theme. Pick this if undecided.

| | |
|---|---|
| Key | `tide` |
| Tagline | coastal · spacious · neutral |
| Mascot | otter — **Marlow** |
| Decoration | `waves` (two soft wave layers at the bottom of the greeting bar + a low sun) |
| Dark mode | no |
| Vibe | sea-air, soft blues, warm sand |

**Palette**

| Token | Hex | Use |
|---|---|---|
| `--bg` | #EAF1F4 | sea-mist page |
| `--paper` | #F8FBFC | paper |
| `--ink` | #1F3A4A | deep-sea text |
| `--sub` | #5E7886 | secondary |
| `--line` | #CFDDE4 | borders |
| `--a1` | #5E94B2 | wave-blue accent |
| `--a2` | #87B4C9 | surf-blue |
| `--sun` | #E8D6A8 | sand / strong fit |
| `--warm` | #E89B8E | coral-pink (very-interested) |
| `--good` | #90B8AE | sea-glass green (offered) |

**Type**

- Serif: Lora (slightly more open than Fraunces, fits coastal feel)
- Sans: Nunito
- Hand: Caveat

**Geometry**

- Card radius: 16px (slightly less round than Garden)
- Kicker case: lowercase (matches Tide's relaxed register)

**Voice**

- Greeting: "hello, {name}."
- Mascot line: "Today: small, steady tides."
- Celebrate: "Mark the day"
- Streak: "7 days, in a row ○"
- Affirmations sample: *"A 'no' is one wave. There are more."*

---

## Theme 4 · Quiet Focus (sharp, professional, masculine-leaning)

> For users who want a serious-looking tool with warmth in the words, not the visuals.

| | |
|---|---|
| Key | `quiet` |
| Tagline | calm · masculine · focused |
| Mascot | none (initials monogram) |
| Decoration | `horizon` (three subtle horizontal lines across the greeting bar) |
| Dark mode | no |
| Vibe | slate, deep blue, crisp type |

**Palette**

| Token | Hex | Use |
|---|---|---|
| `--bg` | #ECEEF2 | slate-mist |
| `--paper` | #FFFFFF | white card |
| `--ink` | #161D27 | navy-ink |
| `--sub` | #5A6573 | secondary |
| `--line` | #D8DCE3 | borders |
| `--a1` | #3B6CA8 | deep blue |
| `--a2` | #7D9DC0 | steel-blue |
| `--sun` | #D9A05B | warm amber (strong fit) |
| `--warm` | #C77565 | brick-red (very-interested) |
| `--good` | #6E9F8C | muted sage (offered) |

**Type**

- Serif: Newsreader (sharp, modern)
- Sans: Inter
- Hand: Inter italic (no script)

**Geometry**

- Card radius: 10px (slightly rounded, but not friendly-rounded)
- Pill radius: 6px (more rectangular)

**Voice**

- Greeting: "Good morning, {name}."
- Mascot line: "Today: one focused hour beats three scattered ones."
- Celebrate: "Mark today"
- Streak: "7 consecutive days ●"
- Affirmations sample: *"Quiet, consistent — that's the work."*

**Important:** Do NOT add coach-speak. No "crush it," "level up," "grind." Quiet means *calm masculine*, not bro masculine.

---

## Theme 5 · Mountain (grounded neutral)

> Reads as "for everyone" — no animals, no script, no warm pastels. Stone and sage. Earnest.

| | |
|---|---|
| Key | `mountain` |
| Tagline | grounded · calm · steady |
| Mascot | none |
| Decoration | `peak` (faint mountain-range silhouette in the greeting bar) |
| Dark mode | no |
| Vibe | stone, sage, alpine air |

**Palette**

| Token | Hex | Use |
|---|---|---|
| `--bg` | #ECE9E3 | stone-cream |
| `--paper` | #F6F4EE | paper |
| `--ink` | #2C2E2A | dark-stone text |
| `--sub` | #6E6F69 | secondary |
| `--line` | #D4CFC4 | borders |
| `--a1` | #7A8B82 | slate-sage |
| `--a2` | #95A89B | sage |
| `--sun` | #D9B872 | desert-amber |
| `--warm` | #B87363 | terracotta |
| `--good` | #95A89B | sage (same as a2; matches the grounded palette) |

**Type**

- Serif: Source Serif Pro (steady, no flourish)
- Sans: Inter
- Hand: Source Serif Pro italic (no script)

**Geometry**

- Card radius: 8px (squarer, geological)
- Pill radius: 6px

**Voice**

- Greeting: "Good morning, {name}."
- Mascot line: "Today: one step, then another."
- Celebrate: "Mark the day"
- Streak: "7 days, climbing ▲"
- Affirmations sample: *"Mountains are climbed by people who kept walking."*

---

## Theme 6 · Dusk (warm dark mode)

> The only dark theme. For evening / night use. Warm tones, not cyberpunk neon.

| | |
|---|---|
| Key | `dusk` |
| Tagline | dark · warm · nocturnal |
| Mascot | luna moth — **Vesper** |
| Decoration | `stars` (faint scattered dots + a soft moon) |
| Dark mode | **yes** |
| Vibe | aubergine, amber, plum |

**Palette**

| Token | Hex | Use |
|---|---|---|
| `--bg` | #1B1726 | deep aubergine |
| `--paper` | #2A2336 | plum card |
| `--ink` | #F5EBE0 | warm cream text |
| `--sub` | #9B8FAF | muted lavender |
| `--line` | #3A3148 | subtle border |
| `--a1` | #A684C9 | warm violet |
| `--a2` | #7390B8 | slate-violet |
| `--sun` | #E8B86C | amber (strong fit, weekly goal) |
| `--warm` | #D69BAA | blush (very-interested) |
| `--good` | #9BBFA3 | sage-green (offered) |

**Type**

- Serif: Fraunces (same as Garden — works in dark)
- Sans: Inter
- Hand: Caveat

**Geometry**

- Card radius: 16px
- Shadow: deeper, larger (dark mode needs bigger shadows to feel layered)

**Voice**

- Greeting: "good evening, {name}."
- Mascot line: "Tonight: the day is over. you did enough."
- Celebrate: "Close the day"
- Streak: "7 nights of showing up ✦"
- Affirmations sample: *"A 'no' under a kind sky is still just one 'no'."*

**Dark-mode caveats**

- Confetti palette stays the same (uses theme tokens which are already dark-mode tuned).
- The `score chip` background colors should keep the same hue family but lighten slightly — test contrast in the dark theme.
- Pick-me-up baby-animal photos: if you ship Dusk with the real photo source, vet a dark-friendly subset or apply a 90% opacity warm overlay.

---

## How users see this

In the onboarding picker, themes are presented in a 2×3 grid with this same order:

```
[ Paper   ] [ Garden  ]
[ Tide    ] [ Quiet   ]
[ Mountain] [ Dusk    ]
```

Each tile shows a mini swatch (mascot + color dots + a serif "Aa") and a 1-sentence blurb (the `blurb` field on each theme). See `onboarding-spec.md`.

---

## Theme order rationale

- Paper first = the safe default reads as the "easy choice." Most users will pick this without scrolling.
- Garden second = the warmest option, signals personality is available.
- Tide third = sits between feminine warmth (Garden) and masculine cool (Quiet) on the page.
- Quiet fourth = pairs against Tide as the masculine counterpart.
- Mountain fifth = grounded neutral, distinct from Paper's plainness.
- Dusk sixth = clearly a "for night" option; positioned last so it doesn't dominate.

Don't reorder unless you have a strong reason.
