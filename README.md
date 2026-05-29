# job-pipeline

A personal job search dashboard. Scrapes postings from Greenhouse, Lever,
USAJobs, NEOGOV, JobSpy (Indeed/LinkedIn), and a few niche boards; scores
them against your profile; tracks the ones you apply to.

Originally built for a single user's career relaunch. This is the
**generic, shareable** version — every Solongo-specific value has been
moved into `config/` so anyone can customize it for their own search.

## Status

**Functional.** The setup wizard works end-to-end; all six themes
render; slug discovery + the community registry are live. Open to
issues / PRs.

For reference, the opinionated parent project lives at
[solongo-jobs](https://github.com/stansond-afk/solongo-jobs).

## What this gives you

- **Six visual themes** (Paper · Garden · Tide · Quiet Focus · Mountain · Dusk),
  picked during onboarding. Mechanics are identical; voice + palette
  + mascot vary. Paper is the safe default — no mascot, no script font,
  just the work.
- **A daily dashboard** at a private URL on your phone or laptop
- **Hands-off nightly scraping** via GitHub Actions (M/W/F by default)
- **Application tracker** — every job you apply to is logged with its
  resume, cover letter, and a snapshot of the JD
- **Slug auto-discovery** — `scripts/discover_company_universe.py`
  probes ~8,500 companies (S&P 500 + private + SEC EDGAR) against
  Greenhouse + Lever APIs and surfaces working ATS slugs for any of them
- **Community slug registry** — opt in to share your discovered slugs
  with other users + pull theirs (~393 verified slugs available as
  starter coverage)
- **Free to run** (Cloudflare Workers free tier + GitHub Actions free tier)

## What you'll need

- A computer (Mac or Windows, with Python 3.11+ installed)
- A Cloudflare account (free)
- A GitHub account (free)
- About 30 minutes for first-time setup
- *Optional:* a USAJobs API key if you want federal jobs (free, 2 min to get)

## Docs

- **[docs/SETUP.md](docs/SETUP.md)** — first-time setup (wizard or manual)
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — how the layers fit together
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** — adding scrapers, the roadmap, design decisions

## Setup

See [docs/SETUP.md](docs/SETUP.md) for the full walkthrough. Short version:

```bash
git clone https://github.com/stansond-afk/job-pipeline.git
cd job-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/setup.py    # interactive wizard at http://localhost:5051
```

The wizard will ask for your profile details, target roles, location, and
help you set up Cloudflare deploy. After setup runs, your local dashboard
is ready at `http://localhost:5050`.

## Project layout

```
job-pipeline/
├── config/                      # YOUR config (gitignored)
│   ├── profile.yaml             # name, email, location, dashboard copy
│   ├── scoring.yaml             # keyword weights, role filters
│   ├── geo_patterns.yaml        # boost/demote by location
│   ├── search_queries.csv       # JobSpy keyword + location queries
│   └── targets.csv              # companies to scrape (Greenhouse/Lever/NEOGOV)
├── config/*.example.*           # COMMITTED templates the wizard reads
├── scripts/
│   ├── setup.py                 # first-launch wizard
│   ├── scrape_*.py              # one per source
│   ├── score_postings.py        # apply scoring config to postings
│   ├── generate_dashboard.py    # render dashboard HTML
│   └── manual_entry_server.py   # Flask backend for write actions
├── jobpipeline/                 # shared Python package
├── worker/                      # Cloudflare Worker (deployed read-write surface)
├── db/                          # SQLite schema + migrations
├── design/                      # design tokens, voice/tone, component specs
└── docs/                        # SETUP.md, ARCHITECTURE.md
```

## Credits

Originally built by **Stanson Dobbs** ([@stansond-afk](https://github.com/stansond-afk))
as a personal job search system, then generalized into this template fork.
Fork it, customize it, share it back if you make it better.

If you fork this for your own use, please keep the LICENSE intact — that's
the only attribution we ask for.

## License

MIT — see [LICENSE](LICENSE). You can use, modify, and distribute this
freely for any purpose. The license requires you to keep the copyright
notice with any copies you share.
