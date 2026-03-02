# Daily AI Briefing

A personal, automatically generated digest of AI news — published daily at [bboyett.github.io/ai-briefing](https://bboyett.github.io/ai-briefing).

## What it is

Each morning the site updates with a new briefing pulling the latest AI headlines from across the web — including TechCrunch, The Verge, MIT Technology Review, VentureBeat, NYT Technology, Bloomberg, Wired, Fox Business, Hacker News, and more. Every source gets its own section with up to 6 stories, each linking out to the original article.

The site has three pages:

- **Home** — a chronological list of every daily briefing
- **Briefings** — each day's full digest, organized by source
- **Sources** — a directory of every publication that has appeared in the briefing, with a full article archive per source

## How it works

`generate_briefing.py` is a Python script that runs once a day (via a GitHub Actions cron job). It:

1. Scrapes each news source — either via RSS feed or by fetching and parsing the HTML page directly
2. Filters feeds that cover general tech (Bloomberg, TechRadar, etc.) down to AI-relevant articles using keyword matching
3. Builds three sets of HTML files from scratch — the daily briefing page, the homepage index, and the per-source archive pages
4. Saves article metadata to `entries.json` and `source_data.json` so the archive pages stay up to date across runs

There is also a `generate_test.py` script for manually testing new sources. It runs the same scrapers but saves output to a timestamped file and adds a collapsible "Test Runs" section to the homepage, separate from the real daily briefings.

The site is fully static — no backend, no database, no dependencies beyond the generated HTML files.
