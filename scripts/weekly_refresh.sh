#!/bin/bash
# Weekly local refresh, scheduled by launchd (com.schermomilano.refresh).
#
# Scrapes every venue from this Mac's residential IP — crucially Cinema Godard, whose ticketing
# Fondazione Prada blocks from cloud/datacenter IPs (so the daily GitHub Actions job can't reach
# it). Then commits the refreshed data and pushes via an SSH deploy key, which triggers a
# Cloudflare rebuild. Runs whenever the Mac is awake near the scheduled time (launchd catches up
# missed runs on wake). Fully hands-off.
#
# Logs: /tmp/schermomilano-refresh.log

set -uo pipefail
REPO="/Users/stefanoveronese/Desktop/Film Aggregator"
KEY="$HOME/.ssh/schermomilano_deploy"
SSH_URL="git@github.com:steveronese/film-aggregator.git"
export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

cd "$REPO" || exit 1
echo "=== refresh $(date) ==="

# Protect any in-progress manual edits: only proceed if nothing uncommitted outside data/cache.
if git status --porcelain | grep -qvE '^.. (data/|scrapers/cache/)'; then
  echo "uncommitted non-data changes present — skipping this week"; exit 0
fi

# Move to the latest remote state (the daily cloud job also commits data), discarding stale data.
git fetch "$SSH_URL" main || { echo "fetch failed"; exit 1; }
git reset --hard FETCH_HEAD

source .venv/bin/activate
set -a; source .env; set +a   # TMDB + Mistral keys + ENABLE_HEADLESS=1 (enables Godard via Playwright)
python -m scrapers.run || { echo "scrape failed"; exit 1; }

git add data scrapers/cache
if git diff --staged --quiet; then
  echo "no data changes"; exit 0
fi
git -c user.name="schermomilano-mac" -c user.email="mac@schermomilano.local" \
    commit -m "data: weekly local refresh incl. Godard ($(date +%F))"
git push "$SSH_URL" HEAD:main && echo "pushed; Cloudflare will redeploy"
