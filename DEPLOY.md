# Deploying SchermoMilano

The site is static and updates itself daily. Two pieces:

- **GitHub Actions** (`.github/workflows/scrape.yml`) — runs daily, scrapes every venue, matches
  against TMDB (AI fallback via Mistral), validates the build, and commits the refreshed `data/`.
- **Cloudflare Pages** — connected to this repo via Git; rebuilds & deploys the Astro site on every
  push (including the daily data commits). Free.

## One-time setup

### 1. GitHub Actions secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**. Add (values are in
your local `.env`, which is gitignored):

| Name | Value |
|---|---|
| `TMDB_ACCESS_TOKEN` | your TMDB v4 read token |
| `MISTRAL_API_KEY` | your Mistral API key |

### 2. Connect Cloudflare Pages
Cloudflare dashboard → **Workers & Pages → Create → Pages → Connect to Git** → pick
`steveronese/film-aggregator`, then:

- **Framework preset:** None
- **Build command:** `cd site && npm ci && npm run build`
- **Build output directory:** `site/dist`
- (Root directory: leave as `/`. Node version is pinned to 20 via `.nvmrc`.)

Save & deploy. Cloudflare gives you a `*.pages.dev` URL; add a custom domain later if you want.

### 3. Kick off the first data refresh
Repo → **Actions → "Scrape & publish" → Run workflow**. It scrapes, commits data, and the push
triggers a Cloudflare deploy. After that it runs automatically every morning (~07:00 Italy).

## Notes
- The daily job installs headless Chromium (`playwright install chromium`) for the WAF-protected
  Cinema Godard scraper — already handled in the workflow.
- TMDB/AI lookups are cached in `scrapers/cache/` (committed), so daily runs stay well within free tiers.
