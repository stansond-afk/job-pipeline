# Development

For anyone picking this up to extend it. ARCHITECTURE.md explains *how
it's built*; this doc explains *what to build next* and the patterns
to follow when you do.

If you're new here, read in this order:
1. [SETUP.md](SETUP.md) — get a working dashboard
2. [ARCHITECTURE.md](ARCHITECTURE.md) — understand the layers
3. This file — pick a project

---

## Local dev workflow

```bash
git clone https://github.com/<your-fork>/job-pipeline.git
cd job-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Get a working DB:
cp config/profile.example.yaml config/profile.yaml   # edit as needed
python3 scripts/init_db.py
for m in db/migrate_*.py; do python3 "$m"; done

# One full pass:
python3 scripts/scrape_greenhouse.py
python3 scripts/score_postings.py
python3 scripts/generate_dashboard.py
open dashboard/index.html
```

The fast feedback loop while iterating on scoring or dashboard rendering:
edit code → `python3 scripts/score_postings.py && python3 scripts/generate_dashboard.py`
→ refresh the browser. Both run against the local SQLite in seconds.

For testing the deployed-write path (Worker + D1), run
`scripts/manual_entry_server.py` — that gives you a Flask server with
the same API surface so you don't need to deploy to test write flows.

---

## Adding a new scraper

The minimal pattern, in order:

1. **Pick your data source.** Some questions:
   - Does it have a public API? (Cheap to build, robust over time.)
   - JSON endpoint? RSS feed? HTML scrape? (In that order of preference.)
   - Does it require auth / API key? (Document in `.env.example` + the
     wizard's secrets-collection step.)

2. **Create `scripts/scrape_<source>.py`.** Use
   [scripts/scrape_greenhouse.py](../scripts/scrape_greenhouse.py) as
   the template — it's the cleanest example.

3. **Load targets from `config/`.** Either extend `config/targets.csv`
   with a new `ats=<your-source>` value, or create a dedicated
   `config/<source>_targets.csv` if your source's data shape is
   different enough to warrant separation.

4. **For each target, fetch + parse postings.** Use
   `requests` for simple HTTP; `python-jobspy` if it's a major board
   (you're probably duplicating work — check first); Playwright (not
   yet a dep) if you need a JS runtime.

5. **Build `jobpipeline.models.Posting` dataclasses.** Required fields:
   `source`, `source_job_id`, `company`, `role`, `url`, `first_seen`,
   `last_seen`, `is_active`. Optional but valuable:
   `location`, `jd_text`, `posted_at`, `department`.

6. **Persist via `jobpipeline.persistence.upsert_posting(conn, posting,
   now)`.** This handles dedup against `(source, source_job_id)`,
   writes URL telemetry automatically (so D32 analyzer picks up your
   new source for free), and updates `last_seen` on re-scrape.

7. **Log a `SourceRun` row** via `jobpipeline.persistence.log_run`.
   Gives the audit trail when your scraper later breaks silently.

8. **Add a step to `.github/workflows/nightly-scrape.yml`.** Pattern:

   ```yaml
   - name: Scrape <source>
     run: python3 scripts/scrape_<source>.py
     timeout-minutes: 10
     continue-on-error: true   # ← critical (see D30 below)
   ```

9. **Test by running locally.** Then re-score + regenerate dashboard.

**Pitfalls to avoid:**

- **Don't bypass `upsert_posting`.** Direct SQL INSERTs skip the URL
  telemetry hook + the dedup constraint. (See "D33" in the original
  project state for the war story.)
- **Don't make the new step block downstream.** If your scraper fails,
  the rest of the nightly should still run. `continue-on-error: true`.
- **Don't rate-limit yourself blind.** Add `time.sleep(0.5)` between
  requests; respect any `Retry-After` headers; identify yourself
  honestly in the `User-Agent` (the original repo uses
  `"job-pipeline/0.1 (personal job search tooling)"`).

---

## Roadmap — what's worth building next

These are sized estimates from the original Solongo build experience.
Sequential numbering is suggestion, not law — pick whatever motivates you.

### Phase 3a: Niche boards (1 session each, high-yield)

These tend to be RSS or simple JSON APIs. Each one adds 50-300 new
high-quality postings if they're in your domain.

| Source                       | Why it's interesting                                    | Effort |
|------------------------------|---------------------------------------------------------|--------|
| **ReliefWeb v2**             | International development / humanitarian (when approved) | 1 day  |
| **Idealist.org**             | Nonprofit jobs                                          | 1 day  |
| **GreenBiz**                 | Sustainability career portal                            | ½ day  |
| **Conservation Careers**     | Environmental / wildlife jobs                           | ½ day  |
| **DevNetJobs**               | International development jobs                          | 1 day  |
| **Handshake**                | Early-career / new-grad                                 | 2 days |
| **USAID / State Dept**       | Beyond what USAJobs already covers                      | 1 day  |

Pattern: each becomes a `scripts/scrape_<source>.py`. Some need an
allowlisted user agent; document in `.env.example`.

### Phase 3b: ATS slug auto-discovery — **SHIPPED**

**The S&P 500 scraper, generalized.** Lives at
`scripts/discover_company_universe.py`. Aggregates ~650 companies from
Wikipedia (S&P 500 + largest US by revenue + largest private), probes
each against Greenhouse + Lever APIs, verifies hits by fetching board
metadata and inspecting actual posting content. False-positive rate
~5% post-verification.

Usage:

```bash
# Re-scrape Wikipedia sources (quarterly is fine)
python scripts/discover_company_universe.py refresh

# Probe each company (~60 min due to rate limiting)
python scripts/discover_company_universe.py probe

# Validate hits (~5 min)
python scripts/discover_company_universe.py verify

# Or all three:
python scripts/discover_company_universe.py all
```

Output: `config/verified_universe.csv`. Review, copy `verdict=verified`
rows into `config/targets.csv`, re-scrape, enjoy the coverage gain.

**Yield benchmark (first real run, June 2026):** ~650 companies probed,
~50-100 verified board hits, including major brands not in Solongo's
original 248-company master list. False positives caught by the
verifier (would have been silent disasters):

- `greenhouse:national` claimed by 4+ different "National X" orgs
  (correctly flagged duplicate)
- `greenhouse:capital` is some EU tech company, NOT Capital One
- `greenhouse:oliver` is OLIVER Agency, NOT Oliver Wyman
- `greenhouse:rockymountain` is an orthopedic clinic, NOT RMI

**Extending the universe** — to widen the candidate pool, add a new
`fetch_<source>()` function to the script and include it in `SOURCES`.
Good candidates:

- Forbes Best Midsize Companies (~400 in $1-10B revenue range)
- Crunchbase free tier (unicorn list — private $1B+ valuations)
- SEC EDGAR XBRL data (every US-listed public company with revenue >$1B)
- Inc. 5000 (fastest-growing US private — many are smaller but might
  use Greenhouse)

**Complementary signal — URL telemetry (D32):** the `url_telemetry`
table also records observed `ats_slug` values from every URL we
ingest via JobSpy. `scripts/analyze_telemetry.py` surfaces companies
seen at `boards.greenhouse.io/<slug>` that are NOT in `targets.csv`
— often even faster path to new coverage than full probing. Use
both: telemetry-from-JobSpy for whatever ATSes Solongo encounters
in practice; universe-probing for proactive expansion to companies
JobSpy hasn't surfaced yet.

**Community slug registry (shared infra):** the project also ships
with a community registry — a separate Cloudflare Worker deployed by
the maintainer that pools verified slugs across all forks. Two opt-in
subcommands:

```bash
# After verify, optionally upload your verified slugs to the community
python scripts/discover_company_universe.py share

# Pull community-verified slugs + prompt to merge into your targets.csv
python scripts/discover_company_universe.py update-from-community
```

The registry's GET endpoint returns slugs with `submission_count >= 2`
by default — a single bad-faith submission can't pollute the canonical
list. Your email address is hashed locally before submission so the
registry never sees plaintext PII. Full details in
[../worker/registry/README.md](../worker/registry/README.md).

For the maintainer: see that README for the one-time Cloudflare
deploy of the registry Worker. Forks point at it automatically via
the `JOB_PIPELINE_REGISTRY_URL` env var (default = the maintainer's
deployed URL).

### Phase 3c: Playwright adapters (3-5 sessions)

The big ATSes that need a JavaScript runtime. URL telemetry already
shows what's worth prioritizing for *your* search — run
`python3 scripts/analyze_telemetry.py` and look at the top ATS counts.

Original Solongo build's priority order from the analyzer (after ~2
weeks of data):

| Adapter     | Tenants found via JobSpy | Postings  | Effort     |
|-------------|--------------------------|-----------|------------|
| **Workday** | 75 distinct tenants      | 118+      | ~3 sessions|
| **iCIMS**   | 18 companies             | ~50       | ~1-2 sessions |
| **BambooHR**| 12 companies             | ~30       | ~1 session |
| **Avature** | ~8 tenants               | ~20       | ~1 session |
| **Paycom**  | ~5 tenants               | ~15       | ~½ session |

**Where to start with Workday:** the
[chuchro3/WebCrawler](https://github.com/chuchro3/WebCrawler) repo has
an open-source Workday scraper that handles most of the tenant-by-tenant
quirks. Borrow + adapt rather than building from scratch — Workday is
hostile to scrapers and you'll burn weeks chasing edge cases otherwise.

### Phase 4: AI enrichment (1-2 sessions, optional)

The original Solongo system was designed with per-posting Claude API
calls in mind — a 3-line role summary + compatibility rating against the
user's master profile. Got **deferred** in session 12 because the API
billing is separate from Claude Pro and the daily operator wanted to
keep monthly costs at $0.

If you want to revisit:

- ~$5-15/month at full enrichment scale (Haiku 4.5 pricing)
- One combined Claude call per posting (summary + compatibility)
- Cache by JD-text hash so re-scoring is free
- Storage: `postings.ai_summary` (TEXT) + `postings.compatibility` (JSON)
  + `postings.compatibility_score` (REAL) + `postings.jd_text_hash` (TEXT)

The triage UX gain is real (richer JD snippets, predicted-fit signal)
but only worth it if you find yourself spending >5 minutes per Strong
fit deciding to apply.

**A safer alternative:** local LLM. `llama.cpp` + a small instruct model
(7B-13B params) for batch summarization — slower but $0 marginal cost.
Quality is below Haiku 4.5 but acceptable for the "extract a 3-line
summary" task.

### Phase 5: Learning loop (2 sessions, **proceed with caution**)

The original idea: feed Claude the list of jobs the user applied to vs.
skipped, derive patterns ("you pass on roles requiring travel >50%"),
adjust the scorer weights.

The original Solongo build **chose not to ship this** after surfacing
the filter-bubble concern: if "jobs like the ones she applied to"
sort to the top, she stops seeing the rest. In a tough job market
where she needed flexibility, that's an active harm.

If you build this, consider the **anti-bubble framing instead**: use
her positive signals to find her *pattern*, then actively surface
strong fits *outside* that pattern. "Outside your usual" card on the
dashboard.

---

## Punchlist (small fixes, no urgency)

These accumulated in the original repo. They're starter-friendly:

- ⬜ **NEOGOV Loudoun County feed timing out.** Intermittent 30s connect
  timeout. Either retry, or accept the loss (5 of 6 NEOGOV agencies
  work, JobSpy covers same roles redundantly).
- ⬜ **Glassdoor 400 / location-not-parsed errors.** JobSpy quirk,
  upstream issue. Check the [python-jobspy issue tracker](https://github.com/cullenwatson/JobSpy/issues)
  for fixes before working around.
- ⬜ **JobSpy `linkedin_fetch_description=True` adds ~30s per
  LinkedIn search.** Worth it for the JD text quality, but the first
  scrape from a fresh DB is slow. Could be made async / parallel.
- ⬜ **First-launch DB seeding.** Currently the user has to run
  `init_db.py` + four migrations in sequence. The wizard should do
  this in one step.
- ⬜ **Dashboard pagination doesn't survive a page reload.** Current
  page index is in JS state only. Could persist in `localStorage` if
  someone wants it.
- ⬜ **`analyze_telemetry.py` output is text-only.** Could become a
  dashboard card showing "top 5 coverage gaps this week" with one-click
  "add to targets.csv" buttons.

---

## Design decisions worth knowing about

These came from the original Solongo project and apply to anything you
build on top of this codebase.

**D30 — Steps in critical pipelines default to `continue-on-error: true`.**
A single bad API response once caused a `sys.exit(1)` that aborted every
downstream step (scrapers, scoring, dashboard regen, dump, commit, push)
under GitHub Actions' default semantics. Silent total engine freeze for
several days. Now the rule: pipeline steps should fail loudly via the
workflow log, but **never** block subsequent steps unless that step is
structurally required for them. Exceptions: setup steps (checkout,
install deps, restore DB). Everything else: `continue-on-error: true`.

**D32 — URL telemetry on every posting.** Every URL that lands in the
postings table gets a `url_telemetry` row tagged with domain / ATS guess
/ ATS slug / source. This is how the slug-gap detector works (Phase 3b).
**Critical:** any new scraper that bypasses `upsert_posting` and writes
direct SQL skips telemetry. Always route through `upsert_posting`.

**D33 — Merge handlers route through `upsert_posting`, not direct SQL
INSERT.** Same reason: telemetry side-effect + dedup. Cost is ~4 extra
lines (lookup posting_id after upsert for downstream scoring).

**Default to anti-bubble UX for any learning feature.** Filter bubbles
silently narrow the user's view. The original Solongo build skipped
the learning loop entirely rather than ship a filter-bubble risk. Any
re-attempt should surface variety, not similarity.

---

## Releasing changes

The original Solongo workflow:

1. Edit code locally, test against your DB.
2. `./deploy.sh` — regenerates dashboard, dumps DB, commits, pushes,
   Cloudflare auto-deploys in ~30 sec.
3. GitHub Actions runs the next M/W/F nightly automatically.

For a feature with config implications (new YAML key, new env var,
etc.) you must also:
- Update `.example` files so future users get the new field
- Update the wizard (scripts/setup.py) to prompt for it
- Update `docs/SETUP.md` if it changes the user-facing flow
- Update `docs/ARCHITECTURE.md` if it changes the architecture

---

## Getting help

The codebase is documented inline. Start by reading the file you want
to extend — every non-trivial function has a docstring. If you're stuck,
the [original Solongo repo](https://github.com/stansond-afk/solongo-jobs)
has session logs going back to 2026-04-17 (every decision is annotated
with date + rationale + "trigger for revisit").
