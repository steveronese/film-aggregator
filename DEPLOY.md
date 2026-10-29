# Deploying SchermoMilano

The site is static and updates itself daily, with no machine of yours involved. Two pieces:

- **GitHub Actions** (`.github/workflows/scrape.yml`) — runs daily, scrapes every venue, matches
  against TMDB (AI fallback via GitHub Models), validates the build, and commits the refreshed `data/`.
- **Cloudflare Pages** — connected to this repo via Git; rebuilds & deploys the Astro site on every
  push (including the daily data commits). Free.

## How it stays healthy unattended

- **Failure alerts:** if a daily run fails, the workflow opens a GitHub issue titled
  *"Daily refresh is failing"* (GitHub notifies you), comments on it for each further failure, and
  closes it automatically on the next successful run.
- **Graceful degradation:** one broken venue never sinks the run (`fetch_safe`); a venue that returns
  nothing keeps its last-known upcoming screenings; if the AI provider fails, matching falls back to
  fuzzy-only.
- **Site self-pruning:** pages hide past days/films in the browser even if a rebuild is missed, and
  show a "showtimes may be out of date" notice once data is 2+ days old.
- **No expiring credentials for AI:** GitHub Models is called with the job's own `GITHUB_TOKEN`.
- **Bounded growth:** the committed TMDB cache keeps only the fields we use (~2 MB, not 40 MB).
- **Pinned majors:** Python deps are capped at their next major version; Node via `.nvmrc`.

## One-time setup

### 1. GitHub Actions secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**. Add (values are in
your local `.env`, which is gitignored):

| Name | Value |
|---|---|
| `TMDB_ACCESS_TOKEN` | your TMDB v4 read token |
| `SCRAPERAPI_KEY` | ScraperAPI key — fetches Cinema Godard through residential IPs (free tier suffices: ~1 call/day) |

No AI key is needed in CI (GitHub Models uses the workflow token). `MISTRAL_API_KEY` is no longer used
by CI and can be deleted.

### 2. Connect Cloudflare Pages
Cloudflare dashboard → **Workers & Pages → Create → Pages → Connect to Git** → pick
`steveronese/film-aggregator`, then:

- **Framework preset:** None
- **Build command:** `cd site && npm ci && npm run build`
- **Build output directory:** `site/dist`
- (Root directory: leave as `/`. Node version is pinned to 24 via `.nvmrc` — Astro 7 needs ≥ 22.23.
  Don't set a `NODE_VERSION` variable in Cloudflare, or it overrides `.nvmrc`.)

Save & deploy. Cloudflare gives you a `*.pages.dev` URL; add a custom domain later if you want.

### 3. Kick off the first data refresh
Repo → **Actions → "Scrape & publish" → Run workflow**. It scrapes, commits data, and the push
triggers a Cloudflare deploy. After that it runs automatically every morning (~05:00–06:00 Italy).

## Manual entries (museums, one-off screenings)

Venues with no scrapable programme can be added by hand in `scrapers/manual_screenings.yaml`
(edit it directly on GitHub and commit — that triggers a deploy):

```yaml
screenings:
  - cinema_id: godard
    raw_title: "Priscilla"
    start: "2026-06-15T20:30:00"
    language: "original_subbed"
```

## Optional: local refresh (launchd, on a Mac)

Not needed any more — the cloud job reaches every venue, Godard included. `scripts/weekly_refresh.sh`
and `scripts/com.schermomilano.refresh.plist` remain for running a refresh from a residential IP
(Playwright, `ENABLE_HEADLESS=1`). If used, the repo must live outside `~/Desktop`, `~/Documents`
and `~/Downloads` (macOS blocks launchd jobs there). Logs: `/tmp/schermomilano-refresh.log`.

## Notes
- TMDB/AI lookups are cached in `scrapers/cache/` (committed), so daily runs stay well within free tiers.
