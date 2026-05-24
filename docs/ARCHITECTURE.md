# Architecture

For contributors. How the system fits together.

## Layered view

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR PERSONAL CONFIG (gitignored)                              │
│  config/profile.yaml  scoring.yaml  geo_patterns.yaml  *.csv    │
│  .env                                                            │
│  wrangler.jsonc (generated)                                      │
└─────────────────────────────────────────────────────────────────┘
              │ read by every script via jobpipeline.config
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SHARED PACKAGE  jobpipeline/                                   │
│  ─────────────────────────────────────────────────────────────  │
│  config.py   db.py   models.py   persistence.py                 │
│  geo.py      achievements.py     jokes.py                       │
│  tailored_files.py  cleanup.py   url_telemetry.py               │
└─────────────────────────────────────────────────────────────────┘
              ▲                                       ▲
              │ imported by                           │
┌─────────────┴────────────────┐         ┌────────────┴───────────┐
│  SCRAPERS  scripts/scrape_*  │         │  DASHBOARD             │
│  greenhouse  lever  neogov   │         │  scripts/              │
│  jobspy  usajobs  greenjobs  │         │   generate_dashboard.py│
└──────────────────────────────┘         │   manual_entry_server  │
              │                          └────────────────────────┘
              ▼                                       │
┌─────────────────────────────────────────────────────┴───────────┐
│  LOCAL DB  db/jobs.db (SQLite — gitignored)                     │
│  ────────────────────────────────────────────────────────────── │
│  postings (~5K rows after a week)                               │
│  applications (everything the user applied to)                  │
│  source_log (audit trail of scraper runs)                       │
│  url_telemetry (coverage-gap signal)                            │
│  achievements (8 milestone unlocks)                             │
└─────────────────────────────────────────────────────────────────┘
              │ dumped to db/jobs.sql.gz, committed to git
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  GITHUB ACTIONS  .github/workflows/nightly-scrape.yml           │
│  Restore DB from dump → run scrapers → score → generate         │
│  dashboard → dump back → commit → push                          │
└─────────────────────────────────────────────────────────────────┘
              │ Cloudflare auto-deploys on push
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  CLOUDFLARE WORKER  worker/index.js                             │
│  Serves dashboard/ + handles write endpoints (Interest /        │
│  Status / Apply / Add Job) via D1 events                        │
└─────────────────────────────────────────────────────────────────┘
              ▲
              │ user actions on phone or laptop hit these endpoints
┌─────────────┴───────────────────────────────────────────────────┐
│  DEPLOYED DASHBOARD  https://<your-worker>.workers.dev          │
│  Protected by Cloudflare Access (your email only)               │
└─────────────────────────────────────────────────────────────────┘
```

## Data flow

### Daily scrape (M/W/F via GitHub Actions, or manually via deploy.sh)

1. Workflow restores `db/jobs.db` from `db/jobs.sql.gz`
2. Workflow runs `merge_d1_events.py` — pulls any interest/status changes
   the user made from the deployed dashboard since the last run
3. Each scraper (`scrape_greenhouse.py`, `scrape_lever.py`, etc.) reads
   `config/targets.csv` (Greenhouse/Lever/NEOGOV) or
   `config/search_queries.csv` / `config/usajobs_queries.csv` (JobSpy/USAJobs)
   and inserts new postings via `jobpipeline.persistence.upsert_posting`
4. `cleanup_stale.py` deletes postings whose `last_seen` is older than 14 days
5. `score_postings.py` reads `config/scoring.yaml` + `config/geo_patterns.yaml`,
   applies the scoring algorithm, updates `fit_score` + `score_notes`
6. `generate_dashboard.py` reads everything + outputs `dashboard/index.html`
7. `generate_postings_snapshot.py` outputs `dashboard/postings.json`
   (compact data for the Worker's Apply modal pre-fill)
8. `db_dump.sh` writes `db/jobs.sql.gz`
9. Workflow commits everything, pushes — Cloudflare auto-deploys

### User interaction (deployed dashboard)

1. User opens the deployed URL → Cloudflare Access checks their email →
   they're in
2. Page loads static HTML — all postings already pre-rendered (paginated
   client-side)
3. User clicks "Interest: ♥ Very interested" on a row
4. JS sends `POST /api/posting/<id>/interest` to the Worker
5. Worker writes an event to D1 (`events` table with `event_type='interest'`)
6. Next nightly run picks up the event in step 2 above, applies it to
   the canonical SQLite DB

### User interaction (local — manual_entry_server.py)

If the user runs `python3 scripts/manual_entry_server.py` on their laptop
(via `launch.sh`), the dashboard's JS detects localhost and routes writes
to the Flask server instead of the Worker. The Flask server writes directly
to the local SQLite DB. Useful for "Add Job" with file path discovery
(which the Worker can't do — no filesystem).

## Why this split?

**SQLite locally + dump committed to git:** the workflow needs persistent
state, but committing a binary SQLite file diff-clobbers git history. The
text SQL dump compresses well (~3MB for ~5K postings) and produces clean
diffs.

**Cloudflare Worker + D1 for writes only:** the user wants to triage on
their phone but doesn't want a full-blown server. The Worker has no
filesystem; D1 stores ephemeral write events; the nightly merge does
the actual reconciliation.

**Config in YAML, not the wizard's database:** YAML edits cleanly in
git (the user can `git diff config/scoring.yaml` to see how their
scoring evolved). The wizard just writes the YAML.

**`*.example.*` fallback pattern:** every script that reads from
`config/foo.yaml` falls back to `config/foo.example.yaml` if the
personal file doesn't exist. Lets the project run end-to-end before
the wizard is ever run, useful for CI / development.

## Key modules

### jobpipeline.config

Central YAML loader + convenience accessors. Every other module calls
`config.short_name()`, `config.weekly_goal()`, `config.role_blacklist()`,
etc. Cached + `reload()` available for the wizard.

### jobpipeline.geo

Geographic tier detection. Reads `boost.patterns` from config; foreign
country tokens are baked in (universal); US state detection prevents
"London, KY" from being misclassified.

### jobpipeline.achievements

Streak / weekly progress / sparkline / funnel / today's picks /
achievement unlock detection. All read-only (computed from postings +
applications tables). The unlock detection writes to the achievements
table.

### jobpipeline.persistence

`upsert_posting` (the dedup-by-source-job-id workhorse),
`upsert_application`, status/interest update helpers. The functions
the scrapers and Flask server both call.

### scripts/score_postings.py

The scoring algorithm: title gate → keyword weight accumulator →
raw-to-0-1 curve → geographic adjustment. ~170 lines of code, all
patterns + weights come from config.

### scripts/generate_dashboard.py

Renders `dashboard/index.html`. ~2900 lines because the design has
many sections (greeting bar, weekly ring, sparkline, funnel, today's
picks, pick-me-up, achievements shelf, full table with pagination).
All user-facing strings interpolate `config.short_name()` and
`config.mascot_name()` at render time.

### worker/index.js

The deployed read-write surface. Validates the Cloudflare Access JWT
on every write endpoint. Pulls posting data from
`dashboard/postings.json` (the snapshot the workflow generates).

## Adding a new scraper

Pattern to follow:

1. Create `scripts/scrape_<source>.py`
2. Read your target list from `config/<source>_targets.csv` (or extend
   `config/targets.csv` with a new `ats=<source>` value)
3. For each target, fetch + parse postings
4. Use `jobpipeline.models.Posting` dataclass for each result
5. Call `jobpipeline.persistence.upsert_posting(conn, posting, now)` —
   handles the dedup constraint, URL telemetry, etc.
6. Log a `SourceRun` row via `jobpipeline.persistence.log_run`
7. Add to the workflow's `nightly-scrape.yml` (with its own
   `continue-on-error: true` step so a failure in your scraper doesn't
   tank the whole nightly)

The existing scrapers (`scrape_greenhouse.py`, `scrape_jobspy.py`)
are good references.

## Adding a new dashboard section

Anything you add lives in `scripts/generate_dashboard.py`:

1. Add a render function returning HTML
2. Call it from `_build_body_html`
3. Add CSS to `_build_css`
4. Add any JS to `_build_js`
5. If you need new backend data, add a query to
   `jobpipeline/achievements.py` (or a new module if it's substantial)
