# Deploy the community registry Worker

One-time setup, ~10 minutes. Run on the same machine where you've been
working on this fork. You only do this **once** — your friends never
touch this, they just point at your deployed URL.

---

## Before you start

You need:
- [ ] A Cloudflare account (the one that hosts your personal `solongo-jobs`
      Worker is fine — different Workers don't conflict)
- [ ] Node.js installed (for `npx wrangler`)
- [ ] A terminal in this repo's root directory

Check your terminal works:
```bash
cd ~/Documents/GitHub/job-pipeline-generic
ls worker/registry
# Should show: DEPLOY.md  README.md  index.js  schema.sql  wrangler.template.jsonc
```

---

## Step 1 — authenticate

```bash
cd worker/registry
npx wrangler login
```

A browser window opens. Pick the Cloudflare account, click Allow.

Verify it took:
```bash
npx wrangler whoami
# Should print your Cloudflare email + account ID
```

---

## Step 2 — create the D1 database

```bash
npx wrangler d1 create job-pipeline-registry
```

Output looks like:
```
✅ Successfully created DB 'job-pipeline-registry' in region ENAM
[[d1_databases]]
binding = "DB"
database_name = "job-pipeline-registry"
database_id = "abc12345-6789-..."   ← copy this UUID
```

**Copy the UUID.** You'll paste it in the next step.

---

## Step 3 — fill in the wrangler config

```bash
cp wrangler.template.jsonc wrangler.jsonc
```

Open `worker/registry/wrangler.jsonc` in your editor and replace:
```
"database_id": "${REGISTRY_D1_DATABASE_ID}"
```
with the UUID from step 2:
```
"database_id": "abc12345-6789-..."
```

Save the file. **Do not commit `wrangler.jsonc`** — the `.gitignore` at the repo root already excludes it.

---

## Step 4 — apply the schema

```bash
# Still in worker/registry/
npx wrangler d1 execute job-pipeline-registry --file=schema.sql
```

Output:
```
🌀 Executing on remote database job-pipeline-registry (abc12345-...)
🚣 Executed 5 queries
```

Verify the tables exist:
```bash
npx wrangler d1 execute job-pipeline-registry --command="SELECT name FROM sqlite_master WHERE type='table'"
# Should list: community_submissions, community_consensus
```

---

## Step 5 — deploy

```bash
npx wrangler deploy
```

Output:
```
Total Upload: 4.32 KiB / gzip: 1.78 KiB
Uploaded job-pipeline-registry (1.23 sec)
Deployed job-pipeline-registry triggers (0.45 sec)
  https://job-pipeline-registry.<your-subdomain>.workers.dev
```

**Copy the URL.** You'll use it in the next step.

---

## Step 6 — verify

```bash
curl https://job-pipeline-registry.<your-subdomain>.workers.dev/api/community/health
```

Expected response:
```json
{"ok":true,"server":"registry"}
```

If you get this, the registry is live.

Try the empty registry pull (should return zero rows on a fresh deploy):
```bash
curl 'https://job-pipeline-registry.<your-subdomain>.workers.dev/api/community/slugs?min_submissions=1'
```
```json
{"ok":true,"min_submissions":1,"ats_filter":null,"count":0,"registry":[]}
```

---

## Step 7 — point the client at your URL

If your deployed URL is **exactly**
`https://job-pipeline-registry.stansond.workers.dev`, you're done — that's
the default baked into `scripts/discover_company_universe.py`.

If it's at a different subdomain (e.g. you named the Worker something else,
or your Cloudflare account uses a different workers.dev prefix), update the
default in the script. Open
`~/Documents/GitHub/job-pipeline-generic/scripts/discover_company_universe.py`
and edit:

```python
DEFAULT_REGISTRY_URL = "https://job-pipeline-registry.stansond.workers.dev"
```
↓
```python
DEFAULT_REGISTRY_URL = "https://job-pipeline-registry.<your-actual-subdomain>.workers.dev"
```

Commit + push so your friends pull the correct URL automatically.

Friends can also override per-session via env var without editing the file:
```bash
JOB_PIPELINE_REGISTRY_URL=https://... python3 scripts/discover_company_universe.py update-from-community
```

---

## Step 8 — seed the registry with what you've already discovered

Once the probe currently running finishes (`config/verified_universe.csv`),
seed the registry with your verified slugs so your friends have something
to pull on day one:

```bash
cd ~/Documents/GitHub/job-pipeline-generic
python3 scripts/discover_company_universe.py share
```

It'll show you what's about to be submitted and prompt before sending.
Sample output:
```
About to share 47 verified slugs with the community registry:
  Endpoint:    https://job-pipeline-registry.stansond.workers.dev/...
  Contributor: sha256(your email)

First 5 entries:
  greenhouse  accenturefederalservices  (589 jobs)  Accenture Federal Services
  greenhouse  tegnainc                  (349 jobs)  Tegna Inc.
  ...

Send these to the registry? [y/N]:
```

Confirm with `y`. The registry now has your 47 slugs at
`submission_count = 1`. Friends who run `update-from-community` will
also need at least one more independent submission per slug before the
default `min_submissions >= 2` filter promotes them — *or* they can pass
`--min-submissions=1` if they want to see single-submission entries.

**Practical fix for the day-one cold-start:** if you want your friends'
first `update-from-community` run to actually return slugs, run
`update-from-community --min-submissions=1` on their behalf, or
temporarily bump the default in the client.

Honestly the simplest answer for cold start: **each of you also commits
your verified slugs directly to `config/targets.example.csv`** so they
ship with the fork. The registry adds value once everyone has been
running discovery independently for a few weeks.

---

## Step 9 — share the URL with your friends

When you onboard a friend, give them:

1. The repo URL: `https://github.com/stansond-afk/job-pipeline`
2. The registry URL (only needed if it differs from the default in step 7)
3. A pointer to `docs/SETUP.md`

That's it. They clone the repo, run the wizard, and once they've done
a discovery run of their own, they can `share` back to your registry.

---

## What can go wrong + how to fix it

### `wrangler: command not found`
You don't have Node.js or you're not using `npx`. Either:
- Install Node.js from [nodejs.org](https://nodejs.org), or
- Make sure you're prefixing commands with `npx wrangler`, not bare `wrangler`

### `Error: A worker named "job-pipeline-registry" was found...`
Wrangler thinks the Worker already exists. Two scenarios:
- You ran step 5 twice — that's fine, it just redeploys. Continue.
- A previous failed attempt left a partial Worker. List existing Workers
  with `npx wrangler list` and delete the orphan via
  `npx wrangler delete <name>`.

### `Error: D1_ERROR: no such table: community_submissions`
Step 4 didn't run. Re-run:
```bash
npx wrangler d1 execute job-pipeline-registry --file=schema.sql
```

### Health check returns 404
Wrangler deployed but the route doesn't exist. Causes:
- You deployed from the wrong directory (the repo-root Worker, not
  `worker/registry/`). Make sure `pwd` shows `.../worker/registry`
  before running `npx wrangler deploy`.
- The deploy used a different `wrangler.jsonc`. Delete + re-copy:
  ```bash
  rm wrangler.jsonc && cp wrangler.template.jsonc wrangler.jsonc
  # then edit + redeploy
  ```

### Health check returns 200 but `share` errors
Most likely the `DEFAULT_REGISTRY_URL` in the script doesn't match your
actual deployed URL. See step 7.

### Friends say "I can't reach your registry"
Their machine can probably reach it — verify with:
```bash
curl https://job-pipeline-registry.<your-subdomain>.workers.dev/api/community/health
```
If that works for them too, the issue is likely the `JOB_PIPELINE_REGISTRY_URL`
env var or the `DEFAULT_REGISTRY_URL` in their checkout. Have them
re-pull and check.

---

## Updating the registry Worker later

If you change `worker/registry/index.js` or `schema.sql`:

```bash
cd worker/registry

# Schema changes — apply migration
npx wrangler d1 execute job-pipeline-registry --command="ALTER TABLE ..."
# (D1 doesn't have automatic migrations; you craft the ALTER yourself)

# Code changes — redeploy
npx wrangler deploy
```

Workers redeploy in ~10 seconds with zero downtime. The next request hits
the new code.

---

## If you ever want to wipe + start fresh

```bash
cd worker/registry
npx wrangler d1 execute job-pipeline-registry --command="DELETE FROM community_consensus; DELETE FROM community_submissions;"
```

Or to drop the whole thing:
```bash
npx wrangler d1 delete job-pipeline-registry
npx wrangler delete job-pipeline-registry
```
