# Setup Guide

Step-by-step instructions for getting `job-pipeline` running for you (or
someone you're helping). About 30 minutes for a first-time setup.

## What you'll need

- A computer with Python 3.11+ installed
- About 30 minutes
- An email you want to use as your "job-search" identity
- A list of companies you'd like to track (you can also start blank and add later)
- *Optional:* a [USAJobs API key](https://developer.usajobs.gov/apirequest/)
  (free, ~2 minutes, only needed if you want federal jobs)

## What you'll set up

By the end of this guide you'll have:

1. A local dashboard at `http://localhost:5050`
2. A deployed, private dashboard at a URL only you can access
3. A scheduled job that scrapes new postings on a cron schedule
4. An applications tracker that remembers everything you've applied to

---

## Path A: Use the setup wizard (Recommended)

```bash
git clone https://github.com/<your-github>/job-pipeline.git
cd job-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/setup.py
```

The wizard opens in your browser at `http://localhost:5051`. Follow the
prompts. Each step explains what it's doing and why. You can pause and
resume anytime — your answers are saved as you go.

Step-by-step the wizard will:

1. **Profile** — your name, email, where you live, your target role
   families. Saved to `config/profile.yaml`.
2. **Scoring** — keyword groups that reflect your target domain. The
   wizard suggests starter weights; you customize. Saved to
   `config/scoring.yaml`.
3. **Geographic preferences** — your target metro, remote-OK,
   relocate-OK. Saved to `config/geo_patterns.yaml`.
4. **Targets** — pick from the 248-company starter list (mostly
   DC-area, but you can curate). Add your own. Saved to
   `config/targets.csv`.
5. **Search queries** — the wizard generates JobSpy + USAJobs queries
   from your profile. You can edit. Saved to
   `config/search_queries.csv` + `config/usajobs_queries.csv`.
6. **Cloudflare** *(optional but recommended)* — sign in with your
   Cloudflare account; the wizard creates a D1 database, deploys the
   Worker, sets up Cloudflare Access (email-protected URL). Saved to
   `.env` + `wrangler.jsonc`.
7. **First scrape** — runs all scrapers, scores postings, generates
   the dashboard. Should take ~10 minutes the first time.
8. **GitHub Actions** *(optional)* — push your repo and add the
   secrets the wizard tells you about. Cron starts running.

When the wizard finishes, run:

```bash
./launch.sh    # opens the dashboard locally
```

---

## Path B: Manual setup (skip the wizard)

If you'd rather edit YAML files by hand, here's the minimum:

### 1. Install + clone

```bash
git clone https://github.com/<your-github>/job-pipeline.git
cd job-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Copy + customize config

```bash
cp config/profile.example.yaml      config/profile.yaml
cp config/scoring.example.yaml      config/scoring.yaml
cp config/geo_patterns.example.yaml config/geo_patterns.yaml
cp config/targets.example.csv       config/targets.csv
cp config/search_queries.example.csv config/search_queries.csv
cp config/usajobs_queries.example.csv config/usajobs_queries.csv
cp .env.example .env
```

Open each `config/*.yaml` in your editor and fill in the values (every
field is commented). For `targets.csv` and the query CSVs, open in
Excel/Numbers/Google Sheets — they're easier to edit there.

### 3. Initialize the local DB

```bash
python3 scripts/init_db.py
python3 db/migrate_001_application_columns.py
python3 db/migrate_002_interest_level.py
python3 db/migrate_003_url_telemetry.py
python3 db/migrate_004_achievements_streak.py
```

### 4. Run your first scrape

```bash
python3 scripts/scrape_greenhouse.py
python3 scripts/scrape_lever.py
python3 scripts/scrape_neogov.py
python3 scripts/scrape_jobspy.py           # this one takes ~10 min
python3 scripts/scrape_usajobs.py          # only if you set up the API key
```

### 5. Score and generate the dashboard

```bash
python3 scripts/score_postings.py
python3 scripts/generate_dashboard.py
open dashboard/index.html
```

### 6. *(Optional)* Deploy to Cloudflare

This is where the wizard saves the most time, but you can do it
manually:

```bash
# Install wrangler
npm install -g wrangler

# Authenticate
wrangler login

# Create D1 database (note the UUID it returns)
wrangler d1 create job-pipeline-events

# Set up Cloudflare Access (in dashboard.cloudflare.com → Zero Trust)
# Note the AUD value from the Access application

# Fill in .env with D1_DATABASE_ID and ACCESS_AUD
# Generate wrangler.jsonc:
bash scripts/build_wrangler.sh

# Deploy
wrangler deploy
```

### 7. *(Optional)* Set up scheduled scraping via GitHub Actions

Push the repo to your own GitHub. Then in repo settings → Secrets →
Actions, add:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `D1_DATABASE_ID`
- `ACCESS_AUD`
- `USAJOBS_API_KEY` *(if using)*
- `USAJOBS_USER_AGENT` *(if using; this is your email)*

The workflow runs M/W/F at 7 AM UTC. You can also trigger it manually
from the Actions tab.

---

## Troubleshooting

**"`python: command not found`":** use `python3` instead, or set up an
alias. (Some scripts call `python` directly — the wizard handles this;
manual setup may need a small edit to `db_restore.sh`.)

**Dashboard renders but shows 0 postings:** scrape probably failed.
Check the terminal output where you ran `scrape_*.py`. The most common
cause is missing `.env` credentials.

**Cloudflare deploy fails with "wrangler: command not found":**
`npm install -g wrangler` (requires Node.js installed).

**JobSpy hangs on LinkedIn for 10+ minutes:** normal. `linkedin_fetch_description`
is on by default; it costs ~30 sec per LinkedIn result for full JD text.
The first scrape can be slow; subsequent runs use `hours_old=168` so
they're much faster.

**"D1 database does not exist":** you ran `wrangler deploy` before
`wrangler d1 create`. Create the database first, copy the UUID into
`.env`, regenerate `wrangler.jsonc`, then deploy.

---

## What to do next

- **Use it daily.** Open the dashboard, mark jobs as
  Interested / Very interested / Pass.
- **Add jobs you find elsewhere.** Click "+ Add Job" in the dashboard,
  paste a URL or JD text. The system auto-fetches and scores it.
- **Apply.** Click `Apply →` on any row, fill in the modal with your
  tailored resume + cover letter paths, save. The application is
  logged with a JD snapshot you can reference forever.
- **Tune scoring.** After 2 weeks of use, if you notice the wrong jobs
  are surfacing, edit `config/scoring.yaml` to adjust keyword weights.
  Re-run `python3 scripts/score_postings.py`.
