# Daily AI Briefing

A personal, automatically generated digest of AI news — published daily at [bboyett.github.io/ai-briefing](https://bboyett.github.io/ai-briefing).

## What it is

Each morning the site updates with a new briefing pulling the latest AI headlines from across the web — including TechCrunch, The Verge, MIT Technology Review, VentureBeat, NYT Technology, Bloomberg, Wired, Fox Business, Hacker News, and more. Every source gets its own section with up to 6 stories, each linking out to the original article.

The site has five pages:

- **Home** — a chronological list of every daily briefing
- **Briefings** — each day's full digest, organized by source
- **Sources** — a directory of every publication that has appeared in the briefing, with a full article archive per source
- **Blog** — Ben's own posts (news commentary, things learned while using AI) plus an About Me section. See `blog_posts/README.md` for how to write a new post
- **Search** — client-side search across every article ever published, with a basic keyword mode and an advanced mode (date range/specific date, one or more sources, keywords)

Sources known to require a subscription (currently NYT, MIT Technology Review, and Bloomberg) are flagged with a small "Subscription may be required" note shown once per source, not per article.

## How it works

`generate_briefing.py` is a Python script that runs once a day (via a GitHub Actions cron job). It:

1. Scrapes each news source — either via RSS feed or by fetching and parsing the HTML page directly
2. Filters feeds that cover general tech (Bloomberg, TechRadar, etc.) down to AI-relevant articles using keyword matching, and filters out ads/event promos (e.g. TechCrunch Disrupt promos) using a title/creator pattern check
3. Builds HTML files from scratch — the daily briefing page, the homepage index, per-source archive pages, the blog, and the search page/index
4. Saves article metadata to `entries.json` and `source_data.json` so the archive pages stay up to date across runs

There is also a `generate_test.py` script for manually testing new sources. It runs the same scrapers but saves output to a timestamped file and adds a collapsible "Test Runs" section to the homepage, separate from the real daily briefings.

The site is fully static — no backend, no database, no dependencies beyond the generated HTML files (search runs entirely in the browser against a generated `search_index.json`).

## Keeping your local clone in sync

Because GitHub Actions commits new briefing files to this repo every day, your local `main` branch falls behind quickly, which can cause push conflicts. Run `.\sync.ps1` (PowerShell) any time before you start editing and again before you push — it stashes local changes if needed, pulls and rebases onto the latest `origin/main`, then commits and pushes your changes. Pass a custom commit message with `.\sync.ps1 -Message "..."`.
