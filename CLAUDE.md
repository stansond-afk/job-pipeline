# job-pipeline (generic) — Claude Code instructions

> Public, shareable fork of the personal `solongo-jobs` repo. Parent lives at
> `../solongo-jobs` (or https://github.com/stansond-afk/solongo-jobs).

## What this is

A reusable job search pipeline anyone can fork. Same architecture as the
parent — six scrapers, scoring, dashboard, tracker — but every personal value
moved into `config/` so users customize for their own search.

**Live demo:** none. **Local dashboard:** `http://localhost:5050`.

## Key differences from solongo-jobs

| | solongo-jobs | job-pipeline-generic |
|---|---|---|
| Python package | `solongo_jobs` | `jobpipeline` |
| Profile data | Inlined in code | `config/profile.yaml` |
| Scoring keywords | `config/scoring.yaml` (Solongo's) | `config/scoring.example.yaml` (user customizes) |
| Themes | Garden (hardcoded) | 6 themes (paper/garden/tide/quiet/mountain/dusk), picked by wizard |
| Wizard | none | `scripts/setup.py` Flask-based |
| Community registry | n/a | `scripts/discover_company_universe.py --share` opt-in |

## Layout (deltas from parent)

```
job-pipeline-generic/
├── config/
│   ├── *.example.yaml         # COMMITTED templates the wizard reads
│   └── profile.yaml etc.      # USER config (gitignored after setup)
├── jobpipeline/
│   ├── themes.py              # 6 theme definitions + token validation
│   ├── mascots.py             # SVG renderers + decoration registry
│   └── config.py              # YAML loaders with safe fallbacks
├── scripts/
│   ├── setup.py               # First-launch Flask wizard (8 steps)
│   ├── discover_company_universe.py  # Slug auto-discovery (~8,500 cos)
│   └── (everything else mirrors parent)
├── worker/
│   ├── (dashboard worker — same as parent, theme-aware)
│   └── registry/              # Community slug registry (separate Worker)
│       ├── index.js
│       ├── schema.sql
│       ├── wrangler.template.jsonc   # COMMITTED
│       └── wrangler.jsonc            # GITIGNORED (user fills in D1 UUID)
└── design/                    # 6 theme tokens, voice/tone, components
```

## Running things

```bash
# First-time setup (Flask wizard)
python3 scripts/setup.py
# → http://localhost:5051 in browser, 8 steps

# Local dashboard
python3 scripts/generate_dashboard.py
open dashboard/index.html

# Slug discovery — probes ~8,500 companies for working Greenhouse/Lever boards
python3 scripts/discover_company_universe.py probe

# Opt into community slug sharing (after probe finds some)
python3 scripts/discover_company_universe.py share

# Pull slugs from other users (consensus filter, default min 2 submissions)
python3 scripts/discover_company_universe.py update-from-community
```

## Conventions

- **Theme is a config string.** `profile.yaml` → `dashboard.theme: "paper"`.
  Store the key, not the object (parent decision from handoff/).
- **Paper is the default.** Don't deprecate it — some users actively want
  zero personality.
- **Don't auto-detect theme from system preference.** Users picked
  explicitly, respect that.
- **`wrangler.jsonc` is gitignored.** Only the `.template.jsonc` is
  committed. The user substitutes their D1 UUID locally.
- **Attribution must stay.** LICENSE references "Stanson Dobbs and
  contributors" — preserve when forking.
- **No commits without explicit user ask.** Strict.

## Setup wizard internals

8 steps: welcome → profile → **theme** → scoring → geo → targets →
cloudflare → github → done. Theme picker is step 3, renders 6 swatch
cards from each theme's tokens. Wizard writes `config/profile.yaml`
including legacy `mascot.name` field as fallback hint.

## Community registry

Deployed at `https://job-pipeline-registry.stansond.workers.dev`.
Two-table D1 schema: `community_submissions` (append-only) +
`community_consensus` (materialized view). Contributors are identified
by SHA-256 of their email (opaque, never stores plaintext). Default
consensus filter: ≥2 submissions per slug to surface.

To redeploy or fork your own registry: see `worker/registry/DEPLOY.md`.

## Recent work (June 2026)

Ported the parent's file-size fix: `cleanup_stale.py --min-fit-score 0.05`
DB floor + `RENDER_MIN_FIT_SCORE = 0.15` dashboard filter. Without these,
forks would hit GitHub's 100 MB push wall once their scrape universe
grew past ~10k postings.

## Recent gotchas

1. **`url_telemetry` FK without ON DELETE CASCADE** — same as parent.
   Cleanup NULLs telemetry refs before deleting postings.
2. **`unistr()` not on older sqlite3** — same fix as parent
   (`scripts/fix_unistr.py` in restore pipeline).
3. **Bot account** — `job-pipeline-bot` commits on nightly runs to the
   public fork too. User signs in once via `gh auth login`.
