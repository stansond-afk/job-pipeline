# Onboarding Spec — The First-Run Theme Picker

> **Source of truth:** `code/onboarding.jsx`. This doc describes intent and what the component asks for / writes.

The first thing a new user sees. One screen, scrollable, 880px max-width. Asks four questions and shows a live preview that updates as they choose.

---

## 1. Goal

Get the user from "I just signed up" to "this app feels personal to me" in under 60 seconds, with a calm first impression that doesn't feel like a corporate onboarding wizard.

**Non-goals:**

- Don't ask for permissions, payment, integrations, or any task-related info. Just personalization.
- Don't ask "what kind of job are you looking for?" — that comes later, in the actual job-search flow.
- Don't enforce a multi-step wizard. One scrollable page.

---

## 2. The 4 sections

### Section 1 · Pick your space (theme)

A 2×3 grid of theme cards. Each card shows:

- A **mini swatch** (88px tall) with the theme's decoration, mascot (if any), 5 color dots from the palette, and a serif "Aa" preview.
- The **theme name** in 15px Inter 600.
- The **tagline** in 11px uppercase Inter 600 ("warm · soft · hand-written").
- The **blurb** in 12px Inter 400 (1-sentence description).

Selected state: 2px accent border + ✓ badge + subtle background tint.

Order:

```
[ Paper   ] [ Garden  ]
[ Tide    ] [ Quiet   ]
[ Mountain] [ Dusk    ]
```

Default selection: **Paper**.

### Section 2 · Want a companion? (mascot toggle — conditional)

**Only shown when the selected theme has a mascot** (Garden / Tide / Dusk).

Two pill toggles:

- "Yes — {mascotName} stays" (active by default)
- "No mascot — just initials"

Writes `prefs.mascotEnabled` boolean.

### Section 3 · Tell us about you

Two text inputs:

- **Your first name** — placeholder "Solongo". Writes `prefs.name`.
- **Who's in your corner?** — placeholder "Stanson, my partner". Writes `prefs.supporter`. Optional.

Plus a checkbox below:

- "Show me a 'you are loved' reminder on the dashboard." Writes `prefs.showPersonalNote`.

Default: name = "" (use placeholder text), supporter = "" (love note silently disables), showPersonalNote = true.

### Section 4 · Live preview strip

A miniature greeting bar (the `<PreviewCard>` component) showing what the user's actual dashboard will look like, given their current selections. Updates as they tap themes / toggle mascot / type their name.

Includes the theme's mascot or monogram, the greeting line in its theme-specific phrasing, the name with theme-specific suffix, the mascot quote, and the celebrate button.

---

## 3. The "Open my dashboard →" CTA

Bottom right of the page. Ink-on-cream button. On click:

1. `POST /api/prefs` with the full prefs object
2. Mark `users.onboarded_at = now()`
3. Redirect to `/` (dashboard)

Left of the button: a small `var(--ob-sub)` note saying *"You can change any of this later from the dashboard settings."*

---

## 4. Onboarding chrome palette

The onboarding screen has its **own neutral palette**, regardless of which theme the user is previewing. This prevents the page itself from feeling like a theme has already been imposed.

```js
const obStyle = {
  '--ob-bg':     '#FAF8F3',
  '--ob-paper':  '#FFFFFF',
  '--ob-ink':    '#1A1A1A',
  '--ob-sub':    '#6B6B6B',
  '--ob-line':   'rgba(0,0,0,0.1)',
  '--ob-accent': '#2C5282',
};
```

Inter for everything except the page title (which uses Fraunces 500 for warmth).

---

## 5. Hero copy

> **Welcome to Jobline.**
>
> Looking for a job is hard. We made this calm on purpose. Pick a feel that fits you — you can change it any time.

Above it: a small kicker pill: `STEP 1 · MAKE IT YOURS`.

This is the whole hero. No marketing copy. No feature list. The page is functional.

---

## 6. Pre-selection persistence

If the user navigates away mid-onboarding (e.g. closes the tab), preserve their in-progress selection so reopening `/onboard` resumes:

- Client-side: `localStorage` is fine (cheap, no backend round-trip)
- Server-side: optionally write a draft prefs row keyed by user_id with `is_draft=1`

Either is acceptable. localStorage is simpler.

---

## 7. Re-entry to onboarding

After the user has onboarded, the `/onboard` page is still reachable from the settings page (link: *"Re-do my setup"*). Visiting it pre-fills with their current prefs and lets them change everything from scratch. Same `POST /api/prefs` on submit.

---

## 8. Accessibility

- Theme cards are `<button>` elements with `aria-pressed={selected}`.
- The live preview is decorative — `aria-hidden="true"`.
- Form inputs have proper `<label>` association.
- Color is never the only signal of state: ✓ badge + border weight + background change all combine.
- Tap targets ≥ 44px (theme cards are way over; inputs and toggles meet it).

---

## 9. Empty / error states

- No internet on submit: keep the form filled, show a small toast "Couldn't save — try again." Don't reset.
- API returns 400 (e.g. server-side validation): show inline error near the offending field.

---

## 10. After-launch follow-on (out of scope for v1)

These come later:

- A second screen for "What kinds of jobs?" — filters + locations preferences
- Resume upload step
- Integration with USAJobs / Greenhouse credentials

Don't bundle these into v1. The point of v1 is *just the theme picker* — get them in the door, let them feel the calm.
