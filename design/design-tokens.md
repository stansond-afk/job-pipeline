# Design Tokens

Warm pastel design system originally developed for the "Solo's Garden"
direction. Copy these into the codebase as CSS variables (already done
in `scripts/generate_dashboard.py`) or Tailwind config.

## Palette

```css
:root {
  /* Surfaces */
  --color-cream:    #FBF7EF;  /* page background */
  --color-paper:    #FFFDF7;  /* card surface */

  /* Text */
  --color-ink:      #2E2B3D;  /* primary text, dark buttons */
  --color-sub:      #6F6A82;  /* secondary text, labels */

  /* Accents — soft pastels, ordered by warmth */
  --color-sky:      #9CC3E8;  /* fills, light backgrounds */
  --color-sky-dk:   #5B8AB8;  /* sky on light, hand-written accents */
  --color-lilac:    #C9B8E0;  /* Tailor button, tertiary actions */
  --color-lilac-dk: #8A77B0;  /* lilac text on light */
  --color-sun:      #F4D87C;  /* highlight, weekly goal, score chip (strong) */
  --color-sun-dk:   #C49F37;  /* sun on light */
  --color-coral:    #F0A89C;  /* "very interested" interest pill, warm CTA accent */
  --color-mint:     #B9DBC4;  /* score chip (good), offer/positive status */

  /* Lines */
  --color-line:     #E7DFCD;  /* card borders, table row dividers (heavier) */
  --color-row:      var(--color-cream); /* table row dividers (lighter) */
}
```

### Where each color is used
- **Cream / paper** — page bg + cards; never use pure white.
- **Sky / sky-dk** — informational accents, the "interested" interest pill background, hand-written copy ("you're 53% of the way there").
- **Lilac / lilac-dk** — secondary buttons (Tailor), hand-written footer copy.
- **Sun / sun-dk** — the headline highlight color: weekly goal ring fill, strong-fit score chip, achievement earned indicator. Use sparingly — it's the loudest color in the palette.
- **Coral** — "very interested" interest pill only. Reserved so it stays meaningful.
- **Mint** — good-fit score chip, future "offered" pill.

### Score-tier color mapping (used in the table)
- Strong (≥ 0.75) → `--color-sun`
- Good (≥ 0.50)   → `--color-mint`
- Medium (≥ 0.20) → `--color-cream`
- Low (< 0.20)    → `--color-line`

### Status pill color mapping
- `new`          → `--color-cream` (with border)
- `tailored`     → `--color-lilac`
- `submitted`    → `--color-sun`
- `interviewing` → `--color-coral`
- `offered`      → `--color-mint`
- `rejected`     → `--color-line` (dimmed)

---

## Typography

```css
:root {
  --font-serif: 'Fraunces', Georgia, 'Times New Roman', serif;
  --font-sans:  'Nunito', system-ui, -apple-system, sans-serif;
  --font-hand:  'Caveat', cursive;
}
```

Load via Google Fonts:
```html
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Nunito:wght@400;500;600;700;800&family=Caveat:wght@500;600;700&display=swap" rel="stylesheet" />
```

### Scale (rounded, no fractional sizes)
| Token       | px  | Use                                                      | Family   | Weight |
|-------------|-----|----------------------------------------------------------|----------|--------|
| `text-xs`   | 10  | Table column headers, kicker labels (UPPERCASE, +0.8 ls) | sans     | 700    |
| `text-sm`   | 11  | Pill text, footnotes                                     | sans     | 700    |
| `text-base` | 12–13 | Body, table cells                                      | sans     | 400/500|
| `text-md`   | 14  | Subtitle text                                            | sans     | 400    |
| `text-lg`   | 16  | Job card titles, table row primary text                  | sans/serif | 500/600 |
| `text-xl`   | 18  | Card titles                                              | serif    | 500    |
| `text-2xl`  | 22  | Card section titles, large stat                          | serif    | 500    |
| `text-3xl`  | 26  | Funnel-stage numbers                                     | serif    | 500    |
| `text-4xl`  | 40–42 | Weekly-goal ring number, greeting name                 | serif    | 500    |

**Hand-written accent (Caveat)** sits at 18–28px. Use for: greetings, "you're X% of the way there," footer signature. Never for data, button labels, or anything ATS-functional.

### Letter spacing
- Kicker labels: `+1.2px`, UPPERCASE
- Display serif: `-0.4px` for sizes ≥ 32px, 0 otherwise
- Everything else: default

---

## Spacing scale

The prototype uses unitless numbers; this is a 4-based scale:

| Token  | px |
|--------|----|
| s-1    | 4  |
| s-2    | 8  |
| s-3    | 12 |
| s-4    | 16 |
| s-5    | 20 |
| s-6    | 24 |
| s-8    | 32 |

Card outer gap is `s-4` (16px). Card inner padding is 20–24px depending on density.

---

## Radii

```css
:root {
  --radius-pill: 999px;     /* all chips, pills, buttons */
  --radius-card: 22px;      /* primary cards */
  --radius-card-lg: 28px;   /* top greeting bar */
  --radius-input: 10px;     /* form inputs, mini-buttons */
  --radius-tag: 14px;       /* funnel stat tiles, achievement tiles */
}
```

**Rule:** big things get big rounding. Never sharp corners; never circle-radius on rectangles wider than 200px.

---

## Shadows & borders

```css
:root {
  --border-soft: 1px solid var(--color-line);
  --shadow-card: 0 1px 0 rgba(255,255,255,0.7) inset, 0 8px 20px -16px rgba(80,60,30,0.15);
  --shadow-float: 0 16px 30px -10px rgba(0,0,0,0.4); /* affirmation toast */
  --shadow-button: 0 6px 16px -8px rgba(0,0,0,0.4); /* primary CTA */
}
```

Cards always carry `--shadow-card` + `--border-soft`. Buttons get shadow only when they're the dark primary (Celebrate / Apply).

---

## Motion

| Where | Duration | Easing | Notes |
|---|---|---|---|
| Affirmation toast in | 400ms | `cubic-bezier(.2,.8,.4,1.4)` | overshoot bounce, draws the eye |
| Affirmation toast out | 300ms | ease-out | quick exit |
| Confetti fall | 2.4–3.6s | `cubic-bezier(.2,.6,.4,1)` | 36 pieces, random drift ±40px |
| Sun rising on horizon | 600ms | default | smooth bar progress |
| Filter/sort updates | instant | — | feels responsive |
| Interest dropdown change | instant + 200ms confetti | — | small reward for marking a job |

**Confetti palette:** sun + coral + sky + lilac + mint (the 5 accent colors). Don't introduce a 6th color just for confetti.

---

## Iconography

The design intentionally **does not** use icon-pack icons (Heroicons, Lucide, etc.). It uses:

- A handful of emoji where they read as warm: 🌱 🔥 🎉 ☀ ✿ 💬 🌟 📍
- Simple SVG shapes (the score circle, the paper-plane confetti pieces)
- The capybara mascot (`Capybara` component in `shared-data.jsx`)
- Hand-drawn glyphs in copy: `→`, `·`, `↘`, `♥`, `★`, `○`, `●`

If you must add an icon, draw it as inline SVG with stroke 1.4–1.6px, round caps, in `--color-sub` or `--color-ink`.

---

## Layout

- Page max-width on desktop: **1360px** centered, 24px gutter.
- Card grid: usually `1.2fr 1fr` or `1.6fr 1fr` two-column, with `gap: 16px`.
- Funnel: 6 equal columns with 8px gap and `→` connectors between.
- Table: `1.6fr 1.6fr 0.9fr 0.7fr 0.8fr 0.9fr` for company / role / location / score / interest / action.

---

## Don't

- ❌ Don't introduce gradients beyond the existing 3 (top greeting bar, Pip's pick-me-up card, achievement earned-tile).
- ❌ Don't use pure black (`#000`) or pure white (`#FFF`). Always ink-on-cream or cream-on-ink.
- ❌ Don't use sans-serif for celebratory copy. Caveat for warmth; Fraunces for milestones.
- ❌ Don't use red as a status color. Even "rejected" is `--color-line` (a neutral). Coral is reserved for *positive* warmth ("very interested"), never for failure.
- ❌ Don't tighten letter-spacing below `-0.4px`.
- ❌ Don't use shadows on inline elements (pills, chips). Shadows are for cards and floating toasts only.
