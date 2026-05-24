# Design

This folder is reference material for anyone tweaking the dashboard look.

The dashboard itself is fully self-contained — `scripts/generate_dashboard.py`
produces a single HTML file with embedded CSS. The CSS variables match the
tokens in [design-tokens.md](design-tokens.md), so this folder is the source
of truth for what colors / fonts / radii / shadows mean.

## Quick reference

- **[design-tokens.md](design-tokens.md)** — colors, typography, spacing, radii,
  shadows, motion. Copy any of these values when adding new components.

## Design principles (carried over from the original)

1. **Encouragement over metrics.** Numbers always paired with affect.
2. **Reward inputs, not outputs.** Confetti when the user submits an
   application, never when an employer responds.
3. **Soften without infantilizing.** Warm pastels + hand-written accents
   + the mascot. But the data + filters + status workflow are real and
   respect the user's intelligence.

## Customizing the look

Per-user customization (mascot name, footer text, weekly goal target,
greeting copy) lives in `config/profile.yaml`. Anything visual that should
be consistent across users (palette, typography, spacing) lives here.
