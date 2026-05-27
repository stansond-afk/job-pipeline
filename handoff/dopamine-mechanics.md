# Dopamine Mechanics

The reward system. What fires, when, why, and how to wire it.

> **Design principle:** reward inputs Solongo controls, not outputs she doesn't. Submitting an application gets confetti; getting an interview also does. Getting rejected does *not* get a sad face — it gets a quiet status update and a calm-mentor quote next time she opens the app.

---

## The mechanics, at a glance

| # | Mechanic | Trigger | Visible reward |
|---|---|---|---|
| 1 | Daily streak | Any positive action that day | Pill in greeting bar: "🔥 N days · showing up" |
| 2 | Weekly goal | Application submitted | Ring fills toward 15; day-of-week pill turns sun-yellow |
| 3 | Funnel progression | Status field changes | Stage count animates +1; if the new stage was empty, brief glow |
| 4 | Achievement unlock | Milestone reached | Toast + confetti + badge unlocks on shelf (gray → color) |
| 5 | Confetti burst | Any of above | 36 pieces in 5-color palette, 2.4–3.6s fall |
| 6 | Affirmation toast | Application submit, status forward, weekly quota | Floating dark pill with Pip + copy from library |
| 7 | Pick-me-up card | Always present; shuffle on demand | Random baby-animal photo + joke; shuffle button |
| 8 | Momentum sparkline | Always present | 14-day line chart; week-over-week delta callout |

---

## 1. Daily streak

**Definition:** consecutive days with at least one of: marked interest, tailored, submitted, status moved.

**Storage:** Add `streak_log` table or count from `applications.updated_at` + `postings.interest_updated_at` (add this column).

```sql
-- New column for streak tracking
ALTER TABLE postings ADD COLUMN interest_updated_at TEXT;
-- streak_log already implicit in existing timestamps
```

**Computation (Python):**
```python
def current_streak(db):
    """Returns N where N = consecutive days ending today with activity."""
    days = db.execute("""
        SELECT DISTINCT DATE(t) AS d FROM (
            SELECT updated_at AS t FROM applications
            UNION
            SELECT interest_updated_at AS t FROM postings WHERE interest_updated_at IS NOT NULL
        ) ORDER BY d DESC
    """).fetchall()
    streak, today = 0, datetime.now(timezone.utc).date()
    for (d,) in days:
        if date.fromisoformat(d) == today - timedelta(days=streak): streak += 1
        else: break
    return streak
```

**Display:** Greeting bar pill. Sun emoji 🔥 + count + "days · showing up." No celebration when it ticks up (it's silent reinforcement); confetti only on multiples of 7 (achievement-unlock territory).

---

## 2. Weekly goal (15/week)

**Definition:** applications submitted Mon 00:00 → Sun 23:59 local. Counts `status = 'submitted'` rows created in the window.

**Display:** Ring with 7 day-of-week pills underneath. Each pill turns sun-yellow as that day gets ≥1 submit. Hand-written subtitle morphs with progress:

| Progress | Subtitle |
|---|---|
| 0/15 | "Mondays are fresh starts." |
| 1–4/15 | "You're {pct}% of the way there." |
| 5–9/15 | "Halfway, capy! Keep going." |
| 10–14/15 | "So close. {15 - done} more this week and you crush the quota." |
| 15/15 | "**You did it.** 15 in a week. Rest tonight." |
| 15+/15 | "{done} this week. Show-off. 🎉" |

**Reset:** Monday 00:00 local. Don't store last week's count separately; sparkline already has it.

---

## 3. Funnel

The 6 stages: `Active postings → On her radar → Tailored → Applied → Interviewing → Offers`.

Counts derived from existing schema:
- Active postings: `SELECT COUNT(*) FROM postings WHERE is_active = 1`
- On her radar: `interest IN ('interested', 'very_interested')`
- Tailored / Applied / Interviewing / Offers: `applications.status`

**Animation:** when a count increments (poll on dashboard refresh or after `POST /api/apply`), the stat tile briefly scales 1.0 → 1.08 → 1.0 over 400ms and the background flashes 20% brighter for 600ms. No sound.

**Zero state:** dim to 55% opacity. Never hide a stage; the funnel needs to feel like a path even when later stages are empty.

---

## 4. Achievements

Initial set (8). Earned conditions are explicit; pick whichever triggers happen in `persistence.py` and emit an `achievement_unlocked` event the frontend polls or socket-streams.

| ID | Name | Description | Unlock condition |
|---|---|---|---|
| `first_app` | First brave step | Sent your first application | First row in `applications` |
| `tailor_5` | Tailor's apprentice | Tailored 5 resumes | 5 distinct postings have `resume_path` not null |
| `week_streak` | Week one warrior | 7-day streak | `current_streak() >= 7` |
| `interview` | First interview | Status → Interviewing | Any application with `status = 'interviewing'` |
| `apps_10` | Double digits | 10 applications submitted | `COUNT(*) FROM applications WHERE status >= 'submitted' >= 10` |
| `weekly_15` | Quota crusher | Hit 15 in a week | Weekly goal hit |
| `month_streak` | Steady gardener | 30-day streak | `current_streak() >= 30` |
| `offer` | The big one | Receive an offer | Any application with `status = 'offered'` |

**Schema:**
```sql
CREATE TABLE achievements (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  icon TEXT NOT NULL,
  earned_at TEXT,        -- ISO-8601 UTC when unlocked; NULL = locked
  seen_at TEXT           -- when Solongo dismissed the unlock toast; NULL = unread
);
```

**Display:** 4×2 grid. Earned ones get sun-yellow gradient + ✓ corner badge. Locked ones gray and dim to 50%, **but the name/description are still visible** — discovery is part of the reward.

**Unlock reaction:** confetti + special toast ("**Achievement unlocked: {name}** — {description}") that stays 5s, longer than the standard affirmation toast.

---

## 5. Confetti

`ConfettiBurst` component in `shared-data.jsx` is the canonical implementation. 36 pieces, 5-color palette, 2.4–3.6s drift fall. CSS animation, no JS frame loop.

**Variants:**
- Small (12 pieces, 1.5s) — interest dropdown change to "very interested," chip toggles
- Medium (36 pieces, 2.4s) — application submit, status forward
- Large (60 pieces, 4s) — weekly quota hit, achievement unlock
- XL (90 pieces, 5s + slow falling palette of all 5 colors) — offer status (reserved for the big day)

---

## 6. Affirmations

See `voice-and-tone.md § Affirmation library`. Picked randomly; never repeat in a single session. Toast component already implemented in `direction-a.jsx` (`AAffirmation`). Visible for ~3.2s with overshoot-bounce entry.

**Important:** affirmations do NOT fire on small actions (chip click, filter change, scroll). They're for **meaningful** actions: submit, status forward, streak milestone, achievement unlock.

---

## 7. Pick-me-up card

Always present in the dashboard. Two parts:

1. **Baby animal placeholder** — currently a pastel-striped div with a caption. To go live:
   - **Recommended:** rotate from a curated S3 / R2 bucket of 20-30 baby-animal GIFs/photos Stanson uploads. Predictable, no API quotas, can be tuned to Solongo's specific taste.
   - **Alternate:** unsplash.com query for "baby animal" — needs API key, rate-limited but free.
   - **Don't:** generate them. AI baby animals look uncanny.
2. **Joke pair** — `joke.q` + `joke.a`. Static array of 30+ at launch in `solongo_jobs/jokes.py`. Hand-curated, Solongo's taste (mildly self-deprecating about the job market, never punching down).

**Shuffle behavior:** clicking 🎲 advances both joke and photo in lockstep; the pair is the unit. Don't independently shuffle.

**No timer.** Some apps auto-rotate every X seconds — don't. The pick-me-up is *hers* when she wants it.

---

## 8. Momentum sparkline

14 days of application-submit counts. Already implemented (`ASparkline` in `direction-a.jsx`). Below the chart, two lines of context copy:

- Identify the best day: "**Best day:** last Friday (4 apps)."
- Week-over-week delta: "Your pace is up **22%** from last week." (Or "down 22% — Pip says: that's okay.")

Down weeks get a calm-mentor framing, never a red color.

---

## When to NOT fire reward mechanics

These are temptations to resist. They cheapen the real rewards.

- ❌ Confetti on filter changes
- ❌ Confetti on logging in
- ❌ Affirmation every time she views a job
- ❌ "Streak in danger!" anxiety messaging
- ❌ Leaderboards or comparisons to other users
- ❌ Sound effects (the app should be silent)
- ❌ Notifications outside the app (no push, no email — she opens the app on her terms)

---

## Implementation order (suggested)

1. **First:** wire the visual mechanics (ring, funnel animation, sparkline). These work off existing data.
2. **Second:** add the `achievements` table + unlock detection on the existing endpoints.
3. **Third:** add the `streak_log` (or computed-from-existing) + greeting bar streak pill.
4. **Fourth:** add the pick-me-up card with a static joke array and placeholder images.
5. **Fifth:** swap placeholders for real baby-animal source.
6. **Sixth:** consider a daily-Claude-generated joke per `D25` budget.
