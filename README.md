# Milan Film Aggregator

A simple, fast, cheap-to-run website that aggregates what films — especially the niche,
hard-to-find, original-language ones — are playing across Milan's cinemas. All film metadata is
canonicalized through [TMDB](https://www.themoviedb.org/).

## How it works

```
Python scrapers  →  TMDB matching (cached)  →  data/*.json  →  Astro static site  →  CDN
   (per cinema)       (build time only)         (committed)      (no server/DB)
```

A scheduled job runs the scrapers daily, matches each screening's (often messy, Italian) title to a
canonical TMDB film, and writes JSON. The Astro site builds static pages from that JSON, so visitors
only ever hit a CDN — no server, no database, no runtime API calls.

## Layout

- `scrapers/` — Python. One module per cinema under `scrapers/cinemas/`. Run with `python -m scrapers.run`.
- `data/` — build output consumed by the site (`screenings.json`, `films.json`, `cinemas.json`, `unmatched.json`).
- `site/` — Astro static site.

## Development

```bash
# Scrapers
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export TMDB_ACCESS_TOKEN=...   # TMDB v4 read access token (optional offline; required for live matching)
python -m scrapers.run

# Site
cd site && npm install && npm run dev
```

## TMDB attribution

This product uses the TMDB API but is not endorsed or certified by TMDB.
