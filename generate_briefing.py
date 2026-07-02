"""
Daily AI Briefing — Blog Generator

Generates:
  briefings/YYYY-MM-DD.html   — daily briefing (only shows sources that returned stories)
  index.html                  — homepage listing all past briefings
  sources.html                — all sources ever used, with descriptions
  sources/<slug>.html         — per-source page: articles grouped by date
"""

import os
import re
import html
import json
import requests
import markdown as md
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── AI relevance filter (used for general-tech feeds that aren't already AI-only) ──
AI_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "llm", "gpt",
    "chatgpt", "openai", "anthropic", "deepmind", "neural", "model",
    "chatbot", "generative", "automation", "robotics",
}

def is_ai_relevant(title, summary=""):
    combined = (title + " " + summary).lower()
    return any(kw in combined for kw in AI_KEYWORDS)


# ── Advertisement / promo filter ────────────────────────────────────────────────
# Some feeds (e.g. TechCrunch) mix in event promos and sponsored posts alongside
# real articles. Filter those out so ads never get linked in a briefing.
AD_CREATORS = {
    "techcrunch events", "techcrunch brand studio", "sponsored content",
    "partner content", "brand studio",
}
AD_TITLE_PATTERN = re.compile(
    r"(disrupt\s?\d{4}|buy (your )?(tickets|pass)|book your ticket|"
    r"save \$\d|\d+%\s*off|early bird|last chance to save|promo code|"
    r"presented by|sponsored content|partner content|"
    r"exhibit(or)? (table|package)|advertisement)",
    re.I,
)

def is_advertisement(title, creator=""):
    if creator and creator.strip().lower() in AD_CREATORS:
        return True
    return bool(AD_TITLE_PATTERN.search(title))

# ── Source Registry ────────────────────────────────────────────────────────────
# Every possible source. Add new ones here — if scraping fails, it just won't appear.

SOURCE_META = {
    "techcrunch": {
        "name": "TechCrunch AI",
        "slug": "techcrunch",
        "color": "#2c3e6b",
        "url": "https://techcrunch.com/category/artificial-intelligence/",
        "description": (
            "TechCrunch is one of the leading technology media properties, dedicated to "
            "obsessively profiling startups, reviewing new internet products, and breaking "
            "tech news. Their AI section covers funding rounds, product launches, and "
            "policy developments across the AI industry."
        ),
    },
    "arstechnica": {
        "name": "Ars Technica AI",
        "slug": "arstechnica",
        "color": "#cc0000",
        "url": "https://arstechnica.com/ai/",
        "description": (
            "Ars Technica has covered technology since 1998 with a reputation for technical "
            "depth and rigorous reporting. Their dedicated AI section covers research "
            "breakthroughs, policy developments, and the industry moves that matter — "
            "written for technically literate readers who want the 'how', not just the 'what'."
        ),
    },
    "zdnet": {
        "name": "ZDNet AI",
        "slug": "zdnet",
        "color": "#d4000d",
        "url": "https://www.zdnet.com/topic/artificial-intelligence/",
        "description": (
            "ZDNet covers technology for business and IT professionals. Their AI topic "
            "section focuses on enterprise adoption, product launches, and practical "
            "implications of AI tools — a grounded counterweight to more research-focused "
            "publications."
        ),
    },
    "rundown": {
        "name": "The Rundown AI",
        "slug": "rundown",
        "color": "#8b1a1a",
        "url": "https://www.therundown.ai/articles",
        "description": (
            "The Rundown AI is a newsletter and news site read by over 2 million subscribers. "
            "It delivers concise, accessible summaries of the most important AI developments "
            "each day — focused on helping readers understand why stories matter and how to "
            "apply them in their work."
        ),
    },
    "verge": {
        "name": "The Verge",
        "slug": "verge",
        "color": "#1a5c3a",
        "url": "https://www.theverge.com/ai-artificial-intelligence",
        "description": (
            "The Verge covers the intersection of technology, science, art, and culture. "
            "Their AI coverage explores both the technical developments and the broader "
            "societal implications — including ethics, labor, creative industries, and "
            "the companies driving the AI boom."
        ),
    },
    "venturebeat": {
        "name": "VentureBeat",
        "slug": "venturebeat",
        "color": "#6b3a1a",
        "url": "https://venturebeat.com/category/ai/",
        "description": (
            "VentureBeat covers transformative technology news and events for enterprise "
            "technology decision-makers. Their AI coverage focuses on enterprise applications, "
            "research breakthroughs, and the business strategies of major AI companies."
        ),
    },
    "nyt": {
        "name": "NYT Technology",
        "slug": "nyt",
        "color": "#2c2c2c",
        "paywalled": True,
        "url": "https://www.nytimes.com/section/technology",
        "description": (
            "The New York Times Technology section provides in-depth reporting on the "
            "people, companies, and ideas shaping the digital world. Their AI coverage "
            "ranges from consumer-facing products to national security implications, "
            "with a focus on impact and accountability journalism."
        ),
    },
    "mit": {
        "name": "MIT Technology Review",
        "slug": "mit",
        "color": "#8b0000",
        "paywalled": True,
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/",
        "description": (
            "MIT Technology Review is one of the world's oldest and most respected technology "
            "publications, founded in 1899. Their AI coverage is known for deep, rigorous "
            "reporting on research, policy, and the long-term implications of emerging "
            "technology — written for a technically literate audience."
        ),
    },
    "wired": {
        "name": "Wired",
        "slug": "wired",
        "color": "#1a1a1a",
        "url": "https://www.wired.com/tag/artificial-intelligence/",
        "description": (
            "Wired is a monthly American magazine and online publication that focuses on how "
            "emerging technologies affect culture, the economy, and politics. Their AI coverage "
            "spans consumer products, research breakthroughs, and the social consequences of "
            "automation and machine intelligence."
        ),
    },
    "foxbusiness": {
        "name": "Fox Business Technology",
        "slug": "foxbusiness",
        "color": "#003366",
        "url": "https://www.foxbusiness.com/technology",
        "description": (
            "Fox Business covers technology through a business and markets lens, reporting on "
            "earnings, executive moves, policy impacts, and the financial stakes of AI and "
            "big tech. Their technology section is a key source for Wall Street's perspective "
            "on the industry."
        ),
    },
    "hackernews": {
        "name": "Hacker News",
        "slug": "hackernews",
        "color": "#ff6600",
        "url": "https://news.ycombinator.com/",
        "description": (
            "Hacker News is a social news site run by Y Combinator, read primarily by software "
            "engineers, founders, and researchers. Its front page surfaces the most discussed "
            "links in the tech and AI community each day — making it a reliable signal of what "
            "practitioners are paying attention to."
        ),
    },
    "bloomberg": {
        "name": "Bloomberg Technology",
        "slug": "bloomberg",
        "color": "#1b1464",
        "paywalled": True,
        "url": "https://www.bloomberg.com/technology",
        "description": (
            "Bloomberg Technology covers the business of tech with a focus on markets, "
            "enterprise, and the global economy. Their AI reporting tracks investment trends, "
            "corporate strategy, and the financial impact of AI across every sector."
        ),
    },
    "techradar": {
        "name": "TechRadar",
        "slug": "techradar",
        "color": "#0057a8",
        "url": "https://www.techradar.com/tag/artificial-intelligence",
        "description": (
            "TechRadar is a leading consumer technology news and reviews site. Their AI coverage "
            "focuses on practical applications, new product launches, and how AI is being "
            "integrated into everyday software and hardware."
        ),
    },
    "siliconvalley": {
        "name": "Silicon Valley News",
        "slug": "siliconvalley",
        "color": "#2e7d32",
        "url": "https://www.siliconvalley.com/technology/",
        "description": (
            "Silicon Valley News covers the tech industry from the heart of the Bay Area, "
            "reporting on startups, established giants, and the culture of innovation. "
            "Their AI coverage reflects the ground-level view from inside the industry."
        ),
    },
    # ── PLACEHOLDER: CNBC ─────────────────────────────────────────────────────
    # CNBC's technology page (https://www.cnbc.com/technology/) is a JavaScript-rendered
    # React app — article titles are NOT present in the raw HTML fetched by requests.
    # TO FIX: Re-upload generate_briefing.py to Claude and ask it to add Selenium or
    # Playwright support for CNBC. The target page is https://www.cnbc.com/technology/
    # and article links follow the pattern /YYYY/MM/DD/article-slug.html
    # ── PLACEHOLDER: WSJ ──────────────────────────────────────────────────────
    # WSJ (https://www.wsj.com/tech) is also JavaScript-rendered AND paywalled.
    # TO FIX: Re-upload generate_briefing.py to Claude and ask it to either:
    #   (a) add Selenium/Playwright support, or
    #   (b) find a working public WSJ RSS feed (try https://feeds.a.dj.com/rss/RSSWSJD.xml)
    # Articles on WSJ tech follow the pattern /articles/article-slug
}


# ── Scrapers ───────────────────────────────────────────────────────────────────

def parse_rss(url, limit=6, ai_filter=False):
    """
    Generic RSS parser. Returns list of {title, link, summary} dicts.
    If ai_filter=True, only includes items whose category contains AI-related terms.
    Skips items that look like ads/event promos (see is_advertisement).
    """
    stories = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        for item in soup.find_all("item"):
            title_tag = item.find("title")
            link_tag = item.find("link")
            desc_tag = item.find("description")

            if not title_tag or not link_tag:
                continue

            title = html.unescape(title_tag.get_text(strip=True))
            link = link_tag.get_text(strip=True)

            creator_tag = item.find("dc:creator")
            creator = creator_tag.get_text(strip=True) if creator_tag else ""
            if is_advertisement(title, creator):
                continue

            if ai_filter:
                cats = [c.get_text(strip=True).lower() for c in item.find_all("category")]
                if not any("ai" in c or "machine learning" in c or "artificial" in c for c in cats):
                    continue

            summary = ""
            if desc_tag:
                desc_soup = BeautifulSoup(desc_tag.get_text(), "html.parser")
                summary = html.unescape(desc_soup.get_text(strip=True))[:220]

            if len(title) > 5:
                stories.append({"title": title[:120], "link": link, "summary": summary})

            if len(stories) >= limit:
                break
    except Exception as e:
        raise e
    return stories


def parse_atom(url, limit=6, keyword_filter=None):
    """
    Generic Atom feed parser (feeds using <entry>/<link href=.../> rather than
    RSS's <item>/<link>text</link>). Returns list of {title, link, summary} dicts.
    If keyword_filter is set, only includes items whose title+summary match is_ai_relevant.
    Skips items that look like ads/event promos.
    """
    stories = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        for entry in soup.find_all("entry"):
            title_tag = entry.find("title")
            link_tag = entry.find("link")
            summary_tag = entry.find("summary") or entry.find("content")

            if not title_tag or not link_tag or not link_tag.get("href"):
                continue

            title = html.unescape(title_tag.get_text(strip=True))
            link = link_tag.get("href").strip()

            author_tag = entry.find("author")
            creator = ""
            if author_tag:
                name_tag = author_tag.find("name")
                creator = name_tag.get_text(strip=True) if name_tag else ""
            if is_advertisement(title, creator):
                continue

            summary = ""
            if summary_tag:
                summary_soup = BeautifulSoup(summary_tag.get_text(), "html.parser")
                summary = html.unescape(summary_soup.get_text(strip=True))[:220]

            if keyword_filter and not is_ai_relevant(title, summary):
                continue

            if len(title) > 5:
                stories.append({"title": title[:120], "link": link, "summary": summary})

            if len(stories) >= limit:
                break
    except Exception as e:
        raise e
    return stories


def scrape_techcrunch_ai():
    try:
        return parse_rss("https://techcrunch.com/category/artificial-intelligence/feed/")
    except Exception as e:
        print(f"  TechCrunch failed: {e}")
        return []


# def scrape_rundown_ai():
#     DISABLED: therundown.ai is JavaScript-rendered — requests only gets an empty shell.
#     TO FIX: Re-upload this file to Claude and ask it to add Selenium/Playwright support.
#     The articles are at https://www.therundown.ai/articles and links start with /articles/


def scrape_verge_ai():
    """The Verge's feeds moved from RSS to Atom format, which is why this
    previously returned nothing — parse_atom() understands <entry> tags."""
    try:
        return parse_atom("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml")
    except Exception as e:
        print(f"  Verge failed: {e}")
        return []


def scrape_venturebeat_ai():
    """VentureBeat's category/ai/feed endpoint stopped updating (it was stuck
    serving articles months old). Their main feed is fresh, so pull from there
    and filter down to AI-relevant stories instead."""
    try:
        stories = parse_rss("https://venturebeat.com/feed/", limit=20)
        return [s for s in stories if is_ai_relevant(s["title"], s["summary"])][:6]
    except Exception as e:
        print(f"  VentureBeat failed: {e}")
        return []

def scrape_zdnet_ai():
    """ZDNet's /topic/artificial-intelligence/rss.xml now just mirrors their
    general news feed instead of filtering to AI, so filter it ourselves."""
    try:
        stories = parse_rss("https://www.zdnet.com/topic/artificial-intelligence/rss.xml", limit=20)
        return [s for s in stories if is_ai_relevant(s["title"], s["summary"])][:6]
    except Exception as e:
        print(f"  ZDNet failed: {e}")
        return []

def scrape_nytimes_ai():
    try:
        return parse_rss(
            "https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/section/technology/rss.xml"
        )
    except Exception as e:
        print(f"  NYT failed: {e}")
        return []

def scrape_arstechnica_ai():
    try:
        return parse_rss("https://arstechnica.com/ai/feed/")
    except Exception as e:
        print(f"  Ars Technica failed: {e}")
        return []

def scrape_mit_ai():
    try:
        return parse_rss("https://www.technologyreview.com/feed/")
    except Exception as e:
        print(f"  MIT Tech Review failed: {e}")
        return []


def scrape_wired_ai():
    """Wired AI tag page — scrape HTML directly."""
    stories = []
    try:
        resp = requests.get(
            "https://www.wired.com/tag/artificial-intelligence/",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Wired article URLs look like /story/article-slug/
            if "/story/" not in href:
                continue
            # Normalise to absolute URL
            if href.startswith("/"):
                href = "https://www.wired.com" + href
            if href in seen:
                continue
            # Title is usually in an <h3> or <h2> inside the link, or the link text itself
            heading = a.find(["h2", "h3"])
            title = html.unescape(heading.get_text(strip=True) if heading else a.get_text(strip=True)[:120])
            if len(title) > 10 and not is_advertisement(title):
                seen.add(href)
                stories.append({"title": title[:120], "link": href, "summary": ""})
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"  Wired failed: {e}")
    return stories


def scrape_foxbusiness_ai():
    """Fox Business technology page — scrape HTML directly.
    Article links are <a href="/technology/article-slug"> with the title in aria-label.
    """
    stories = []
    try:
        resp = requests.get(
            "https://www.foxbusiness.com/technology",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Only article links under /technology/
            if not href.startswith("/technology/"):
                continue
            # aria-label carries the clean title on Fox Business
            title = html.unescape(a.get("aria-label", "").strip())
            if not title:
                # Fallback: look for an <h3> inside the link
                h = a.find("h3")
                title = html.unescape(h.get_text(strip=True)) if h else ""
            full_url = "https://www.foxbusiness.com" + href
            if full_url not in seen and len(title) > 10 and not is_advertisement(title):
                seen.add(full_url)
                stories.append({"title": title[:120], "link": full_url, "summary": ""})
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"  Fox Business failed: {e}")
    return stories


def scrape_hackernews():
    """Hacker News — RSS feed (robots.txt disallows but not technically blocked)."""
    try:
        return parse_rss("https://news.ycombinator.com/rss", limit=6)
    except Exception as e:
        print(f"  Hacker News failed: {e}")
        return []


def scrape_bloomberg_ai():
    """Bloomberg Technology — RSS feed with keyword AI filter."""
    stories = []
    try:
        resp = requests.get(
            "https://feeds.bloomberg.com/technology/news.rss",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "xml")
        for item in soup.find_all("item"):
            title_tag = item.find("title")
            link_tag = item.find("link")
            desc_tag = item.find("description")
            if not title_tag or not link_tag:
                continue
            title = html.unescape(title_tag.get_text(strip=True))
            link = link_tag.get_text(strip=True)
            if is_advertisement(title):
                continue
            summary = ""
            if desc_tag:
                summary = html.unescape(BeautifulSoup(desc_tag.get_text(), "html.parser").get_text(strip=True))[:220]
            # Only keep if title or summary mentions AI
            if not is_ai_relevant(title, summary):
                continue
            if len(title) > 5:
                stories.append({"title": title[:120], "link": link, "summary": summary})
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"  Bloomberg failed: {e}")
    return stories


def scrape_techradar_ai():
    """TechRadar — RSS feed with keyword AI filter."""
    stories = []
    try:
        resp = requests.get(
            "https://www.techradar.com/rss",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "xml")
        for item in soup.find_all("item"):
            title_tag = item.find("title")
            link_tag = item.find("link")
            desc_tag = item.find("description")
            if not title_tag or not link_tag:
                continue
            title = html.unescape(title_tag.get_text(strip=True))
            link = link_tag.get_text(strip=True)
            if is_advertisement(title):
                continue
            summary = ""
            if desc_tag:
                summary = html.unescape(BeautifulSoup(desc_tag.get_text(), "html.parser").get_text(strip=True))[:220]
            if not is_ai_relevant(title, summary):
                continue
            if len(title) > 5:
                stories.append({"title": title[:120], "link": link, "summary": summary})
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"  TechRadar failed: {e}")
    return stories


def scrape_siliconvalley_ai():
    """Silicon Valley News — scrape the technology page directly with AI keyword filter."""
    stories = []
    try:
        resp = requests.get(
            "https://www.siliconvalley.com/business/technology/",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("https://www.siliconvalley.com/2"):
                continue
            heading = a.find(["h2", "h3"])
            title = html.unescape(heading.get_text(strip=True) if heading else a.get_text(strip=True)[:120])
            if len(title) < 10 or href in seen:
                continue
            if not is_ai_relevant(title) or is_advertisement(title):
                continue
            seen.add(href)
            stories.append({"title": title[:120], "link": href, "summary": ""})
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"  Silicon Valley News failed: {e}")
    return stories


# Map slug -> scraper function
SCRAPERS = {
    "techcrunch":    scrape_techcrunch_ai,   # Best Source
    "techradar":     scrape_techradar_ai,    # Really Good Source
    "nyt":           scrape_nytimes_ai,      # Good Source
    "mit":           scrape_mit_ai,          # Great, in depth source. Paywalled though
    "wired":         scrape_wired_ai,        # Good Source
    "arstechnica":   scrape_arstechnica_ai,  # idk yet
    "zdnet":         scrape_zdnet_ai,        # idk yet
    "bloomberg":     scrape_bloomberg_ai,    # Good Source
    "foxbusiness":   scrape_foxbusiness_ai,  # Not great
    "verge":         scrape_verge_ai,        # idk yet
    "venturebeat":   scrape_venturebeat_ai,  # idk yet
    "siliconvalley": scrape_siliconvalley_ai,# Solid source
    "hackernews":    scrape_hackernews,      # N/A (not real news)
    # "cnbc":        scrape_cnbc_ai,   # TODO: needs Selenium — see placeholder in SOURCE_META
    # "wsj":         scrape_wsj_ai,    # TODO: needs Selenium — see placeholder in SOURCE_META
    # "rundown":     scrape_rundown_ai,# TODO: needs Selenium — JS-rendered
}


# ── Shared CSS ─────────────────────────────────────────────────────────────────

SHARED_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=IBM+Plex+Sans:wght@300;400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --ink:    #1a1410;
  --paper:  #f7f3ec;
  --cream:  #ede8df;
  --accent: #c0392b;
  --muted:  #7a6f65;
  --rule:   #c8bfb0;
}

body {
  background: var(--paper);
  color: var(--ink);
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 300;
  line-height: 1.6;
}

a { color: inherit; text-decoration: none; }
a:hover { text-decoration: underline; }

.page-wrap {
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 24px 80px;
}

.topnav {
  display: flex;
  gap: 24px;
  font-size: 12px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  border-bottom: 1px solid var(--rule);
  padding-bottom: 20px;
  margin-bottom: 40px;
}
.topnav a { color: var(--muted); }
.topnav a:hover { color: var(--accent); text-decoration: none; }
.topnav a.active { color: var(--ink); font-weight: 500; }

.masthead { margin-bottom: 48px; }
.masthead-label {
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 12px;
}
.masthead h1 {
  font-family: 'Playfair Display', serif;
  font-size: clamp(32px, 6vw, 52px);
  font-weight: 700;
  line-height: 1.1;
}
.masthead-rule {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 20px 0;
  color: var(--accent);
  font-size: 18px;
}
.masthead-rule::before,
.masthead-rule::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--rule);
}

.footer {
  text-align: center;
  padding-top: 40px;
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.05em;
  border-top: 1px solid var(--rule);
  margin-top: 60px;
}
"""


def topnav(depth=0, active=None):
    prefix = "../" * depth
    links = [
        f'<a href="{prefix}index.html" class="{"active" if active=="briefings" else ""}">All Briefings</a>',
        f'<a href="{prefix}sources.html" class="{"active" if active=="sources" else ""}">Sources</a>',
        f'<a href="{prefix}blog/index.html" class="{"active" if active=="blog" else ""}">Blog</a>',
        f'<a href="{prefix}search.html" class="{"active" if active=="search" else ""}">Search</a>',
    ]
    return f'<nav class="topnav">{"".join(links)}</nav>'


# ── Briefing Page ──────────────────────────────────────────────────────────────

def build_briefing_page(date_str, display_date, results):
    """results: list of (slug, stories) — only sources that returned stories."""
    toc_items = "".join(
        f'<li><a href="#{slug}">{SOURCE_META[slug]["name"]}</a></li>'
        for slug, stories in results if stories
    )

    sections_html = ""
    for slug, stories in results:
        if not stories:
            continue
        meta = SOURCE_META[slug]
        color = meta["color"]
        name = meta["name"]
        paywall_badge = (
            '<span class="paywall-badge">🔒 Subscription may be required</span>'
            if meta.get("paywalled") else ""
        )

        items_html = ""
        for s in stories:
            excerpt = f'<p class="excerpt">{s["summary"]}</p>' if s.get("summary") else ""
            items_html += f"""
            <article class="story">
              <a class="story-link" href="{s['link']}" target="_blank" rel="noopener">
                <h3 class="story-title">{s['title']}</h3>
              </a>
              {excerpt}
            </article>"""

        sections_html += f"""
        <section class="source" id="{slug}">
          <div class="source-header">
            <h2 class="source-name" style="color:{color}">{name}</h2>
            <a class="source-link" href="../sources/{slug}.html">View all →</a>
          </div>
          {paywall_badge}
          <div class="source-rule" style="background:{color}"></div>
          <div class="stories">{items_html}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Briefing — {display_date}</title>
  <meta name="description" content="Your daily AI news digest for {display_date}, featuring stories from {', '.join(SOURCE_META[slug]['name'] for slug, _ in results)}.">
  <style>
{SHARED_CSS}

.masthead {{ text-align: center; }}

.paywall-badge {{
  display: inline-block;
  font-size: 11px;
  color: var(--muted);
  margin-top: 4px;
  letter-spacing: 0.03em;
}}

.toc {{
  background: var(--cream);
  border: 1px solid var(--rule);
  border-radius: 4px;
  padding: 20px 24px;
  margin-bottom: 48px;
}}
.toc-title {{
  font-size: 11px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}}
.toc ul {{ list-style: none; display: flex; flex-wrap: wrap; gap: 8px 24px; }}
.toc a {{ font-size: 14px; border-bottom: 1px dotted var(--rule); }}
.toc a:hover {{ color: var(--accent); border-color: var(--accent); text-decoration: none; }}

.source {{ margin-bottom: 48px; padding-bottom: 48px; border-bottom: 1px solid var(--rule); }}
.source:last-of-type {{ border-bottom: none; }}

.source-header {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
}}
.source-name {{
  font-family: 'Playfair Display', serif;
  font-size: 22px;
  font-weight: 700;
}}
.source-rule {{ height: 2px; margin-bottom: 20px; }}
.source-link {{ font-size: 12px; color: var(--muted); }}
.source-link:hover {{ color: var(--accent); text-decoration: none; }}

.story {{ margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px dotted var(--rule); }}
.story:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
.story-title {{ font-size: 16px; font-weight: 500; line-height: 1.4; transition: color 0.15s; }}
.story-link:hover .story-title {{ color: var(--accent); }}
.excerpt {{ font-size: 14px; color: var(--muted); margin-top: 6px; line-height: 1.55; }}
  </style>
</head>
<body>
<div class="page-wrap">
  {topnav(depth=1, active="briefings")}

  <header class="masthead">
    <p class="masthead-label">Daily AI Briefing</p>
    <h1>{display_date}</h1>
    <div class="masthead-rule">✦</div>
  </header>

  <nav class="toc">
    <p class="toc-title">In this issue</p>
    <ul>{toc_items}</ul>
  </nav>

  {sections_html}

  <footer class="footer">
    Generated automatically on {display_date} · Your Daily AI Briefing
  </footer>
</div>
</body>
</html>"""


# ── Index Page ─────────────────────────────────────────────────────────────────

def build_index_page(entries):
    items = ""
    for i, e in enumerate(entries):
        badge = '<span class="badge">Latest</span>' if i == 0 else ""
        source_tags = ""
        if e.get("sources"):
            source_tags = " ".join(
                f'<span class="src-tag">{SOURCE_META[s]["name"]}</span>'
                for s in e["sources"] if s in SOURCE_META
            )
        items += f"""
        <a class="entry" href="briefings/{e['date_str']}.html">
          <div class="entry-main">
            <span class="entry-date">{e['display_date']}</span>
            {f'<div class="entry-sources">{source_tags}</div>' if source_tags else ""}
          </div>
          {badge}
          <span class="entry-arrow">→</span>
        </a>"""

    count = len(entries)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily AI Briefing</title>
  <meta name="description" content="A daily digest of the latest artificial intelligence news, automatically generated each morning from TechCrunch, NYT, MIT Technology Review, and more.">
  <style>
{SHARED_CSS}

.page-wrap {{ max-width: 680px; }}
.masthead {{ margin-bottom: 48px; }}
.masthead h1 {{ font-size: clamp(38px, 8vw, 64px); line-height: 1.05; }}
.masthead-sub {{ margin-top: 16px; font-size: 15px; color: var(--muted); max-width: 440px; }}

.section-label {{
  font-size: 11px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 16px;
}}

.entry-list {{ display: flex; flex-direction: column; gap: 2px; }}

.entry {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: var(--cream);
  border: 1px solid transparent;
  border-radius: 4px;
  transition: border-color 0.15s, background 0.15s;
}}
.entry:hover {{ border-color: var(--rule); background: #fff; text-decoration: none; }}

.entry-main {{ flex: 1; }}
.entry-date {{ font-size: 15px; font-weight: 400; display: block; }}
.entry-sources {{ margin-top: 5px; display: flex; flex-wrap: wrap; gap: 4px; }}
.src-tag {{
  font-size: 10px;
  letter-spacing: 0.04em;
  background: var(--rule);
  color: var(--muted);
  padding: 2px 6px;
  border-radius: 2px;
}}

.badge {{
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: var(--accent);
  color: white;
  padding: 3px 8px;
  border-radius: 2px;
  white-space: nowrap;
}}

.entry-arrow {{ color: var(--muted); font-size: 16px; transition: color 0.15s, transform 0.15s; }}
.entry:hover .entry-arrow {{ color: var(--accent); transform: translateX(4px); }}
  </style>
</head>
<body>
<div class="page-wrap">
  {topnav(depth=0, active="briefings")}

  <header class="masthead">
    <p class="masthead-label">Ben's Archive</p>
    <h1>Daily AI<br>Briefing</h1>
    <p class="masthead-sub">A daily digest of AI news, generated automatically each morning from across the web.</p>
  </header>

  <p class="section-label">{count} issue{'s' if count != 1 else ''}</p>
  <div class="entry-list">
    {items or '<p style="color:var(--muted);font-style:italic">No briefings yet.</p>'}
  </div>

  <footer class="footer">Updated daily · AI Briefing Blog</footer>
</div>
</body>
</html>"""


# ── Sources Index Page ─────────────────────────────────────────────────────────

def build_sources_page(used_sources):
    cards = ""
    for slug, meta in SOURCE_META.items():
        if slug not in used_sources:
            continue
        color = meta["color"]
        cards += f"""
        <a class="source-card" href="sources/{slug}.html">
          <div class="card-accent" style="background:{color}"></div>
          <div class="card-body">
            <h2 class="card-name">{meta['name']}</h2>
            <p class="card-desc">{meta['description']}</p>
            <span class="card-cta">View archive →</span>
          </div>
        </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sources — Daily AI Briefing</title>
  <meta name="description" content="Browse all the news sources behind the Daily AI Briefing, including TechCrunch AI, NYT Technology, MIT Technology Review, and more.">
  <style>
{SHARED_CSS}

.page-wrap {{ max-width: 760px; }}
.masthead h1 {{ font-size: clamp(30px, 5vw, 46px); }}
.masthead-sub {{ margin-top: 12px; font-size: 15px; color: var(--muted); }}

.source-grid {{ display: flex; flex-direction: column; gap: 12px; }}

.source-card {{
  display: flex;
  background: var(--cream);
  border: 1px solid var(--rule);
  border-radius: 6px;
  overflow: hidden;
  transition: border-color 0.15s, background 0.15s;
  color: var(--ink);
}}
.source-card:hover {{ border-color: #aaa; background: #fff; text-decoration: none; }}

.card-accent {{ width: 6px; flex-shrink: 0; }}
.card-body {{ padding: 20px 24px; flex: 1; }}
.card-name {{
  font-family: 'Playfair Display', serif;
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 8px;
}}
.card-desc {{ font-size: 14px; color: var(--muted); line-height: 1.6; margin-bottom: 12px; }}
.card-cta {{ font-size: 12px; letter-spacing: 0.06em; color: var(--accent); text-transform: uppercase; }}
  </style>
</head>
<body>
<div class="page-wrap">
  {topnav(depth=0, active="sources")}

  <header class="masthead">
    <p class="masthead-label">Sources</p>
    <h1>Where the news<br>comes from</h1>
    <p class="masthead-sub">Every source that has appeared in this briefing, with an archive of all articles pulled from each one.</p>
  </header>

  <div class="source-grid">
    {cards or '<p style="color:var(--muted);font-style:italic">No sources yet.</p>'}
  </div>

  <footer class="footer">Daily AI Briefing · Sources</footer>
</div>
</body>
</html>"""


# ── Per-Source Page ────────────────────────────────────────────────────────────

def build_source_page(slug, entries):
    meta = SOURCE_META[slug]
    color = meta["color"]
    name = meta["name"]

    total_articles = sum(len(e.get("articles", [])) for e in entries)
    total_days = len(entries)

    date_groups = ""
    for e in entries:
        articles = e.get("articles", [])
        article_html = ""
        for a in articles:
            excerpt = f'<p class="excerpt">{a["summary"]}</p>' if a.get("summary") else ""
            article_html += f"""
            <article class="story">
              <a class="story-link" href="{a['link']}" target="_blank" rel="noopener">
                <h3 class="story-title">{a['title']}</h3>
              </a>
              {excerpt}
            </article>"""

        date_groups += f"""
        <div class="date-group">
          <a class="date-label" href="../briefings/{e['date_str']}.html">{e['display_date']} →</a>
          <div class="stories">{article_html}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} — AI Briefing Archive</title>
  <meta name="description" content="Archive of AI news articles from {name}. {meta['description'][:120]}...">
  <style>
{SHARED_CSS}

.masthead h1 {{ color: {color}; }}
.paywall-badge {{
  display: inline-block;
  font-size: 11px;
  color: var(--muted);
  margin-top: 10px;
  letter-spacing: 0.03em;
}}
.source-desc {{
  font-size: 15px;
  color: var(--muted);
  line-height: 1.7;
  padding: 20px 24px;
  background: var(--cream);
  border-left: 4px solid {color};
  border-radius: 0 4px 4px 0;
  margin-bottom: 40px;
}}

.stats {{ display: flex; gap: 32px; margin-bottom: 40px; padding-bottom: 24px; border-bottom: 1px solid var(--rule); }}
.stat-value {{
  font-family: 'Playfair Display', serif;
  font-size: 32px;
  font-weight: 700;
  color: {color};
  line-height: 1;
}}
.stat-label {{ font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-top: 4px; }}

.date-group {{ margin-bottom: 40px; padding-bottom: 40px; border-bottom: 1px solid var(--rule); }}
.date-group:last-child {{ border-bottom: none; }}

.date-label {{
  display: inline-block;
  font-family: 'Playfair Display', serif;
  font-size: 18px;
  font-weight: 700;
  color: {color};
  margin-bottom: 16px;
  border-bottom: 2px solid {color};
  padding-bottom: 4px;
}}
.date-label:hover {{ opacity: 0.8; text-decoration: none; }}

.story {{ margin-bottom: 18px; padding-bottom: 18px; border-bottom: 1px dotted var(--rule); }}
.story:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
.story-title {{ font-size: 15px; font-weight: 500; line-height: 1.4; transition: color 0.15s; }}
.story-link:hover .story-title {{ color: var(--accent); }}
.excerpt {{ font-size: 13px; color: var(--muted); margin-top: 5px; line-height: 1.55; }}
  </style>
</head>
<body>
<div class="page-wrap">
  {topnav(depth=1, active="sources")}

  <header class="masthead">
    <p class="masthead-label">Source Archive</p>
    <h1>{name}</h1>
    {'<span class="paywall-badge">🔒 Subscription may be required</span>' if meta.get('paywalled') else ''}
  </header>

  <p class="source-desc">{meta['description']}</p>

  <div class="stats">
    <div>
      <div class="stat-value">{total_articles}</div>
      <div class="stat-label">Articles</div>
    </div>
    <div>
      <div class="stat-value">{total_days}</div>
      <div class="stat-label">Days covered</div>
    </div>
  </div>

  {date_groups or '<p style="color:var(--muted);font-style:italic">No articles yet.</p>'}

  <footer class="footer">{name} · Daily AI Briefing Archive</footer>
</div>
</body>
</html>"""


# ── Blog ───────────────────────────────────────────────────────────────────────
# Posts are plain markdown files in blog_posts/ — drop a new .md file in there
# (see blog_posts/about.md for the header format) and it gets picked up and
# published automatically next time this script runs.

BLOG_POSTS_DIR = "blog_posts"


def load_blog_posts(posts_dir=BLOG_POSTS_DIR):
    """Parse every blog_posts/*.md file (except about.md) into a post dict."""
    posts = []
    if not os.path.isdir(posts_dir):
        return posts
    for fname in sorted(os.listdir(posts_dir)):
        if not fname.endswith(".md") or fname.lower() in ("about.md", "readme.md"):
            continue
        with open(os.path.join(posts_dir, fname), encoding="utf-8") as f:
            text = f.read()

        header_text, sep, body = text.partition("\n---\n")
        if not sep:
            print(f"  Skipping {fname}: missing '---' header separator")
            continue

        meta = {}
        for line in header_text.strip().splitlines():
            key, colon, val = line.partition(":")
            if colon:
                meta[key.strip().lower()] = val.strip()

        date_str = meta.get("date", "")
        try:
            display_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            display_date = date_str

        posts.append({
            "slug": os.path.splitext(fname)[0],
            "title": meta.get("title", fname),
            "date_str": date_str,
            "display_date": display_date,
            "summary": meta.get("summary", ""),
            "content_html": md.markdown(body.strip(), extensions=["extra"]),
        })

    posts.sort(key=lambda p: p["date_str"], reverse=True)
    return posts


def load_about_html(posts_dir=BLOG_POSTS_DIR):
    path = os.path.join(posts_dir, "about.md")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return md.markdown(f.read().strip(), extensions=["extra"])


BLOG_POST_CSS = """
.post-content { font-size: 16px; line-height: 1.7; }
.post-content p { margin-bottom: 16px; }
.post-content h1, .post-content h2, .post-content h3 {
  font-family: 'Playfair Display', serif;
  margin: 28px 0 12px;
}
.post-content ul, .post-content ol { margin: 0 0 16px 24px; }
.post-content a { color: var(--accent); border-bottom: 1px dotted var(--accent); }
.post-content blockquote {
  border-left: 3px solid var(--rule);
  padding-left: 16px;
  color: var(--muted);
  margin: 16px 0;
}
.post-content code {
  background: var(--cream);
  padding: 2px 5px;
  border-radius: 3px;
  font-size: 0.9em;
}
.post-content pre {
  background: var(--cream);
  padding: 14px 16px;
  border-radius: 4px;
  overflow-x: auto;
  margin-bottom: 16px;
}
"""


def build_blog_index_page(posts, about_html):
    post_items = "".join(f"""
        <a class="entry" href="{p['slug']}.html">
          <div class="entry-main">
            <span class="entry-date">{p['title']}</span>
            <div class="entry-sources"><span class="src-tag">{p['display_date']}</span></div>
            {f'<p style="margin-top:8px;font-size:14px;color:var(--muted)">{p["summary"]}</p>' if p.get('summary') else ''}
          </div>
          <span class="entry-arrow">→</span>
        </a>""" for p in posts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Blog — Daily AI Briefing</title>
  <meta name="description" content="Ben's blog — commentary on AI news and things learned while using AI day to day.">
  <style>
{SHARED_CSS}
{BLOG_POST_CSS}

.page-wrap {{ max-width: 680px; }}
.about-box {{
  background: var(--cream);
  border: 1px solid var(--rule);
  border-radius: 6px;
  padding: 24px 28px;
  margin-bottom: 48px;
}}
.about-box .post-content {{ font-size: 15px; }}
.about-box .post-content p:last-child {{ margin-bottom: 0; }}
.section-label {{
  font-size: 11px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 16px;
}}
.entry-list {{ display: flex; flex-direction: column; gap: 2px; }}
.entry {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: var(--cream);
  border: 1px solid transparent;
  border-radius: 4px;
  transition: border-color 0.15s, background 0.15s;
}}
.entry:hover {{ border-color: var(--rule); background: #fff; text-decoration: none; }}
.entry-main {{ flex: 1; }}
.entry-date {{ font-size: 16px; font-weight: 500; display: block; font-family: 'Playfair Display', serif; }}
.entry-sources {{ margin-top: 5px; display: flex; flex-wrap: wrap; gap: 4px; }}
.src-tag {{
  font-size: 10px;
  letter-spacing: 0.04em;
  background: var(--rule);
  color: var(--muted);
  padding: 2px 6px;
  border-radius: 2px;
}}
.entry-arrow {{ color: var(--muted); font-size: 16px; transition: color 0.15s, transform 0.15s; }}
.entry:hover .entry-arrow {{ color: var(--accent); transform: translateX(4px); }}
  </style>
</head>
<body>
<div class="page-wrap">
  {topnav(depth=1, active="blog")}

  <header class="masthead">
    <p class="masthead-label">Ben's Blog</p>
    <h1>Notes &amp; Commentary</h1>
  </header>

  <div class="about-box">
    <p class="section-label">About Me</p>
    <div class="post-content">{about_html or '<p>Add blog_posts/about.md to introduce yourself here.</p>'}</div>
  </div>

  <p class="section-label">{len(posts)} post{'s' if len(posts) != 1 else ''}</p>
  <div class="entry-list">
    {post_items or '<p style="color:var(--muted);font-style:italic">No posts yet — add a markdown file to blog_posts/ to publish one.</p>'}
  </div>

  <footer class="footer">Ben's Blog · Daily AI Briefing</footer>
</div>
</body>
</html>"""


def build_blog_post_page(post):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{post['title']} — Ben's Blog</title>
  <meta name="description" content="{post.get('summary') or post['title']}">
  <style>
{SHARED_CSS}
{BLOG_POST_CSS}
  </style>
</head>
<body>
<div class="page-wrap">
  {topnav(depth=1, active="blog")}

  <header class="masthead">
    <p class="masthead-label">{post['display_date']}</p>
    <h1>{post['title']}</h1>
  </header>

  <div class="post-content">{post['content_html']}</div>

  <footer class="footer"><a href="index.html">← Back to Blog</a></footer>
</div>
</body>
</html>"""


# ── Data Management ────────────────────────────────────────────────────────────

ENTRIES_FILE = "entries.json"
SOURCE_DATA_FILE = "source_data.json"


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)



# ── Search ─────────────────────────────────────────────────────────────────────

def build_search_index(source_data):
    """Flatten source_data.json into a deduped list of articles for client-side search.
    The same story often gets re-pulled by a source across many days (that's kept in the
    daily briefings on purpose), but search should only surface the latest occurrence of
    each one — so dedupe by (source, title), keeping whichever has the newest date."""
    latest_by_key = {}
    for slug, day_entries in source_data.items():
        meta = SOURCE_META.get(slug)
        if not meta:
            continue
        for e in day_entries:
            for a in e.get("articles", []):
                item = {
                    "title": a["title"],
                    "link": a["link"],
                    "summary": a.get("summary", ""),
                    "source": slug,
                    "source_name": meta["name"],
                    "date": e["date_str"],
                    "display_date": e["display_date"],
                    "paywalled": bool(meta.get("paywalled")),
                }
                key = (slug, a["title"].strip().lower())
                existing = latest_by_key.get(key)
                if not existing or item["date"] > existing["date"]:
                    latest_by_key[key] = item

    index = list(latest_by_key.values())
    index.sort(key=lambda x: x["date"], reverse=True)
    return index


def build_search_page(used_sources):
    checkboxes = "".join(
        f'<label class="src-check"><input type="checkbox" value="{slug}"> {SOURCE_META[slug]["name"]}</label>'
        for slug in sorted(used_sources, key=lambda s: SOURCE_META[s]["name"])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Search — Daily AI Briefing</title>
  <meta name="description" content="Search every article ever featured in the Daily AI Briefing, by keyword, source, or date.">
  <style>
{SHARED_CSS}

.page-wrap {{ max-width: 760px; }}
.search-box {{ display: flex; gap: 8px; margin-bottom: 12px; }}
.search-box input[type="text"] {{
  flex: 1;
  font: inherit;
  font-size: 16px;
  padding: 12px 14px;
  border: 1px solid var(--rule);
  border-radius: 4px;
  background: #fff;
  color: var(--ink);
}}
.search-box button {{
  font: inherit;
  font-size: 14px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 0 20px;
  border: none;
  border-radius: 4px;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
}}
.search-box button:hover {{ opacity: 0.9; }}

.advanced-toggle {{
  background: none;
  border: none;
  font: inherit;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
  padding: 0;
  margin-bottom: 20px;
  text-decoration: underline dotted;
}}
.advanced-toggle:hover {{ color: var(--accent); }}

.advanced-panel {{
  display: none;
  background: var(--cream);
  border: 1px solid var(--rule);
  border-radius: 4px;
  padding: 20px 24px;
  margin-bottom: 32px;
  gap: 20px;
}}
.advanced-panel.open {{ display: flex; flex-wrap: wrap; }}
.advanced-field {{ display: flex; flex-direction: column; gap: 6px; min-width: 160px; }}
.advanced-field.sources-field {{ flex: 1 1 100%; }}
.advanced-field label.field-label {{
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}}
.advanced-field input[type="date"] {{
  font: inherit;
  padding: 8px 10px;
  border: 1px solid var(--rule);
  border-radius: 4px;
}}
.source-checks {{ display: flex; flex-wrap: wrap; gap: 6px 16px; }}
.src-check {{ font-size: 13px; display: flex; align-items: center; gap: 6px; cursor: pointer; }}

.results-meta {{ font-size: 13px; color: var(--muted); margin-bottom: 16px; }}
.result {{ margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px dotted var(--rule); }}
.result:last-child {{ border-bottom: none; }}
.result-title {{ font-size: 16px; font-weight: 500; line-height: 1.4; }}
.result-title:hover {{ color: var(--accent); }}
.result-meta {{ font-size: 12px; color: var(--muted); margin-top: 4px; letter-spacing: 0.02em; }}
.result-excerpt {{ font-size: 14px; color: var(--muted); margin-top: 6px; line-height: 1.55; }}
  </style>
</head>
<body>
<div class="page-wrap">
  {topnav(depth=0, active="search")}

  <header class="masthead">
    <p class="masthead-label">Search</p>
    <h1>Find an article</h1>
    <p class="masthead-sub" style="margin-top:12px;font-size:15px;color:var(--muted)">Search across every briefing ever published, by keyword, source, or date.</p>
  </header>

  <form id="search-form">
    <div class="search-box">
      <input type="text" id="q" placeholder="Search titles, summaries, or source names…" autocomplete="off">
      <button type="submit">Search</button>
    </div>
    <button type="button" class="advanced-toggle" id="advanced-toggle">Advanced options ▾</button>
    <div class="advanced-panel" id="advanced-panel">
      <div class="advanced-field">
        <label class="field-label" for="date-from">From date</label>
        <input type="date" id="date-from">
      </div>
      <div class="advanced-field">
        <label class="field-label" for="date-to">To date (or same as From for a single day)</label>
        <input type="date" id="date-to">
      </div>
      <div class="advanced-field sources-field">
        <label class="field-label">News sites (none checked = all)</label>
        <div class="source-checks">{checkboxes}</div>
      </div>
    </div>
  </form>

  <p class="results-meta" id="results-meta">Loading article index…</p>
  <div id="results"></div>

  <footer class="footer">Daily AI Briefing · Search</footer>
</div>
<script src="search.js" defer></script>
</body>
</html>"""


# ── Sitemap ────────────────────────────────────────────────────────────────────

def build_sitemap(entries, blog_posts, base_url="https://bboyett.github.io/ai-briefing"):
    today = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")

    def url_block(loc, priority):
        return f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>{priority}</priority>\n  </url>"

    blocks = []
    # Homepage
    blocks.append(url_block(f"{base_url}/", "1.00"))
    blocks.append(url_block(f"{base_url}/index.html", "0.80"))
    # Sources index
    blocks.append(url_block(f"{base_url}/sources.html", "0.80"))
    # Blog + Search
    blocks.append(url_block(f"{base_url}/blog/index.html", "0.70"))
    blocks.append(url_block(f"{base_url}/search.html", "0.60"))
    # Each daily briefing
    for e in entries:
        blocks.append(url_block(f"{base_url}/briefings/{e['date_str']}.html", "0.80"))
    # Each per-source page
    for slug in SOURCE_META:
        blocks.append(url_block(f"{base_url}/sources/{slug}.html", "0.64"))
    # Each blog post
    for p in blog_posts:
        blocks.append(url_block(f"{base_url}/blog/{p['slug']}.html", "0.60"))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9
              http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">
{chr(10).join(blocks)}
</urlset>"""

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    now = datetime.utcnow()
    date_str = now.strftime("%Y-%m-%d")
    display_date = now.strftime("%B %d, %Y")

    print(f"Generating briefing for {display_date}...")

    # 1. Scrape all sources
    raw_results = {}
    for slug, scraper in SCRAPERS.items():
        print(f"  Scraping {SOURCE_META[slug]['name']}...")
        stories = scraper()
        raw_results[slug] = stories
        print(f"    -> {len(stories)} stories")

    # 2. Filter to sources that returned something
    results = [(slug, stories) for slug, stories in raw_results.items() if stories]
    successful_slugs = [slug for slug, _ in results]
    print(f"\n  Active sources today: {', '.join(successful_slugs) or 'none'}")

    # 3. Write daily briefing page
    os.makedirs("briefings", exist_ok=True)
    briefing_html = build_briefing_page(date_str, display_date, results)
    with open(f"briefings/{date_str}.html", "w", encoding="utf-8") as f:
        f.write(briefing_html)
    print(f"  Written: briefings/{date_str}.html")

    # 4. Update entries.json
    entries = load_json(ENTRIES_FILE, [])
    existing = next((e for e in entries if e["date_str"] == date_str), None)
    if existing:
        existing["sources"] = successful_slugs
    else:
        entries.insert(0, {
            "date_str": date_str,
            "display_date": display_date,
            "sources": successful_slugs,
        })
    save_json(ENTRIES_FILE, entries)

    # 5. Update source_data.json
    source_data = load_json(SOURCE_DATA_FILE, {})
    for slug, stories in results:
        if slug not in source_data:
            source_data[slug] = []
        existing_entry = next((e for e in source_data[slug] if e["date_str"] == date_str), None)
        if existing_entry:
            existing_entry["articles"] = stories
        else:
            source_data[slug].insert(0, {
                "date_str": date_str,
                "display_date": display_date,
                "articles": stories,
            })
    save_json(SOURCE_DATA_FILE, source_data)

    # 6. Rebuild index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(build_index_page(entries))
    print("  Written: index.html")

    # 7. Rebuild sources.html and per-source pages
    all_used_sources = set()
    for e in entries:
        all_used_sources.update(e.get("sources", []))

    with open("sources.html", "w", encoding="utf-8") as f:
        f.write(build_sources_page(all_used_sources))
    print("  Written: sources.html")

    os.makedirs("sources", exist_ok=True)
    for slug in all_used_sources:
        if slug not in source_data:
            continue
        with open(f"sources/{slug}.html", "w", encoding="utf-8") as f:
            f.write(build_source_page(slug, source_data[slug]))
        print(f"  Written: sources/{slug}.html")

    # 8. Rebuild blog (index + individual posts)
    os.makedirs("blog", exist_ok=True)
    blog_posts = load_blog_posts()
    about_html = load_about_html()
    with open("blog/index.html", "w", encoding="utf-8") as f:
        f.write(build_blog_index_page(blog_posts, about_html))
    print("  Written: blog/index.html")
    for post in blog_posts:
        with open(f"blog/{post['slug']}.html", "w", encoding="utf-8") as f:
            f.write(build_blog_post_page(post))
        print(f"  Written: blog/{post['slug']}.html")

    # 9. Rebuild search index + search page
    search_index = build_search_index(source_data)
    save_json("search_index.json", search_index)
    print(f"  Written: search_index.json ({len(search_index)} articles)")
    with open("search.html", "w", encoding="utf-8") as f:
        f.write(build_search_page(all_used_sources))
    print("  Written: search.html")

    # 10. Rebuild sitemap.xml
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(build_sitemap(entries, blog_posts))
    print("  Written: sitemap.xml")

    print("\nDone!")
