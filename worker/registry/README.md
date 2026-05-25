# Community registry Worker

The shared infrastructure that lets users of this project contribute
discovered ATS slugs to a common pool. Anyone who uses
`discover_company_universe.py` can:

1. **Pull** the current registry as part of their next discovery run
   (`update-from-community` subcommand). This gives them all
   community-verified slugs as candidates to add to their `config/targets.csv`.

2. **Submit** their own verified slugs after running `verify`
   (opt-in prompt at the end of the verify step).

## Architecture

Two-tier storage:

  - `community_submissions` — append-only log. One row per
    `(slug, contributor)`. Re-submissions silently dedupe.

  - `community_consensus` — materialized view. One row per `(ats, slug)`,
    with `submission_count`. The pull endpoint defaults to
    `min_submissions >= 2` so a single bad-faith contribution can't
    pollute the canonical list.

Trust model: **anonymous-with-soft-identity**. Submissions don't require
auth, but each contributor sends `contributor_email_hash = sha256(their_email)`
which:

- Lets us dedupe re-submissions (UNIQUE constraint on the hash + slug)
- Enforces a 1000-submissions-per-contributor-per-day abuse cap
- Doesn't reveal the email — we never store the plaintext

## Deployment (one time, by the maintainer)

```bash
cd worker/registry

# 1. Authenticate with the same Cloudflare account that hosts your
#    personal Worker
npx wrangler login

# 2. Create the D1 database
npx wrangler d1 create job-pipeline-registry
# It prints a UUID — copy it.

# 3. Fill in the template
cp wrangler.template.jsonc wrangler.jsonc
# Edit: replace ${REGISTRY_D1_DATABASE_ID} with the UUID from step 2

# 4. Apply the schema
npx wrangler d1 execute job-pipeline-registry --file=schema.sql

# 5. Deploy
npx wrangler deploy

# 6. Verify
curl https://job-pipeline-registry.<your-subdomain>.workers.dev/api/community/health
# Should return: {"ok":true,"server":"registry"}
```

The deployed URL goes into the project's defaults so forks point at it
automatically — see the `JOB_PIPELINE_REGISTRY_URL` constant in
`scripts/discover_company_universe.py`.

## API

### GET /api/community/health
Up-check. Returns `{ok: true, server: "registry"}`.

### GET /api/community/slugs
Returns the consensus registry.

Query parameters:
- `min_submissions=N` — only include slugs with ≥ N independent submissions.
  Default: 2.
- `ats=greenhouse` — filter to one ATS.

Response:
```json
{
  "ok": true,
  "min_submissions": 2,
  "count": 142,
  "registry": [
    {
      "ats": "greenhouse",
      "slug": "notion",
      "company_canonical": "Notion Labs",
      "submission_count": 4,
      "first_seen": "2026-05-10T14:30:00Z",
      "last_seen": "2026-05-24T09:15:00Z"
    },
    ...
  ]
}
```

### POST /api/community/submit-slugs
Submit verified slugs. Body:

```json
{
  "contributor_email_hash": "<sha256(your email, hex)>",
  "submissions": [
    {
      "ats": "greenhouse",
      "slug": "notion",
      "company_hint": "Notion Labs",
      "job_count_observed": 47
    }
  ]
}
```

Limits:
- 200 submissions per request
- 1000 submissions per contributor per day
- ATS must be in the known-platform list
- slug must match `^[a-z0-9][a-z0-9_-]{0,80}$`

Response:
```json
{ "ok": true, "accepted": 4, "duplicates": 1, "rejected": 0 }
```

## Manual moderation

The consensus table holds rows immediately upon first submission, but
the GET endpoint only returns rows with `submission_count >= 2` by default
(controllable via `min_submissions` query param).

If you want to manually purge bad data:

```bash
npx wrangler d1 execute job-pipeline-registry --command "
  DELETE FROM community_consensus WHERE ats = 'greenhouse' AND slug = 'bad_slug';
  DELETE FROM community_submissions WHERE ats = 'greenhouse' AND slug = 'bad_slug';
"
```

## Cost

Cloudflare D1 free tier:
- 5 GB storage (our usage: ~1 MB even at 10,000 slugs)
- 5M reads / day
- 100K writes / day

Realistic usage with 10 active forks each submitting weekly:
- Reads: ~100/day (each fork pulls registry on `update-from-community`)
- Writes: ~50/day (each fork submits ~5 new slugs per discovery run)

Free tier handles this with 5 orders of magnitude to spare.
