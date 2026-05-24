# job-pipeline

A personal job search dashboard. Scrapes postings from Greenhouse, Lever,
USAJobs, NEOGOV, JobSpy (Indeed/LinkedIn), and a few niche boards; scores
them against your profile; tracks the ones you apply to.

Originally built for a single user's career relaunch. This is the
**generic, shareable** version — every Solongo-specific value has been
moved into `config/` so anyone can customize it for their own search.

## Status

🚧 **Under construction.** The generic fork is mid-build. See the
parent project ([solongo-jobs](https://github.com/stansond-afk/solongo-jobs))
for a working, opinionated version.

## What this gives you

- A daily dashboard at a private URL on your phone or laptop
- Hands-off nightly scraping via GitHub Actions
- Application tracker — every job you apply to is logged with its resume,
  cover letter, and a snapshot of the JD
- Free to run (Cloudflare Workers free tier + GitHub Actions free tier)

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
git clone https://github.com/<your-username>/job-pipeline.git
cd job-pipeline
python scripts/setup.py    # interactive wizard
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
