# Pick-me-up Content Providers

> A small modular system for the dashboard's "pick-me-up" card. Users choose during onboarding what kind of content lives there — or pick none, and the card hides itself.

The pick-me-up is one card on the dashboard. It used to be hardcoded as `(baby animal photo + job-search joke)`. Not everyone wants either. The provider system replaces that with a pluggable registry.

---

## 1. The 7 providers (+ off)

| ID | Name | Kind | What it shows | Default? |
|---|---|---|---|---|
| `quotes` | Quotes | text | Short optimistic lines from people who got through hard things | **on** |
| `history` | On this day | text | A positive event that happened today, with the year | **on** |
| `jokes` | A little joke | text | Mostly-corny one-liners about the job hunt | off |
| `animals` | Baby animals | image+text | A daily warm small-animal photo | off |
| `nature` | Calm scenes | image+text | Quiet places where nothing happens | **on** |
| `breath` | A breath | practice | A 10-second mindfulness prompt | **on** |
| `poems` | A small poem | text | Three or four lines, public domain | off |
| *(none)* | — | — | Card hides entirely | — |

**Default set for new users:** `['quotes', 'history', 'nature', 'breath']` — broad, inoffensive, optimistic, mostly text + image. Job-search jokes and baby animals are off by default because they're polarizing (some users love, some find condescending).

---

## 2. Architecture

`content-providers.jsx` exports:

```js
window.CONTENT_PROVIDERS = {
  quotes:  { id, name, description, blurb, kind, getOne },
  history: {...},
  // ...
};
window.DEFAULT_PROVIDERS = ['quotes', 'history', 'nature', 'breath'];
window.getNextContent(enabledIds, lastIndex);
```

Each provider is a plain JS object with one method:

```js
const QuotesProvider = {
  id: 'quotes',
  name: 'Quotes',
  description: 'Short, optimistic lines from people who got through hard things.',
  blurb: '"Tomorrow is always fresh, with no mistakes in it yet." — L. M. Montgomery',
  kind: 'text',                  // 'text' | 'image+text' | 'practice'
  getOne(date) {                 // date optional; history uses it
    return {
      kind: 'text',
      primary: '...',            // the headline (Hand font)
      secondary: '...',          // the byline / body
      mood: 'reflective',        // affects styling
      multiline: false,          // preserve line breaks?
    };
  },
};
```

`getOne()` returns pure data — no React. The dashboard renders it.

The dashboard cycles fairly through enabled providers: on each shuffle, it advances to the next provider in the user's list, then asks that provider for its content. If the user enabled three providers, three clicks of shuffle cycle through all three before repeating.

---

## 3. Adding a new provider

```js
const HaikuProvider = {
  id: 'haiku',
  name: 'A daily haiku',
  description: 'Three lines. Five-seven-five. Public domain.',
  blurb: 'A new line waits / quietly at the bottom / of every blank page.',
  kind: 'text',
  getOne() {
    const h = HAIKUS[Math.floor(Math.random() * HAIKUS.length)];
    return { kind: 'text', primary: h.lines.join('\n'), secondary: `— ${h.by}`, multiline: true };
  },
};

// register
CONTENT_PROVIDERS.haiku = HaikuProvider;
```

The onboarding picker auto-discovers via `Object.values(CONTENT_PROVIDERS)`. No UI changes needed.

---

## 4. Content rules (universal)

Every provider's content MUST be:

- **Public domain** — no in-copyright quotes, lyrics, or poems past the cutoff.
- **Politically neutral** — no contested figures, no recent political events.
- **Optimistic or calming** — never gallows, never bleak, never "real talk" about how hard the world is.
- **Inclusive** — no references that assume a specific country, religion, family structure, or life stage.
- **Short** — primary ≤ 25 words. Secondary ≤ 12 words.

Curation effort goes here. If a quote or "this day in history" entry fails any of the above, drop it.

---

## 5. "On this day" — date handling

`HistoryProvider.getOne(date)` accepts a `Date` (defaults to today). It keys by `MM-DD`. If a day has no entry, falls back to one of 3 universal lines (`"Today, somewhere, someone is starting over. So are you."`).

Coverage today: ~30 days. Goal: 365. **Curate over time.** Don't bulk-generate via AI — every entry is reviewed by a human against the rules above.

If you want to ship faster: contract a copy editor for a 1-week pass at ~10 entries/day.

---

## 6. Real images for `animals` and `nature`

Both are currently `PhotoPlaceholder` (striped gradients with captions). To ship real images:

**Option A — curated set in `static/`.** ~30 images per provider, randomly selected. Highest control, zero API risk. Recommended for launch.

**Option B — Unsplash / Pexels API.** Random photo from a curated collection. Fresh content forever; requires API key + a content-safety pass.

**Option C — User-uploaded.** Let the user upload their own (kids' photos, pet photos, vacation photos). Most personal; most engineering.

Pick A for v1. The `getOne()` for these providers just needs to return `{ kind: 'image+text', src: '/static/animals/abc.jpg', caption: '...', alt: '...' }` instead of `bg: [...]`. The dashboard already handles `src` in `PhotoPlaceholder` if you extend it (one-line change).

---

## 7. UI surface

**In onboarding (4th section, after personalisation):**

> ### Your pick-me-up corner
> A small daily lift on the dashboard. Pick the kinds you like — or none, and it disappears.

A 2-column grid of provider cards. Each card shows: name, description, an example blurb, and a checkbox. Multi-select.

If the user clears all selections: show an inline note *"None selected — the pick-me-up card will hide itself on your dashboard. That's fine; some people don't want it."* — no scolding, no override.

**In settings (post-onboarding):**

Same 2-column grid, prefilled. Same multi-select.

**On the dashboard:**

The PickMeUp card's kicker line shows the active provider's `name` (e.g. "ON THIS DAY", "QUOTES", "CALM SCENES"). Helps the user know what's about to land.

---

## 8. Server-side

Two new fields on the user model:

```sql
-- providers stored as a JSON-array TEXT column or a comma-separated list
ALTER TABLE users ADD COLUMN providers TEXT DEFAULT '["quotes","history","nature","breath"]';
```

`/api/prefs` GET returns the parsed array; POST accepts an array. Validate against the known keys server-side:

```python
KNOWN_PROVIDERS = {'quotes', 'history', 'jokes', 'animals', 'nature', 'breath', 'poems'}
def is_valid_providers(arr):
    return isinstance(arr, list) and all(p in KNOWN_PROVIDERS for p in arr)
```

---

## 9. Files

```
handoff/code/content-providers.jsx   ← all 7 providers + registry
handoff/code/dashboard.jsx           ← consumes via getNextContent()
handoff/code/onboarding.jsx          ← <ProviderCard> + the picker section
handoff/code/themes.js               ← DEFAULT_PREFS.providers array
```

---

## 10. What the user said

> "Not everyone wants job search jokes or dog photos, we need modularity and ideas on what to fill in those boxes — maybe famous quotes that are optimistic, famous things that happened that day in history that are positive, etc."

This system delivers exactly that: 7 options, multi-select, sensible defaults, and an "off" state for users who want nothing in that corner. The dashboard's pick-me-up is now a content surface, not a hardcoded gimmick.
