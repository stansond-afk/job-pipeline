# Voice & Tone — Universal Rules + Per-Theme Variation

The voice does the heaviest lifting in this design. Without it, the palette is decoration. With it, every interaction is the product saying *we see you, this is hard, you're doing it anyway.*

This is a public product now, so the voice has to scale across users — but the *core stance* doesn't change between themes. Only the *register* changes.

---

## 1. Universal core stance

> The user is doing a hard thing slowly. Every word reflects that we know it, we see them, and we are quietly on their side.

This holds for every theme. Always.

Three modes the voice shifts between, picked contextually:

| Mode | When | Universal example |
|---|---|---|
| **Cheerleader** | Milestones (first app, quota hit, streak day) | "You did it. 15 in a week — that's a real number." |
| **Calm mentor** | Setbacks (rejection, missed day, no responses) | "Beautiful work showing up today. Onward." |
| **Steady narrator** | Routine moments, chrome, button labels | varies by theme |

Use **steady narrator** in chrome by default. Reserve **cheerleader** for big confetti moments. Reserve **calm mentor** for when a number goes the wrong way.

---

## 2. What we never do (any theme)

- ❌ **Toxic positivity.** "Every rejection is a blessing!" No. Rejection is data, not a verdict — that's the universal framing.
- ❌ **Hustle-culture metaphors.** No "grind," "crush it," "level up your career," "10x your search."
- ❌ **Faux urgency.** No "act fast," "don't miss out," countdown timers, scarcity tricks.
- ❌ **Generic AI cheerfulness.** "Great choice!" after every click numbs fast. Reserve praise for actions that took effort.
- ❌ **Diminishing copy.** No "just," "only," "simply." Those tell the user the thing they're struggling with should be easy.
- ❌ **Comparisons to other users.** No leaderboards. No "you're in the top 20%." Their search is their search.
- ❌ **Anxiety triggers.** No "streak in danger" warnings. No red colors on negative deltas. Calm framing always.

These apply to all 6 themes without exception.

---

## 3. Per-theme register

Each theme picks a personality on the affirmation/greeting register. The *content* stays universally calm; the *delivery* changes.

| Theme | Register | Example affirmation |
|---|---|---|
| **Paper** | Declarative, calm, no decoration | "You sent applications today. That is real work." |
| **Garden** | Gentle friend, occasional emoji, hand-written accents | "Look at you go." / "You're doing the hard thing, slowly." |
| **Tide** | Soft, oceanic metaphors (sparingly) | "A 'no' is one wave. There are more." |
| **Quiet Focus** | Stoic mentor, no emoji, no exclamations | "Quiet, consistent — that's the work." |
| **Mountain** | Grounded guide, path metaphors | "Mountains are climbed by people who kept walking." |
| **Dusk** | Soft companion, evening-light language | "The day is closing. You did your part." |

**Always check before writing new copy:** does it sound like the theme's voice? If you wrote a Quiet Focus affirmation and it has a heart emoji in it, it's wrong. If you wrote a Garden affirmation and it sounds like a drill sergeant, it's wrong.

---

## 4. The "someone loves you" line

The love-note pill below the greeting bar is unique to this product and worth getting right.

**With supporter name:**

> "{supporter_name} thinks you are the best thing in the world. {mascot_name ? mascot_name + " agrees." : "We agree."}"

**Without supporter name (`supporter_name = ''` or `'someone'`):**

> "Remember — you are loved. You are the best thing in someone's world."

**Tone notes:**

- It's intentionally cheesy. The user opted in. Don't dilute it.
- It's never plural ("you are loved by many people") — too generic.
- It's never anonymous in the with-supporter case. Naming a specific person makes it land.
- It's dismissible. If the user clicks the ×, don't show it again that session.
- It re-appears on next login. The point is that they forgot they were loved; we're reminding them.

---

## 5. Greeting bar copy patterns

Each theme has a pattern. The dashboard fills `{name}` from prefs.

| Theme | Pattern | Example |
|---|---|---|
| Paper | `"Good morning, {name}."` | "Good morning, Alex." |
| Garden | `"good morning, {name} ☀"` | "good morning, Solongo ☀" |
| Tide | `"hello, {name}."` | "hello, Riley." |
| Quiet | `"Good morning, {name}."` | "Good morning, Jordan." |
| Mountain | `"Good morning, {name}."` | "Good morning, Sam." |
| Dusk | `"good evening, {name}."` | "good evening, Casey." |

(Mountain and Quiet share a pattern but the typography pulls them apart visually.)

Rotate the time-of-day prefix client-side based on local hour. The mascot quote rotates from a static list per theme — pick at page load, don't change mid-session.

---

## 6. Affirmation toasts — when they fire

This is unchanged from the previous handoff but worth re-stating because it's load-bearing:

| Action | UI response |
|---|---|
| Mark a job "very interested" | Subtle confetti (12 pieces). No toast. |
| Click Tailor → | Affirmation toast with cheerleader-ish copy. |
| Submit an application | **Big** confetti (36 pieces) + cheerleader toast + +1 on weekly ring |
| Hit weekly quota (15) | Bigger confetti (60 pieces, 4s) + special toast: *"15 in a week. That's a number to be proud of."* |
| Status moves forward (submitted → interviewing) | Confetti + cheerleader toast: *"Interviewing. They want to meet you."* |
| Mark a job "pass" | No celebration. Row dims. |
| Day-7 streak | Confetti + achievement unlock |

Toast content comes from `theme.copy.affirmations` (a 7-item array per theme). Pick randomly; don't repeat in a session.

---

## 7. Empty states (per theme)

The previous handoff's empty-state copy was Garden-specific ("Pip suggests clearing filters…"). For the multi-theme system, the dashboard either:

- (a) **Uses theme.copy.* keys** for empty states (cleanest; add new keys as needed), or
- (b) **Falls back to a universal calm string** when the theme doesn't override.

Recommended universal fallbacks if (b):

| Empty state | Universal copy |
|---|---|
| No matching jobs after filter | "Nothing matches that combo." + "*Try clearing the filters.*" |
| Achievement still locked | (Badge dims to 50%; no copy — discovery is the reward.) |
| Zero applications this week | "0 of 15 this week. Mondays are fresh starts." |
| No baby-animal yet | "A photo will appear in a moment." |
| Server offline (mobile read-only) | "read-only · mobile" |

For Garden/Tide/Dusk you can override with theme-flavored variants (Pip / Marlow / Vesper).

---

## 8. Numbers and stats

Always pair a number with a feeling or a frame, never raw.

| Bad | Good (universal) |
|---|---|
| "Conversion rate: 0.6%" | "47 on your radar → 1 interview. Each step is a real thing you did." |
| "0 applications today" | "today's a blank page" (G/T/D) / "0 of 15 this week" (P/Q/M) |
| "Streak: 7" | "7 days, in a row" (P/M/Q/T) / "7 days showing up 🔥" (G) / "7 nights of showing up ✦" (D) |
| "Score: 86" | (just the number in the chip — the chip color does the qualitative work) |

---

## 9. Calm-mentor moments

The most-important register. Used when something goes wrong from the user's perspective.

| Trigger | Universal copy direction |
|---|---|
| Application marked rejected | No automatic toast. On *next* dashboard open, greeting Pip-line shifts to: *"rejection is data, not a verdict."* (or theme equivalent). |
| 3+ days no activity | "Missed a few days — that's okay. Your spot is held." (Top of dashboard, dismissible.) |
| No matches in 2 weeks | "The well is quiet right now. That's the market, not you." |

These appear in all themes. Per-theme tone adjustment is fine but the *message* doesn't change.

---

## 10. How copy gets written for new features

The 5-step process (unchanged from previous handoff, still right):

1. Draft the functional sentence first ("Click here to upload your resume").
2. Strip imperative if possible ("Drop your resume here").
3. Add specificity if it fits in 9 words or less.
4. Read it out loud. If it sounds like a chipper LinkedIn ad, soften it.
5. If in doubt, the calm mentor is always right.

**Extra step for the multi-theme product:**

6. Decide if the copy needs to vary per theme. If it carries personality, yes — add it to `theme.copy.*` for each theme. If it's purely functional ("Apply", "Cancel"), no — leave it hardcoded in the component.

---

## 11. Mascot voice (the 3 themes that have one)

| Mascot | Theme | Voice |
|---|---|---|
| **Pip** (capybara) | Garden | Calm, steady, slightly amused by the absurdity of the job market. Speaks in short sentences. Quietly proud. |
| **Marlow** (otter) | Tide | Floats. Doesn't push. Comments occasionally. Likes warm water. |
| **Vesper** (luna moth) | Dusk | Speaks softly because it's evening. Sees things in low light. |

**When in doubt for any mascot:** would a very calm version of this animal say this? If yes, ship. If no, rewrite.

None of the mascots are ever sarcastic about the user. Occasionally sarcastic about employers (Pip: *"'we'll get back to you' is the most expensive lie in tech."*) — sparingly.
