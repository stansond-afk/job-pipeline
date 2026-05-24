#!/usr/bin/env bash
# deploy.sh — refresh the deployed dashboard AND keep the SQL dump in sync.
#
# What this does:
#   1. Regenerates dashboard/index.html from the current local DB
#   2. Dumps db/jobs.db → db/jobs.sql.gz (so GitHub Actions and Cloudflare see fresh data)
#   3. Commits whatever changed (dashboard, dump, or both)
#   4. Pushes to GitHub
#   5. Cloudflare picks up the push and redeploys (~30 sec)
#
# Use after running scrapers locally:
#   $ python scripts/scrape_jobspy.py
#   $ python scripts/score_postings.py
#   $ python scripts/cleanup_stale.py     # optional but recommended
#   $ ./deploy.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "→ Regenerating dashboard/index.html…"
python scripts/generate_dashboard.py

echo "→ Dumping DB → db/jobs.sql.gz…"
bash scripts/db_dump.sh

# Stage what may have changed. git add is a no-op for unchanged files.
git add dashboard/index.html db/jobs.sql.gz

# Only commit if something actually changed.
if git diff --staged --quiet; then
  echo "→ Nothing changed. Skipping commit/push."
  exit 0
fi

TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
git commit -m "Refresh dashboard ($TIMESTAMP)"

echo "→ Pushing to GitHub (Cloudflare will redeploy automatically)…"
git push

echo ""
echo "✓ Done. Cloudflare will redeploy in ~30 sec."
echo "  Live: <your-worker>.workers.dev"
